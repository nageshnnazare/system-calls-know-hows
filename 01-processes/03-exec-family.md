# 1.3 — Running Programs: the exec Family

`fork()` duplicates a process; **`execve()` replaces what it runs**. Together with
`wait()` (Part 1.4), they form the Unix process-launch idiom every shell, init
system, and application server uses. There is only **one** kernel syscall here —
`execve()` — and a family of libc wrappers that differ in how they pass arguments
and locate the binary.

---

## 1.3.1 execve() is the real syscall

> **The call ▸**
> ```c
> #include <unistd.h>
>
> int execve(const char *pathname, char *const argv[], char *const envp[]);
> ```
> **Returns:** does not return on success; **-1** on error (`errno` set).

```
   BEFORE execve("/bin/ls", ...)          AFTER (same PID!)
   ┌─────────────────────────┐            ┌─────────────────────────┐
   │  old text/data/heap     │  overlay   │  /bin/ls mapped in      │
   │  old stack (replaced)   │  ────────▶ │  fresh stack with argv  │
   │  PID 1001 unchanged     │            │  PID 1001 unchanged     │
   └─────────────────────────┘            └─────────────────────────┘
```

![exec memory overlay](figures/exec-overlay.svg)

> **Under the hood ▸** The kernel loads the ELF (or interpreter — see shebang
> below), builds a new address space **in place** (same `task_struct`, same PID),
> sets up the stack with `argc/argv/envp`, clears pending signals and signal
> handlers to defaults, and jumps to the program entry point. On failure, the
> old image remains intact.

---

## 1.3.2 The wrapper naming scheme

All `exec*` functions call `execve()` (directly or via `execveat()`). The suffix
letters encode **how** arguments and the binary path are supplied:

| Wrapper | Path | argv | env | Notes |
|---------|------|------|-----|-------|
| `execl` | literal | list (`..., NULL`) | inherits | `l` = list |
| `execv` | literal | array | inherits | `v` = vector |
| `execle` | literal | list | explicit | `e` = environ |
| `execve` | literal | array | explicit | the syscall |
| `execlp` | `PATH` search | list | inherits | `p` = PATH |
| `execvp` | `PATH` search | array | inherits | most common in shells |

Mnemonic: **`l`** vs **`v`** = varargs list vs `char *argv[]`; **`p`** = search
`PATH`; **`e`** = explicit `envp[]`.

```c
/* these are equivalent (modulo PATH): */
execl("/bin/ls", "ls", "-l", NULL);
char *av[] = { "ls", "-l", NULL };
execv("/bin/ls", av);
execvp("ls", av);   /* searches PATH */
```

**Pitfall ▸** Every `argv` list **must** be NULL-terminated. Forgetting the
final `NULL` makes the kernel read past your array — undefined behavior, often
`EFAULT`.

---

## 1.3.3 What survives exec vs what is replaced

| Survives `execve()` | Replaced / reset |
|---------------------|------------------|
| **PID**, **PPID** | Entire memory image (text, data, heap, stack) |
| Open fds (unless `O_CLOEXEC` / `FD_CLOEXEC`) | Signal handlers → default (except ignored) |
| Nice value, scheduling policy | Signal mask: pending signals cleared |
| Current working directory | Memory locks (`mlock`) cleared |
| umask, resource limits | Some perf counters reset |

```
   fork()  →  same program, duplicated memory
   exec()  →  same PID, new program, new memory
```

File descriptors are the classic footgun (Part 0.5): a daemon that `fork()`s and
`exec()`s without closing or marking fds **CLOEXEC** leaks the parent's open
web server socket into unrelated children.

---

## 1.3.4 argv and envp

The kernel constructs the new stack roughly as:

```
   high addresses
   ┌─────────────────┐
   │  env strings    │  KEY=VALUE\0 ...
   │  arg strings    │  "ls\0", "-l\0"
   │  envp[]         │  pointers → env strings, NULL
   │  argv[]         │  pointers → arg strings, NULL
   │  argc           │  integer
   └─────────────────┘
   low addresses (stack grows down on x86-64)
```

- **`argv[0]`** is conventionally the program name — `ps` and `/proc/[pid]/cmdline`
  display it; it need not match the executable path.
- **`envp`** is an array of `"KEY=VALUE"` strings; if NULL to `execve`, the child
  inherits the parent's environment. Shells export variables into `envp` before
  exec.

---

## 1.3.5 The shebang (`#!`)

When `pathname` is not a binary ELF but a script:

```
   file: /usr/bin/python3
   ┌──────────────────────────────┐
   │ #!/usr/bin/python3           │  ← kernel reads first line
   │ import sys ...               │
   └──────────────────────────────┘
        │
        ▼
   kernel execve's the *interpreter* with argv[0]=interpreter, argv[1]=script
```

> **Under the hood ▸** The kernel sees `#!` magic, parses the interpreter path,
> and effectively does `execve("/usr/bin/python3", ["python3", "/path/script", ...], envp)`.
> The script itself is not executed as machine code.

---

## 1.3.6 fork + exec + wait — the canonical idiom

Shells don't `exec` themselves — they **fork a child** that **exec**s the command,
while the parent **wait**s (Part 1.4):

```
   shell (parent)                child
        │                          │
        │ fork()                   │
        ├─────────────────────────▶│
        │                          │ execve("/bin/ls", ...)
        │ waitpid()                │ ... runs ls ...
        │◀────── exit status ──────│ _exit()
        │                          ✗ gone (reaped)
```

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
        /* child: replace image with /bin/echo */
        char *argv[] = { "echo", "hello from exec", NULL };
        execvp("echo", argv);
        /* only reached if exec fails */
        perror("execvp");
        _exit(127);   /* conventional "exec failed" status */
    }

    /* parent: wait for child */
    int status;
    if (waitpid(pid, &status, 0) == -1) {
        perror("waitpid");
        exit(1);
    }

    if (WIFEXITED(status)) {
        int code = WEXITSTATUS(status);
        if (code == 127)
            fprintf(stderr, "child: exec failed\n");
        else
            printf("child exited with %d\n", code);
    } else if (WIFSIGNALED(status)) {
        fprintf(stderr, "child killed by signal %d\n", WTERMSIG(status));
    }

    return 0;
}
```

**Errors ▸** (exec family — all set `errno`, return -1)

| `errno` | when it happens |
|---------|-----------------|
| `ENOENT` | file not found (or interpreter in shebang missing) |
| `EACCES` | not executable / search permission denied |
| `ENOEXEC` | file not in recognized executable format |
| `ENOMEM` | kernel cannot map segments |
| `E2BIG` | argument list or environment too large |
| `ETXTBSY` | executable open for writing (race with writer) |

---

## Summary

- **`execve()`** replaces the process memory image; **PID and open fds survive**
  (unless CLOEXEC).
- Wrapper suffixes: **`l`** list, **`v`** vector, **`p`** PATH, **`e`** explicit env.
- **`argv`** must be NULL-terminated; **`envp`** is `KEY=VALUE` strings.
- The **shebang** makes the kernel exec an interpreter with the script as an argument.
- Production pattern: **`fork()` → child `exec*()` → parent `wait*()`** — the
  shell's core loop.

Next: [1.4 — wait(), Zombies & Orphans](04-wait-zombies-orphans.md)
