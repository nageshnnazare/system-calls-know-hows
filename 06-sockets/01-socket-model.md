# 6.1 — The Socket Model

A **socket** is a kernel object for network (or local) communication, exposed to your
program as a **file descriptor** (Part 0.5). You create it with `socket()`, name it with
`bind()` or `connect()`, move bytes with `read()`/`write()` or `send()`/`recv()`, and
release it with `close()`. Part 6.2–6.4 specialize for TCP, UDP, and Unix domain;
this chapter establishes the common model.

---

## 6.1.1 socket() — domain, type, protocol

> **The call ▸**
> ```c
> #include <sys/socket.h>
>
> int socket(int domain, int type, int protocol);
> ```
> **Returns:** new fd ≥ 0 on success; **-1** on error (`errno` set).

```
   socket(domain, type, protocol)
         │
         ▼
   fd table[n] ──▶ open file description ──▶ socket inode (protocol state)
```

| Parameter | Common values |
|-----------|---------------|
| `domain` | `AF_INET` (IPv4), `AF_INET6` (IPv6), `AF_UNIX` (local — Part 6.4) |
| `type` | `SOCK_STREAM` (reliable byte stream), `SOCK_DGRAM` (datagrams) |
| `protocol` | `0` (pick default for domain+type), or `IPPROTO_TCP`, `IPPROTO_UDP` |

**Errors ▸**

| errno | When |
|-------|------|
| `EAFNOSUPPORT` | Domain not supported |
| `EINVAL` | Unknown type/protocol combination |
| `EMFILE` / `ENFILE` | Per-process or system fd limit |
| `ENOBUFS` / `ENOMEM` | Kernel memory pressure |

**Pitfall ▸** Forgetting `protocol = 0` with exotic combinations — usually you want
`socket(AF_INET, SOCK_STREAM, 0)` and let the kernel pick TCP.

---

## 6.1.2 SOCK_STREAM vs SOCK_DGRAM

```
   SOCK_STREAM (TCP)                 SOCK_DGRAM (UDP)
   ─────────────────                 ────────────────
   connection-oriented               connectionless
   reliable, ordered bytes           messages, may drop/reorder
   read() may return partial         recvfrom() = one datagram
   listen/accept (server)          bind only; no accept
   Part 6.2                          Part 6.3
```

**Trade-offs ▸** TCP: complexity + latency (handshake) for reliability. UDP: you own
retransmission, ordering, and congestion — but lowest overhead for small, latency-bound
messages (DNS, gaming, QUIC builds on UDP).

---

## 6.1.3 sockaddr structures and the cast idiom

Sockets are named by **sockaddr** structures; each address family has its own layout.

> **The call ▸**
> ```c
> #include <netinet/in.h>   /* struct sockaddr_in, sockaddr_in6 */
> #include <sys/un.h>       /* struct sockaddr_un — Part 6.4 */
> #include <sys/socket.h>   /* struct sockaddr, sockaddr_storage */
> ```

```c
struct sockaddr_in addr;
memset(&addr, 0, sizeof addr);
addr.sin_family = AF_INET;
addr.sin_port = htons(8080);
inet_pton(AF_INET, "127.0.0.1", &addr.sin_addr);

bind(fd, (struct sockaddr *)&addr, sizeof addr);
```

**Why `sockaddr_storage`?** IPv4 and IPv6 addresses differ in size. `sockaddr_storage`
is large enough for any family — use it for APIs that accept either:

```c
struct sockaddr_storage ss;
socklen_t len = sizeof ss;
getpeername(fd, (struct sockaddr *)&ss, &len);
if (ss.ss_family == AF_INET) {
    struct sockaddr_in *in = (struct sockaddr_in *)&ss;
    /* use in */
}
```

**Pitfall ▸** Forgetting to zero the struct leaves garbage in padding bytes that
`bind()` rejects with `EADDRNOTAVAIL` or causes subtle bugs.

---

## 6.1.4 Byte order: htons, htonl, ntohs, ntohl

Network protocols use **big-endian** byte order. Host order varies (x86-64 is little-endian).

> **The call ▸**
> ```c
> #include <arpa/inet.h>
>
> uint16_t htons(uint16_t hostshort);
> uint16_t ntohs(uint16_t netshort);
> uint32_t htonl(uint32_t hostlong);
> uint32_t ntohl(uint32_t netlong);
> ```

```
   port 8080 on x86 host:
   host memory:  0x901F  (little-endian bytes 1F 90)
   on wire:      0x1F90  (big-endian)  ← htons() produces this for sin_port
```

Always `htons()` on ports and `htonl()` on IPv4 addresses before stuffing into
`sockaddr_in`. Convert back with `ntohs`/`ntohl` when printing.

Modern alternative: `inet_pton` / `inet_ntop` handle address strings without manual
shifting.

---

## 6.1.5 A socket is an fd

From Part 0.5, a socket fd participates in the same table as files and pipes:

| Operation | Works on socket fd? |
|-----------|---------------------|
| `read` / `write` | ✓ (TCP connected; semantics vary) |
| `close` | ✓ |
| `fcntl` (non-blocking, `FD_CLOEXEC`) | ✓ |
| `dup` / `dup2` | ✓ |
| `poll` / `select` / `epoll` | ✓ (Part 6.6, Part 7.2) |
| `lseek` | ✗ (`ESPIPE` / `EINVAL`) |

**Systems ▸** `ss -tlnp` and `lsof -p PID` show socket fds alongside regular files.
`strace -e socket,bind,listen,accept,connect` traces the setup syscalls.

---

## 6.1.6 Minimal socket creation

```c
#include <arpa/inet.h>
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

int main(void) {
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd == -1) {
        perror("socket");
        exit(1);
    }

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof addr);
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    addr.sin_port = htons(0);   /* ephemeral port assigned by bind */

    if (bind(fd, (struct sockaddr *)&addr, sizeof addr) == -1) {
        perror("bind");
        close(fd);
        exit(1);
    }

    socklen_t len = sizeof addr;
    if (getsockname(fd, (struct sockaddr *)&addr, &len) == -1) {
        perror("getsockname");
        close(fd);
        exit(1);
    }

    char ip[INET_ADDRSTRLEN];
    inet_ntop(AF_INET, &addr.sin_addr, ip, sizeof ip);
    printf("listening socket fd=%d on %s:%u\n",
           fd, ip, (unsigned)ntohs(addr.sin_port));

    close(fd);
    return 0;
}
```

---

## Summary

- `socket(domain, type, protocol)` returns an fd referencing a kernel socket object.
- `AF_INET`/`AF_INET6` for network; `SOCK_STREAM` (TCP) vs `SOCK_DGRAM` (UDP).
- Address structures (`sockaddr_in`, `sockaddr_storage`) require zero-init and family-
  correct casts to `struct sockaddr *`.
- Ports and multi-byte fields need `htons`/`htonl` before wire transmission.
- Sockets are fds: `close`, `poll`, `fcntl`, and the Part 2 I/O rules apply.

Next: [6.2 — TCP sockets](02-tcp-sockets.md)
