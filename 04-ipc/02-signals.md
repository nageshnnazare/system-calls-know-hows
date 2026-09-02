# 4.2 — Signals

A **signal** is a software interrupt: the kernel notifies a process that an event
occurred (terminal key, timer, child exit, segmentation fault, explicit `kill()`).
Delivery is **asynchronous** — your thread may be interrupted between any two
instructions. That power makes signals essential for shells, daemons, and debuggers,
and dangerous when handlers violate the async-signal-safe rules.

---

## 4.2.1 Signal numbers and default actions

Each signal has a number (`SIGINT` = 2, `SIGTERM` = 15, `SIGSEGV` = 11, …) and a
**default disposition**: terminate, ignore, stop, or continue.

```
   common signals
   ┌──────────┬────────────────────────────────────────────┐
   │ SIGINT   │ Ctrl+C → terminate (catchable)             │
   │ SIGTERM  │ polite shutdown request                    │
   │ SIGKILL  │ uncatchable forced kill                    │
   │ SIGSTOP  │ uncatchable stop (job control)             │
   │ SIGCHLD  │ child state changed (Part 1.4)             │
   │ SIGSEGV  │ invalid memory access (Part 3.1)           │
   │ SIGPIPE  │ write to closed pipe (Part 4.1)            │
   │ SIGUSR1/2│ user-defined                               │
   └──────────┴────────────────────────────────────────────┘
```

> **Under the hood ▸** Pending signals live in per-thread `task_struct` bitmasks.
> Delivery happens on return from a syscall or interrupt to user mode — not mid-
> instruction unless hardware exception (SIGSEGV, SIGFPE).

**SIGKILL** and **SIGSTOP** cannot be caught, blocked, or ignored — the kernel uses
them to guarantee termination/control.

---

## 4.2.2 sigaction() — prefer over signal()

> **The call ▸**
> ```c
> #include <signal.h>
>
> int sigaction(int signum, const struct sigaction *act,
>               struct sigaction *oldact);
>
> struct sigaction {
>     void     (*sa_handler)(int);           /* or sa_sigaction with SA_SIGINFO */
>     void     (*sa_sigaction)(int, siginfo_t *, void *);
>     sigset_t sa_mask;
>     int      sa_flags;
> };
> ```
> **`sa_flags`:** `SA_RESTART` (restart interrupted syscalls), `SA_SIGINFO`
> (three-arg handler), `SA_RESETHAND` (one-shot), `SA_NODEFER` (don't auto-block).

![Signal delivery from kernel to handler](figures/signal-delivery.svg)

```
   signal arrives
        │
        ├─ blocked?  → set pending bit, deliver later
        │
        └─ not blocked → save context, run handler, restore (or terminate)
```

**Pitfall ▸** Legacy `signal(2)` behaviour varies across Unix; **`sigaction()`** is
portable and explicit. Never use `signal()` in new code.

**Errors ▸**

| `errno` | When |
|---------|------|
| `EINVAL` | Invalid signal number or flags |
| `EFAULT` | Bad pointer |

---

## 4.2.3 Pending and blocked masks

Each thread has:

```
   pending mask   — signals arrived but not yet delivered
   blocked mask   — signals temporarily held (sigprocmask)
```

> **The call ▸**
> ```c
> int sigprocmask(int how, const sigset_t *set, sigset_t *oldset);
> int sigpending(sigset_t *set);
> int sigemptyset(sigset_t *set);
> int sigfillset(sigset_t *set);
> int sigaddset(sigset_t *set, int signum);
> int sigismember(const sigset_t *set, int signum);
> ```
> **`how`:** `SIG_BLOCK`, `SIG_UNBLOCK`, `SIG_SETMASK`.

While handling signal **S**, **S** is automatically blocked unless `SA_NODEFER`.
Add other signals to `sa_mask` to block them during the handler.

---

## 4.2.4 Async-signal-safety

Inside a signal handler you may call only **async-signal-safe** functions (see
`signal-safety(7)`). Safe: `read`, `write`, `_exit`, `sem_post`, `kill`. **Not safe:**
`printf`, `malloc`, `free`, most libc — they may hold locks your interrupted code
also needs → deadlock.

```
   main thread: malloc() holds arena lock
        │
   SIGINT arrives mid-malloc
        │
   handler: printf() → tries same lock → deadlock
```

**Trade-offs ▸** Keep handlers minimal: set a **`volatile sig_atomic_t` flag** and
return; main loop does the real work.

---

## 4.2.5 Correct sigaction handler with sig_atomic_t flag

```c
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <unistd.h>

static volatile sig_atomic_t got_usr1 = 0;

static void on_usr1(int signo) {
    (void)signo;
    got_usr1 = 1;   /* only async-signal-safe ops here */
}

int main(void) {
    struct sigaction sa;

    sa.sa_handler = on_usr1;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = 0;   /* no SA_RESTART needed — we use sleep/poll loop */

    if (sigaction(SIGUSR1, &sa, NULL) == -1) {
        perror("sigaction");
        return 1;
    }

    printf("PID %d: send SIGUSR1 with kill -USR1 %d\n", getpid(), getpid());

    while (!got_usr1) {
        if (pause() == -1 && errno != EINTR) {
            perror("pause");
            return 1;
        }
    }

    /* safe to use stdio after handler returns to normal context */
    puts("main: observed got_usr1 flag, continuing...");
    return 0;
}
```

Test: `kill -USR1 <pid>` from another shell.

---

## 4.2.6 kill(), raise(), killpg()

> **The call ▸**
> ```c
> #include <signal.h>
> #include <sys/types.h>
>
> int kill(pid_t pid, int sig);
> int raise(int sig);
> int killpg(pid_t pgrp, int sig);
> ```
> **`kill(0, sig)`** → all processes in caller's process group (Part 1.5).
> **`kill(-1, sig)`** → broadcast (restricted; needs privilege for most signals).

**Errors ▸**

| `errno` | When |
|---------|------|
| `ESRCH` | No such process/group |
| `EINVAL` | Invalid signal |
| `EPERM` | Caller lacks permission |

---

## 4.2.7 siginfo and SA_SIGINFO

With `SA_SIGINFO`, the handler receives **`siginfo_t`** — sender PID, fault address
(for `SIGSEGV`), band event for `SIGPOLL`, etc.

```c
static void on_segv(int sig, siginfo_t *info, void *ctx) {
    (void)ctx;
    /* only async-signal-safe logging: write() with ASCII */
    char buf[64];
    int len = snprintf(buf, sizeof buf, "fault at %p\n", info->si_addr);
    if (len > 0)
        write(STDERR_FILENO, buf, (size_t)len);
}
```

Note: `snprintf` is **not** officially async-signal-safe — production code uses raw
`write()` of fixed strings or defers to the main thread.

---

## 4.2.8 Restartability and EINTR

Slow syscalls (`read`, `connect`, `sleep`) may return **-1** with **`EINTR`** if a
handler runs without **`SA_RESTART`**.

```
   read() blocked
        │
   signal delivered → handler runs → read returns EINTR
```

Options:

- Set **`SA_RESTART`** on handlers that shouldn't interrupt I/O.
- Loop on `EINTR` manually (Part 2.2).
- Use **`signalfd()`** or **self-pipe trick** (write a byte from handler to a pipe
  watched by `poll`/`epoll`, Part 6.6) to integrate signals into event loops safely.

**Systems ▸** `signalfd` + `epoll` is how many servers avoid signal handlers in hot
paths entirely — signals become readable events on an fd.

---

## Summary

- Signals are asynchronous notifications identified by number; defaults include
  terminate, ignore, stop, or continue.
- Install handlers with **`sigaction()`**, not `signal()`; **`SIGKILL`/`SIGSTOP`**
  are uncatchable.
- **Pending** vs **blocked** masks control delivery timing via **`sigprocmask()`**.
- Handlers must be **async-signal-safe** — typically set a **`volatile sig_atomic_t`**
  flag only.
- **`kill`/`raise`/`killpg`** send signals; **`SA_RESTART`** and **`EINTR`** govern
  syscall interruption; **`signalfd`/self-pipe** integrate with modern event loops.

Next: [4.3 — System V IPC: message queues & semaphores](03-sysv-ipc.md)
