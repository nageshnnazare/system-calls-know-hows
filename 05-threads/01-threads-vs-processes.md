# 5.1 — Threads vs Processes

A **process** is an isolated execution context with its own virtual address space, file
descriptor table, and PID. A **thread** is a lighter-weight execution context *inside*
that address space — same heap, same open files, but its own stack, register set, and
**thread ID (TID)**. Part 1.2 introduced `fork()` and `clone()` for processes; this
chapter explains why Linux threads are really `clone()` with sharing flags, and when
to pick threads over separate processes.

---

## 5.1.1 Two tasks, one address space

![Threads share an address space; processes do not](figures/thread-vs-process.svg)

```
   PROCESS A                          PROCESS B
   ┌─────────────────────────┐        ┌─────────────────────────┐
   │  heap, globals, code    │        │  heap, globals, code    │
   │  (private VMA)          │        │  (private VMA)          │
   │  ┌──────┐  ┌──────┐       │        │  ┌──────┐               │
   │  │stack │  │stack │       │        │  │stack │               │
   │  │ T1   │  │ T2   │       │        │  │ T1   │               │
   │  └──────┘  └──────┘       │        │  └──────┘               │
   │  fd table: 0,1,2,3,...    │        │  fd table: 0,1,2,...    │
   └─────────────────────────┘        └─────────────────────────┘
        PID 1000, TIDs 1000,1001            PID 1001, TID 1001
```

| Resource | Threads (same process) | Processes (after fork) |
|----------|------------------------|------------------------|
| Virtual address space | **Shared** (heap, globals, `.bss`) | **Separate** (COW at fork) |
| Stack | **Per thread** | **Per process** |
| Registers / PC | **Per thread** | **Per process** |
| File descriptors | **Shared table** (same fd → same open file desc) | **Copied table** (independent offsets per process — Part 0.5) |
| PID | Same | Different |
| TID (`gettid()`) | Unique per thread | Equals PID for single-threaded process |
| Signal disposition | Process-wide (with thread-targeting rules — Part 5.6) | Independent |

**Systems ▸** From the kernel's scheduler perspective, a thread is just a **task**
(`task_struct`). Threads in one process share `mm_struct` (memory), `files_struct`
(fds), and signal handlers. Processes do not.

---

## 5.1.2 clone() is the primitive

> **The call ▸**
> ```c
> #define _GNU_SOURCE
> #include <sched.h>
> #include <unistd.h>
> #include <sys/syscall.h>
>
> pid_t clone(int (*fn)(void *), void *stack, int flags, void *arg, ...);
> /* glibc wrapper; pthread_create uses clone() internally */
> ```
> **Returns:** child TID in parent; **0 in child** (like fork); **-1** on error (`errno` set).

`fork()` is `clone()` **without** sharing flags — child gets a new address space (COW).
`pthread_create()` is `clone()` **with** sharing:

```
   fork()                    pthread_create()
     │                            │
     ▼                            ▼
   clone(0)                  clone(CLONE_VM      ← share address space
                                  | CLONE_FILES   ← share fd table
                                  | CLONE_SIGHAND ← share signal handlers
                                  | CLONE_THREAD  ← same thread group
                                  | CLONE_SYSVSEM ← share SysV sem adjust
                                  | ...)
```

> **Under the hood ▸** `CLONE_VM` makes parent and child point at the same
> `mm_struct`. A write to a global in one thread is immediately visible to all
> others — no IPC, no serialization, no copy. That is the speed win and the
> correctness hazard.

Common `clone()` flags (see `man clone`):

| Flag | Effect |
|------|--------|
| `CLONE_VM` | Share virtual memory |
| `CLONE_FILES` | Share fd table |
| `CLONE_FS` | Share cwd / umask |
| `CLONE_SIGHAND` | Share signal handlers |
| `CLONE_THREAD` | Put in same thread group (same PID namespace view) |
| `CLONE_SETTLS` | Set thread-local storage pointer |
| `CLONE_CHILD_CLEARTID` | Address for futex wake on thread exit (Part 5.5) |

**Pitfall ▸** Calling `fork()` in a multi-threaded program is dangerous: only the
calling thread survives in the child; other threads' locks may be held forever.
Use `pthread_atfork()` handlers or avoid `fork()` after threads exist (prefer
`posix_spawn()` — Part 1.3).

---

## 5.1.3 What threads share — and what breaks

```
   thread A                    thread B
      │                           │
      │  writes *global = 42      │  reads global → 42  ✓ (no IPC)
      │                           │
      │  malloc() → heap ptr      │  free(same ptr)     ✗ (unless coordinated)
      │                           │
      │  write(fd 3, ...)         │  read(fd 3, ...)    ✓ (shared offset!)
      │                           │
      │  stack local int x        │  cannot see x       ✓ (private stacks)
```

Shared mutable state without synchronization is a **data race** — undefined behavior
in C/C++ (Part 5.6). Shared fds mean two threads advancing the same file offset
without coordination corrupt reads (Part 2.2).

---

## 5.1.4 When to use threads vs processes

**Trade-offs ▸**

| Choose **threads** when… | Choose **processes** when… |
|--------------------------|------------------------------|
| Tight data sharing (in-memory cache, game state) | Strong **isolation** required (crash containment, security) |
| Low creation cost for many workers | Need separate address spaces (different `mmap` layouts) |
| Latency-sensitive handoff of small structures | CPU-bound parallelism + **GIL-like** constraints don't apply |
| One failure should not kill the whole service | Want OS-level resource limits per worker (`setrlimit`, cgroups) |

```
   threads                         processes
   ───────                         ─────────
   fast create (~µs)               slower create (fork COW metadata)
   shared memory (free)            IPC required (pipes, shm — Part 4)
   one bug → whole process dies    one worker crash → others survive
   harder to debug races           easier to reason about ownership
```

**Systems ▸** Production servers often hybridize: **one process per CPU core**
(or container) with a **thread pool** inside for connection handling — nginx worker
processes + threads, or event loops with thread pools for CPU work (Part 7).

---

## 5.1.5 Observing threads in the kernel

Each thread has a TID visible in `/proc`:

```bash
# main thread and worker TIDs for PID 1234
ls /proc/1234/task/
# 1234  1235  1236

cat /proc/1234/task/1235/status | grep -E '^(Name|Tgid|Pid|Threads)'
# Tgid: 1234    ← thread group ID (= process PID)
# Pid:  1235    ← this thread's TID
```

`strace -f` follows all threads; without `-f` you only see the main thread's syscalls.

---

## 5.1.6 Minimal comparison: fork vs pthread

```c
#define _GNU_SOURCE
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/wait.h>

static int shared_counter = 0;   /* visible to all threads; NOT to forked child
                                    until exec unless in shared memory */

static void *thread_fn(void *arg) {
    (void)arg;
    shared_counter++;
    return NULL;
}

int main(void) {
    pid_t pid = fork();
    if (pid == -1) {
        perror("fork");
        exit(1);
    }
    if (pid == 0) {
        /* child: shared_counter is COW copy — increment doesn't affect parent */
        shared_counter = 99;
        _exit(0);
    }
    if (waitpid(pid, NULL, 0) == -1) {
        perror("waitpid");
        exit(1);
    }
    printf("after fork child: shared_counter = %d (still 0)\n", shared_counter);

    pthread_t t;
    int err = pthread_create(&t, NULL, thread_fn, NULL);
    if (err != 0) {
        fprintf(stderr, "pthread_create: %s\n", strerror(err));
        exit(1);
    }
    if (pthread_join(t, NULL) != 0) {
        fprintf(stderr, "pthread_join failed\n");
        exit(1);
    }
    printf("after thread:     shared_counter = %d (now 1)\n", shared_counter);
    return 0;
}
```

Compile threads with `-pthread`. The fork child sees a **copy** of `shared_counter`;
the pthread sees the **same** memory.

---

## Summary

- Threads share address space, fd table, and signal handlers; each thread has its own
  stack, registers, and TID.
- Linux implements threads via `clone()` with `CLONE_VM | CLONE_FILES | …`; `fork()`
  is `clone()` without sharing.
- Threads win on sharing speed and creation cost; processes win on isolation and
  failure containment.
- Shared fds and heap require explicit synchronization (Parts 5.3–5.5); `fork()` in
  a threaded program needs special care.

Next: [5.2 — The pthread lifecycle](02-pthreads-lifecycle.md)
