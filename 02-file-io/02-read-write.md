# 2.2 — read() & write()

Once you have an fd from `open()` (Part 2.1), `read()` and `write()` are how
bytes move between your address space and whatever object sits behind the fd —
regular file, pipe, socket, device, or `/proc` entry. They look simple. The
mechanics — short counts, partial writes, shared offsets — cause a disproportionate
share of real bugs.

---

## 2.2.1 The basic contract

```
   user buffer                         kernel
   ┌──────────────┐                   ┌─────────────────┐
   │ buf[0..n-1]  │  read(fd,buf,n)   │ page cache /    │
   │              │ ◀─────────────────│ pipe buffer /   │
   │              │  write(fd,buf,n)  │ socket skbuff   │
   │              │ ─────────────────▶│ ...             │
   └──────────────┘                   └─────────────────┘
```

> **The call ▸**
> ```c
> #include <unistd.h>
>
> ssize_t read(int fd, void *buf, size_t count);
> ssize_t write(int fd, const void *buf, size_t count);
> ```
> On success: number of bytes transferred (≥ 0). **`0` from `read()` = EOF** (no
> bytes available now, and for regular files/pipes often means no more data).
> On failure: `-1`, `errno` set.

The fd's **current file offset** advances by the returned count (except for
`O_APPEND` writes and `pread`/`pwrite` — see below). That offset lives in the
**open file description**, shared by all fds dup'd from the same open (Part 2.4).

![Open file table: fd → open file description → inode/VFS](figures/open-file-table.svg)

---

## 2.2.2 Short reads and short writes

A successful `read()` or `write()` may transfer **fewer than `count` bytes**. This
is normal, not an error.

```
   you ask for 4096 bytes
        │
        ▼
   read() returns 512   ← still success; you must loop if you need all 4096
```

**Why short reads happen:**

- **Regular files:** Less data remaining before EOF.
- **Pipes/sockets/TCP:** Kernel buffer has only partial data available now.
- **Signals:** `read()` may return `-1` with `EINTR` after partial transfer on
  some systems; always loop.
- **Line discipline / terminals:** Byte-at-a-time behaviour is common.

**Why short writes happen:**

- **Pipes/sockets:** Receiver not reading fast enough; kernel pipe/socket buffer
  full — `write()` returns how much fit (or `-1` with `EAGAIN` if non-blocking).
- **Disk/files:** Less common but possible; **never assume** `write(n)` wrote `n`.

> **Pitfall ▸** Checking only `write(...) == -1` and ignoring `0 < n < count` is
> a classic bug. For pipes and sockets, partial writes are routine.

**Trade-offs ▸** Buffered stdio (`fread`/`fwrite`) hides short I/O inside libc.
Raw syscalls give control and predictability at the cost of writing loops yourself.

---

## 2.2.3 The mandatory loops

### Read until EOF (streaming)

For unknown-length input, loop until `read()` returns **0**:

```c
ssize_t n;
while ((n = read(fd, buf, sizeof buf)) > 0) {
    /* process buf[0..n-1] */
}
if (n == -1) {
    perror("read");
    /* error */
}
```

### Read exactly N bytes

```c
ssize_t read_full(int fd, void *buf, size_t count) {
    char *p = buf;
    while (count > 0) {
        ssize_t n = read(fd, p, count);
        if (n == -1) {
            if (errno == EINTR)
                continue;
            return -1;
        }
        if (n == 0)              /* EOF before count satisfied */
            return -1;           /* or set errno = EIO / custom */
        p     += n;
        count -= (size_t)n;
    }
    return 0;
}
```

### Write all bytes — `write_all()`

```c
#include <errno.h>
#include <unistd.h>

ssize_t write_all(int fd, const void *buf, size_t count) {
    const char *p = buf;
    while (count > 0) {
        ssize_t n = write(fd, p, count);
        if (n == -1) {
            if (errno == EINTR)
                continue;
            return -1;
        }
        if (n == 0) {            /* should not happen on regular files */
            errno = EIO;
            return -1;
        }
        p     += n;
        count -= (size_t)n;
    }
    return 0;
}
```

Use `write_all()` anywhere a partial write would corrupt a protocol or file
format — length-prefixed messages, HTTP headers, structured logs.

---

## 2.2.4 pread() and pwrite() — I/O at an offset

`lseek()` + `read()`/`write()` is two syscalls and **not atomic** if another
thread shares the same open file description. `pread()`/`pwrite()` combine offset
and I/O in **one** syscall without changing the shared offset:

> **The call ▸**
> ```c
> #include <unistd.h>
>
> ssize_t pread(int fd, void *buf, size_t count, off_t offset);
> ssize_t pwrite(int fd, const void *buf, size_t count, off_t offset);
> ```
> `offset` is absolute (from file start). The fd's stored offset is **unchanged**.

**Systems ▸** Databases and index files use `pread`/`pwrite` from thread pools
precisely because the offset is per-call, not per-fd.

---

## 2.2.5 readv() and writev() — scatter-gather

One syscall, multiple buffers — fewer boundary crossings, natural for headers +
payload:

> **The call ▸**
> ```c
> #include <sys/uio.h>
>
> ssize_t readv(int fd, const struct iovec *iov, int iovcnt);
> ssize_t writev(int fd, const struct iovec *iov, int iovcnt);
>
> struct iovec {
>     void  *iov_base;
>     size_t iov_len;
> };
> ```

```
   writev(fd, iov, 2)

   iov[0]: "HTTP/1.1 200\r\n"  ──┐
   iov[1]: body bytes           ──┼──▶ single syscall, possibly one TCP segment
                                  ┘
```

Still subject to **short writes** — advance iov pointers and retry on partial counts.

---

## 2.2.6 O_APPEND atomicity

When the open file description has `O_APPEND`, **every** `write()` (not `pwrite`
to an explicit offset) atomically:

1. Sets the file offset to the current end-of-file.
2. Writes data at that position.

```
   thread A: write("aaa")  ──┐
   thread B: write("bbb")  ──┼──▶ kernel serializes; no interleaved garbage
                             │    at the byte level within each write() call
                             └──▶ final file: ...aaabbb (order depends on scheduling)
```

Only each individual `write()` is atomic with respect to the offset bump.
**Pitfall ▸** `pwrite()` ignores `O_APPEND` — use plain `write()` for log-style append.

---

## 2.2.7 Example: copy with correct loops

```c
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
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
        p     += n;
        count -= (size_t)n;
    }
    return 0;
}

int main(int argc, char *argv[]) {
    if (argc != 3) {
        fprintf(stderr, "usage: %s src dst\n", argv[0]);
        return 1;
    }

    int in = open(argv[1], O_RDONLY);
    if (in == -1) { perror("open src"); return 1; }

    int out = open(argv[2], O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (out == -1) { perror("open dst"); close(in); return 1; }

    char buf[8192];
    ssize_t n;
    while ((n = read(in, buf, sizeof buf)) > 0) {
        if (write_all(out, buf, (size_t)n) == -1) {
            perror("write");
            close(in);
            close(out);
            return 1;
        }
    }
    if (n == -1) {
        perror("read");
        close(in);
        close(out);
        return 1;
    }

    if (close(in) == -1 || close(out) == -1) {
        perror("close");
        return 1;
    }
    return 0;
}
```

**Errors ▸**

| errno | when it happens |
|-------|-----------------|
| `EBADF` | Invalid fd, or fd not open for reading/writing |
| `EINTR` | Interrupted by signal before completion |
| `EAGAIN`/`EWOULDBLOCK` | Non-blocking fd, operation would block |
| `EINVAL` | Invalid count, or fd is connected but shutdown for this direction |
| `EIO` | I/O error on underlying object |
| `EPIPE` | Write to pipe/socket with no readers (also raises `SIGPIPE`) |
| `EFBIG` | Write would exceed implementation file-size limit |
| `ENOSPC` | No space left on device |

---

## Summary

- `read()`/`write()` move bytes through the fd; success returns a **count** that
  may be less than requested — not an error.
- `read()` returning `0` means EOF (for many fd types); loop until 0 for streams,
  loop until N for fixed-size records.
- Always implement **write-all** (and read-exactly-N when needed) for correctness
  on pipes, sockets, and under load.
- `pread`/`pwrite` I/O at a given offset without changing the shared file offset;
  `readv`/`writev` scatter-gather in one syscall.
- `O_APPEND` makes each `write()` atomically seek-to-end then write; multi-write
  sequences still need explicit synchronization.

Next: [2.3 — Seeking & file offsets](03-seek-and-offsets.md)
