# The Linux System Calls Mastery Guide

> A single, deep, diagram-driven reference for how a C program actually talks to
> the Linux kernel: from the `SYSCALL` instruction and the user/kernel boundary,
> through processes, files, memory, IPC, threads and sockets, to the
> high-performance I/O engines (`epoll`, `io_uring`, zero-copy) and the kernel
> interfaces (`/proc`, namespaces, `seccomp`) that power modern containers.
>
> Written for **systems engineers — especially C and C++ engineers — who want
> expert-level mechanical detail**, not a list of function prototypes. Every
> system call is grounded in what the kernel does on the other side of the trap,
> with diagrams, exact error semantics, working C, and the engineering
> trade-offs that matter in production.

---

## Who this is for

You can already write C. You may have called `open()` and `read()`, forked a
process, or opened a socket. But you want to *truly* understand:

- What actually happens between your `write(fd, buf, n)` and the bytes hitting
  the disk — register by register, copy by copy.
- Why `fork()` is cheap even for a 10 GB process (copy-on-write), and why the
  child returns `0`.
- What a file descriptor *is* — the three kernel tables behind the integer.
- Why `read()` can return fewer bytes than you asked for, and why ignoring that
  is a classic bug.
- How `mmap()` lets you treat a file as memory, and when that beats `read()`.
- What a signal handler may and may not do, and why `printf()` inside one is a
  time bomb.
- Why `select()` is O(n) but `epoll` is O(1), and when `io_uring` beats both.
- How `sendfile()`/`splice()` move a file to a socket with zero user-space
  copies.
- How namespaces + cgroups + seccomp turn a plain process into a container.

If you finish this guide, you will be able to read `strace` output, a man page,
and kernel-adjacent source (musl, glibc, liburing, nginx) fluently, and reason
about every syscall on your program's hot path.

---

## The 30,000-foot map

```
   your C program (user space, ring 3, unprivileged)
        │
        │  libc wrapper sets up registers (rax = syscall no., rdi/rsi/rdx = args)
        ▼
   ┌────────────────────────────────────────────────────────────┐
   │   SYSCALL instruction  →  mode switch  →  ring 0 (kernel)    │  ← the trap
   └────────────────────────────────────────────────────────────┘
        │
        │  entry_SYSCALL_64 → sys_call_table[rax] → sys_read / sys_mmap / ...
        ▼
   ┌─────────────┬─────────────┬─────────────┬─────────────┬──────────────┐
   │ Process mgmt│  File / VFS │   Memory    │     IPC     │   Net stack  │
   │ fork exec   │ open read   │ brk mmap    │ pipe signal │ socket bind  │
   │ wait clone  │ write stat  │ mprotect    │ shm msgq    │ epoll ...    │
   └─────────────┴─────────────┴─────────────┴─────────────┴──────────────┘
        │
        │  result placed in rax  (>= 0 on success, or -errno)
        ▼
   libc: if rax ∈ [-4095,-1] → set errno = -rax, return -1 ; else return rax
```

Each box is a chapter this guide dissects. Each arrow is a mechanism with a
cost, a failure mode, and a trade-off.

---

## How to read this guide

The parts are ordered as a **learning path** from the boundary mechanism itself
up to production I/O engines. If you already know the fundamentals, jump to
Part 4 (IPC), Part 6 (sockets), or Part 7 (I/O & performance) — the
engineering-heavy heart of the guide.

Every chapter has:

- **Concept** sections with hand-drawn diagrams.
- **The call ▸** call-outs: exact signature, headers, arguments, return value.
- **Under the hood ▸** boxes: what the kernel does on the other side of the trap.
- **Errors ▸** tables: the `errno` values you must actually handle.
- **Example ▸** blocks: compilable, correct C — including the error checking.
- **Trade-offs ▸** and **Pitfall ▸**: real failure modes explained by the
  mechanics.

---

## Table of contents

### Part 0 — Foundations (`00-foundations/`)
1. [What is a system call?](00-foundations/01-what-is-a-syscall.md)
2. [The user/kernel boundary](00-foundations/02-user-kernel-boundary.md)
3. [The syscall mechanism & ABI](00-foundations/03-syscall-mechanism.md)
4. [errno & error handling](00-foundations/04-errno-and-error-handling.md)
5. [File descriptors: the core abstraction](00-foundations/05-file-descriptors.md)

### Part 1 — Process management (`01-processes/`)
1. [The process model](01-processes/01-process-model.md)
2. [Creating processes: fork & clone](01-processes/02-fork-and-clone.md)
3. [Running programs: the exec family](01-processes/03-exec-family.md)
4. [wait(), zombies & orphans](01-processes/04-wait-zombies-orphans.md)
5. [PIDs, process groups & sessions](01-processes/05-pids-groups-sessions.md)
6. [Scheduling & priority](01-processes/06-scheduling-and-priority.md)

### Part 2 — File I/O & the VFS (`02-file-io/`)
1. [open() & close()](02-file-io/01-open-close.md)
2. [read() & write()](02-file-io/02-read-write.md)
3. [Seeking & file offsets](02-file-io/03-seek-and-offsets.md)
4. [dup() & I/O redirection](02-file-io/04-dup-and-redirection.md)
5. [fcntl(), flags & metadata](02-file-io/05-fcntl-and-metadata.md)
6. [Links & directories](02-file-io/06-links-and-directories.md)
7. [The VFS, inodes & "everything is a file"](02-file-io/07-vfs-and-inodes.md)

### Part 3 — Memory management (`03-memory/`)
1. [The virtual address space](03-memory/01-virtual-address-space.md)
2. [brk() & the heap](03-memory/02-brk-and-heap.md)
3. [mmap(): mapping files & anonymous memory](03-memory/03-mmap.md)
4. [mprotect(), mlock() & madvise()](03-memory/04-mprotect-and-locking.md)
5. [Shared memory](03-memory/05-shared-memory.md)

### Part 4 — Inter-process communication (`04-ipc/`)
1. [Pipes & FIFOs](04-ipc/01-pipes-and-fifos.md)
2. [Signals](04-ipc/02-signals.md)
3. [System V IPC: message queues & semaphores](04-ipc/03-sysv-ipc.md)
4. [POSIX IPC](04-ipc/04-posix-ipc.md)
5. [Choosing an IPC mechanism](04-ipc/05-choosing-ipc.md)

### Part 5 — Threads & concurrency (`05-threads/`)
1. [Threads vs processes](05-threads/01-threads-vs-processes.md)
2. [The pthread lifecycle](05-threads/02-pthreads-lifecycle.md)
3. [Mutexes & read-write locks](05-threads/03-mutexes-and-rwlocks.md)
4. [Condition variables](05-threads/04-condition-variables.md)
5. [Atomics & the futex](05-threads/05-atomics-and-futex.md)
6. [Concurrency pitfalls](05-threads/06-concurrency-pitfalls.md)

### Part 6 — Sockets & networking (`06-sockets/`)
1. [The socket model](06-sockets/01-socket-model.md)
2. [TCP sockets](06-sockets/02-tcp-sockets.md)
3. [UDP sockets](06-sockets/03-udp-sockets.md)
4. [Unix domain sockets](06-sockets/04-unix-domain-sockets.md)
5. [Socket options](06-sockets/05-socket-options.md)
6. [I/O multiplexing: select, poll & epoll](06-sockets/06-io-multiplexing.md)

### Part 7 — I/O models & performance (`07-io-performance/`)
1. [Blocking vs non-blocking I/O](07-io-performance/01-blocking-nonblocking.md)
2. [epoll in depth](07-io-performance/02-epoll-deep-dive.md)
3. [Asynchronous I/O & io_uring](07-io-performance/03-async-io-and-io-uring.md)
4. [Zero-copy: sendfile, splice & friends](07-io-performance/04-zero-copy.md)
5. [The cost of a syscall & batching](07-io-performance/05-syscall-cost-and-batching.md)

### Part 8 — Kernel interfaces (`08-kernel-interfaces/`)
1. [The /proc filesystem](08-kernel-interfaces/01-proc-filesystem.md)
2. [/sys & sysctl](08-kernel-interfaces/02-sys-and-sysctl.md)
3. [ioctl()](08-kernel-interfaces/03-ioctl.md)
4. [Tracing: strace, ftrace, perf & eBPF](08-kernel-interfaces/04-tracing-and-perf.md)
5. [Namespaces & cgroups: how containers work](08-kernel-interfaces/05-namespaces-and-cgroups.md)
6. [seccomp & syscall security](08-kernel-interfaces/06-seccomp-and-security.md)

### Reference (`99-reference/`)
- [System-call cheat sheet](99-reference/syscall-cheatsheet.md)
- [errno reference](99-reference/errno-reference.md)
- [Glossary](99-reference/glossary.md)

### Runnable examples (`examples/`)
Compilable C programs for the major topics. Build them all with:

```bash
cd examples && make
```

---

## Conventions used in this guide

| Notation / call-out | Meaning                                                     |
|---------------------|-------------------------------------------------------------|
| **The call ▸**      | Exact prototype, required headers, and semantics            |
| **Under the hood ▸**| What the kernel does after the trap                         |
| **Errors ▸**        | The `errno` values you actually have to handle              |
| **Example ▸**       | Compilable, correct C (with error checking)                 |
| **Trade-offs ▸**    | Advantages vs disadvantages of a mechanism                  |
| **Pitfall ▸**       | A common mistake explained mechanically                     |
| `fd`                | A file descriptor (a small non-negative integer)            |
| `-1 / errno`        | The classic Unix failure convention (see Part 0.4)          |
| ring 3 / ring 0     | Unprivileged user mode / privileged kernel mode             |

---

## The one rule that never changes (read this first)

Almost every system call in this guide follows the **same failure contract**:

```c
ssize_t n = write(fd, buf, count);
if (n == -1) {
    // the call failed; errno says why
    perror("write");          // or: fprintf(stderr, "%s\n", strerror(errno));
    // handle or propagate
}
```

- On **success**, a syscall returns `0`, a count, or a new descriptor.
- On **failure**, it returns `-1` and sets the thread-local `errno`.
- A few calls (`getpriority`, `mmap`) use different sentinels — noted where they
  appear.

If you internalize "**check the return value, then read `errno`**," you have
already avoided the majority of real-world syscall bugs. We belabor error
handling on purpose.

Let's begin. → [Part 0.1: What is a system call?](00-foundations/01-what-is-a-syscall.md)
