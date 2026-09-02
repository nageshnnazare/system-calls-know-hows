# 2.7 — The VFS, Inodes & "Everything Is a File"

Every `open()`, `read()`, and `write()` in Parts 2.1–2.6 funnels through the
**Virtual File System (VFS)** — a kernel layer that presents one uniform API over
ext4, xfs, tmpfs, procfs, sysfs, pipes, sockets, and device nodes. The fd integer
in your process is the handle; behind it lie **dentries**, **inodes**, and
**struct file** objects wired together by function pointers.

---

## 2.7.1 The VFS stack

```
   your program:  read(fd, buf, n)
        │
        ▼
   ┌─────────────────────────────────────────────────────────────┐
   │  VFS  — generic file layer (path walk, fd table, struct file)│
   └───────────────┬─────────────────────────────────────────────┘
                   │  dispatches via f_op->read_iter / write_iter
       ┌───────────┼───────────┬────────────┬──────────────┐
       ▼           ▼           ▼            ▼              ▼
    ext4        xfs         tmpfs       procfs         pipefs
    (disk)      (disk)      (RAM)       (/proc)        (kernel pipe)
```

> **Under the hood ▸** Each mounted filesystem registers a `struct file_system_type`.
> Path resolution walks **dentries** (cached name components). A dentry points to
> an **inode** (metadata + `i_op` for metadata ops, `i_fop` or linked `file_operations`
> for data). An open fd references a **struct file** (offset, flags, `f_op`).

![VFS layer: dentry, inode, struct file, and concrete filesystems](figures/vfs-inode.svg)

One API drives them all — which is why `strace` shows `read(3, ...)` whether fd 3
is a disk file, a pipe, or `/proc/self/maps`.

---

## 2.7.2 Three objects — don't conflate them

```
   pathname  "/var/log/app.log"
        │
        ▼ walk dentries
   dentry "app.log" ──▶ inode 90210  (size, mode, block map)
        │
        ▼ open()
   struct file  (f_pos=0, f_flags=O_RDONLY, f_op→ext4)
        │
        ▼ install in fd table
   fd 3  in your process
```

| object | lifetime | holds |
|--------|----------|-------|
| dentry | cache; LRU reclaimed | one path component + pointer to inode |
| inode | while link count > 0 or open | metadata, ops, identity on one fs |
| struct file | from `open` until last `close` | offset, status flags, read/write path |

Part 0.5 maps the fd table; Part 2.4 showed multiple fds → one `struct file`.
Part 2.6 showed multiple names (hard links) → one inode.

---

## 2.7.3 The page cache and durability

Regular file I/O usually flows through the **page cache** — file data cached in
RAM as pages:

```
   write(fd, buf, n)  ──▶  copy into page cache (dirty pages)
                         ──▶  may return before disk platter moves

   read(fd, buf, n)   ──▶  satisfy from cache if page present
                         ──▶  else read from disk into cache, then copy out
```

Durability syscalls push toward physical storage:

> **The call ▸**
> ```c
> #include <unistd.h>
> int fsync(int fd);           /* data + metadata for this file */
> int fdatasync(int fd);       /* data only (and minimal metadata to retrieve it) */
> int sync(void);              /* flush all dirty buffers system-wide (heavy) */
> ```

```
   crash after write() returns     may lose recent data (still in cache)
   crash after fsync() returns     data for that fd on persistent storage *
```

\* Subject to drive write-cache settings (`hdparm`, NVMe FUA), RAID controllers,
and network filesystem semantics — **mechanical** guarantee is weaker than the
man page suggests on some stacks.

**Trade-offs ▸** `O_SYNC` / `O_DSYNC` on open make each write wait for storage
(slow, predictable). Databases batch writes and `fsync` at transaction boundaries.

---

## 2.7.4 O_DIRECT — bypass the page cache

`O_DIRECT` (Part 2.1) asks the filesystem to align I/O and transfer between your
buffer and device with **minimal caching**:

```
   normal read:   disk → page cache → user buffer
   O_DIRECT read: disk ──────────────▶ user buffer (aligned)
```

Requires buffer, length, and file offset aligned to logical block size (often 512
or 4096). Useful for databases and streaming that implement their own cache.
**Pitfall ▸** Mixing `O_DIRECT` and non-direct I/O on the same file causes cache
coherency pain — pick one strategy per file.

---

## 2.7.5 "Everything is a file"

If it can be referenced by an fd and supports read/write (or ioctl), it plugs
into the same VFS fd machinery:

```
   regular files     open + read/write + lseek
   directories       open (O_DIRECTORY) + getdents via readdir
   pipes/FIFOs       pipe() / open fifo — read/write, no seek
   sockets           socket() — read/write or send/recv (Part 6)
   character devices /dev/tty, /dev/urandom — byte streams
   block devices     /dev/sda — often mmap or ioctl; buffered differently
   eventfd, timerfd, signalfd   fd + read/write semantics (Part 4, Part 7)
   /proc, /sys       pseudo-fs — generate content on read
```

```
        ┌──────────────────────────────────────┐
        │         single fd abstraction       │
        │   poll/epoll works on all of these  │
        └──────────────────────────────────────┘
              │      │       │        │
           file   pipe   socket   /proc/net/tcp
```

That unification is why **I/O multiplexing** (`select`/`poll`/`epoll`, Part 6.6)
and **`read()` loops** (Part 2.2) look the same across object types — the
polymorphism lives in kernel `file_operations`, not in your C types.

---

## 2.7.6 Example: observe cache vs durability

```c
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char *argv[]) {
    if (argc != 2) {
        fprintf(stderr, "usage: %s path\n", argv[0]);
        return 1;
    }

    int fd = open(argv[1], O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd == -1) { perror("open"); return 1; }

    const char msg[] = "durability demo\n";
    ssize_t n = write(fd, msg, sizeof msg - 1);
    if (n == -1) { perror("write"); close(fd); return 1; }
    if (n != (ssize_t)(sizeof msg - 1)) {
        fprintf(stderr, "short write\n");
        close(fd);
        return 1;
    }

    /* Data may still be in page cache only. */
    if (fsync(fd) == -1) {
        perror("fsync");
        close(fd);
        return 1;
    }

    if (close(fd) == -1) {
        perror("close");
        return 1;
    }
    return 0;
}
```

Compare with `strace`:

```bash
gcc -Wall -Wextra -o fsync_demo fsync_demo.c
strace -e trace=open,write,fsync,close ./fsync_demo /tmp/vfs_demo.txt
```

For read-only metadata from a pseudo-fs:

```bash
cat /proc/self/fd/   # lists your open fds — procfs generates listing at read time
```

**Errors ▸** (fsync family)

| errno | when it happens |
|-------|-----------------|
| `EBADF` | Invalid fd or fd not open for writing |
| `EINTR` | Interrupted |
| `EIO` | I/O error flushing to storage |
| `EINVAL` | fd does not support syncing (e.g. some special fds) |
| `ENOSPC` | No space to flush |

---

## Summary

- The **VFS** is the kernel's uniform file layer; concrete filesystems (ext4,
  xfs, tmpfs, procfs, pipefs, …) plug in via inodes and `file_operations`.
- **Dentries** cache names; **inodes** hold identity and metadata; **struct file**
  holds per-open state (offset, flags) — the fd indexes your process's reference.
- The **page cache** sits between most file I/O and disk; `fsync`/`fdatasync`/
  `sync` push durability; `O_DIRECT` bypasses cache with alignment constraints.
- Pipes, sockets, devices, and `/proc` entries are all **fd-backed** — one
  abstraction powering redirection (Part 2.4), IPC (Part 4), and networking
  (Part 6).

Next: [Part 3.1 — The virtual address space](../03-memory/01-virtual-address-space.md)
