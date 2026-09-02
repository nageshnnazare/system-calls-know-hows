# 2.5 — fcntl(), Flags & Metadata

`fcntl()` is the Swiss-army syscall for fd manipulation: query and tweak per-fd and
per-open-description flags, duplicate fds, and manage **advisory** record locks.
Alongside it, `stat()` family calls read **inode metadata** without opening the
file, and `chmod`/`chown`/`access()` change or test permissions.

---

## 2.5.1 fcntl() — two flag namespaces

Confusing until you see the split:

```
   ┌────────────────────────────┬──────────────────────────────────────┐
   │  FD flags (per fd number)  │  file status flags (open description)│
   │  F_GETFD / F_SETFD         │  F_GETFL / F_SETFL                   │
   │  FD_CLOEXEC only           │  O_NONBLOCK, O_APPEND, O_ASYNC, ...  │
   │  dup() does not copy CLOEXEC│ shared by dup'd fds                 │
   └────────────────────────────┴──────────────────────────────────────┘
```

> **The call ▸**
> ```c
> #include <fcntl.h>
> int fcntl(int fd, int cmd, ... /* arg */ );
> ```

Common commands:

| cmd | arg | effect |
|-----|-----|--------|
| `F_GETFL` | — | Return status flags + access mode |
| `F_SETFL` | flags | Set **some** status flags (OR masked subset) |
| `F_GETFD` | — | Return fd flags (`FD_CLOEXEC`) |
| `F_SETFD` | flags | Set fd flags |
| `F_DUPFD` | minfd | Dup to lowest fd ≥ minfd |
| `F_DUPFD_CLOEXEC` | minfd | Same + CLOEXEC |
| `F_SETLK` | struct flock * | Set/clear advisory lock (non-blocking) |
| `F_SETLKW` | struct flock * | Same, wait until available |

> **Under the hood ▸** `F_SETFL` updates `struct file->f_flags`. Only certain
> bits are mutable after open (`O_APPEND`, `O_NONBLOCK`, `O_ASYNC`, `O_DIRECT`
> on some kernels). Access mode (`O_RDONLY` etc.) is fixed at open time.

Flip non-blocking at runtime:

```c
int flags = fcntl(fd, F_GETFL);
if (flags == -1) { perror("F_GETFL"); return -1; }
if (fcntl(fd, F_SETFL, flags | O_NONBLOCK) == -1) {
    perror("F_SETFL");
    return -1;
}
```

Part 7.1 covers non-blocking I/O patterns.

---

## 2.5.2 Advisory record locks (F_SETLK / F_SETLKW)

POSIX byte-range locks — **cooperative** (processes must use fcntl to participate):

```c
struct flock lock = {
    .l_type   = F_WRLCK,    /* F_RDLCK, F_WRLCK, F_UNLCK */
    .l_whence = SEEK_SET,
    .l_start  = 0,
    .l_len    = 0,          /* 0 = lock to EOF */
    .l_pid    = 0,          /* kernel fills */
};
fcntl(fd, F_SETLKW, &lock);   /* block until lock acquired */
```

```
   process A: F_WRLCK bytes 0-999   ✓
   process B: F_WRLCK bytes 0-999   ✗ EAGAIN (F_SETLK) or blocks (F_SETLKW)
   process C: ignores fcntl         ✓ writes anyway — advisory only
```

**Trade-offs ▸** Advisory locks are useless against uncooperative writers. For
mandatory enforcement you need different tools (file permissions, exclusive
`O_CREAT|O_EXCL`, or database-level locking). Locks are associated with the
**process** — they release on **any** close of that fd in the process.

---

## 2.5.3 stat family — metadata without reading bytes

> **The call ▸**
> ```c
> #include <sys/stat.h>
>
> int stat(const char *path, struct stat *buf);
> int lstat(const char *path, struct stat *buf);   /* do not follow symlink */
> int fstat(int fd, struct stat *buf);
> int statx(int dirfd, const char *path, int flags, unsigned int mask,
>           struct statx *buf);   /* Linux 4.11+, richer timestamps */
> ```

Key `struct stat` fields:

```
   st_mode   file type + permission bits (S_IFREG, S_IRUSR, ...)
   st_size   logical size in bytes
   st_ino    inode number (unique on this filesystem)
   st_nlink  hard link count
   st_dev    device ID of filesystem
   st_uid/st_gid  owner
   st_atime/st_mtime/st_ctime  access, content mod, metadata change (legacy)
   st_blocks/st_blksize        space accounting (512-byte units for st_blocks)
```

Type tests — always mask with macros, never raw octal guesses:

```c
if (S_ISREG(sb.st_mode))  /* regular file */
if (S_ISDIR(sb.st_mode))  /* directory */
if (S_ISLNK(sb.st_mode))  /* symlink (from lstat) */
if (S_ISCHR(sb.st_mode))  /* char device */
if (S_ISBLK(sb.st_mode))  /* block device */
if (S_ISFIFO(sb.st_mode)) /* FIFO */
if (S_ISSOCK(sb.st_mode)) /* socket (not always visible via stat) */
```

> **Under the hood ▸** Path-based `stat` walks dentries; `fstat` uses the fd's
> already-resolved inode. `lstat` stops at symlinks — essential for tools that
> must not follow untrusted links.

---

## 2.5.4 access(), chmod(), chown()

> **The call ▸**
> ```c
> #include <unistd.h>
> int access(const char *path, int mode);  /* F_OK, R_OK, W_OK, X_OK */
> #include <sys/stat.h>
> int chmod(const char *path, mode_t mode);
> int fchmod(int fd, mode_t mode);
> int chown(const char *path, uid_t owner, gid_t group);
> int fchown(int fd, uid_t owner, gid_t group);
> int lchown(const char *path, uid_t owner, gid_t group);  /* no symlink follow */
> ```

`access()` checks permissions using the **real** uid/gid (not effective) — use
before setuid programs drop privileges.

`chmod` changes permission bits in `st_mode`; `chown` changes owner/group (and
on Linux historically could affect setuid behaviour — see `fchownat` man page).

**Pitfall ▸** `stat().st_mode & 0777` shows mode bits; file **type** lives in
the high bits (`S_IFMT`). Use `S_IS*` macros for type, `(sb.st_mode & 0777)` for
rwx permissions.

---

## 2.5.5 Example: inspect and toggle flags

```c
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static void print_stat(const char *path) {
    struct stat sb;
    if (stat(path, &sb) == -1) {
        perror("stat");
        return;
    }
    printf("%s: inode=%lu size=%lld mode=%o nlink=%lu\n",
           path, (unsigned long)sb.st_ino, (long long)sb.st_size,
           sb.st_mode & 0777, (unsigned long)sb.st_nlink);
    if (S_ISREG(sb.st_mode)) printf("  type: regular file\n");
    else if (S_ISDIR(sb.st_mode)) printf("  type: directory\n");
    else if (S_ISLNK(sb.st_mode)) printf("  type: symlink\n");
}

int main(int argc, char *argv[]) {
    if (argc != 2) {
        fprintf(stderr, "usage: %s path\n", argv[0]);
        return 1;
    }

    print_stat(argv[1]);

    if (access(argv[1], R_OK) == 0)
        printf("readable (real uid)\n");

    int fd = open(argv[1], O_RDONLY | O_NONBLOCK);
    if (fd == -1) { perror("open"); return 1; }

    int fl = fcntl(fd, F_GETFL);
    if (fl == -1) { perror("F_GETFL"); close(fd); return 1; }
    printf("O_NONBLOCK %s\n", (fl & O_NONBLOCK) ? "set" : "clear");

    int fdfl = fcntl(fd, F_GETFD);
    if (fdfl == -1) { perror("F_GETFD"); close(fd); return 1; }
    if (fcntl(fd, F_SETFD, fdfl | FD_CLOEXEC) == -1) {
        perror("F_SETFD");
        close(fd);
        return 1;
    }
    printf("FD_CLOEXEC set on fd %d\n", fd);

    if (close(fd) == -1) {
        perror("close");
        return 1;
    }
    return 0;
}
```

**Errors ▸** (fcntl / stat)

| errno | when it happens |
|-------|-----------------|
| `EBADF` | Invalid fd |
| `EACCES` | Lock denied or search permission on path |
| `EAGAIN`/`EACCES` | `F_SETLK` cannot acquire lock |
| `EDEADLK` | Lock conflict detected as deadlock (F_SETLKW) |
| `ENOENT` | Path component missing |
| `ENOTDIR` | Component not a directory |
| `ELOOP` | Too many symlinks |
| `EOVERFLOW` | File size cannot be represented in fields |

---

## Summary

- `fcntl()` splits **fd flags** (`FD_CLOEXEC` via `F_GETFD`/`F_SETFD`) from
  **file status flags** (`O_NONBLOCK`, `O_APPEND` via `F_GETFL`/`F_SETFL`).
- `F_DUPFD` / `F_DUPFD_CLOEXEC` duplicate fds; record locks use `F_SETLK` /
  `F_SETLKW` with `struct flock` (advisory, cooperative).
- `stat`/`lstat`/`fstat`/`statx` fill `struct stat` — `st_mode`, `st_size`,
  `st_ino`, timestamps; use `S_ISREG`/`S_ISDIR`/… macros for type.
- `access()` tests real uid permissions; `chmod`/`chown` (and `fchmod`/`fchown`)
  change mode and ownership.

Next: [2.6 — Links & directories](06-links-and-directories.md)
