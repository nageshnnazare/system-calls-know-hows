# 2.4 — dup() & I/O Redirection

The shell's `> file`, `2>&1`, and `|` are not magic — they are **`dup2()`**
arrangements on file descriptors. Before `execve()` runs your program, the shell
clones and reassigns fds so fd 0/1/2 (and pipe ends) point at the right open file
descriptions.

`dup()` family syscalls manipulate the **fd table** without creating a new kernel
object: two integers, one shared open file description (Part 0.5).

---

## 2.4.1 dup, dup2, dup3

```
   fd table (before)              fd table (after dup2(out, 1))
   ┌───┬─────────────┐            ┌───┬─────────────┐
   │ 0 │ stdin       │            │ 0 │ stdin       │
   │ 1 │ stdout ─────┼──┐         │ 1 │ stdout ─────┼──┐
   │ 3 │ file out ───┼──┼──▶ OFD  │ 3 │ (closed)    │  │
   └───┴─────────────┘  │         └───┴─────────────┘  │
                        └──────────────────────────────┘
                              both 1 and 3 pointed here;
                              after dup2: only 1 → OFD, 3 closed if was open
```

> **The call ▸**
> ```c
> #include <unistd.h>
>
> int dup(int oldfd);
> int dup2(int oldfd, int newfd);
> int dup3(int oldfd, int newfd, int flags);  /* flags: O_CLOEXEC */
> ```
> `dup(oldfd)` → lowest unused fd ≥ oldfd, same open file description.
> `dup2(oldfd, newfd)` → if `newfd` was open, **close it first**, then make
> `newfd` a copy of `oldfd`. Returns `newfd` on success.
> `dup3` adds `O_CLOEXEC` atomically (avoids race before fcntl).

> **Under the hood ▸** Kernel increments `struct file` refcnt and installs a new
> fd-table slot. **Offset, status flags (`O_APPEND`, `O_NONBLOCK`), and file
> position are shared** — not duplicated.

![File descriptor redirection: shell dup2 before exec](figures/fd-redirection.svg)

**Pitfall ▸** After `dup2(pipe_read, 0)`, both the original pipe fd and stdin may
briefly refer to the same description until you `close()` the spare pipe fd —
otherwise reads may steal data from the wrong slot and the pipe never sees EOF.

---

## 2.4.2 How the shell wires redirection

### `cmd > out.txt` (stdout to file)

```
   1. fd_out = open("out.txt", O_WRONLY|O_CREAT|O_TRUNC, 0666)
   2. dup2(fd_out, STDOUT_FILENO)   /* 1 */
   3. close(fd_out)                 /* 1 still points at file */
   4. execve("cmd", ...)
```

Child sees fd 1 as the file. Original `fd_out` number is closed so it won't leak.

### `cmd 2>&1` (stderr to wherever stdout goes)

```
   dup2(STDOUT_FILENO, STDERR_FILENO)   /* make fd 2 same as fd 1 */
```

Both stderr and stdout share one open file description → **same offset** for
writes. Interleaved `printf`/`fprintf(stderr)` can produce mixed output in one
stream — usually intended for log files.

### `cmd1 | cmd2` (pipe)

```
   parent creates pipe:  fd[0]=read, fd[1]=write

   child1 (cmd1):  dup2(fd[1], 1); close(fd[0]); close(fd[1]);
   child2 (cmd2):  dup2(fd[0], 0); close(fd[0]); close(fd[1]);
   parent:         close both ends
```

Each child starts with only the end it needs on the standard slot; extra pipe fds
**must** be closed or the pipe never hits EOF (Part 4.1).

---

## 2.4.3 F_DUPFD via fcntl

Older portable duplicate-to-lowest-n:

> **The call ▸**
> ```c
> #include <fcntl.h>
> int fcntl(int fd, F_DUPFD, int arg);   /* lowest fd >= arg */
> int fcntl(int fd, F_DUPFD_CLOEXEC, int arg);
> ```

Prefer `dup3(..., O_CLOEXEC)` or `F_DUPFD_CLOEXEC` over plain `dup()` in
long-lived servers that spawn subprocesses — inherited surprise fds are a security
and correctness hazard.

---

## 2.4.4 O_CLOEXEC interaction

`O_CLOEXEC` on `open()` / `dup3()` / `F_DUPFD_CLOEXEC` marks the **fd flag**
`FD_CLOEXEC`: the fd is automatically closed on successful `execve()`.

```
   server accepts connection → socket fd 5
   fork + exec helper without FD_CLOEXEC  →  helper inherits fd 5 (leak)
   with FD_CLOEXEC                        →  helper starts clean
```

**Trade-offs ▸** `FD_CLOEXEC` is fd-table metadata; it is **not** inherited by
`dup()` unless you use `dup3`/`F_DUPFD_CLOEXEC`. A dup'd fd clears CLOEXEC on
the new slot by default.

---

## 2.4.5 Example: manual shell-style redirection

```c
#define _GNU_SOURCE
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int main(int argc, char *argv[]) {
    if (argc < 2) {
        fprintf(stderr, "usage: %s cmd [args...]\n", argv[0]);
        return 1;
    }

    int log = open("run.log", O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (log == -1) { perror("open"); return 1; }

    /* Redirect stdout and stderr to the log (like cmd > run.log 2>&1). */
    if (dup2(log, STDOUT_FILENO) == -1 ||
        dup2(log, STDERR_FILENO) == -1) {
        perror("dup2");
        close(log);
        return 1;
    }
    close(log);  /* fd 1 and 2 hold refs; drop the spare number */

    /* Replace this process with the target program. */
    execvp(argv[1], &argv[1]);
    perror("execvp");
    return 1;
}
```

Without `execvp`, the same `dup2` pattern works for in-process logging — but
remember stdout and stderr now **share an offset** into `run.log`.

**Errors ▸**

| errno | when it happens |
|-------|-----------------|
| `EBADF` | `oldfd` not valid, or `newfd` out of range |
| `EMFILE` | Process fd limit reached |
| `EINTR` | Interrupted (retry on dup2) |
| `EINVAL` | `dup3` invalid flags |

---

## Summary

- `dup`/`dup2`/`dup3` copy fd-table entries to new numbers; the open file
  description (offset, flags) is **shared**.
- `dup2(old, new)` closes `new` first if it was open — the core of shell
  redirection and pipe setup before `exec`.
- `> file` = `open` + `dup2` to 1 + `close` spare; `2>&1` = `dup2(1, 2)`;
  `|` = `pipe` + `dup2` pipe ends to 0/1 in children + close extras.
- Use `O_CLOEXEC` / `F_DUPFD_CLOEXEC` so exec'd children do not inherit sensitive
  fds; plain `dup()` does not set CLOEXEC on the copy.

Next: [2.5 — fcntl(), flags & metadata](05-fcntl-and-metadata.md)
