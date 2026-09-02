# 1.2 — Creating Processes: fork & clone

`fork()` is the Unix answer to "run this code path in a new process." It is the
syscall behind nearly every daemon, shell pipeline, and server worker. Mechanically,
it **clones the calling task** and returns **twice** — once in the parent, once
in the child. Part 1.3 overlays a new program with `execve()`; Part 1.4 reaps the
child with `wait()`.

---

## 1.2.1 fork() returns twice

> **The call ▸**
> ```c
> #include <unistd.h>
> #include <sys/types.h>
>
> pid_t fork(void);
> ```
> **Returns:** child PID in parent; **0 in child**; **-1** on error (`errno` set).

```
   BEFORE fork()                    AFTER fork()
   ┌──────────────┐                 ┌──────────────┐  ┌──────────────┐
   │   parent     │                 │   parent     │  │    child     │
   │   PID 1000   │   fork()        │   PID 1000   │  │   PID 1001   │
   └──────────────┘  ──────────▶    │  return 1001 │  │  return 0    │
                                    └──────────────┘  └──────────────┘
                                           │                  │
                                           └──── same code ───┘
                                                continues in both
```

The child sees `fork() == 0` because it is a **new task** — there is no other way
to distinguish "am I the original or the copy?" in C. The parent gets the child's
PID to track, signal, or `wait()` for it.

**Pitfall ▸** Testing `if (fork() == 0)` in a loop without saving PIDs creates
uncontrolled children that all execute the loop body. Always branch immediately:
parent records PID, child does work or `exec`s, never falls through into another
`fork()`.

---

## 1.2.2 Copy-on-write: why fork is "cheap"

![fork copy-on-write](figures/fork-cow.svg)

Naïvely cloning a 10 GB address space would copy 10 GB. Linux uses
**copy-on-write (COW)**:

```
   fork()
     │
     ├─ duplicate page *tables* (metadata), mark all pages read-only, shared
     │
     └─ on first write in parent OR child → page fault → kernel copies ONE page
```

Both tasks share physical pages until one writes — then only that page is copied.
Fork cost is roughly **O(number of mapped VMAs + page table entries)**, not
O(process size). See Part 3.1 for the virtual memory layout fork duplicates.

> **Under the hood ▸** `fork()` is implemented via `clone()` with
> `SIGCHLD`-equivalent flags and **without** `CLONE_VM` — child gets its own
> `mm_struct` pointing at COW-shared pages.

**Trade-offs ▸** COW means **fork + immediate exec** (the shell pattern) is very
cheap. Fork + mutate a huge writable mapping in both parent and child can trigger
mass page copies — profile before forking memory-heavy parents.

---

## 1.2.3 Inherited vs not inherited

After `fork()`, the child is a near-copy of the parent at the instant of the call:

| Inherited (copied / COW-shared) | Not inherited (fresh in child) |
|----------------------------------|--------------------------------|
| Memory mappings (COW) | Pending signals *delivered to child* |
| File descriptor table (shared entries, independent offsets) | `exec` will replace memory |
| Environment, cwd, umask | Parent's memory **after fork returns** diverges on write |
| Signal dispositions (with rules) | Thread-local state in parent-only libs |
| Nice value, scheduling class | — |
| Resource limits (`getrlimit`) | — |

Open files deserve emphasis (Part 0.5): parent and child share the **same
underlying file description** for each fd number, but **file offsets are
independent** per process.

```c
/* parent opens file, reads 100 bytes */
/* child inherits fd 3 at offset 100 — not 0 */
```

Use `O_CLOEXEC` (Part 2.1) or `fcntl(FD_CLOEXEC)` so `execve()` closes sensitive
fds in the child.

---

## 1.2.4 A correct fork() example

```c
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <errno.h>

int main(void) {
    pid_t pid = fork();

    if (pid == -1) {
        perror("fork");
        exit(1);
    }

    if (pid == 0) {
        /* child: only the child executes this branch */
        printf("[child]  PID=%d PPID=%d\n", getpid(), getppid());
        _exit(42);   /* _exit avoids flushing stdio twice (Part 1.4) */
    }

    /* parent */
    printf("[parent] forked child PID=%d\n", pid);

    int status;
    if (waitpid(pid, &status, 0) == -1) {
        perror("waitpid");
        exit(1);
    }

    if (WIFEXITED(status))
        printf("[parent] child exited with %d\n", WEXITSTATUS(status));

    return 0;
}
```

Compile: `gcc -Wall -Wextra -o fork_demo fork_demo.c`

**Errors ▸**

| `errno` | when it happens |
|---------|-----------------|
| `EAGAIN` | `/proc/sys/kernel/pid_max` processes exist, or RLIMIT_NPROC hit |
| `ENOMEM` | kernel cannot allocate task_struct / page tables |

---

## 1.2.5 vfork() — avoid it

> **The call ▸** `pid_t vfork(void);` — same return convention as `fork()`.

```
   vfork():  parent BLOCKED until child exec()s or _exit()s
             child runs in *parent's* address space — must not return from vfork in child
```

Historical `vfork()` suspended the parent until the child `exec`/`exit`. It was a
performance hack before COW; on modern Linux **`fork()` is strictly better**.
glibc maps `vfork` to `clone(CLONE_VM | CLONE_VFORK)` — still dangerous if the
child modifies memory before `exec`.

**Pitfall ▸** Never use `vfork()` in new code. If you see it in legacy code, the
child must call `execve()` or `_exit()` immediately — no stack frame to return to in
shared memory safely.

---

## 1.2.6 clone() — the general primitive

> **The call ▸**
> ```c
> #define _GNU_SOURCE
> #include <sched.h>
>
> int clone(int (*fn)(void *), void *stack, int flags, void *arg, ...);
> ```
> `fork()` ≈ `clone(..., SIGCHLD, 0)`. pthreads ≈ `clone(..., CLONE_VM | CLONE_FILES | ...)`.

Important **clone flags** (from `<sched.h>`):

```
   CLONE_VM          share address space        → threads
   CLONE_FILES       share fd table
   CLONE_FS          share cwd/root/umask
   CLONE_SIGHAND     share signal handlers
   CLONE_THREAD      same thread group (same PID/tgid)
   CLONE_VFORK       parent blocks until child execs (vfork semantics)
   CLONE_PIDFD       return pidfd for the child (Linux 5.2+)
```

```
   fork()     = clone with own mm, shared or copied files, SIGCHLD
   pthread    = clone with CLONE_VM | CLONE_FILES | CLONE_SIGHAND | CLONE_THREAD
   unshare()  = clone-like detach from shared resource (Part 8.5 namespaces)
```

Part 5.1 expands thread `clone()` flags; Part 8.5 covers `CLONE_NEWPID` and
friends for containers.

---

## 1.2.7 PID reuse

When a child exits and is **reaped** (`wait()` — Part 1.4), its PID returns to
the kernel pool:

```
   PID 1001 exits → zombie → parent wait() → slot freed
   next fork() may assign 1001 again (after pid_max wrap)
```

Don't cache PIDs assuming they won't be recycled. Use `waitpid()` return value or
`pidfd_open()` (Linux 5.3+) if you need stable handles.

---

## Summary

- `fork()` creates a near-duplicate task; it returns **0 in the child**, the
  **child PID in the parent**, **-1** on error.
- **Copy-on-write** makes fork cheap until pages are written; fork+exec is the
  shell's fast path.
- The child **inherits** fds, cwd, environment; memory **diverges** on write;
  use **`O_CLOEXEC`** before exec.
- **`vfork()`** is obsolete — use `fork()`.
- **`clone()`** with flags is the real syscall behind fork, threads, and
  namespaces.
- **PIDs are reused** after the zombie is reaped.

Next: [1.3 — Running Programs: the exec Family](03-exec-family.md)
