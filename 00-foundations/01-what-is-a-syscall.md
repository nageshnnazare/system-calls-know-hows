# 0.1 — What Is a System Call?

A system call is, mechanically, **the only legitimate way for your program to
ask the kernel to do something it is not allowed to do itself**:

```
   your code (ring 3)  ──[controlled trap]──▶  kernel (ring 0)  ──▶  hardware
```

Reading a file, sending a network packet, creating a process, allocating a page
of memory — none of these can be done with ordinary CPU instructions from user
space. The CPU physically forbids it. A system call is the guarded doorway
through that wall.

---

## 0.1.1 Why the wall exists

Modern CPUs run code at (at least) two **privilege levels**, called *rings* on
x86:

```
   ring 3  — user mode      your program, shells, browsers, databases
   ring 0  — kernel mode    the Linux kernel: drivers, schedulers, filesystems
```

In ring 3 the CPU **refuses** to execute privileged instructions: you cannot
touch physical memory directly, program a disk controller, or reprogram the
MMU. If you try, the CPU faults. This is deliberate — it is what stops a buggy
or malicious program from crashing the machine or reading another process's
memory.

But your program legitimately needs those capabilities (to read a file, the
kernel must talk to the disk). So the kernel exposes a **fixed, numbered menu**
of operations it will perform on your behalf, each validated before it runs.
That menu is the system-call interface.

> **The core idea ▸** A syscall is a *protected procedure call into more
> privileged code*. You don't jump to a kernel address (you can't — it's not
> mapped for execution by you). Instead you execute a special instruction that
> **transitions** the CPU to ring 0 at a single, kernel-chosen entry point. The
> kernel decides what happens next. You never get to run arbitrary code as root.

---

## 0.1.2 System call vs library call

This distinction trips up almost everyone at first:

```
   ┌────────────────────────────────────────────────────────────┐
   │  LIBRARY CALL   e.g. printf(), fopen(), malloc(), strlen()  │
   │  • ordinary function in libc, runs entirely in user space   │
   │  • portable, may buffer, may call zero or many syscalls     │
   └───────────────────────────┬────────────────────────────────┘
                               │  (sometimes)
                               ▼
   ┌────────────────────────────────────────────────────────────┐
   │  SYSTEM CALL    e.g. write(), open(), mmap(), fork()        │
   │  • request to the kernel; crosses the ring 3 → ring 0 wall  │
   │  • the real work; every I/O byte and page ultimately here   │
   └────────────────────────────────────────────────────────────┘
```

- `strlen()` is **pure user space** — it never calls the kernel.
- `printf("hi\n")` is a library call that *buffers* your text and eventually
  issues **one** `write()` syscall (often only when the buffer fills or the
  program exits).
- `write(1, "hi\n", 3)` **is** the syscall — it crosses the wall immediately.

Even `write()` as you call it in C is technically a *thin libc wrapper* around
the raw syscall, but it maps 1:1 to it. When this guide says "the `write`
syscall," it means the kernel operation the wrapper triggers.

**Pitfall ▸** Mixing buffered (`fwrite`, `printf`) and raw (`write`) output on
the same descriptor produces interleaved, out-of-order text, because the libc
buffer is flushed at a different time than your direct `write()`. Pick one layer
per descriptor.

---

## 0.1.3 What a syscall costs

Crossing the wall is not free. A syscall involves, at minimum:

```
   1. set up registers with the call number + arguments
   2. execute SYSCALL  → CPU switches to ring 0, swaps to the kernel stack
   3. kernel saves your registers, validates arguments, does the work
   4. kernel puts the result in a register, executes SYSRET
   5. CPU switches back to ring 3; libc translates the result
```

On modern x86-64 this is on the order of **100–300 nanoseconds** of pure
overhead — before the actual work — and it pollutes CPU caches and branch
predictors. That sounds tiny, but it is the reason:

- `printf` buffers instead of calling `write` per character.
- High-performance servers use `epoll` and `io_uring` to handle thousands of
  connections with *few* syscalls (Part 7).
- Mitigations for CPU bugs (Meltdown/Spectre) that made the boundary crossing
  more expensive were a measurable performance event across the industry.

**Systems ▸** You can *see* every syscall a program makes with `strace`:

```bash
strace -c ./myprogram        # summary: counts + time per syscall
strace ./myprogram           # full trace, one line per syscall
```

Reading `strace` output is one of the most useful debugging skills this guide
builds toward.

---

## 0.1.4 The categories of system calls

There are a few hundred Linux syscalls (≈ 350+ on x86-64), but they cluster into
a handful of families — which are exactly the parts of this guide:

```
   ┌──────────────────┬───────────────────────────────────────────────┐
   │ Process control  │ fork, clone, execve, exit, wait4, kill         │
   │ File I/O         │ open, close, read, write, lseek, stat, dup     │
   │ Memory           │ brk, mmap, munmap, mprotect, madvise           │
   │ IPC              │ pipe, signalfd, shmget, msgsnd, semop          │
   │ Networking       │ socket, bind, listen, accept, connect, sendto  │
   │ Time & signals   │ nanosleep, clock_gettime, sigaction, timerfd   │
   │ System / kernel  │ ioctl, prctl, sysinfo, perf_event_open, bpf    │
   └──────────────────┴───────────────────────────────────────────────┘
```

Learn the *shape* of each family and you can predict how an unfamiliar syscall
in it behaves.

---

## 0.1.5 A first, complete example

The smallest honest program that does I/O purely through syscalls — no `stdio`,
no buffering:

```c
#include <unistd.h>     // read, write, close
#include <fcntl.h>      // open
#include <stdio.h>      // perror
#include <stdlib.h>     // exit

int main(void) {
    // open() is a syscall: ask the kernel for a descriptor to the file.
    int fd = open("/etc/hostname", O_RDONLY);
    if (fd == -1) {                 // the universal failure check
        perror("open");
        exit(1);
    }

    char buf[256];
    ssize_t n;
    // read() is a syscall; it may return fewer bytes than the buffer size.
    while ((n = read(fd, buf, sizeof buf)) > 0) {
        // write() is a syscall; write exactly the n bytes we just read.
        if (write(STDOUT_FILENO, buf, (size_t)n) != n) {
            perror("write");
            exit(1);
        }
    }
    if (n == -1) {                  // read() itself failed
        perror("read");
        exit(1);
    }

    close(fd);                      // release the descriptor
    return 0;
}
```

Compile and trace it:

```bash
gcc -Wall -Wextra -o cat_hostname cat_hostname.c
strace ./cat_hostname
# ... openat("/etc/hostname", O_RDONLY) = 3
# ... read(3, "myhost\n", 256)          = 7
# ... write(1, "myhost\n", 7)           = 7
# ... read(3, "", 256)                  = 0     ← EOF
# ... close(3)                          = 0
```

Every line of that trace is a wall-crossing. This tiny loop already shows three
things the rest of the guide expands on: **descriptors** (the `3`), **short
reads** (Part 2.2), and the **`-1`/`errno`** contract (Part 0.4).

---

## Summary

- A system call is the CPU-enforced, kernel-controlled doorway from unprivileged
  user mode (ring 3) into the privileged kernel (ring 0).
- The privilege wall exists to protect the machine and isolate processes; a
  syscall is a *protected procedure call* to a fixed, numbered menu of kernel
  operations.
- Library calls run in user space and may issue zero, one, or many syscalls;
  `printf` buffers, `write` is the raw syscall.
- Crossing the boundary costs ~100–300 ns plus cache effects — the reason for
  buffering, `epoll`, and `io_uring`.
- Syscalls cluster into families (process, file, memory, IPC, network, system)
  that map onto the parts of this guide.

Next: [0.2 — The user/kernel boundary](02-user-kernel-boundary.md)
