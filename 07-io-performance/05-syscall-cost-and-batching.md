# 7.5 — The Cost of a Syscall & Batching

Part 0.1 quoted ~100–300 ns per syscall on modern x86-64. That number is the
**floor** — the mode switch, register save, validation, and return path — before
the kernel does real work. In hot loops, syscalls also evict caches, miss TLB
entries, and (on mitigated kernels) pay **KPTI** costs for Meltdown-class bugs.
This chapter makes the cost measurable, then shows how buffering, vector I/O,
message batching, io_uring, and vDSO reduce boundary crossings.

---

## 7.5.1 What you pay per crossing

```
   user                          kernel
   ────                          ──────
   setup rax/rdi/rsi/rdx/...     entry_SYSCALL_64
   SYSCALL instruction    ──▶   save pt_regs, stack switch
                                 syscall table dispatch
                                 validate pointers (copy_from_user)
                                 do work
                                 copy_to_user if needed
   SYSRET                 ◀──   restore, return
   libc: -1 → errno
```

Components of cost:

| component | typical impact |
|-----------|----------------|
| instruction + pipeline flush | tens of ns |
| kernel entry/exit stub | ~100–300 ns baseline |
| argument validation | varies (pointer checks, fd lookup) |
| actual work | unbounded (disk, network) |
| cache/TLB pollution | hard to isolate; shows up in follow-on user code |
| KPTI (user→kernel page table switch) | +30–50% boundary cost on affected CPUs |

**Systems ▸** Meltdown mitigation (**Kernel Page Table Isolation**) keeps separate
page tables for user and kernel. Every syscall switches CR3 — extra TLB flushes.
Cloud providers felt this in 2018; still relevant when micro-benchmarking syscalls
on laptop vs bare metal vs VM.

---

## 7.5.2 Measuring syscall overhead

**Micro-benchmark** (isolate empty syscall):

```c
#define _GNU_SOURCE
#include <stdio.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

static inline long sys_getpid_raw(void) {
    long ret;
    __asm__ volatile ("syscall"
        : "=a"(ret)
        : "a"(SYS_getpid)
        : "rcx", "r11", "memory");
    return ret;
}

int main(void) {
    struct timespec ts;
    const int N = 1000000;
    long sum = 0;

    for (int i = 0; i < N; i++)
        sum += sys_getpid_raw();   /* warm */
    (void)sum;

    clock_gettime(CLOCK_MONOTONIC, &ts);
    long long t0 = ts.tv_sec * 1000000000LL + ts.tv_nsec;

    sum = 0;
    for (int i = 0; i < N; i++)
        sum += sys_getpid_raw();

    clock_gettime(CLOCK_MONOTONIC, &ts);
    long long t1 = ts.tv_sec * 1000000000LL + ts.tv_nsec;

    double ns = (double)(t1 - t0) / N;
    printf("getpid syscall: %.1f ns/call (sum=%ld)\n", ns, sum);
    return 0;
}
```

Expect ~150–350 ns depending on CPU, kernel, mitigations. `getpid()` via libc
may hit **vDSO** instead (see §7.5.6) — this raw loop measures true syscall cost.

**Application-level profiling:**

```bash
strace -c ./myserver          # syscall counts + cumulative time
perf stat -e syscalls:sys_enter_* ./myserver
perf record -g ./myserver && perf report
```

Part 8.4 expands tracing tools.

---

## 7.5.3 Amortization: buffering

The oldest strategy — fewer, larger transfers:

```
   per-character write():  1 byte × 1 syscall × 300 ns  = disaster
   stdio 4 KB buffer:      4096 bytes per write()       = 300 ns / 4096 B
```

Part 0.1: `printf` buffers for a reason. Read side: accumulate into a ring buffer,
process in user space, refill with one `read()`.

**Trade-offs ▸** Buffering adds latency (Nagle-like trade-off) and memory. Flush
policy matters for interactive UIs vs batch ETL.

---

## 7.5.4 Vector I/O: readv / writev

> **The call ▸**
> ```c
> #include <sys/uio.h>
>
> ssize_t readv(int fd, const struct iovec *iov, int iovcnt);
> ssize_t writev(int fd, const struct iovec *iov, int iovcnt);
> ```

One syscall scatters/gathers across multiple buffers — useful for protocol headers
+ payload without `memcpy` concat:

```c
struct iovec iov[2] = {
    { .iov_base = header, .iov_len = header_len },
    { .iov_base = body,   .iov_len = body_len   },
};
ssize_t n = writev(fd, iov, 2);
if (n == -1) { perror("writev"); return -1; }
```

Same boundary crossing as one `write()`, two logical regions.

---

## 7.5.5 Socket batching: sendmmsg / recvmmsg

> **The call ▸**
> ```c
> #include <sys/socket.h>
>
> int sendmmsg(int sockfd, struct mmsghdr *msgvec,
>              unsigned int vlen, unsigned int flags);
> int recvmmsg(int sockfd, struct mmsghdr *msgvec,
>              unsigned int vlen, unsigned int flags,
>              struct timespec *timeout);
> ```

Send or receive **up to vlen** datagrams in one syscall — critical for DNS,
gaming, telemetry at high PPS:

```
   1000 UDP packets
   ────────────────
   recvfrom × 1000  →  1000 boundary crossings
   recvmmsg × 10    →  10 crossings (100 msgs each)
```

Part 6.3 (UDP) benefits directly.

---

## 7.5.6 vDSO: syscalls without crossing

Some "syscalls" never trap — the kernel maps a **vDSO** (virtual dynamic shared
object) page into every process:

```
   clock_gettime(CLOCK_MONOTONIC)  ──▶  vDSO stub in user space  (no SYSCALL)
   gettimeofday()                  ──▶  often vDSO
   getpid()                        ──▶  may be cached in libc after first call
   time()                          ──▶  vDSO on modern glibc
```

Check: `ldd /bin/date` or `man 7 vdso`. **Under the hood ▸** The kernel publishes
read-only data (timestamps) and code stubs updated by timer interrupts — user reads
coherent time without ring transition.

**Pitfall ▸** Benchmarking "syscall cost" with `clock_gettime` measures vDSO, not
trap cost. Use a real trap (`getpid` raw, `read` on `/dev/zero`, etc.).

---

## 7.5.7 io_uring batching

Part 7.3: fill many SQEs, one `io_uring_submit()`:

```
   64 reads queued in SQ ring ──▶ one io_uring_enter ──▶ 64 CQEs
```

SQPOLL mode can eliminate even the enter call when the kernel thread keeps up.
This is the modern answer when epoll + non-blocking still spends too much time in
`read`/`write` traps.

---

## 7.5.8 Avoiding syscalls in hot loops

```
   ✓  batch work (mmsg, writev, io_uring)
   ✓  cache fd lookups — don't open/close per request
   ✓  use vDSO time sources (CLOCK_MONOTONIC via clock_gettime)
   ✓  memory-map config read once (Part 3.3) vs stat/open each tick
   ✓  event-driven I/O (Part 7.2) vs poll-by-sleep loop
   ✗  don't "optimize" away necessary security checks or error handling
```

Anti-pattern:

```c
while (running) {
    usleep(1000);              /* nanosleep syscall */
    if (poll(state)) handle(); /* another syscall */
}
```

Better: block in one waiter (`epoll_wait`) with timeout, or io_uring timeout op.

---

## 7.5.9 Profiling workflow

```
   1. strace -c ./app     → which syscalls dominate count/time?
   2. perf record -g      → user stacks leading to those syscalls
   3. fix highest ROI     → batch, buffer, zero-copy (Part 7.4), io_uring
   4. re-measure          → strace -c + workload benchmark
```

Example `strace -c` reading:

```
   % time    syscall        calls
   45.00    read            500000    ← investigate buffer size
   30.00    write           500000
   15.00    futex           12000     ← lock contention, not syscall batching
    5.00    epoll_wait       8000     ← expected for event loop
```

**Errors ▸** Profiling itself adds overhead — `strace` slows programs 10–100×. Use
`-c` summary for counts; `perf` for production-like load.

---

## Summary

- Syscall baseline ~100–300 ns plus cache/TLB effects; KPTI adds measurable cost
  on mitigated kernels.
- Measure with raw micro-benchmarks, `strace -c`, and `perf` — not assumptions.
- Amortize via buffering, `readv`/`writev`, `sendmmsg`/`recvmmsg`, and io_uring
  SQ batching.
- vDSO provides user-space fast paths for time — not a general escape hatch.
- Profile first, batch the syscalls that dominate count or wall time.

Next: [8.1 — The /proc Filesystem](../08-kernel-interfaces/01-proc-filesystem.md)
