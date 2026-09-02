# 6.6 — I/O Multiplexing: select, poll & epoll

A thread blocked in `accept()` or `read()` on one socket cannot serve others. **I/O
multiplexing** waits on **many fds at once** and returns those ready for I/O — the
foundation of the **C10k problem** (10 000 concurrent connections on one machine). Part 6.2
showed blocking TCP; Part 7.2 goes deeper on `epoll`; this chapter compares `select`,
`poll`, and `epoll` mechanically.

---

## 6.6.1 The C10k problem

```
   blocking model (one thread per connection):
   ───────────────────────────────────────────
   10 000 connections → 10 000 threads
   → 10 000 stacks (GBs RAM), scheduler thrashing, context switches

   event-driven model (multiplexing):
   ─────────────────────────────────
   one thread (or few) + epoll_wait → handle only ready fds
```

**Systems ▸** nginx, redis, and modern game servers combine non-blocking sockets +
`epoll` (or `io_uring` — Part 7.3) with worker threads for CPU-bound work (Part 5).

---

## 6.6.2 select()

> **The call ▸**
> ```c
> #include <sys/select.h>
>
> int select(int nfds, fd_set *restrict readfds, fd_set *restrict writefds,
>            fd_set *restrict exceptfds, struct timeval *restrict timeout);
> ```
> **Returns:** count of ready fds; `0` on timeout; **-1** + `errno`.

```
   user space                    kernel
   fd_set (bitmap)  ──copy──▶   scan fds 0..nfds-1  O(n)
   ◀── modified ────          set bits for ready fds
```

| Aspect | Detail |
|--------|--------|
| fd set | `FD_SET`, `FD_CLR`, `FD_ISSET`, `FD_ZERO` macros |
| limit | `FD_SETSIZE` — typically **1024** on Linux glibc |
| complexity | **O(n)** each call — kernel scans all bits up to `nfds` |
| fd lifetime | must re-build set after each call (kernel overwrites) |

**Pitfall ▸** `nfds` must be **one plus highest fd number** — easy to get wrong.
**Pitfall ▸** `FD_SETSIZE` cap makes `select` unsuitable for high fd counts.

```c
fd_set rfds;
FD_ZERO(&rfds);
FD_SET(listen_fd, &rfds);
FD_SET(client_fd, &rfds);
int maxfd = (listen_fd > client_fd ? listen_fd : client_fd) + 1;

int ready = select(maxfd, &rfds, NULL, NULL, NULL);
if (ready > 0 && FD_ISSET(listen_fd, &rfds))
    /* accept */;
```

---

## 6.6.3 poll()

> **The call ▸**
> ```c
> #include <poll.h>
>
> int poll(struct pollfd *fds, nfds_t nfds, int timeout);
> ```
> **Returns:** ready count; `0` timeout; **-1** + `errno`.

```c
struct pollfd fds[] = {
    { .fd = listen_fd, .events = POLLIN },
    { .fd = client_fd,  .events = POLLIN },
};
int ready = poll(fds, 2, -1);
if (fds[0].revents & POLLIN) { /* accept */ }
```

| vs select | poll |
|-----------|------|
| fd limit | no 1024 cap (ulimit / RAM bound) |
| interface | array of `struct pollfd`, not bitmap |
| complexity | still **O(n)** — scans entire array each call |
| portability | POSIX, clean API |

**Trade-offs ▸** `poll` fixes `select`'s size limit but not linear scan cost — fine for
hundreds of fds, painful for tens of thousands checked every loop.

---

## 6.6.4 epoll

![epoll: register once, wait for readiness events](figures/epoll.svg)

> **The call ▸**
> ```c
> #include <sys/epoll.h>
>
> int epoll_create1(int flags);           /* EPOLL_CLOEXEC */
> int epoll_ctl(int epfd, int op, int fd, struct epoll_event *event);
> int epoll_wait(int epfd, struct epoll_event *events,
>                int maxevents, int timeout);
> ```
> **Returns:** `epoll_ctl`/`epoll_create1`: 0 or -1; `epoll_wait`: ready count.

```
   setup (once per fd):
   epoll_create1() → epfd
   epoll_ctl(ADD, client_fd, EPOLLIN)  → kernel links fd to interest set

   loop:
   epoll_wait(epfd, events[], max, timeout)  → only ready fds returned
```

**Why O(1)?** The kernel maintains a **ready list** keyed by epoll instance. When data
arrives, only affected fds are linked — `epoll_wait` returns without scanning all
registered fds (amortized constant work per event).

| op (`epoll_ctl`) | Meaning |
|------------------|---------|
| `EPOLL_CTL_ADD` | Register fd + events |
| `EPOLL_CTL_MOD` | Change events |
| `EPOLL_CTL_DEL` | Remove fd |

---

## 6.6.5 Level-triggered vs edge-triggered

| Mode | Behavior |
|------|----------|
| **Level-triggered (LT)** default | Ready as long as condition holds (data in buffer) |
| **Edge-triggered (ET)** `EPOLLET` | Notify **once** on 0→ready transition |

```
   LT: data in socket buffer → epoll_wait keeps reporting IN until drained
   ET: one notification → must read until EAGAIN or miss events
```

**Pitfall ▸** ET requires **non-blocking** fds and **drain-to-EAGAIN** loops (Part 7.1).
LT is forgiving; ET reduces syscall count when coded correctly.

```c
struct epoll_event ev = { .events = EPOLLIN | EPOLLET, .data.fd = fd };
epoll_ctl(epfd, EPOLL_CTL_ADD, fd, &ev);

/* ET read loop */
for (;;) {
    ssize_t n = read(fd, buf, sizeof buf);
    if (n > 0) continue;
    if (n == 0) break;   /* EOF */
    if (errno == EAGAIN || errno == EWOULDBLOCK) break;
    perror("read");
    break;
}
```

---

## 6.6.6 Comparison table

| | select | poll | epoll |
|---|--------|------|-------|
| fd scale | ~1024 | thousands | tens/hundreds of thousands |
| wait complexity | O(n) scan | O(n) scan | O(ready) |
| registration | each call | each call | `epoll_ctl` once |
| fd set copy | full bitmap user↔kernel | array user↔kernel | event array out only |
| edge-triggered | no | no | yes (`EPOLLET`) |
| portability | everywhere | POSIX | Linux (BSD: kqueue) |

**Systems ▸** On Linux servers, **`epoll` is the default choice** for connection-heavy
services. Use `poll` for moderate fd counts or portability. Avoid `select` except legacy
code or tiny fd sets.

Part **7.2** covers `EPOLLONESHOT`, `EPOLLRDHUP`, thundering herd, and tuning. Part **7.3**
introduces `io_uring` as the next step beyond epoll.

---

## 6.6.7 Minimal epoll echo server sketch

```c
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/epoll.h>
#include <sys/socket.h>
#include <unistd.h>

#define MAX_EVENTS 64
#define PORT 9092

static void die(const char *msg) {
    perror(msg);
    exit(1);
}

static void set_nonblock(int fd) {
    int flags = fcntl(fd, F_GETFL, 0);
    if (flags == -1 || fcntl(fd, F_SETFL, flags | O_NONBLOCK) == -1)
        die("fcntl");
}

int main(void) {
    int listen_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (listen_fd == -1)
        die("socket");

    int yes = 1;
    setsockopt(listen_fd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof yes);

    struct sockaddr_in addr = { 0 };
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(PORT);
    if (bind(listen_fd, (struct sockaddr *)&addr, sizeof addr) == -1)
        die("bind");
    if (listen(listen_fd, 128) == -1)
        die("listen");

    int epfd = epoll_create1(EPOLL_CLOEXEC);
    if (epfd == -1)
        die("epoll_create1");

    struct epoll_event ev = { .events = EPOLLIN, .data.fd = listen_fd };
    if (epoll_ctl(epfd, EPOLL_CTL_ADD, listen_fd, &ev) == -1)
        die("epoll_ctl");

    struct epoll_event events[MAX_EVENTS];

    for (;;) {
        int n = epoll_wait(epfd, events, MAX_EVENTS, -1);
        if (n == -1) {
            if (errno == EINTR)
                continue;
            die("epoll_wait");
        }

        for (int i = 0; i < n; i++) {
            if (events[i].data.fd == listen_fd) {
                int conn = accept(listen_fd, NULL, NULL);
                if (conn == -1) {
                    perror("accept");
                    continue;
                }
                set_nonblock(conn);
                ev.events = EPOLLIN | EPOLLET;
                ev.data.fd = conn;
                if (epoll_ctl(epfd, EPOLL_CTL_ADD, conn, &ev) == -1)
                    perror("epoll_ctl add");
            } else {
                char buf[4096];
                ssize_t r = read(events[i].data.fd, buf, sizeof buf);
                if (r <= 0) {
                    close(events[i].data.fd);
                    continue;
                }
                write(events[i].data.fd, buf, (size_t)r);
            }
        }
    }
}
```

Requires `fcntl.h` for `O_NONBLOCK`. Simplified — production code handles
partial writes and `EPOLLRDHUP`.

---

## Summary

- Multiplexing lets one thread serve many sockets; essential for C10k-scale servers.
- `select`: bitmap, 1024 fd cap, O(n). `poll`: array, no cap, still O(n).
- `epoll`: register with `epoll_ctl`, wait with `epoll_wait` — scales to many connections.
- LT vs ET: ET needs non-blocking fds and drain-to-EAGAIN; see Part 7.2 for depth.

Next: [7.1 — Blocking vs non-blocking I/O](../07-io-performance/01-blocking-nonblocking.md)
