# 2.1 — open() & close()

`open()` is the front door to the kernel's file layer: you pass a pathname and a
set of flags, and the kernel returns a **file descriptor** — a small integer that
indexes your process's open-file table (Part 0.5). Every subsequent `read()`,
`write()`, `lseek()`, or `fcntl()` on that fd goes through the same kernel
*open file description*.

`close()` tears down your process's reference to that description. It sounds
trivial; it is not — `close()` can fail, and closing the wrong fd is a classic
production bug.

---

## 2.1.1 The open family

Three entry points, one kernel path:

```
   open(path, flags, mode)     ← classic; path is relative to CWD
   openat(dirfd, path, flags, mode)  ← path relative to dirfd (or AT_FDCWD = CWD)
   creat(path, mode)             ← shorthand: open(path, O_CREAT|O_WRONLY|O_TRUNC, mode)
```

On x86-64, glibc's `open()` is typically implemented as `openat(AT_FDCWD, ...)`.
`openat()` matters for **directory-relative** opens (avoiding TOCTOU races on
symlinks), for sandboxed code that holds a dir fd, and for `O_TMPFILE` creation.

> **The call ▸**
> ```c
> #include <fcntl.h>
> #include <sys/stat.h>
> #include <unistd.h>
>
> int open(const char *pathname, int flags, ... /* mode_t mode */);
> int openat(int dirfd, const char *pathname, int flags, ... /* mode_t mode */);
> int creat(const char *pathname, mode_t mode);
> ```
> Returns a **new fd** (lowest unused ≥ 0) on success, `-1` on failure.
> `mode` is required only when `O_CREAT` (or `O_TMPFILE`) is set.

> **Under the hood ▸** The kernel walks the VFS: resolve the pathname through
> dentries → inode, checks permissions, allocates a `struct file`, installs an
> entry in the process fd table pointing at it, and returns the index. Creation
> flags may create a new inode on disk. See Part 2.7 for the full VFS picture.

---

## 2.1.2 Flag groups — read them as bitmasks

Flags are OR'd together. Think in **groups**:

```
   ┌─────────────────────────────────────────────────────────────────┐
   │  ACCESS MODE  (mutually exclusive — pick one)                    │
   │    O_RDONLY   read only                                          │
   │    O_WRONLY   write only                                         │
   │    O_RDWR     read and write                                     │
   ├─────────────────────────────────────────────────────────────────┤
   │  CREATION / EXISTENCE                                            │
   │    O_CREAT    create if missing (needs mode arg)                   │
   │    O_EXCL     with O_CREAT: fail if file already exists (atomic) │
   │    O_TRUNC    truncate regular file to length 0 on open-for-write│
   ├─────────────────────────────────────────────────────────────────┤
   │  STATUS / BEHAVIOUR                                              │
   │    O_APPEND   every write goes to end-of-file (atomic per write) │
   │    O_NONBLOCK non-blocking I/O (pipes, sockets, some devices)    │
   │    O_CLOEXEC  set FD_CLOEXEC on the new fd (close on exec)       │
   │    O_DIRECT   bypass page cache for this fd (alignment rules apply)│
   │    O_SYNC     data+metadata synced to storage before write returns │
   └─────────────────────────────────────────────────────────────────┘
```

**Access mode** is stored in the open file description and queried later with
`fcntl(F_GETFL) & O_ACCMODE`. You cannot flip `O_RDONLY` ↔ `O_RDWR` after open —
reopen the file.

**O_CREAT | O_EXCL** is the standard pattern for **atomic create**: either you
get a new empty file or `EEXIST`. No race between "does it exist?" and "create
it." Lock files, PID files, and temp-file schemes use this.

**O_TRUNC** only affects **regular files**. Opening a directory or device with
`O_TRUNC` fails with `EISDIR` or `EINVAL`.

**Trade-offs ▸** `O_CLOEXEC` on open (Linux 2.6.23+) beats remembering to
`fcntl(F_SETFD, FD_CLOEXEC)` in every code path — especially before `exec` in
multi-threaded programs where another thread could fork/exec between open and
fcntl.

---

## 2.1.3 mode and umask

When `O_CREAT` is set, you pass `mode_t mode` — the **desired** permission bits
(owner/group/other, e.g. `0644`). The kernel applies the process **umask** before
writing the inode:

```
   inode mode  =  mode  &  ~umask

   example:  mode = 0666, umask = 0022  →  file created as 0644
```

```
   process umask (e.g. 0022)
        │
        │  masks out write for group/other at create time
        ▼
   open("f", O_CREAT|O_WRONLY, 0666)  ──▶  inode permissions 0644
```

`umask()` is a process attribute, inherited across `fork()`, not per-fd. Shells
often set `umask 022` in profile scripts.

> **Pitfall ▸** Passing `0644` to `open()` does **not** mean "this fd is
> read-only." Access mode comes from `O_RDONLY`/`O_WRONLY`/`O_RDWR`, not from
> `mode`. `mode` only affects the **new inode's** permission bits.

---

## 2.1.4 What close() actually does

```
   your process fd table                kernel open file descriptions
   ┌─────┬──────────────┐              ┌─────────────────────────────┐
   │  3  │ ─────────────┼─────────────▶│ struct file (offset, flags) │
   │  4  │ ─────────────┼───┐          │  refcnt = 2                 │
   └─────┴──────────────┘   │          └─────────────────────────────┘
                            └──────────▶ (same struct file as fd 3)

   close(3):  drop fd 3's reference; refcnt 2 → 1; fd 3 slot freed
   close(4):  refcnt 1 → 0; kernel releases struct file, may flush buffers
```

`close(fd)`:

1. Removes `fd` from **your** fd table (the integer becomes invalid immediately).
2. Decrements the reference count on the shared open file description.
3. When the count hits zero, the kernel flushes buffered data, releases locks
   held on that description, and may invoke the filesystem's `release` method.

> **The call ▸**
> ```c
> #include <unistd.h>
> int close(int fd);
> ```
> Returns `0` on success, `-1` on failure. **On success, `fd` is gone** — retrying
> `close(fd)` is undefined (and usually `EBADF`).

**Errors ▸**

| errno | when it happens |
|-------|-----------------|
| `EBADF` | `fd` is not an open fd |
| `EINTR` | A signal arrived before the kernel finished; **fd state is unspecified** |
| `EIO` | I/O error during flush (e.g. NFS server gone, disk error) |

> **Pitfall ▸** After `close()` returns `-1` with `EINTR`, POSIX leaves the fd
> **in an indeterminate state** — it may or may not be closed. Production code
> either retries `close()` in a loop ignoring further `EINTR`, or leaks the fd
> deliberately rather than double-close. Never assume "EINTR means still open."

> **Pitfall ▸** **Closing the wrong fd** — often from an off-by-one or reusing a
> variable — closes stdin (0), stdout (1), or a socket the event loop still polls.
> The kernel **reuses** the lowest free fd number; if you close fd 1 and later
> `open()` a file, that file may become stdout. Always close the **exact** fd
> returned by `open()`, and consider `O_CLOEXEC` so exec'd children don't inherit
> sensitive fds.

---

## 2.1.5 A complete open/close example

```c
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int close_retry(int fd) {
    while (close(fd) == -1) {
        if (errno == EINTR)
            continue;
        return -1;
    }
    return 0;
}

int main(int argc, char *argv[]) {
    if (argc != 2) {
        fprintf(stderr, "usage: %s <path>\n", argv[0]);
        return 1;
    }

    /* Atomic create: fail if the path already exists. */
    int fd = open(argv[1], O_CREAT | O_EXCL | O_WRONLY, 0644);
    if (fd == -1) {
        if (errno == EEXIST)
            fprintf(stderr, "%s: already exists\n", argv[1]);
        else
            perror("open");
        return 1;
    }

    const char msg[] = "created atomically\n";
    ssize_t n = write(fd, msg, sizeof msg - 1);
    if (n == -1) {
        perror("write");
        close_retry(fd);
        return 1;
    }
    if (n != (ssize_t)(sizeof msg - 1)) {
        fprintf(stderr, "short write\n");
        close_retry(fd);
        return 1;
    }

    if (close_retry(fd) == -1) {
        perror("close");
        return 1;
    }
    return 0;
}
```

Trace the syscalls:

```bash
gcc -Wall -Wextra -o atomic_create atomic_create.c
strace ./atomic_create /tmp/test.lock
# openat(..., O_CREAT|O_EXCL|O_WRONLY, 0644) = 3
# write(3, "created atomically\n", 19)    = 19
# close(3)                               = 0
```

**Errors ▸** (open family)

| errno | when it happens |
|-------|-----------------|
| `EACCES` | Permission denied on path or search in a directory component |
| `EEXIST` | `O_CREAT|O_EXCL` and file already exists |
| `EISDIR` | Path is a directory and write/trunc requested |
| `EMFILE` | Process fd table full (`RLIMIT_NOFILE`) |
| `ENFILE` | System-wide open-file limit |
| `ENOENT` | Component of path does not exist (and no `O_CREAT`) |
| `ENAMETOOLONG` | Pathname too long |
| `ENOTDIR` | A component is not a directory (e.g. trailing slash on file) |
| `EROFS` | Filesystem mounted read-only |
| `ELOOP` | Too many symlinks while resolving path |
| `ETXTBSY` | Writing an executable that is currently executing |

---

## Summary

- `open()` / `openat()` / `creat()` allocate an fd pointing at a kernel open
  file description; flags control access mode, creation, truncation, and
  runtime behaviour (`O_APPEND`, `O_NONBLOCK`, `O_CLOEXEC`, `O_DIRECT`, `O_SYNC`).
- With `O_CREAT`, `mode` sets desired inode permissions after umask — it does
  not set the fd's read/write access mode.
- `close()` drops your fd-table entry and decrements the shared description's
  refcnt; the last close may flush and release kernel resources.
- `close()` can fail (`EIO`, `EINTR`); after `EINTR` the fd state is ambiguous.
- Closing the wrong fd (especially 0–2) causes subtle bugs because the kernel
  reuses the lowest free fd number.

Next: [2.2 — read() & write()](02-read-write.md)
