# 0.5 — File Descriptors: the Core Abstraction

Every `open()`, `socket()`, and `pipe()` returns a small non-negative **integer** — a
file descriptor. That integer is not the file; it is an **index** into a per-process
table that points, indirectly, at kernel objects. Understanding the three-level structure
behind `fd` is prerequisite to everything in Part 2 (file I/O), Part 6 (sockets), and
Part 7 (epoll).

```
   your code:  write(3, buf, n)
                    │
                    ▼
   fd table[3]  ──▶  open file description  ──▶  inode (file/socket/pipe)
   (per-process)     (offset, flags)            (metadata, ops)
```

---

## 0.5.1 What a file descriptor actually is

> **The call ▸**
>
> ```c
> #include <unistd.h>
> int open(const char *pathname, int flags, ...);  /* returns fd ≥ 0, or -1 */
> int close(int fd);
> ```
>
> A **file descriptor** is a non-negative integer indexing the process's **file
> descriptor table**. Each slot points to an **open file description** (struct
> `file` in kernel terms) shared across processes when duplicated.

The integer itself lives only in your process's memory — the kernel maintains the
tables. When you pass `fd=3` to `read()`, the kernel:

1. Bounds-checks `3` against your fd table size.
2. Follows the pointer to the open file description.
3. Uses its current **file offset** and **status flags**.
4. Dispatches to the inode's operations (`->read`, `->write`, …).

**Pitfall ▸** Storing an `fd` in a file, sending it to another machine, or using it
after `close()` is undefined. Fds are process-local handles, not global names (use paths,
socket addresses, or `SCM_RIGHTS` for cross-process sharing — Part 6.4).

---

## 0.5.2 The three levels

![Three levels behind a file descriptor: fd table, open file table, inode](figures/fd-table.svg)

```
   LEVEL 1 — per-process FD TABLE
   ┌────┬──────────────────────────────┐
   │ 0  │ ──▶ stdin  open file desc    │
   │ 1  │ ──▶ stdout open file desc    │
   │ 2  │ ──▶ stderr open file desc    │
   │ 3  │ ──▶ myfile open file desc    │
   │ 4  │ ──▶ (empty)                  │
   └────┴──────────────────────────────┘

   LEVEL 2 — OPEN FILE DESCRIPTION (system-wide, ref-counted)
   ┌─────────────────────────────────┐
   │ file offset: 4096               │
   │ flags: O_RDONLY | O_CLOEXEC     │
   │ mode: FMODE_READ                │
   │ f_op: &ext4_file_operations     │
   │ f_inode: ──▶ ...                │
   └─────────────────────────────────┘

   LEVEL 3 — INODE / VNODE (the "file" itself)
   ┌─────────────────────────────────┐
   │ size, permissions, uid/gid      │
   │ data blocks on disk (or pipe    │
   │ buffer, socket state, etc.)     │
   └─────────────────────────────────┘
```

| Level | Scope | Duplicated by |
|-------|-------|---------------|
| FD table slot | Per process | `fork()` (copies table) |
| Open file description | Shared, ref-counted | `dup()`, `fork()` (same entry) |
| Inode | Global VFS object | `link()`, second `open()` of same path |

Part 2.7 and [02-file-io/07-vfs-and-inodes.md](../02-file-io/07-vfs-and-inodes.md) go
deeper into the VFS layer.

---

## 0.5.3 Standard fds: 0, 1, 2

Every process starts with three open file descriptions:

| fd | Name | Default | `<unistd.h>` constant |
|----|------|---------|------------------------|
| 0 | stdin | terminal or pipe read end | `STDIN_FILENO` |
| 1 | stdout | terminal or pipe write end | `STDOUT_FILENO` |
| 2 | stderr | terminal (unbuffered diagnostics) | `STDERR_FILENO` |

```bash
ls -l /proc/self/fd/
# 0 -> /dev/pts/0
# 1 -> /dev/pts/0
# 2 -> /dev/pts/0
# 3 -> /some/path (after open)
```

Shell redirection (`cmd > out.txt 2>&1`) works by rearranging these table entries
**before** `exec` — Part 2.4. Closing fd 0/1/2 without repointing them causes
surprising behavior (daemon pattern: dup to `/dev/null`).

**Systems ▸** `write(2, ...)` goes to stderr regardless of stdio buffering — one reason
`perror()` and debug logs use fd 2.

---

## 0.5.4 fork, dup, and shared offsets

Behavior differs depending on **how** you got a second fd:

```
   SCENARIO A: dup() or fork()
   ───────────────────────────
   parent fd 3  ──┐
                  ├──▶  same open file description (shared offset!)
   child  fd 3  ──┘

   parent read(3, ...) advances offset
   child  read(3, ...) sees new offset  ✓ shared

   SCENARIO B: two open() calls on same path
   ─────────────────────────────────────────
   fd 3  ──▶  open file desc A  (offset 0)  ──▶  inode
   fd 4  ──▶  open file desc B  (offset 0)  ──▶  same inode

   independent offsets  ✓
```

Part 1.2 covers `fork()`; Part 2.4 covers `dup()` and shell redirection.

---

## 0.5.5 O_CLOEXEC: close on exec

`fork()` + `exec()` is how new programs start (Part 1.3). Without care, **every open fd
leaks into the child program**:

```
   parent has fd 3..1023 open  ──exec──▶  child inherits ALL unless closed
                                          (security bug: leak socket to untrusted code)
```

> **The call ▸**
>
> ```c
> #include <fcntl.h>
> int open(const char *pathname, int flags, ...);
> /* O_CLOEXEC — set close-on-exec atomically at open time (preferred) */
>
> #include <unistd.h>
> int fcntl(int fd, int cmd, ...);
> /* F_SETFD / FD_CLOEXEC — set on existing fd */
> ```

Always use **`O_CLOEXEC`** (or `openat` + `O_CLOEXEC`) on fds that must not survive
`exec`. Since Linux 2.6.23, `open()` does not race with concurrent threads calling
`exec` if you set `O_CLOEXEC` at creation time.

**Pitfall ▸** Forgetting CLOEXEC on a listening socket or database connection handle
before `exec("/bin/sh")` in a compromised app is a classic privilege-escalation path.

---

## 0.5.6 fd limits: RLIMIT_NOFILE

Each process has a soft and hard limit on open fds:

> **The call ▸**
>
> ```c
> #include <sys/resource.h>
> int getrlimit(int resource, struct rlimit *rlim);
> int setrlimit(int resource, struct rlimit *rlim);
> /* resource = RLIMIT_NOFILE */
> ```

```bash
ulimit -n          # soft limit (default often 1024 or 65536)
cat /proc/sys/fs/file-max   # system-wide ceiling
ls /proc/self/fd/ | wc -l   # how many you have open now
```

High-concurrency servers (thousands of connections) must raise `RLIMIT_NOFILE` **and**
ensure the kernel `fs.file-max` and epoll setup (Part 7.2) support the load.

**Errors ▸**

| `errno` | when it happens |
|---------|-------------------|
| `EMFILE` | Process fd table full (per-process limit) |
| `ENFILE` | System-wide open file table exhausted |
| `EBADF` | fd not open (use after close, or invalid number) |

See [examples/resource_limits.c](../examples/resource_limits.c) for a runnable demo.

---

## 0.5.7 "Everything is a file"

The fd abstraction generalizes beyond disk files:

```
   ┌────────────────┬────────────────────────────────────────────┐
   │ Regular file   │ open("/path") → read/write/seek            │
   │ Directory      │ open(".", O_DIRECTORY) — not read like file│
   │ Pipe           │ pipe() → fd[0] read, fd[1] write           │
   │ Socket         │ socket() → bind/connect/send/recv          │
   │ Device         │ open("/dev/sda", ...)                      │
   │ Pseudo-file    │ open("/proc/self/maps") — no disk inode    │
   │ epoll/timer    │ epoll_create1(), timerfd_create() → fd     │
   │ signalfd       │ signalfd() → fd                            │
   └────────────────┴────────────────────────────────────────────┘
```

All share the same **fd → open file description → file operations** pattern. `poll`/
`epoll`/`select` multiplex any of these fds uniformly (Part 6.6). This unification is
why Unix I/O composes: redirect a socket like a file, `sendfile` from file to socket
(Part 7.4).

**Trade-offs ▸** Not everything maps cleanly — directories are not stream-readable;
sockets ignore `lseek`. The `ioctl()` escape hatch (Part 8.3) handles device-specific
operations that do not fit `read`/`write`.

---

## 0.5.8 Example: inspecting the three levels from user space

You cannot see kernel structs directly, but `/proc` exposes the fd table:

```c
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int main(void) {
    const char *path = "/tmp/fd_demo.txt";
    int fd1 = open(path, O_RDWR | O_CREAT | O_TRUNC | O_CLOEXEC, 0644);
    if (fd1 == -1) {
        perror("open fd1");
        return 1;
    }

    int fd2 = dup(fd1);                 /* same open file description */
    if (fd2 == -1) {
        perror("dup");
        close(fd1);
        return 1;
    }

    int fd3 = open(path, O_RDONLY);     /* new open file description, same inode */
    if (fd3 == -1) {
        perror("open fd3");
        close(fd1);
        close(fd2);
        return 1;
    }

    if (write(fd1, "hello", 5) != 5) {
        perror("write");
        goto cleanup;
    }

    char buf[16] = {0};
    /* fd1 and fd2 share offset — both at 5 after the write above */
    ssize_t n2 = read(fd2, buf, 5);
    if (n2 == -1) {
        perror("read fd2");
        goto cleanup;
    }
    printf("fd2 read at shared EOF offset: %zd bytes (expect 0)\n", n2);

    if (lseek(fd2, 0, SEEK_SET) == (off_t)-1) {  /* moves shared offset for fd1 too */
        perror("lseek fd2");
        goto cleanup;
    }
    if (read(fd1, buf, 5) != 5) {
        perror("read fd1 after shared lseek");
        goto cleanup;
    }
    buf[5] = '\0';
    printf("fd1 read after lseek on fd2: '%s'\n", buf);

    lseek(fd3, 0, SEEK_SET);
    if (read(fd3, buf, 5) != 5) {
        perror("read fd3");
        goto cleanup;
    }
    buf[5] = '\0';
    printf("fd3 independent open: '%s'\n", buf);

cleanup:
    close(fd3);
    close(fd2);
    close(fd1);
    return 0;
}
```

Run and compare: `fd2` hits EOF after `fd1`'s write (shared offset); `lseek` on `fd2`
rewinds `fd1` too; `fd3` reads from the start independently.

---

## Summary

- A file descriptor is a per-process index into the fd table, pointing to an open file
  description (offset + flags), which references an inode or kernel object.
- Stdin/stdout/stderr are fds 0, 1, 2 — inherited and rearranged by shells before exec.
- `dup()` and `fork()` share the open file description (shared offset); separate
  `open()` calls get independent descriptions on the same inode.
- Use `O_CLOEXEC` to prevent fd leaks across `exec`.
- `RLIMIT_NOFILE` caps open fds per process; `EMFILE`/`ENFILE` when exhausted.
- Pipes, sockets, `/proc` files, epoll — all use the same fd abstraction ("everything
  is a file").

Next: [Part 1.1 — The process model](../01-processes/01-process-model.md)
