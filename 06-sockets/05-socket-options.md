# 6.5 — Socket Options

`setsockopt` and `getsockopt` tune socket behavior without changing your application
protocol — reuse addresses, disable Nagle, resize buffers, set timeouts. Part 6.2
mentioned `SO_REUSEADDR` and TIME_WAIT; this chapter covers the options production
servers actually set.

---

## 6.5.1 The setsockopt interface

> **The call ▸**
> ```c
> #include <sys/socket.h>
>
> int getsockopt(int sockfd, int level, int optname,
>                void *restrict optval, socklen_t *restrict optlen);
> int setsockopt(int sockfd, int level, int optname,
>                const void *optval, socklen_t optlen);
> ```
> **Returns:** `0` on success; **-1** + `errno` on error.

| Level | Scope |
|-------|-------|
| `SOL_SOCKET` | Generic (all socket types) |
| `IPPROTO_TCP` | TCP-only (`TCP_NODELAY`, …) |
| `IPPROTO_IP` / `IPPROTO_IPV6` | IP-layer options |

```
   setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof yes)
        │
        ▼
   kernel socket structure fields updated in place
```

**Errors ▸**

| errno | When |
|-------|------|
| `EINVAL` | Unknown option or wrong level |
| `ENOPROTOOPT` | Option not supported for this socket type |
| `EBADF` | Not a socket fd |

---

## 6.5.2 SO_REUSEADDR and SO_REUSEPORT

> **The call ▸**
> ```c
> int yes = 1;
> setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof yes);
> setsockopt(fd, SOL_SOCKET, SO_REUSEPORT, &yes, sizeof yes);
> ```

**SO_REUSEADDR** — allows `bind()` to a port in **TIME_WAIT** from a **previous**
connection with the same local tuple (common on servers restarting quickly). Also allows
binding wildcard when a specific address is in TIME_WAIT (with nuances).

**SO_REUSEPORT** (Linux) — multiple sockets **bind to the same port**; kernel load-
balances incoming connections across them. Enables **multi-process** accept pools
(nginx, SO_REUSEPORT workers) without a single accept bottleneck.

```
   without REUSEADDR on restart:
   bind:8080 → EADDRINUSE (old socket in TIME_WAIT)

   with REUSEADDR:
   bind:8080 → OK (rules satisfied)
```

**Pitfall ▸** `SO_REUSEADDR` does **not** mean "two unrelated processes bind the same
port" on all OSes — behavior differs. Use `SO_REUSEPORT` for deliberate sharing.

---

## 6.5.3 TCP_NODELAY (Nagle's algorithm)

> **The call ▸**
> ```c
> int one = 1;
> setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &one, sizeof one);
> ```

Nagle coalesces small writes until an outstanding segment is ACK'd — reduces packet count,
adds latency for tiny messages (telnet, RPC, games).

**Trade-offs ▸**

| Nagle ON (default) | TCP_NODELAY |
|--------------------|-------------|
| Fewer packets | Lower latency for small sends |
| Buffered small writes | More packets on wire |

Combine with **TCP_CORK** (Linux) or write buffering in application for bulk + low latency.

**Pitfall ▸** Classic **deadlock**: thread sends small request with Nagle on while waiting
for reply before sending rest — pair with `TCP_NODELAY` or buffer full requests.

---

## 6.5.4 SO_RCVBUF and SO_SNDBUF

> **The call ▸**
> ```c
> int sz = 256 * 1024;
> setsockopt(fd, SOL_SOCKET, SO_RCVBUF, &sz, sizeof sz);
> setsockopt(fd, SOL_SOCKET, SO_SNDBUF, &sz, sizeof sz);
> ```

Kernel **doubles** the value you set internally (documented Linux behavior) for overhead
accounting. Larger buffers absorb bursts without dropping (TCP backpressure) or blocking
sender — at memory cost per connection.

**Systems ▸** Tune with `ss -tm` / `/proc/sys/net/core/rmem_max` caps. High-throughput
servers scale buffer size × connection count carefully.

---

## 6.5.5 SO_KEEPALIVE

> **The call ▸**
> ```c
> int yes = 1;
> setsockopt(fd, SOL_SOCKET, SO_KEEPALIVE, &yes, sizeof yes);
> ```

Enables TCP keepalive probes on idle connections to detect dead peers (crashed host,
NAT timeout). Probe timing via `TCP_KEEPIDLE`, `TCP_KEEPINTVL`, `TCP_KEEPCNT`
(`IPPROTO_TCP`).

**Trade-offs ▸** Detects half-open connections; adds idle traffic. Not a substitute for
application-level heartbeats with shorter deadlines.

---

## 6.5.6 SO_LINGER

> **The call ▸**
> ```c
> struct linger lg = { .l_onoff = 1, .l_linger = 5 };
> setsockopt(fd, SOL_SOCKET, SO_LINGER, &lg, sizeof lg);
> ```

Controls `close()` behavior when unsent data exists:

| `l_onoff` | `l_linger` | Effect |
|-----------|------------|--------|
| 0 | — | `close` returns immediately (default) |
| 1 | > 0 | Block up to `l_linger` seconds flushing data |
| 1 | 0 | **Abort** — send RST, discard data |

**Pitfall ▸** `l_linger = 0` causes RST — peer gets `ECONNRESET`. Use deliberately for
error paths, not graceful shutdown (prefer `shutdown(SHUT_WR)` — Part 6.2).

---

## 6.5.7 SO_RCVTIMEO (and SO_SNDTIMEO)

> **The call ▸**
> ```c
> struct timeval tv = { .tv_sec = 5, .tv_usec = 0 };
> setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof tv);
> ```

Blocking `read`/`recv` returns `-1` with `EAGAIN`/`EWOULDBLOCK` after timeout (Linux
uses `EAGAIN`). Alternative: non-blocking fd + `poll`/`epoll` (Part 6.6) for finer control.

Modern code often prefers `poll` with timeout or `SO_RCVTIMEO` on worker threads only.

---

## 6.5.8 Typical server bootstrap

```c
#include <netinet/tcp.h>
#include <sys/socket.h>
#include <string.h>

static int tune_server_socket(int fd) {
    int yes = 1;
    if (setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof yes) == -1)
        return -1;
#ifdef SO_REUSEPORT
    if (setsockopt(fd, SOL_SOCKET, SO_REUSEPORT, &yes, sizeof yes) == -1)
        return -1;
#endif
    return 0;
}

static int tune_connected_tcp(int fd) {
    int nodelay = 1;
    if (setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &nodelay, sizeof nodelay) == -1)
        return -1;
    int keep = 1;
    if (setsockopt(fd, SOL_SOCKET, SO_KEEPALIVE, &keep, sizeof keep) == -1)
        return -1;
    return 0;
}
```

Apply `tune_server_socket` before `bind`; `tune_connected_tcp` on each `accept` fd if
needed.

---

## Summary

- `setsockopt`/`getsockopt(level, optname, …)` adjust kernel socket state in place.
- `SO_REUSEADDR` eases TIME_WAIT restart pain; `SO_REUSEPORT` enables multi-process
  accept on one port.
- `TCP_NODELAY` trades packets for latency; buffer sizes affect throughput vs memory.
- `SO_KEEPALIVE`, `SO_LINGER`, and `SO_RCVTIMEO` control idle detection, close behavior,
  and read timeouts.

Next: [6.6 — I/O multiplexing: select, poll & epoll](06-io-multiplexing.md)
