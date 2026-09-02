# 3.4 — mprotect(), mlock() & madvise()

Once memory is mapped (`mmap()`, Part 3.3) or faulted in from the heap (Part 3.2),
three syscalls let you **change permissions**, **pin pages in RAM**, and **hint
access patterns** to the kernel. They operate on **page-granular** regions and are
the building blocks for guard pages, JIT sandboxes, real-time latency control, and
performance tuning.

---

## 3.4.1 mprotect() — changing page permissions

> **The call ▸**
> ```c
> #include <sys/mman.h>
>
> int mprotect(void *addr, size_t len, int prot);
> ```
> **`addr`** — page-aligned start (kernel rounds down). **`len`** — rounded up to
> page boundary. **`prot`** — `PROT_READ | PROT_WRITE | PROT_EXEC | PROT_NONE`
> (combinations must be valid for the mapping).
> **Returns:** 0 on success, **-1** on error.

```
   before mprotect(page, PROT_NONE)
   ┌────────────────┐
   │ read/write OK  │
   └────────────────┘

   after
   ┌────────────────┐
   │ any access     │ ──▶ SIGSEGV (Part 3.1)
   └────────────────┘
```

> **Under the hood ▸** `mprotect()` updates PTE permissions in the page tables for
> the affected VMA range. Existing TLB entries are flushed on return to user space.
> It does not allocate or free physical pages — only access rights change.

**Errors ▸**

| `errno` | When |
|---------|------|
| `EINVAL` | Invalid prot; addr not page-aligned in strict cases; unmapped range |
| `ENOMEM` | Kernel internal tables cannot track change |
| `EACCES` | Address outside your mappings |

---

## 3.4.2 Guard pages and W^X

**Guard pages** — a `PROT_NONE` region adjacent to stacks or heap overflow traps:

```
   stack grows ▼
   ┌──────────────┐
   │ stack frames │
   ├──────────────┤  ◀── mprotect guard (PROT_NONE)
   │  unmapped    │      overflow → immediate SIGSEGV
   └──────────────┘
```

Thread stacks created by pthreads include guard pages by default.

**W^X (Write XOR Execute)** — modern kernels and security policies discourage
simultaneous write+execute on the same page:

```
   JIT pattern:
   1. mmap(RW)           write bytecode
   2. mprotect(RX)       flip to executable
   3. call generated code
```

**Pitfall ▸** `mprotect(addr, len, PROT_READ | PROT_WRITE | PROT_EXEC)` may fail
with `EACCES` when **PaX**, **SELinux**, or **seccomp** (Part 8.6) enforce no
RWX pages. Design JITs for RW → RX transitions.

**Trade-offs ▸** Guard pages cost one page per stack/thread but turn silent
corruption into immediate faults — cheap insurance in native code.

---

## 3.4.3 mlock(), munlock(), mlockall()

> **The call ▸**
> ```c
> #include <sys/mman.h>
>
> int mlock(const void *addr, size_t len);
> int munlock(const void *addr, size_t len);
> int mlockall(int flags);
> int munlockall(void);
> ```
> **`mlock`** — pin pages in RAM; prevent swap-out. **`mlockall`** — current and/or
> future mappings: `MCL_CURRENT`, `MCL_FUTURE`, `MCL_ONFAULT` (Linux 4.4+).

```
   normal page  ──▶ may swap to disk under memory pressure
   mlock'd page ──▶ stays in physical RAM until munlock or process exit
```

**Why pin memory?**

- **Real-time / low-latency** — avoid multi-millisecond major faults from swap
  (Part 3.1).
- **Cryptographic secrets** — reduce exposure of key material in swap files (still
  not a complete defence — use `madvise(MADV_DONTNEED)` on free, `mlock` limits).
- **Benchmarking** — stable timing without cold fault noise.

**Errors ▸**

| `errno` | When |
|---------|------|
| `ENOMEM` | Would exceed **RLIMIT_MEMLOCK** (see below) |
| `EPERM` | Insufficient privilege for requested amount |
| `EINVAL` | Bad flags to `mlockall` |
| `EAGAIN` | Some pages could not be locked |

---

## 3.4.4 RLIMIT_MEMLOCK

```bash
ulimit -l              # kilobytes on many systems; unlimited often shown as unlimited
cat /proc/self/limits  # RLIMIT_MEMLOCK line
```

Non-root processes default to a **small** memlock cap (historically 64 KiB; varies).
Root or `CAP_IPC_LOCK` can lock more. Exceeding the limit → `mlock()` fails with
`ENOMEM`.

```c
#include <sys/resource.h>

struct rlimit rl;
if (getrlimit(RLIMIT_MEMLOCK, &rl) == -1) {
    perror("getrlimit");
} else {
    printf("memlock soft=%llu hard=%llu bytes\n",
           (unsigned long long)rl.rlim_cur,
           (unsigned long long)rl.rlim_max);
}
```

**Systems ▸** Database engines and audio/DSP daemons often raise `RLIMIT_MEMLOCK` in
unit files (`LimitMEMLOCK=infinity` in systemd) — but pinning everything is dangerous
on memory-constrained hosts.

---

## 3.4.5 madvise() — hints, not guarantees

> **The call ▸**
> ```c
> #include <sys/mman.h>
>
> int madvise(void *addr, size_t length, int advice);
> ```
> Kernel **may** ignore advice. Returns 0 or -1 with `errno`.

| Advice | Intent |
|--------|--------|
| `MADV_NORMAL` | Default behaviour |
| `MADV_RANDOM` | Random access — reduce readahead |
| `MADV_SEQUENTIAL` | Sequential scan — aggressive readahead |
| `MADV_WILLNEED` | Prefault soon — warm cache |
| `MADV_DONTNEED` | Drop clean page-cache-backed pages; free anonymous |
| `MADV_FREE` (Linux) | Lazy free — contents undefined until touched |
| `MADV_HUGEPAGE` | Prefer transparent huge pages for range |
| `MADV_NOHUGEPAGE` | Disable THP for range |

```
   MADV_SEQUENTIAL scan of 1 GiB file mapping
        │
        └─ kernel readahead pulls next pages → fewer major faults
```

> **Under the hood ▸** `madvise()` updates VMA flags and page cache policies.  
> `MADV_DONTNEED` on **file-backed** shared mappings drops clean cache pages — next
> access refaults from disk. On **anonymous** memory, pages may be zeroed on remap.

**Pitfall ▸** `MADV_DONTNEED` on data you still need causes **silent refault cost**
or, for anonymous mappings, **zero-filled replacement** — not "keep my bytes."

---

## 3.4.6 Combined example: guard + lock + sequential hint

```c
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

#define PAGE_SIZE 4096
#define DATA_PAGES 4

int main(void) {
    size_t total = PAGE_SIZE * (DATA_PAGES + 1); /* +1 guard page */
    char *base = mmap(NULL, total, PROT_READ | PROT_WRITE,
                      MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (base == MAP_FAILED) {
        perror("mmap");
        return 1;
    }

    char *data = base;
    char *guard = base + PAGE_SIZE * DATA_PAGES;

    if (mprotect(guard, PAGE_SIZE, PROT_NONE) == -1) {
        perror("mprotect guard");
        munmap(base, total);
        return 1;
    }

    size_t data_len = PAGE_SIZE * DATA_PAGES;
    if (madvise(data, data_len, MADV_SEQUENTIAL) == -1) {
        perror("madvise");
        munmap(base, total);
        return 1;
    }

    memset(data, 0xAB, data_len);

    if (mlock(data, data_len) == -1) {
        perror("mlock");  /* may fail under default RLIMIT_MEMLOCK — not fatal demo */
    }

    printf("locked %zu bytes at %p, guard at %p (PROT_NONE)\n",
           data_len, (void *)data, (void *)guard);

    if (munlock(data, data_len) == -1)
        perror("munlock");

    if (munmap(base, total) == -1) {
        perror("munmap");
        return 1;
    }
    return 0;
}
```

---

## Summary

- **`mprotect()`** changes read/write/execute permissions on page-aligned ranges —
  used for guard pages, JIT W^X transitions, and hardening.
- **`mlock()`/`mlockall()`** pin pages in RAM, bounded by **`RLIMIT_MEMLOCK`**;
  essential for latency-sensitive and anti-swap secret handling.
- **`madvise()`** provides non-binding access hints (`SEQUENTIAL`, `WILLNEED`,
  `DONTNEED`, `HUGEPAGE`) to tune fault and readahead behaviour.
- All three operate at **page granularity** on existing mappings from `mmap()` or
  the heap — they do not create new virtual areas.

Next: [3.5 — Shared memory](05-shared-memory.md)
