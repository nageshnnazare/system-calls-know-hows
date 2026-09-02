# 7.3 — Asynchronous I/O & io_uring

POSIX asynchronous I/O (`aio_read`, `aio_write`) promised "submit and forget."
On Linux it disappointed: limited op types, thread-pool emulation in glibc, poor
socket support. **io_uring** (Linux 5.1+, mature by 5.10+) is the kernel-native
answer: shared **submission** and **completion** ring buffers mapped into your
address space, batched syscalls, and optional kernel-side polling. Part 7.2's epoll
tells you when to I/O; io_uring can **perform** the I/O asynchronously.

---

## 7.3.1 Why POSIX AIO failed on Linux

```
   POSIX AIO (libaio / glibc aio)
   ───────────────────────────────
   • historically disk-only in kernel
   • sockets often emulated with threads
   • no unified completion model
   • clunky API, poor ecosystem

   io_uring
   ────────
   • reads, writes, accept, connect, splice, fsync, ...
   • true async completion via CQ ring
   • batched io_uring_enter — one syscall, many ops
   • liburing wraps it cleanly
```

**Trade-offs ▸** epoll + non-blocking I/O remains simpler for classic network
servers. io_uring wins when syscall rate, disk I/O depth, or mixed op types dominate
( databases, proxies, high-QPS storage ).

---

## 7.3.2 Architecture: SQ and CQ rings

![io_uring: submission queue, completion queue, shared mmap rings](figures/io-uring.svg)

```
   user space                              kernel
   ┌─────────────────────────────────────────────────────────────┐
   │  SQ ring  ──▶  [ SQE | SQE | SQE | ... ]  tail/head indices │
   │  CQ ring  ◀──  [ CQE | CQE | ... ]                         │
   │  SQE array (mmap) — 64-byte submission entries               │
   └───────────────────────────┬─────────────────────────────────┘
                               │ io_uring_setup / io_uring_enter
                               ▼
                    kernel submits ops, posts completions
```

Three mmap regions from `io_uring_setup`:

1. **SQ ring** — indices + flags (`IORING_SQ_NEED_WAKEUP`)
2. **CQ ring** — completion indices + overflow count
3. **SQEs** — array of `struct io_uring_sqe` (your actual requests)

> **The call ▸**
> ```c
> #include <linux/io_uring.h>
> #include <sys/mman.h>
> #include <unistd.h>
>
> int io_uring_setup(unsigned entries, struct io_uring_params *p);
> int io_uring_enter(int fd, unsigned to_submit, unsigned min_complete,
>                    unsigned flags, sigset_t *sig);
> int io_uring_register(int fd, unsigned opcode, void *arg, unsigned nr_args);
> ```

`entries` must be power of two (e.g. 256). Returns an **uring fd** used for
subsequent calls. Most programs use **liburing** instead of raw syscalls.

> **Under the hood ▸** You fill an SQE, advance the SQ tail. `io_uring_enter`
> (or SQPOLL kernel thread) picks up entries, executes them, writes CQEs with
> `user_data` and `res` (result or `-errno`). You reap CQEs by advancing CQ head.

---

## 7.3.3 SQEs and CQEs

Submission queue entry (conceptual fields):

```
   struct io_uring_sqe {
       __u8    opcode;      /* IORING_OP_READ, WRITE, ACCEPT, ... */
       __s32   fd;
       __u64   off;
       __u64   addr;        /* buffer pointer */
       __u32   len;
       __u64   user_data;   /* echoed in CQE — your cookie */
       ...
   };
```

Completion queue entry:

```
   struct io_uring_cqe {
       __u64   user_data;
       __s32   res;         /* byte count, or negative errno */
       __u32   flags;
   };
```

Typical flow:

```
   1. io_uring_get_sqe()           grab empty SQE slot
   2. io_uring_prep_read(sqe,...)  fill opcode + args
   3. sqe->user_data = cookie
   4. io_uring_submit()            io_uring_enter — push to kernel
   5. io_uring_wait_cqe() / peek   reap completion
   6. cqe->res                     bytes transferred or -errno
   7. io_uring_cqe_seen()           advance CQ head
```

**Errors ▸** (in `cqe->res`, negated errno)

| value | when |
|-------|------|
| `-EAGAIN` | non-blocking op not ready (if IOSQE_ASYNC) |
| `-EBADF` | invalid fd in SQE |
| `-EINVAL` | malformed SQE |
| `-ENOMEM` | kernel couldn't allocate for op |

---

## 7.3.4 SQPOLL: zero-syscall submission mode

`IORING_SETUP_SQPOLL` spawns a **kernel thread** that polls the SQ ring:

```
   without SQPOLL:  user ──io_uring_enter──▶ kernel (per batch)
   with SQPOLL:     kernel thread polls SQ ──▶ picks up SQEs automatically
                    user wakes kernel only if IORING_SQ_NEED_WAKEUP set
```

Requires root or `CAP_SYS_ADMIN` / `RLIMIT_MEMLOCK` on some configs. Trades CPU
(pinned kernel thread) for lower latency and fewer boundary crossings — useful at
extreme IOPS. Part 7.5 discusses syscall amortization.

---

## 7.3.5 liburing high-level API

Install: `liburing-dev` (Debian/Ubuntu) or build from source. Link `-luring`.

```c
#include <liburing.h>

struct io_uring ring;
io_uring_queue_init(256, &ring, 0);          /* 256 SQ entries */
io_uring_queue_exit(&ring);
```

`io_uring_prep_*` helpers set opcode fields. `IOSQE_IO_LINK` chains ops (write
after read). `IORING_OP_READ_FIXED` uses registered buffers (zero-copy friendly).

---

## 7.3.6 liburing read example

```c
#define _GNU_SOURCE
#include <fcntl.h>
#include <liburing.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "usage: %s <file>\n", argv[0]);
        return 1;
    }

    int fd = open(argv[1], O_RDONLY);
    if (fd == -1) { perror("open"); return 1; }

    struct io_uring ring;
    int ret = io_uring_queue_init(8, &ring, 0);
    if (ret < 0) {
        fprintf(stderr, "io_uring_queue_init: %s\n", strerror(-ret));
        close(fd);
        return 1;
    }

    char buf[4096];
    struct io_uring_sqe *sqe = io_uring_get_sqe(&ring);
    if (!sqe) {
        fprintf(stderr, "get_sqe failed\n");
        io_uring_queue_exit(&ring);
        close(fd);
        return 1;
    }

    io_uring_prep_read(sqe, fd, buf, sizeof buf, 0);
    io_uring_sqe_set_data(sqe, (void *)(uintptr_t)42);  /* cookie */

    ret = io_uring_submit(&ring);
    if (ret < 0) {
        fprintf(stderr, "submit: %s\n", strerror(-ret));
        io_uring_queue_exit(&ring);
        close(fd);
        return 1;
    }

    struct io_uring_cqe *cqe;
    ret = io_uring_wait_cqe(&ring, &cqe);
    if (ret < 0) {
        fprintf(stderr, "wait_cqe: %s\n", strerror(-ret));
        io_uring_queue_exit(&ring);
        close(fd);
        return 1;
    }

    if (cqe->res < 0) {
        fprintf(stderr, "read failed: %s\n", strerror(-cqe->res));
        io_uring_queue_exit(&ring);
        close(fd);
        return 1;
    }

    if (io_uring_cqe_get_data(cqe) != (void *)(uintptr_t)42) {
        fprintf(stderr, "unexpected cookie\n");
        io_uring_queue_exit(&ring);
        close(fd);
        return 1;
    }

    ssize_t n = cqe->res;
    if (write(STDOUT_FILENO, buf, (size_t)n) != n) {
        perror("write");
        io_uring_queue_exit(&ring);
        close(fd);
        return 1;
    }

    io_uring_cqe_seen(&ring, cqe);
    io_uring_queue_exit(&ring);
    close(fd);
    return 0;
}
```

Build: `gcc -Wall -o uring_read uring_read.c -luring`

---

## 7.3.7 io_uring vs epoll

```
   ┌────────────────────┬─────────────────────┬─────────────────────┐
   │                    │ epoll               │ io_uring            │
   ├────────────────────┼─────────────────────┼─────────────────────┤
   │ Primary role       │ readiness notify      │ submit + complete   │
   │ Data path          │ you call read/write   │ kernel can do I/O   │
   │ Syscall pattern    │ epoll_wait + rw       │ batched enter       │
   │ Maturity / tooling │ universal on Linux    │ newer, fast moving  │
   │ Complexity         │ moderate              │ higher              │
   └────────────────────┴─────────────────────┴─────────────────────┘
```

Many designs combine both: io_uring for disk, epoll for network — or use
`IORING_OP_POLL_ADD` to integrate. Part 7.5 covers batching economics.

**Pitfall ▸** Assuming io_uring replaces non-blocking discipline. Linked ops,
buffer lifetimes, and CQE ordering still require careful ownership — the kernel
does not make your protocol state machine free.

---

## Summary

- POSIX AIO on Linux was limited; io_uring provides kernel-native async I/O via
  mmap'd SQ/CQ rings and `io_uring_setup` / `io_uring_enter` / `io_uring_register`.
- SQEs describe work; CQEs return `user_data` + `res` (count or `-errno`).
- SQPOLL mode reduces syscalls at the cost of a kernel polling thread.
- liburing is the practical API; use it unless you need minimal dependencies.
- epoll = readiness; io_uring = submission + completion — complementary, not always
  interchangeable.

Next: [7.4 — Zero-copy: sendfile, splice & Friends](04-zero-copy.md)
