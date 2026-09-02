# 4.1 — Pipes & FIFOs

A **pipe** is a unidirectional byte stream connecting two file descriptors in the
same process or across a `fork()` boundary. The shell's `cmd1 | cmd2` is built from
`pipe()` + `dup2()` + `execve()` (Parts 1.3, 2.4). **FIFOs** (named pipes) are the
same kernel object with a filesystem path — unrelated processes open them like files.

---

## 4.1.1 pipe() and pipe2()

> **The call ▸**
> ```c
> #include <unistd.h>
>
> int pipe(int pipefd[2]);
> int pipe2(int pipefd[2], int flags);
> ```
> On success: **0**. `pipefd[0]` = read end, `pipefd[1]` = write end.
> **`pipe2` flags:** `O_NONBLOCK`, `O_CLOEXEC` (Part 2.1 — safe across `exec`).

![Pipe kernel ring buffer connecting two file descriptors](figures/pipe.svg)

```
   writer process                kernel                  reader process
   write(pipefd[1], buf, n)  ──▶ ┌──────────────┐  ──▶ read(pipefd[0], ...)
                                 │ ring buffer  │
                                 │  (pipe inode)│
                                 └──────────────┘
```

> **Under the hood ▸** A pipe is a **pipe inode** with a kernel buffer (capacity
> ~64 KiB on modern Linux, query with `fcntl(F_GETPIPE_SZ)`). Data is copied from
> writer's user buffer → kernel buffer → reader's user buffer. No disk involved.

**Errors ▸**

| `errno` | When |
|---------|------|
| `EMFILE` | Process fd limit reached |
| `ENFILE` | System-wide open file limit |
| `EINVAL` | Invalid `pipe2` flags |

---

## 4.1.2 Blocking, flow control, and EOF

```
   buffer empty, reader blocks (unless O_NONBLOCK → EAGAIN)
   buffer full, writer blocks (unless O_NONBLOCK → EAGAIN)
```

When **all write ends are closed** and the buffer is drained:

- `read()` returns **0** — EOF (Part 2.2).
- Further `write()` → **`SIGPIPE`** (default: terminate) or `-1` with `EPIPE` if
  ignored/handled.

**Pitfall ▸** Forgetting to `close()` unused pipe ends in `fork()` children causes
EOF never to arrive — readers hang forever because a writer still exists.

Rule after `fork()`:

| Process | Close | Keep |
|---------|-------|------|
| Reader child | write end | read end |
| Writer parent | read end | write end |

---

## 4.1.3 PIPE_BUF and atomic writes

POSIX guarantees writes of **≤ `PIPE_BUF`** bytes (often **4096** on Linux) are
**atomic** if they fit in the buffer — they won't interleave with other writers'
atomic writes on the same pipe.

```c
#include <unistd.h>
printf("PIPE_BUF = %ld\n", (long)PIPE_BUF);
```

Writes **> `PIPE_BUF`** may interleave with other writers. For record boundaries,
use length prefixes, `sendmsg` with control data, or message queues (Part 4.3–4.4).

---

## 4.1.4 SIGPIPE

```
   reader gone, write end still open
        │
        write() ──▶ kernel sends SIGPIPE to writer thread
                      default: terminate process
                      ignored: write returns -1, errno=EPIPE
```

Daemons often ignore `SIGPIPE` globally:

```c
signal(SIGPIPE, SIG_IGN);   /* legacy; prefer sigaction in Part 4.2 */
```

Or use `MSG_NOSIGNAL` on sockets (Part 6). For pipes, handle `EPIPE` explicitly.

---

## 4.1.5 Named FIFOs: mkfifo()

> **The call ▸**
> ```c
> #include <sys/stat.h>
>
> int mkfifo(const char *pathname, mode_t mode);
> ```
> Creates a filesystem node; `open(path, O_RDONLY|O_WRONLY)` blocks until a peer
> opens the other end (unless `O_NONBLOCK`).

```
   producer                          consumer
   fd = open("my.fifo", O_WRONLY)    fd = open("my.fifo", O_RDONLY)
        │                                  │
        └──────── same pipe inode ─────────┘
```

Unlike anonymous pipes, unrelated processes discover the path via the filesystem
(Part 2.6). Cleanup: `unlink("my.fifo")` when done.

**Trade-offs ▸** FIFOs give shell-friendly names but no random access, no fd passing
(by themselves), and the same byte-stream semantics as pipes.

---

## 4.1.6 Shell pipelines via dup2()

```
   shell:  ls | wc -l

   pipe(p)
   pid1 = fork()
   if child1:
       close(p[0]); dup2(p[1], STDOUT_FILENO); close(p[1])
       execve("ls", ...)
   pid2 = fork()
   if child2:
       close(p[1]); dup2(p[0], STDIN_FILENO); close(p[0])
       execve("wc", ...)
   parent: close both ends; waitpid × 2
```

See Part 2.4 for `dup2()` and the fd table. Each child inherits the pipe but must
close the wrong end before `exec` so EOF propagates correctly.

---

## 4.1.7 Parent-child pipe example

```c
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

static ssize_t write_all(int fd, const void *buf, size_t count) {
    const char *p = buf;
    while (count > 0) {
        ssize_t n = write(fd, p, count);
        if (n == -1) {
            if (errno == EINTR)
                continue;
            return -1;
        }
        p += n;
        count -= (size_t)n;
    }
    return 0;
}

int main(void) {
    int pfd[2];
    if (pipe(pfd) == -1) {
        perror("pipe");
        return 1;
    }

    pid_t pid = fork();
    if (pid == -1) {
        perror("fork");
        close(pfd[0]);
        close(pfd[1]);
        return 1;
    }

    if (pid == 0) {
        /* child: reader */
        if (close(pfd[1]) == -1) {
            perror("close write end");
            _exit(1);
        }

        char buf[256];
        ssize_t n = read(pfd[0], buf, sizeof buf - 1);
        if (n == -1) {
            perror("read");
            close(pfd[0]);
            _exit(1);
        }
        buf[n > 0 ? (size_t)n : 0] = '\0';
        printf("[child] received: %s (%zd bytes)\n", buf, n);

        if (close(pfd[0]) == -1) {
            perror("close read end");
            _exit(1);
        }
        _exit(0);
    }

    /* parent: writer */
    if (close(pfd[0]) == -1) {
        perror("close read end");
        close(pfd[1]);
        return 1;
    }

    const char msg[] = "hello through the pipe";
    if (write_all(pfd[1], msg, strlen(msg)) == -1) {
        perror("write");
        close(pfd[1]);
        return 1;
    }

    if (close(pfd[1]) == -1) {
        perror("close write end");
        return 1;
    }

    int status;
    if (waitpid(pid, &status, 0) == -1) {
        perror("waitpid");
        return 1;
    }
    if (!WIFEXITED(status) || WEXITSTATUS(status) != 0) {
        fprintf(stderr, "child failed\n");
        return 1;
    }
    return 0;
}
```

Trace with `strace -f -e trace=pipe,read,write,fork,close ./pipe_demo`.

---

## Summary

- **`pipe()`/`pipe2()`** create a kernel ring buffer with read fd `0` and write fd
  `1`; data flows one direction, copied through kernel memory.
- **Blocking** applies when buffer full/empty; closing all writers yields **EOF**
  (`read` → 0); writes to no reader → **SIGPIPE** / **EPIPE**.
- Writes ≤ **`PIPE_BUF`** bytes are atomic on a given pipe.
- **`mkfifo()`** exposes the same mechanism as a filesystem path for unrelated
  processes.
- Shell pipelines = **`pipe` + `fork` + `dup2` + `execve`**; always close unused
  ends.

Next: [4.2 — Signals](02-signals.md)
