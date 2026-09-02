# 1.1 — The Process Model

Everything in Part 1 rests on one kernel object: the **process** (more precisely,
the **task**). A process is not a `.exe` file on disk — it is a *live execution
context* the kernel tracks: an address space, a set of open resources, scheduling
state, and an identity (PID). When you `fork()`, `execve()`, or `wait4()`, you
are manipulating this object through the syscall interface (Part 0.1).

---

## 1.1.1 Program vs process

```
   on disk                         in memory (one running process)
   ┌──────────────┐                ┌─────────────────────────────┐
   │  /bin/ls     │   execve()     │  text  (machine code, RO)   │
   │  ELF binary  │  ──────────▶   │  data  (globals, RW)        │
   │  (inactive)  │                │  heap  (malloc/brk grows ↑) │
   └──────────────┘                │  ...                        │
                                   │  stack (locals, grows ↓)    │
                                   └─────────────────────────────┘
                                         ▲
                                         │ one virtual address space
                                         │ one task_struct in the kernel
```

- A **program** is a file — bytes on disk, not executing.
- A **process** is that program *loaded and running* (or sleeping, or stopped)
  under kernel supervision. Many processes can run the same program file
  simultaneously, each with its own address space and PID.

**Systems ▸** `ps`, `top`, and `/proc` enumerate **processes**, not programs.
`pgrep ls` finds processes whose executable is `ls`, not the file itself.

---

## 1.1.2 What the kernel tracks: task_struct

From your program's perspective you have a PID. Inside the kernel, every runnable
entity is a **`struct task_struct`** — the process/thread descriptor:

```
   task_struct (kernel memory, not visible to user space)
   ┌─────────────────────────────────────────────────────────┐
   │  pid, tgid          identity                            │
   │  mm                  → mm_struct (page tables, VMAs)    │
   │  files               → file descriptor table            │
   │  fs                  → cwd, root, umask                 │
   │  signal              → pending/handlers/mask            │
   │  sched              → priority, policy, run queue state │
   │  parent / children   → process tree links               │
   │  state               → RUNNING / SLEEPING / ZOMBIE ...  │
   └─────────────────────────────────────────────────────────┘
```

> **Under the hood ▸** The scheduler does not "run programs" — it picks
> `task_struct` entries and runs their saved register state on a CPU. The MMU
> uses the task's `mm_struct` to translate virtual addresses. Every syscall that
> touches memory, files, or signals goes through fields in this struct. Part 5
> shows that **threads share one `mm_struct`** but get their own `task_struct`;
> for now, treat "process ≈ one task with its own address space."

---

## 1.1.3 PID and PPID

> **The call ▸**
> ```c
> #include <unistd.h>
> #include <sys/types.h>
>
> pid_t getpid(void);    // this process's PID
> pid_t getppid(void);   // parent process's PID
> ```
> Both always succeed; neither sets `errno`.

Every process has:

| Field | Meaning |
|-------|---------|
| **PID** | Process ID — a small positive integer, unique *while the process lives* |
| **PPID** | Parent PID — who created this process (`fork`/`clone` parent) |

```
        init/systemd (PID 1)
              │
         ┌────┴────┐
         │  shell  | PID 1000, PPID 1
         └────┬────┘
        ┌─────┴─────┐
        │           │
     PID 1001     PID 1002
     PPID 1000   PPID 1000
     (child A)    (child B)
```

**Trade-offs ▸** PIDs are **reused** after a process exits and is reaped (see
Part 1.4). The kernel allocates PIDs from a cyclic counter (`/proc/sys/kernel/pid_max`);
don't assume a PID means the same process forever.

---

## 1.1.4 Task states

A process is always in exactly one **state** from the scheduler's point of view.
The canonical Linux states:

![Process state diagram](figures/process-states.svg)

```
   RUNNING / RUNNABLE          on a CPU, or ready to be scheduled
         │
         ▼
   INTERRUPTIBLE SLEEP (S)     waiting for I/O, lock, timer — signals can wake it
         │
         ▼
   UNINTERRUPTIBLE SLEEP (D)   waiting on disk I/O — cannot be killed until I/O done
         │
         ▼
   STOPPED (T)                 SIGSTOP / job control — not scheduled
         │
         ▼
   ZOMBIE (Z)                  exited, waiting for parent to wait()
```

| State | What it means | Visible as |
|-------|---------------|------------|
| **Running / Runnable** | Executing or queued for a CPU | `R` in `ps` |
| **Interruptible sleep** | Blocked, wakeable by signal | `S` |
| **Uninterruptible sleep** | Blocked on uninterruptible I/O | `D` — often a stuck driver |
| **Stopped** | Suspended by signal or debugger | `T` |
| **Zombie** | Dead but not reaped by parent | `Z` — see Part 1.4 |

> **Under the hood ▸** `ps` reads `/proc/[pid]/stat` field 3 for the one-letter
> state. A zombie still holds a `task_struct` slot until the parent calls
> `wait()` — it has exited but its exit status is stored for the parent.

**Pitfall ▸** Hundreds of zombies (`defunct` in `ps`) mean the parent never
calls `wait()`. They consume kernel task slots and PIDs; they do **not** use
much memory, but they will eventually exhaust the PID space.

---

## 1.1.5 Inspecting live processes: /proc/[pid]

`/proc` is a virtual filesystem (Part 8.1) exposing kernel data as files:

```
   /proc/[pid]/
   ├── status      human-readable: State, Pid, PPid, VmRSS, ...
   ├── stat        one-line kernel stats (state, utime, stime, ...)
   ├── cmdline     argv as NUL-separated C strings
   ├── environ     environment (needs permission)
   ├── cwd         symlink → current working directory
   ├── exe         symlink → executable file
   ├── maps        memory mappings (Part 3.1)
   └── fd/           symlinks to open file descriptors (Part 0.5)
```

> **Example ▸** Read your own PID and parent:

```c
#include <stdio.h>
#include <unistd.h>
#include <sys/types.h>

int main(void) {
    printf("PID  = %d\n", getpid());
    printf("PPID = %d\n", getppid());
    return 0;
}
```

Or from the shell: `cat /proc/self/status | head -5` — `self` is a kernel alias
for the calling process.

---

## 1.1.6 Threads as tasks (preview)

Linux does not distinguish "process" vs "thread" at the scheduler level — both
are **`task_struct`** entries:

```
   process (traditional view)          Linux kernel view
   ┌─────────────────────┐            ┌── task ── task ── task ──┐
   │  one address space  │     ≡      │  shared mm_struct        │
   │  one PID            │            │  same tgid, different tid│
   └─────────────────────┘            └──────────────────────────┘
                                              ↑
                                    clone() with CLONE_VM (Part 1.2, Part 5.1)
```

- **PID** (`getpid()`) = thread group ID (`tgid`) — what users think of as "the process PID."
- **TID** (`gettid()`) = per-thread ID — unique for each thread in the group.

We defer thread mechanics to Part 5; for Part 1, remember: **fork creates a new
task + new address space; pthread_create uses `clone()` to share the address space.

---

## 1.1.7 How this connects to upcoming syscalls

The process lifecycle syscalls you will use constantly:

```
   fork()/clone()  →  new task_struct, (usually) new address space
   execve()        →  replace memory image, same PID
   exit()          →  child becomes zombie until parent wait()s
   wait()          →  parent reaps zombie, frees task_struct
```

Part 1.2 covers creation; Part 1.3 exec; Part 1.4 wait and zombies. The process model above is the backdrop for all of it.

---

## Summary

- A **process** is a live kernel `task_struct` with its own virtual address space,
  resources, and PID; a **program** is just the on-disk executable.
- **PID/PPID** identify the process and its parent; PIDs are reused after reap.
- Task **states** (running, sleeping, stopped, zombie) determine schedulability;
  zombies mean the parent has not called `wait()`.
- **`/proc/[pid]`** exposes process state, memory maps, fds, and cmdline without
  special tools.
- **Threads** are separate tasks sharing one address space — preview for Part 5.

Next: [1.2 — Creating Processes: fork & clone](02-fork-and-clone.md)
