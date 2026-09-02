# 5.6 — Concurrency Pitfalls

Threads make programs fast and shared-memory simple — until they make bugs **non-deterministic**.
This chapter catalogs the failure modes that survive code review: data races, deadlock,
ABA, false sharing, thread-unsafe libc, signals crossing threads, and what ThreadSanitizer
(TSan) catches. Parts 5.1–5.5 gave you the tools; here is where they go wrong in production.

---

## 5.6.1 Data races and undefined behavior

A **data race** occurs when two threads access the same memory location, at least one
is a write, and neither uses synchronization. In C/C++, that is **undefined behavior** —
not "maybe wrong," but license for the compiler and CPU to do anything.

```
   thread A              shared int x              thread B
      │                      0                         │
      │── x++ (read 0) ────────────────────────────────│── x++ (read 0)
      │── write 1 ─────────────────────────────────────│── write 1
      │                      1  (expected 2) ✗
```

**Fixes:** mutex (Part 5.3), atomics with correct ordering (Part 5.5), or confine
mutation to one thread and pass messages (queues — Part 5.4).

**Pitfall ▸** "It works on my machine" — races are timing-dependent. A billion correct
runs prove nothing.

**Systems ▸** Compile with `-fsanitize=thread` (TSan) to catch races at runtime:

```bash
gcc -fsanitize=thread -g -pthread -o prog prog.c
./prog
# WARNING: ThreadSanitizer: data race (pid=...)
```

TSan instruments every load/store; expect ~5–15× slowdown — dev/CI only.

---

## 5.6.2 Deadlock and livelock

**Deadlock** — threads cycle waiting for locks (Part 5.3 lock ordering).

```
   T1: lock(A) ──wait(B)     T2: lock(B) ──wait(A)
              └──── cycle ────┘
```

**Livelock** — threads aren't blocked but make no progress (e.g. both trylock, fail,
yield, retry forever). Looks alive in `top`, accomplishes nothing.

| Symptom | Mechanism |
|---------|-----------|
| Frozen app, low CPU | Classic deadlock |
| High CPU, no work done | Spinning / livelock |
| One thread stuck | Self-deadlock on non-recursive mutex |

Mitigations: global lock order, lock timeouts (`trylock` + backoff), lock hierarchy
with `std::lock`-style all-or-nothing acquisition in C++.

---

## 5.6.3 The ABA problem

Lock-free algorithms using CAS can fail when a location **changes A → B → A** between
your load and CAS — the CAS succeeds even though the structure changed underneath.

```
   stack top = A
   thread 1: read A, prepare pop
   thread 2: pop A, pop B, push A   (top is A again)
   thread 1: CAS(top, A, next) ✓   /* but 'next' may be stale → corruption */
```

Fixes: tagged pointers (version counter in unused high bits), hazard pointers, epoch
reclamation (used in kernel RCU). **Trade-offs ▸** Lock-free structures are hard to
get right — prefer mutexes unless profiling demands otherwise.

---

## 5.6.4 False sharing

Two threads modify **different variables** that live on the **same cache line** (typically
64 bytes). CPUs cache at line granularity — each write invalidates the other's core,
destroying scalability.

```
   cache line [ counter_a | counter_b | padding... ]
                  ↑                ↑
               thread 1         thread 2
               writes a         writes b
               ── both cores fight over one line ──
```

**Fix:** pad structures so hot per-thread counters occupy separate cache lines:

```c
#include <stdatomic.h>

#define CACHE_LINE 64

typedef struct {
    atomic_long count;
    char pad[CACHE_LINE - sizeof(atomic_long)];
} padded_counter_t;
```

**Systems ▸** `perf c2c` (Linux) detects false sharing on supported hardware.

---

## 5.6.5 Thread-safety of libc

Not all libc functions are thread-safe. Categories:

| Safe | Unsafe / caveats |
|------|------------------|
| `read`, `write`, `open`, `close` on **different fds** | Same fd without sync (Part 5.1) |
| `malloc` / `free` (glibc: per-arena locking) | `strtok` — static internal state |
| `strerror_r` (preferred) | `strerror` — may use static buffer |
| `snprintf`, `memcpy` | `localtime`, `gethostbyname` (use `getaddrinfo`) |

**errno is thread-local (TLS).** Each thread has its own `errno` (Part 0.4). A syscall
failure in thread A does not clobber thread B's `errno`. **Pthread functions still do
not set `errno`** — they return the error code (Part 5.2).

```c
/* ✓ per-thread reentrant */
char buf[128];
strtok_r(line, " ", &saveptr);

/* ✗ shared static cursor */
strtok(line, " ");
```

**Pitfall ▸** `printf`/`fprintf` lock a stdio mutex internally — safe but serializes
output and is slow on hot paths. Use per-thread buffers or `write()` to fds (Part 2.2).

---

## 5.6.6 Signals and threads

Signals are process-oriented but **delivered to one thread** (Part 4.2). Which thread
is ambiguous unless you control it.

> **The call ▸**
> ```c
> int pthread_sigmask(int how, const sigset_t *restrict set,
>                     sigset_t *restrict oldset);
> int sigaction(int signum, const struct sigaction *act,
>               struct sigaction *oldact);
> ```
> Block signals in worker threads with `pthread_sigmask`; dedicate one thread to
> `sigwait()` / `signalfd` for async-safe handling.

```
   recommended pattern:
   ───────────────────
   worker threads:  pthread_sigmask(SIG_BLOCK, all_signals)
   main / sig thread: sigwait() → handle with async-signal-safe ops only
```

**Pitfall ▸** Calling non-async-signal-safe functions (`malloc`, `printf`, most
pthread APIs) from a signal handler that interrupted another thread → deadlock if
the handler runs while the interrupted thread held a libc lock.

**Pitfall ▸** `EINTR`: blocking syscalls (`read`, `accept`, `poll`) may return `-1`
with `errno == EINTR` when a signal arrives. Restart or handle explicitly (Part 4.2).

---

## 5.6.7 ThreadSanitizer checklist

TSan reports:

- Data races on plain memory
- Lock order inversions (potential deadlock)
- Mutex misuse (unlock by wrong thread)

It does **not** catch:

- Logical races (correct atomics, wrong algorithm)
- ABA without special annotations
- Deadlock that never happens in the test run

Run TSan on integration tests with realistic concurrency; combine with stress tests
and `helgrind` (Valgrind) as a secondary tool where TSan isn't available.

---

## 5.6.8 Pitfall summary diagram

```
   concurrency bug taxonomy
   ┌─────────────────────────────────────────────────────────┐
   │  data race ──▶ UB, TSan, -fsanitize=thread              │
   │  deadlock  ──▶ lock order, trylock, graph analysis      │
   │  livelock  ──▶ backoff, don't busy-wait forever         │
   │  ABA       ──▶ version tags, hazard pointers            │
   │  false sharing ──▶ cache-line padding, perf c2c         │
   │  libc      ──▶ strtok_r, strerror_r, avoid handler UB   │
   │  signals   ──▶ pthread_sigmask, sigwait, EINTR          │
   └─────────────────────────────────────────────────────────┘
```

---

## Summary

- Unsynchronized concurrent access to non-atomic memory is UB; use mutexes, atomics,
  or single-owner design.
- Deadlock needs lock cycles; livelock wastes CPU without progress; ABA breaks naive CAS.
- Pad per-thread hot fields to avoid false sharing on cache lines.
- `errno` is per-thread; pthread returns error codes directly; many libc APIs need
  `_r` reentrant variants.
- Block signals in workers; handle async events on a dedicated thread; expect `EINTR`.
- TSan is the first-line detector for races and lock misuse in development builds.

Next: [6.1 — The socket model](../06-sockets/01-socket-model.md)
