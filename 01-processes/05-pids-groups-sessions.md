# 1.5 — PIDs, Process Groups & Sessions

Beyond individual PIDs, the kernel groups processes for **job control**, **signal
delivery**, and **terminal access**. A shell's pipeline (`cmd1 | cmd2`), a
foreground job, and a daemon detached from the terminal all manipulate **process
groups** and **sessions**. This layer sits on top of the process model (Part 1.1)
and the fork/exec/wait lifecycle (Parts 1.2–1.4).

---

## 1.5.1 PID, PPID, and TID

> **The call ▸**
> ```c
> #include <unistd.h>
> #include <sys/types.h>
>
> pid_t getpid(void);     /* thread group ID — "the process PID" */
> pid_t getppid(void);    /* parent PID */
> ```
> ```c
> #define _GNU_SOURCE
> #include <unistd.h>
> #include <sys/types.h>
>
> pid_t gettid(void);     /* this thread's kernel ID (Linux-specific) */
> ```

```
   thread group (what users call "the process")
   ┌─────────────────────────────────────────┐
   │  tgid = 1000  (getpid() returns this)   │
   │  ┌─────────┐ ┌─────────┐ ┌─────────┐    │
   │  │ tid 1000│ │ tid 1001│ │ tid 1002│    │
   │  │ main    │ │ worker  │ │ worker  │    │
   │  └─────────┘ └─────────┘ └─────────┘    │
   └─────────────────────────────────────────┘
```

- **`getpid()`** returns **tgid** — same for all threads in a process.
- **`gettid()`** returns the per-thread ID — useful in `strace`, `/proc/self/task/`,
  and `sched_setaffinity` on a specific thread (Part 1.6).

`/proc/self/task/` lists all TIDs in your thread group.

---

## 1.5.2 Process groups

A **process group** is a set of processes that share one **PGID** (process group ID).
Every process belongs to exactly one group; the PGID equals some member's PID
(the **group leader**).

> **The call ▸**
> ```c
> #include <unistd.h>
> #include <sys/types.h>
>
> pid_t getpgrp(void);              /* getpgid(0) */
> pid_t getpgid(pid_t pid);
> int   setpgid(pid_t pid, pid_t pgid);
> ```

```
   session
   ┌─────────────────────────────────────────────────────┐
   │  PGID 2000 (group leader: shell)                    │
   │    shell PID 2000                                   │
   │    ├─ pipeline child PGID 2000  (same group)        │
   │    └─ pipeline child PGID 2000                      │
   │                                                     │
   │  PGID 2005 (background job)                         │
   │    long_running &                                   │
   └─────────────────────────────────────────────────────┘
```

Shells call **`setpgid(0, 0)`** in a child to put it in its own group, or
**`setpgid(child, pgid)`** so pipeline stages share one PGID — enabling **`kill(-pgid, SIGINT)`**
to interrupt the whole pipeline.

**Errors ▸** (`setpgid`)

| `errno` | when it happens |
|---------|-----------------|
| `EACCES` | child already `exec()`ed across an `setpgid` race |
| `EINVAL` | invalid `pgid` |
| `EPERM`  | policy prevents moving process to requested group |

**Pitfall ▸** **`setpgid` must happen in both parent and child** around `fork`/`exec`
to avoid a window where the child is in the wrong group — shells use careful
ordering; see `man 2 setpgid`.

---

## 1.5.3 Sessions and the controlling terminal

A **session** is a set of process groups. One process is the **session leader**
(creator). A session may have at most one **controlling terminal** (tty).

> **The call ▸**
> ```c
> #include <unistd.h>
>
> pid_t getsid(pid_t pid);
> pid_t setsid(void);
> ```
> **`setsid()`** creates a **new session**, makes the caller **session leader**,
> puts the caller in a **new process group**, and **disconnects from the controlling tty**.

```
   login shell session
   ┌───────────────────────────────────────────────┐
   │  SID 2000  (session leader = shell)           │
   │  controlling terminal: /dev/pts/0             │
   │                                               │
   │  foreground PGID 2000  ← keyboard input       │
   │  background PGID 2005  ← SIGTTIN if reads tty |
   └───────────────────────────────────────────────┘
```

**Rules that matter:**

- Only a process that is **not** a process group leader may call **`setsid()`**
  successfully — hence the **double-fork** trick for daemons (below).
- Background groups that **`read()` the controlling tty** get **`SIGTTIN`**;
  background **`write()`** may get **`SIGTTOU`**.

---

## 1.5.4 Foreground, background, and job control

Job control signals (Part 4.2):

| Signal | Typical effect |
|--------|----------------|
| `SIGINT` (Ctrl-C) | sent to **foreground process group** |
| `SIGTSTP` (Ctrl-Z) | stop foreground group |
| `SIGCONT` | continue stopped group |

```
   terminal driver
        │
        │  knows: session SID, foreground PGID
        ▼
   Ctrl-C  ──▶  SIGINT to every process in foreground PGID
```

The shell adjusts foreground PGID with **`tcsetpgrp()`** (libc, uses `ioctl` on the
tty — Part 8.3) when you run `fg`, `bg`, or start a pipeline.

**Systems ▸** `ps -o pid,pgid,sid,tty,stat -p $$` shows your shell's IDs. `jobs`
lists background groups in bash.

---

## 1.5.5 Signals to a whole group

> **The call ▸**
> ```c
> #include <signal.h>
> int kill(pid_t pid, int sig);
> ```

- **`kill(pid, sig)`** — one process.
- **`kill(-pgid, sig)`** — **every process** in group `pgid` (if you have permission).
- **`kill(0, sig)`** — every process in the **caller's group**.

This is how **`kill %1`** in a shell stops a background job: the shell knows the
job's PGID and sends `SIGTERM` or `SIGCONT`.

**Errors ▸** (`kill`)

| `errno` | when it happens |
|---------|-----------------|
| `EINVAL` | invalid signal |
| `EPERM` | no permission to signal target |
| `ESRCH` | pid/pgid does not exist |

---

## 1.5.6 Detaching a daemon: setsid and double-fork

Classic daemon startup (simplified):

```
   1. fork()           parent exits → child not a shell foreground job
   2. setsid()         new session, no controlling tty
   3. fork() again     parent exits → child is not session leader
                       (cannot accidentally acquire a tty)
   4. chdir("/")       don't hold mount busy
   5. close fds 0,1,2  or redirect to /dev/null
   6. exec server      or continue in same binary
```

```c
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <errno.h>

static int daemonize(void) {
    pid_t pid = fork();
    if (pid == -1) {
        perror("fork");
        return -1;
    }
    if (pid > 0)
        _exit(0);   /* parent exits */

    if (setsid() == -1) {
        perror("setsid");
        return -1;
    }

    pid = fork();
    if (pid == -1) {
        perror("fork");
        return -1;
    }
    if (pid > 0)
        _exit(0);

    if (chdir("/") == -1) {
        perror("chdir");
        return -1;
    }

    int fd = open("/dev/null", O_RDWR);
    if (fd == -1) {
        perror("open /dev/null");
        return -1;
    }
    if (dup2(fd, STDIN_FILENO) == -1 ||
        dup2(fd, STDOUT_FILENO) == -1 ||
        dup2(fd, STDERR_FILENO) == -1) {
        perror("dup2");
        close(fd);
        return -1;
    }
    if (fd > STDERR_FILENO)
        close(fd);

    return 0;
}

int main(void) {
    if (daemonize() == -1)
        exit(1);
    /* long-lived daemon body — no controlling terminal */
    for (;;)
        pause();
    return 0;
}
```

Modern alternative: **`sd_notify`** / **`Type=notify`** with systemd, or **`daemon(3)`**
from libc (wraps similar steps — read its source before trusting it in production).

**Trade-offs ▸** Double-fork is historical; **`setsid()` alone** suffices if you
never open a tty and don't need to avoid being session leader for SIGHUP semantics.
Containers often skip forking entirely — PID 1 in a namespace is a different story
(Part 8.5).

---

## Summary

- **`getpid`/`getppid`/`gettid`** identify process and thread IDs; `/proc/self/task/`
  lists threads.
- **Process groups (PGID)** batch processes for signals; **`setpgid`** sets membership.
- **Sessions (SID)** hold groups; **`setsid`** creates a session and drops the controlling tty.
- **Job control** routes terminal signals to the **foreground process group**.
- **`kill(-pgid, sig)`** signals an entire group; daemons use **fork + setsid +
  double-fork** to detach from the shell's terminal.

Next: [1.6 — Scheduling & Priority](06-scheduling-and-priority.md)
