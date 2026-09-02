# 1.4 — wait(), Zombies & Orphans

When a process calls `exit()` or returns from `main`, its memory is torn down —
but the kernel **keeps a skeleton** until the parent collects the exit status.
That skeleton is a **zombie**. `wait()` family syscalls are how parents **reap**
children, free kernel slots, and learn how they terminated. This closes the loop
started by `fork()` (Part 1.2) and often follows `exec()` (Part 1.3).

---

## 1.4.1 The process lifecycle

![Process lifecycle](figures/process-lifecycle.svg)

```
   fork()
     │
     ▼
   RUNNING ──exit()──▶ ZOMBIE ──parent wait()──▶ (removed from process table)
     │                    │
     │                    └── still has PID, exit code; no user memory
     │
     └── if parent dies first ──▶ orphan ──▶ reparented to PID 1 (systemd)
```

> **Under the hood ▸** `_exit()` / `exit_group()` syscall sets exit code, sends
> `SIGCHLD` to parent (if handler is default/ignored in a way that notifies),
> and transitions to `EXIT_ZOMBIE`. Only `wait*()` (or parent death + init reap)
> frees the `task_struct`.

---

## 1.4.2 The wait family

> **The call ▸**
> ```c
> #include <sys/types.h>
> #include <sys/wait.h>
>
> pid_t wait(int *wstatus);
> pid_t waitpid(pid_t pid, int *wstatus, int options);
> ```
> **`wait(status)`** ≡ **`waitpid(-1, status, 0)`** — any child, blocking.

> **The call ▸** (Linux extensions)
> ```c
> int waitid(idtype_t idtype, id_t id, siginfo_t *infop, int options);
> pid_t wait4(pid_t pid, int *wstatus, int options, struct rusage *rusage);
> ```
> `wait4` adds **resource usage**; `waitid` uses `siginfo_t` and finer `idtype`
> (`P_PID`, `P_PGID`, `P_ALL`).

**`waitpid` options:**

| Flag | Effect |
|------|--------|
| `0` | block until a matching child exits |
| `WNOHANG` | return immediately; `0` if no child ready |
| `WUNTRACED` | also report stopped children (`SIGSTOP`) |
| `WCONTINUED` | report continued children (`SIGCONT`) |

**Errors ▸**

| `errno` | when it happens |
|---------|-----------------|
| `ECHILD` | caller has no children (or none matching `pid`) |
| `EINTR` | interrupted by signal — retry or handle |
| `EINVAL` | invalid `options` |

---

## 1.4.3 Decoding wstatus: WIF* macros

Never inspect `wstatus` with raw bit tests — use `<sys/wait.h>` macros:

```c
#include <sys/wait.h>

if (WIFEXITED(status)) {
    int code = WEXITSTATUS(status);   /* 0–255 from exit()/return */
}
if (WIFSIGNALED(status)) {
    int sig  = WTERMSIG(status);      /* signal that killed child */
    int core = WCOREDUMP(status);     /* core dumped? */
}
if (WIFSTOPPED(status)) {
    int sig  = WSTOPSIG(status);      /* job control / ptrace stop */
}
if (WIFCONTINUED(status)) {
    /* child resumed by SIGCONT */
}
```

```
   wstatus layout (simplified; use macros!)
   ┌──────────────────────────────────────┐
   │  low byte: exit code (if exited)      │
   │  or signal number (if signaled)       │
   │  flag bits: exited / signaled / stopped│
   └──────────────────────────────────────┘
```

**Pitfall ▸** Only **`WEXITSTATUS`** is valid if **`WIFEXITED`** is true.
Reading exit code when the child was killed by `SIGKILL` is undefined — check
`WIFSIGNALED` first.

---

## 1.4.4 Zombies: unreaped children

A **zombie** (`Z` in `ps`, `<defunct>`) is a process that has **exited** but whose
parent has not **`wait()`ed**:

```
   parent busy / buggy                kernel
   ┌─────────────┐                   ┌──────────────┐
   │  parent     │  never wait()     │ zombie child │
   │  PID 1000   │◀── SIGCHLD ───────│ PID 1001, Z  │
   └─────────────┘                   │ exit code: 42│
                                     └──────────────┘
                                           │
                                     holds PID slot
```

Why it matters:

- Each zombie consumes a **`task_struct`** and a **PID** until reaped.
- They use negligible RAM (no mappings), but **thousands of zombies exhaust
  `pid_max`** — new `fork()` fails with `EAGAIN`.
- Fix: parent must **`wait()`** (or ignore children with `SIG_IGN` — see below).

---

## 1.4.5 Orphans and PID 1

If the **parent exits before the child**, the child becomes an **orphan**:

```
   parent exits (no wait)     child still running
         │                         │
         ▼                         ▼
   removed from tree          reparented to init (PID 1)
                              systemd adopts, will wait() on exit
```

> **Under the hood ▸** The kernel walks the process tree and reassigns orphans to
> **PID 1** (`systemd` on modern Linux). PID 1 is written to **`wait()`** in a
> loop so orphans never accumulate as zombies system-wide.

**Trade-offs ▸** Double-fork daemon pattern (Part 1.5) ensures the long-lived
daemon's parent is PID 1 immediately — so daemon children aren't tied to a
shell session.

---

## 1.4.6 SIGCHLD and automatic reap

When a child terminates, the kernel may send **`SIGCHLD`** to the parent. Default
action is **ignore**, but a waiting `wait()` still works. With a **`SIGCHLD` handler**,
use **`waitpid(-1, &st, WNOHANG)` in a loop** — multiple children may exit before
one signal:

```c
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <signal.h>
#include <errno.h>

static volatile sig_atomic_t got_sigchld;

static void on_sigchld(int sig) {
    (void)sig;
    got_sigchld = 1;
}

static void reap_children(void) {
    int status;
    pid_t pid;

    while ((pid = waitpid(-1, &status, WNOHANG)) > 0) {
        if (WIFEXITED(status))
            fprintf(stderr, "reaped PID %d, exit %d\n",
                    pid, WEXITSTATUS(status));
        else if (WIFSIGNALED(status))
            fprintf(stderr, "reaped PID %d, signal %d\n",
                    pid, WTERMSIG(status));
    }
    if (pid == -1 && errno != ECHILD)
        perror("waitpid");
}

int main(void) {
    struct sigaction sa = { .sa_handler = on_sigchld, .sa_flags = SA_RESTART };
    sigemptyset(&sa.sa_mask);
    if (sigaction(SIGCHLD, &sa, NULL) == -1) {
        perror("sigaction");
        exit(1);
    }

    for (int i = 0; i < 3; i++) {
        pid_t pid = fork();
        if (pid == -1) { perror("fork"); exit(1); }
        if (pid == 0) {
            sleep(1);
            _exit(i + 10);
        }
    }

    while (got_sigchld == 0)
        pause();   /* wait for signal; SA_RESTART handles EINTR on some syscalls */

    reap_children();
    return 0;
}
```

Setting **`signal(SIGCHLD, SIG_IGN)`** (or `sa_handler = SIG_IGN` with
`SA_NOCLDWAIT` on Linux) tells the kernel to **auto-reap** children — useful for
worker pools where you don't need exit status.

**Pitfall ▸** Calling non-async-signal-safe functions (e.g. `printf`) inside a
`SIGCHLD` handler is unsafe (Part 4.2). Set a flag and reap in the main loop, as
above.

---

## 1.4.7 _exit vs exit in children after fork

After `fork()`, only one branch should call **`exit()`** from libc — it flushes
stdio buffers shared with the parent. Children should use **`_exit()`** / **`_Exit()`**
to terminate without duplicate output or double-free of libc state.

---

## Summary

- **`wait`/`waitpid`/`wait4`/`waitid`** block (or poll with `WNOHANG`) for child
  state changes and reap zombies.
- Use **`WIFEXITED`/`WEXITSTATUS`/`WIFSIGNALED`** macros — never raw bit hacks.
- **Zombies** hold PIDs until reaped; fix the parent, not the zombie.
- **Orphans** are reparented to **PID 1**, which reaps them.
- Handle **`SIGCHLD`** with a **`WNOHANG` loop**; use **`_exit()`** in forked children.

Next: [1.5 — PIDs, Process Groups & Sessions](05-pids-groups-sessions.md)
