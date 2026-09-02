# 2.3 — Seeking & File Offsets

Every open file description carries a **current file offset** — a byte position
where the next `read()` or `write()` (without `O_APPEND`) will start. `lseek()`
moves that offset. It does not touch the disk directly; it updates kernel state
that subsequent I/O consults.

Understanding where the offset lives — and who shares it — is essential for
threads, `dup()`, and `fork()` (Part 0.5, Part 2.4).

---

## 2.3.1 Where the offset lives

```
   process A                          process B (after fork)
   fd 3 ──┐                           fd 3 ──┐
   fd 5 ──┼──▶ open file description       ├──▶ same description
          │    offset = 4096               │    offset = 4096  (shared!)
          └──▶ inode / pipe / socket       └──▶ ...
```

The offset is a field in the **open file description** (`struct file` in the
kernel), **not** in the fd table slot. Two fds from `dup()` share one offset.
After `fork()`, parent and child share offsets on inherited fds until either
process `close()`s its copy or opens with `O_CLOEXEC`-cleared inheritance.

**Pitfall ▸** Thread A calls `lseek()` while thread B `read()`s the same fd —
both use the same offset with no locking. Use `pread`/`pwrite` (Part 2.2) or a
mutex around seek+read/write pairs.

---

## 2.3.2 lseek()

> **The call ▸**
> ```c
> #include <unistd.h>
>
> off_t lseek(int fd, off_t offset, int whence);
> ```
> Returns the **new** offset from the start of the file on success, `(off_t)-1` on
> failure.

**whence** values:

```
   SEEK_SET   offset is absolute from byte 0
   SEEK_CUR   offset is relative to current position
   SEEK_END   offset is relative to EOF (may be negative)

   example: file size = 1000
      lseek(fd, 0, SEEK_END)   → returns 1000
      lseek(fd, -10, SEEK_END) → returns 990
      lseek(fd, 0, SEEK_SET)   → returns 0  (rewind)
```

> **Under the hood ▸** For regular files, `lseek` updates `struct file->f_pos`.
> For pipes, sockets, and some devices, seeking is meaningless — `lseek` returns
> `-1` with `ESPIPE` ("illegal seek").

**Trade-offs ▸** `lseek(fd, 0, SEEK_CUR)` is a common trick to query the current
offset without moving it (returns current position). Linux also provides
`lseek64()` for explicit 64-bit offsets on LFS builds.

---

## 2.3.3 Sparse files and holes

If you `lseek()` far past EOF and `write()` one byte, the filesystem creates a
**sparse file**: logical size is huge, but disk blocks are allocated only for
written ranges.

```
   logical file:  [====data====][........hole........][=data=]
   disk blocks:   [====data====]                      [=data=]
                              ▲
                         no blocks allocated (hole)
```

Reading a hole returns **zero bytes** (not stale disk data). `du` and `ls -s`
may show much less space than `ls -l` reports as size.

Linux extensions for discovering holes (regular files, some fs):

> **The call ▸**
> ```c
> /* SEEK_DATA  — next byte at or after offset that has data
>    SEEK_HOLE  — next hole at or after offset */
> off_t off = lseek(fd, start, SEEK_HOLE);
> ```

Useful for backup tools and sendfile-style copy that can skip holes.

---

## 2.3.4 off_t and large files

`off_t` width depends on feature macros:

```
   default 32-bit off_t     max file ~2 GiB  (historical pain)
   _FILE_OFFSET_BITS=64     off_t is 64-bit; open becomes open64 etc.
   O_LARGEFILE              legacy flag on 32-bit (mostly obsolete on 64-bit)
```

On modern x86-64 Linux, `off_t` is 64-bit by default. On embedded 32-bit ARM,
compile with `-D_FILE_OFFSET_BITS=64` for large-file support.

**Systems ▸** If `lseek`/`read`/`write` fail with `EOVERFLOW` on a 32-bit system,
you are hitting the 2 GiB wall — rebuild with 64-bit offsets.

---

## 2.3.5 ftruncate() — set size without I/O

> **The call ▸**
> ```c
> #include <unistd.h>
> int ftruncate(int fd, off_t length);
> ```
> Sets the **regular file's** size to `length`. Extending fills with zero bytes;
> truncating drops data beyond `length` (and may create a hole if offset was
> past old EOF).

Requires write access on the fd. Does not change your current file offset unless
it pointed past the new size (implementation: offset may be clamped).

```
   ftruncate(fd, 0)   equivalent to opening with O_TRUNC — empty file
   ftruncate(fd, n)   after writing a header, reserve space for payload
```

Pair with `posix_fallocate()` (library) or `fallocate()` (syscall) when you need
to **preallocate** disk blocks, not just logical size.

---

## 2.3.6 Example: patch bytes in the middle of a file

```c
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char *argv[]) {
    if (argc != 4) {
        fprintf(stderr, "usage: %s file offset text\n", argv[0]);
        return 1;
    }

    off_t off = (off_t)atoll(argv[2]);
    const char *text = argv[3];

    int fd = open(argv[1], O_RDWR);
    if (fd == -1) { perror("open"); return 1; }

    if (lseek(fd, off, SEEK_SET) == (off_t)-1) {
        perror("lseek");
        close(fd);
        return 1;
    }

    ssize_t len = (ssize_t)strlen(text);
    ssize_t n = write(fd, text, (size_t)len);
    if (n == -1) {
        perror("write");
        close(fd);
        return 1;
    }
    if (n != len) {
        fprintf(stderr, "short write\n");
        close(fd);
        return 1;
    }

    /* Query size */
    off_t end = lseek(fd, 0, SEEK_END);
    if (end == (off_t)-1) {
        perror("lseek SEEK_END");
        close(fd);
        return 1;
    }
    printf("file size now: %lld\n", (long long)end);

    if (close(fd) == -1) {
        perror("close");
        return 1;
    }
    return 0;
}
```

Same program using **no shared-offset mutation** for the write (thread-safe style):

```c
ssize_t n = pwrite(fd, text, (size_t)len, off);
```

**Errors ▸** (lseek / ftruncate)

| errno | when it happens |
|-------|-----------------|
| `EBADF` | fd not open appropriately (e.g. seek on pipe) |
| `ESPIPE` | fd is pipe, socket, or non-seekable |
| `EINVAL` | Invalid whence, or resulting offset negative / too large |
| `EOVERFLOW` | Result does not fit in `off_t` (32-bit LFS issues) |
| `EINTR` | Interrupted (some implementations) |
| `EFBIG` | `ftruncate` length exceeds maximum file size |
| `EACCES`/`EPERM` | No write permission for truncate |

---

## Summary

- The file offset lives in the **open file description**, shared by `dup()`'d fds
  and across `fork()` for inherited fds — not per-fd.
- `lseek(fd, offset, whence)` with `SEEK_SET` / `SEEK_CUR` / `SEEK_END` sets
  that offset; pipes and sockets return `ESPIPE`.
- Sparse files have holes (reads as zero); `SEEK_HOLE` / `SEEK_DATA` locate them.
- Use 64-bit `off_t` (`_FILE_OFFSET_BITS=64`) for large files on 32-bit platforms.
- `ftruncate()` sets logical file size without read/write I/O.

Next: [2.4 — dup() & I/O redirection](04-dup-and-redirection.md)
