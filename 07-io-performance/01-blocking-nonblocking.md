# 7.1 — Blocking vs Non-blocking I/O

Every `read()`, `write()`, `accept()`, and `connect()` on a socket or pipe either
**blocks** the calling thread until the kernel can complete the operation, or
**returns immediately** with a status code that tells you to try again later. That
distinction — not "sync vs async" in the marketing sense — is the mechanical
foundation of every high-performance server. Part 2.5 introduced `O_NONBLOCK` via
`fcntl()`; Part 6.6 surveyed `select`/`poll`/`epoll`. This chapter names the four
I/O models, explains the **readiness** contract, and shows when a blocking thread
is perfectly fine.

---

## 7.1.1 The four I/O models

![The four I/O models: blocking, non-blocking+poll, multiplexing, async](figures/io-models.svg)

```
   Model 1 — BLOCKING (default)
   ─────────────────────────────
   thread ──read()──▶ kernel waits for data ──▶ returns bytes
          (thread asleep; scheduler runs other tasks)

   Model 2 — NON-BLOCKING + poll loop
   ───────────────────────────────────
   thread ──read()──▶ EAGAIN (no data yet)
          ──poll()──▶ blocks until readable
          ──read()──▶ returns bytes

   Model 3 — MULTIPLEXING (select / poll / epoll)
   ───────────────────────────────────────────────
   thread ──epoll_wait([fd1,fd2,...])──▶ returns ready set
          ──read/write each ready fd (usually non-blocking)

   Model 4 — ASYNCHRONOUS (io_uring, POSIX AIO)
   ────────────────────────────────────────────
   thread ──submit request──▶ continues other work
          ◀── completion notification ── result ready
```

| Model | Syscall pattern | Thread blocked? | Scales to N fds? |
|-------|-----------------|-----------------|------------------|
| Blocking | one fd per thread | yes, on I/O | poor (thread explosion) |
| Non-blocking + poll | poll per fd | yes, on poll | poor |
| Multiplexing | one waiter, many fds | yes, on epoll_wait | excellent (Part 7.2) |
| Async | submit + reap | optional | excellent (Part 7.3) |

**Systems ▸** nginx, Redis, and most event-driven servers use **model 3** (epoll +
non-blocking fds). Databases and storage engines increasingly use **model 4**
(io_uring). Model 1 remains correct for CLI tools, batch jobs, and low-concurrency
services.

---

## 7.1.2 Setting non-blocking mode

Two equivalent paths
to flip a descriptor into non-blocking mode:

```c
// at open time
int fd = open(path, O_RDONLY | O_NONBLOCK);

// or at runtime via fcntl (Part 2.5)
int flags = fcntl(fd, F_GETFL);
if (flags == -1) { perror("F_GETFL"); return -1; }
if (fcntl(fd, F_SETFL, flags | O_NONBLOCK) == -1) {
    perror("F_SETFL");
    return -1;
}
```

For sockets, `ioctl(fd, FIONBIO, &one)` also works (Part 8.3) — same effect,
different API surface.

> **The call ▸**
> ```c
> #include <fcntl.h>
> int fcntl(int fd, int cmd, ...);
> // F_GETFL / F_SETFL with O_NONBLOCK
> ```
> Non-blocking applies to the **open file description** (Part 0.5): all dup'd fds
> share the flag.

> **Under the hood ▸** When `O_NONBLOCK` is set, the kernel's wait queue hook for
> this fd returns `-EAGAIN` immediately instead of putting the task on the sleep
> queue. The fd's state (readable/writable) is unchanged — you just didn't wait
> for it.

---

## 7.1.3 EAGAIN and EWOULDBLOCK

On Linux, `EAGAIN` and `EWOULDBLOCK` are **the same value**. A non-blocking
operation that cannot proceed **right now** returns `-1` with one of these:

```
   non-blocking read() on empty socket buffer
        │
        ▼
   return -1, errno = EAGAIN   ("try again later — not an error")

   non-blocking connect() still in progress
        │
        ▼
   return -1, errno = EINPROGRESS   (different: operation started)
```

**Errors ▸**

| errno | when |
|-------|------|
| `EAGAIN` / `EWOULDBLOCK` | Non-blocking I/O cannot complete without waiting |
| `EINTR` | Signal interrupted the blocking call (retry) |
| `EINPROGRESS` | Non-blocking `connect()` started; finish with `select`/`poll`/`getsockopt(SO_ERROR)` |

**Pitfall ▸** Treating `EAGAIN` as a fatal error. It is the **expected** return on
a non-blocking fd when nothing is ready. Your event loop must loop: wait for
readiness, then retry.

**Pitfall ▸** Mixing blocking and non-blocking fds in one `epoll` set without
setting `O_NONBLOCK` on every monitored fd. A blocking `read()` inside an epoll
handler stalls the entire event thread.

---

## 7.1.4 The readiness model

Multiplexing syscalls (`select`, `poll`, `epoll_wait`) do **not** transfer data.
They answer one question: **"which fds can I read/write/accept without blocking
right now?"**

```
   epoll_wait returns: fd 7 is EPOLLIN (readable)
        │
        ▼
   you MUST still call read(fd7, ...)
        │
        ▼
   read may return 1 byte, 4096 bytes, or EAGAIN (edge-triggered edge case)
```

This is **level-triggered readiness** by default: as long as data sits in the
socket buffer, `epoll_wait` keeps reporting `EPOLLIN`. Edge-triggered mode
(`EPOLLET`, Part 7.2) fires once per transition — you must drain until `EAGAIN`.

**Trade-offs ▸** Readiness-based I/O keeps **one thread** serving thousands of
connections. The cost is application complexity: you become a manual scheduler,
buffering partial reads/writes yourself (Part 2.2 short-read rules still apply).

---

## 7.1.5 When blocking is fine

Blocking I/O is not legacy — it is the right tool when:

```
   ✓  one thread, one connection (simple client)
   ✓  low concurrency (≤ tens of concurrent I/O operations)
   ✓  thread-per-connection with bounded pool (some Java servlet containers)
   ✓  disk I/O on fast local SSD where thread count is modest
   ✓  code clarity matters more than tail latency (admin tools, cron jobs)
```

Blocking fails when:

```
   ✗  thousands of idle connections (each thread ≈ 8 MB stack + scheduler cost)
   ✗  latency-sensitive multiplexing (one slow client blocks others on same thread)
   ✗  syscall overhead dominates (Part 7.5)
```

```
   10 000 idle TCP connections
   ───────────────────────────
   blocking:  10 000 threads  →  ~80 GB virtual stack, context-switch storm
   epoll:     1 thread         →  one epoll_wait, O(ready) work per wakeup
```

---

## 7.1.6 A minimal non-blocking read loop

```c
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <poll.h>

static int set_nonblock(int fd) {
    int flags = fcntl(fd, F_GETFL);
    if (flags == -1) return -1;
    return fcntl(fd, F_SETFL, flags | O_NONBLOCK);
}

static ssize_t read_all_nonblock(int fd, char *buf, size_t cap) {
    size_t total = 0;
    for (;;) {
        ssize_t n = read(fd, buf + total, cap - total);
        if (n > 0) {
            total += (size_t)n;
            if (total == cap) break;
            continue;
        }
        if (n == 0) break;                    /* EOF */
        if (errno == EAGAIN || errno == EWOULDBLOCK) break;
        if (errno == EINTR) continue;
        return -1;
    }
    return (ssize_t)total;
}

int main(int argc, char **argv) {
    if (argc != 2) {
        fprintf(stderr, "usage: %s <file>\n", argv[0]);
        return 1;
    }

    int fd = open(argv[1], O_RDONLY);
    if (fd == -1) { perror("open"); return 1; }
    if (set_nonblock(fd) == -1) { perror("fcntl"); close(fd); return 1; }

    char buf[4096];
    struct pollfd pfd = { .fd = fd, .events = POLLIN };

    for (;;) {
        int pr = poll(&pfd, 1, -1);           /* block until readable */
        if (pr == -1) {
            if (errno == EINTR) continue;
            perror("poll");
            close(fd);
            return 1;
        }

        ssize_t n = read_all_nonblock(fd, buf, sizeof buf);
        if (n == -1) { perror("read"); close(fd); return 1; }
        if (n == 0) break;                    /* EOF after drain */

        if (write(STDOUT_FILENO, buf, (size_t)n) != n) {
            perror("write");
            close(fd);
            return 1;
        }
    }

    close(fd);
    return 0;
}
```

This is model 2: non-blocking `read()` + `poll()` for readiness. Part 7.2 replaces
`poll()` with `epoll` for many fds; Part 7.3 replaces both with io_uring.

---

## Summary

- Four I/O models: blocking, non-blocking+poll, multiplexing (epoll), and true
  async (io_uring) — each trades thread count for application complexity.
- `O_NONBLOCK` (via `open` or `fcntl`) makes syscalls return immediately with
  `EAGAIN`/`EWOULDBLOCK` when data is not ready — not an error.
- Multiplexing answers **readiness**, not data transfer; you still call
  `read()`/`write()` and handle short counts (Part 2.2).
- Blocking threads are fine for low concurrency; at thousands of connections,
  readiness-based event loops win.

Next: [7.2 — epoll in Depth](02-epoll-deep-dive.md)
