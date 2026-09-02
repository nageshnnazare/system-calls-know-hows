# 7.2 — epoll in Depth

`epoll` is Linux's scalable I/O multiplexor: one syscall waits on **many** file
descriptors, and the kernel returns only those that are **ready** — O(number ready)
work per wakeup instead of O(total fds) like `select()`. Part 6.6 introduced the
API; this chapter goes mechanical: `epoll_ctl` bookkeeping, level- vs edge-triggered
semantics, `EPOLLONESHOT`, thundering herd, and a production-grade edge-triggered
accept loop.

---

## 7.2.1 Architecture

![epoll: epoll instance, interest list, ready list, epoll_wait](figures/epoll.svg)

```
   your process                          kernel
   ┌─────────────────┐                  ┌──────────────────────────┐
   │ epoll_fd (efd)  │◀── epoll_create1 │  struct eventpoll         │
   │                 │                  │    interest list (rbtree)│
   │ monitored fds   │── epoll_ctl ADD  │    ready list (linked)   │
   │  sock 4, 7, 12  │                  │    wait queue for efd     │
   └────────┬────────┘                  └────────────┬─────────────┘
            │                                        │
            │  epoll_wait(efd, events, max, timeout) │
            │◀─────────── returns ready subset ──────┘
            │
            ▼
   for each event: read/write/accept on that fd (non-blocking!)
```

> **The call ▸**
> ```c
> #include <sys/epoll.h>
>
> int epoll_create1(int flags);   /* EPOLL_CLOEXEC */
> int epoll_ctl(int epfd, int op, int fd, struct epoll_event *event);
> int epoll_wait(int epfd, struct epoll_event *events,
>                int maxevents, int timeout);
> ```
> `epoll_create1` returns a new epoll fd. `epoll_ctl` registers interest.
> `epoll_wait` blocks until ≥1 fd is ready or timeout elapses.

| `epoll_ctl` op | effect |
|----------------|--------|
| `EPOLL_CTL_ADD` | Register fd + events mask |
| `EPOLL_CTL_MOD` | Change events mask |
| `EPOLL_CTL_DEL` | Remove fd from set |

---

## 7.2.2 epoll_event and epoll_data

```c
typedef union epoll_data {
    void    *ptr;
    int      fd;
    uint32_t u32;
    uint64_t u64;
} epoll_data_t;

struct epoll_event {
    uint32_t     events;   /* EPOLLIN, EPOLLOUT, EPOLLERR, ... */
    epoll_data_t data;     /* user payload — NOT used by kernel for I/O */
};
```

The kernel **stores** `data` and returns it unchanged in `epoll_wait`. Common
patterns:

```
   data.fd = sockfd          simple: event carries the fd
   data.ptr = conn_ctx *     preferred: pointer to per-connection state
```

**Pitfall ▸** Setting `data.fd` but reading `event.data.ptr` (or vice versa) after
`epoll_wait`. The union is one slot — pick one convention per program.

Event bits (most used):

| bit | meaning |
|-----|---------|
| `EPOLLIN` | readable (recv, accept on listening fd) |
| `EPOLLOUT` | writable (send buffer has space) |
| `EPOLLERR` | error condition — always check |
| `EPOLLHUP` | hang up (peer closed write side) |
| `EPOLLET` | edge-triggered (see below) |
| `EPOLLONESHOT` | one-shot (see below) |
| `EPOLLEXCLUSIVE` | exclusive wakeup (accept storm mitigation) |

---

## 7.2.3 Level-triggered (default) vs edge-triggered

**Level-triggered (LT)** — default, no `EPOLLET`:

```
   socket recv buffer:  [====data====]
                              │
   epoll_wait:  EPOLLIN fires
   read 1 byte: [===data=====]
   epoll_wait:  EPOLLIN fires again  ← still data left
```

As long as the condition holds (data in buffer), `epoll_wait` keeps reporting the
fd. Forgiving — you can read lazily.

**Edge-triggered (ET)** — `events | EPOLLET`:

```
   empty ──▶ data arrives ──▶ EPOLLIN (one edge)
   read partial ──▶ NO new edge until empty ──▶ full again ──▶ EPOLLIN
```

> **Under the hood ▸** ET mode clears the "already notified" edge when the fd
> transitions to not-ready. If you read one byte and stop, **you will not get
> another notification** until the fd goes not-ready and ready again. You must
> **drain until `EAGAIN`**.

**Pitfall ▸** ET + blocking fd = deadlock risk in a shared event loop. ET + partial
read without drain = stuck connection until more data arrives.

ET drain pattern (mandatory):

```c
for (;;) {
    ssize_t n = read(fd, buf, sizeof buf);
    if (n > 0) { /* process */ continue; }
    if (n == 0) { /* EOF */ break; }
    if (errno == EAGAIN || errno == EWOULDBLOCK) break;
    if (errno == EINTR) continue;
    /* real error */
}
```

**Trade-offs ▸** LT: simpler, slightly more wakeups. ET: fewer syscalls, stricter
discipline, higher bug rate if fds aren't non-blocking. nginx uses ET; many apps
use LT successfully.

---

## 7.2.4 EPOLLONESHOT

`EPOLLONESHOT` disables the fd in the epoll set after one event until you
`EPOLL_CTL_MOD` re-arms it:

```
   event fires ──▶ fd masked off ──▶ your handler runs (maybe in thread pool)
   handler done ──▶ epoll_ctl(MOD) re-enable
```

Useful with **thread pools**: one event dispatched to a worker; no other thread
gets a duplicate wakeup for the same fd until re-armed. Pairs naturally with
non-blocking I/O and careful serialization.

---

## 7.2.5 Thundering herd and EPOLLEXCLUSIVE

When many threads block on the **same** epoll fd (or many processes on a
listening socket), one readiness event can wake **all** of them — the **thundering
herd**:

```
   listen fd readable (many connections queued)
        │
        ▼
   wake thread 1, 2, 3, ... N   (all compete for accept)
        │
        ▼
   one wins, N-1 go back to sleep — wasted scheduler work
```

`EPOLLEXCLUSIVE` (since Linux 4.5) on a listening fd: only **one** epoll waiter
gets woken per readiness edge. Combine with `EPOLLET` on the listen socket for
accept loops at high connection rates.

> **Under the hood ▸** Exclusive wakeups use a flag on the wait queue entry so
> the kernel stops after the first successful wakeup for that event.

---

## 7.2.6 Common bugs checklist

```
   ✗  blocking I/O inside epoll handler
   ✗  ET without drain-until-EAGAIN
   ✗  forgetting EPOLLERR / EPOLLHUP handling
   ✗  ADD same fd twice (EEXIST)
   ✗  close(fd) without EPOLL_CTL_DEL (fd number reuse → wrong handler)
   ✗  epoll_wait maxevents too small — multiple events per fd need slots
   ✗  thundering herd on shared epoll fd without EPOLLEXCLUSIVE
```

**Errors ▸**

| errno | when |
|-------|------|
| `EEXIST` | `EPOLL_CTL_ADD` on fd already in set |
| `ENOENT` | `EPOLL_CTL_MOD`/`DEL` on fd not in set |
| `EBADF` | invalid epfd or fd |
| `EINTR` | signal during `epoll_wait` — retry |

Always `EPOLL_CTL_DEL` before `close`, or close the epoll fd last and let kernel
cleanup handle it — but fd reuse makes explicit DEL safer.

---

## 7.2.7 Minimal edge-triggered accept loop

```c
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/epoll.h>
#include <sys/socket.h>
#include <unistd.h>

static int set_nonblock(int fd) {
    int fl = fcntl(fd, F_GETFL);
    if (fl == -1) return -1;
    return fcntl(fd, F_SETFL, fl | O_NONBLOCK);
}

static int create_listener(uint16_t port) {
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd == -1) return -1;

    int one = 1;
    setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof one);

    struct sockaddr_in addr = {
        .sin_family = AF_INET,
        .sin_port   = htons(port),
        .sin_addr.s_addr = htonl(INADDR_ANY),
    };
    if (bind(fd, (struct sockaddr *)&addr, sizeof addr) == -1) goto fail;
    if (listen(fd, SOMAXCONN) == -1) goto fail;
    if (set_nonblock(fd) == -1) goto fail;
    return fd;

fail:
    close(fd);
    return -1;
}

static void accept_drain(int efd, int listen_fd) {
    for (;;) {
        int conn = accept(listen_fd, NULL, NULL);
        if (conn == -1) {
            if (errno == EAGAIN || errno == EWOULDBLOCK) break;
            if (errno == EINTR) continue;
            perror("accept");
            break;
        }
        /* handle conn — register on efd with EPOLLIN | EPOLLET, etc. */
        fprintf(stderr, "accepted fd %d\n", conn);
        close(conn);
    }
}

int main(void) {
    int listen_fd = create_listener(8080);
    if (listen_fd == -1) { perror("listen"); return 1; }

    int efd = epoll_create1(EPOLL_CLOEXEC);
    if (efd == -1) { perror("epoll_create1"); return 1; }

    struct epoll_event ev = {
        .events = EPOLLIN | EPOLLET | EPOLLEXCLUSIVE,
        .data.fd = listen_fd,
    };
    if (epoll_ctl(efd, EPOLL_CTL_ADD, listen_fd, &ev) == -1) {
        perror("epoll_ctl");
        return 1;
    }

    struct epoll_event events[64];
    for (;;) {
        int n = epoll_wait(efd, events, 64, -1);
        if (n == -1) {
            if (errno == EINTR) continue;
            perror("epoll_wait");
            return 1;
        }
        for (int i = 0; i < n; i++) {
            if (events[i].data.fd == listen_fd)
                accept_drain(efd, listen_fd);
        }
    }
}
```

Pair with Part 6.2 (TCP sockets) and Part 7.1 (`O_NONBLOCK`). Part 7.3 covers
io_uring as an alternative when syscall batching matters more.

---

## Summary

- `epoll_create1` / `epoll_ctl` / `epoll_wait` maintain an interest set and return
  only ready fds — O(ready) per wakeup.
- `epoll_event.data` is your payload; the kernel does not interpret it.
- LT (default) re-notifies while ready; ET (`EPOLLET`) requires drain-until-`EAGAIN`
  on non-blocking fds.
- `EPOLLONESHOT` serializes per-fd dispatch; `EPOLLEXCLUSIVE` reduces thundering
  herd on listen sockets.
- Delete from epoll before close, handle `EPOLLERR`/`EPOLLHUP`, never block in the
  handler.

Next: [7.3 — Asynchronous I/O & io_uring](03-async-io-and-io-uring.md)
