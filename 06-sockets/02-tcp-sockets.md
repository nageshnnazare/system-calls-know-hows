# 6.2 — TCP Sockets

TCP provides a **reliable, ordered byte stream** between two endpoints. The server path is
`socket` → `bind` → `listen` → `accept`; the client path is `socket` → `connect`.
Part 6.1 introduced the socket fd; this chapter walks the full lifecycle with syscalls,
handshake mechanics, and a compilable echo pair.

---

## 6.2.1 Server and client flows

![TCP server/client syscall sequence](figures/socket-sequence.svg)

```
   SERVER                              CLIENT
   ──────                              ──────
   socket()                            socket()
   bind(local addr)                    connect(server addr)
   listen(backlog)                           │
   accept() ◀────── SYN/SYN-ACK/ACK ──────────┘
        │                                  │
   new connected fd                    connected fd (same socket())
   read/write ◀──────────────────────▶ read/write
   close()                             close()
```

> **The call ▸** — server setup
> ```c
> #include <sys/socket.h>
> #include <netinet/in.h>
>
> int bind(int sockfd, const struct sockaddr *addr, socklen_t addrlen);
> int listen(int sockfd, int backlog);
> int accept(int sockfd, struct sockaddr *restrict addr,
>            socklen_t *restrict addrlen);
> int connect(int sockfd, const struct sockaddr *addr, socklen_t addrlen);
> ```
> All return `0` on success except `accept`/`connect` noted below; **-1** + `errno` on error.

| Syscall | Success return |
|---------|----------------|
| `accept` | **New fd** for the connected socket (≥ 0) |
| `connect` | `0` (TCP; may block until handshake completes) |

**Pitfall ▸** `accept` returns a **new** fd. The listening fd stays open for more
connections. Never `read()` on the listening socket.

---

## 6.2.2 The three-way handshake

![TCP three-way handshake](figures/tcp-handshake.svg)

```
   client                          server
     │── SYN seq=x ──────────────────▶│
     │◀─ SYN-ACK seq=y, ack=x+1 ─────│
     │── ACK ack=y+1 ────────────────▶│
     │         ESTABLISHED            │
```

`connect()` initiates the handshake; `accept()` returns after the kernel completes it
for an incoming connection. Until ESTABLISHED, data you `write()` may buffer or block.

**Under the hood ▸** The kernel maintains TCP state machines per socket (CLOSED,
LISTEN, SYN_RECEIVED, ESTABLISHED, …). Your program sees blocking, `EAGAIN` (non-blocking),
or `poll` readiness (Part 6.6) — not individual SYN packets.

---

## 6.2.3 Backlog

> **The call ▸** `listen(sockfd, backlog)`

`backlog` is the queue length for **completed** connections waiting for `accept()` (since
Linux 4.5+, also influenced by `somaxconn` sysctl). If the queue fills, new SYNs may be
dropped or clients see `ECONNREFUSED`.

**Trade-offs ▸** Too small → connection failures under burst load. Too large → many idle
ESTABLISHED sockets consuming memory before your app accepts them. Size for peak connect
rate × accept latency.

---

## 6.2.4 I/O on the connected socket

Use `read`/`write` or `recv`/`send` interchangeably for TCP (flags differ for MSG_OOB etc.).

**Pitfall ▸** `read()` may return **fewer bytes than requested** (Part 2.2) — not a
short read "error." Loop until buffer full or return 0 (peer closed).

```c
ssize_t total = 0;
while (total < (ssize_t)want) {
    ssize_t n = read(fd, buf + total, want - (size_t)total);
    if (n == 0) break;          /* orderly shutdown */
    if (n == -1) {
        if (errno == EINTR) continue;
        perror("read");
        break;
    }
    total += n;
}
```

`write()` can also short-write — retry with pointer advance.

---

## 6.2.5 Orderly close and TIME_WAIT

> **The call ▸**
> ```c
> int shutdown(int sockfd, int how);   /* SHUT_RD, SHUT_WR, SHUT_RDWR */
> int close(int fd);
> ```

```
   graceful close (typical):
   ─────────────────────────
   shutdown(fd, SHUT_WR)   /* send FIN; still can read remaining data */
   drain reads until 0
   close(fd)
```

**TIME_WAIT** — the side that initiates active close keeps the quad (src/dst IP+port)
in TIME_WAIT ~2× MSL (minutes on Linux) to handle stray packets. High-churn clients
opening many connections to the same server/port can exhaust ephemeral ports.

Mitigations: `SO_REUSEADDR` on server (Part 6.5), tune `ip_local_port_range`, or
design connection pooling. TIME_WAIT on server after client close is normal.

**Pitfall ▸** `close()` without reading pending data may send RST instead of FIN →
client sees `ECONNRESET`. Always drain or use `SO_LINGER` deliberately (Part 6.5).

---

## 6.2.6 Minimal echo server

```c
#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

#define PORT    9090
#define BACKLOG 16
#define BUF_SZ  4096

static void die(const char *msg) {
    perror(msg);
    exit(1);
}

int main(void) {
    int listen_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (listen_fd == -1)
        die("socket");

    int yes = 1;
    if (setsockopt(listen_fd, SOL_SOCKET, SO_REUSEADDR,
                   &yes, sizeof yes) == -1)
        die("setsockopt");

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof addr);
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(PORT);

    if (bind(listen_fd, (struct sockaddr *)&addr, sizeof addr) == -1)
        die("bind");
    if (listen(listen_fd, BACKLOG) == -1)
        die("listen");

    fprintf(stderr, "echo server on port %d\n", PORT);

    for (;;) {
        int conn = accept(listen_fd, NULL, NULL);
        if (conn == -1) {
            if (errno == EINTR)
                continue;
            die("accept");
        }

        for (;;) {
            char buf[BUF_SZ];
            ssize_t n = read(conn, buf, sizeof buf);
            if (n == 0)
                break;
            if (n == -1) {
                if (errno == EINTR)
                    continue;
                perror("read");
                break;
            }
            ssize_t off = 0;
            while (off < n) {
                ssize_t w = write(conn, buf + off, (size_t)(n - off));
                if (w == -1) {
                    if (errno == EINTR)
                        continue;
                    perror("write");
                    off = n;
                    break;
                }
                off += w;
            }
        }
        close(conn);
    }
}
```

---

## 6.2.7 Minimal echo client

```c
#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

#define PORT 9090

static void die(const char *msg) {
    perror(msg);
    exit(1);
}

int main(void) {
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd == -1)
        die("socket");

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof addr);
    addr.sin_family = AF_INET;
    addr.sin_port = htons(PORT);
    if (inet_pton(AF_INET, "127.0.0.1", &addr.sin_addr) != 1) {
        fprintf(stderr, "invalid address\n");
        exit(1);
    }

    if (connect(fd, (struct sockaddr *)&addr, sizeof addr) == -1)
        die("connect");

    char line[256];
    while (fputs("> ", stdout), fgets(line, sizeof line, stdin) != NULL) {
        size_t len = strlen(line);
        ssize_t sent = 0;
        while (sent < (ssize_t)len) {
            ssize_t n = write(fd, line + sent, len - (size_t)sent);
            if (n == -1) {
                if (errno == EINTR)
                    continue;
                die("write");
            }
            sent += n;
        }
        ssize_t n = read(fd, line, sizeof line - 1);
        if (n <= 0)
            break;
        line[n] = '\0';
        fputs(line, stdout);
    }

    close(fd);
    return 0;
}
```

```bash
gcc -Wall -Wextra -o echo_server echo_server.c
gcc -Wall -Wextra -o echo_client echo_client.c
./echo_server &  ./echo_client
```

**Errors ▸** (selected)

| errno | When |
|-------|------|
| `EADDRINUSE` | `bind`: port taken (see Part 6.5 `SO_REUSEADDR`) |
| `ECONNREFUSED` | `connect`: nothing listening |
| `EPIPE` / `SIGPIPE` | `write` after peer closed |
| `ECONNRESET` | Peer sent RST |
| `EINTR` | Signal interrupted blocking call — retry |

---

## Summary

- TCP server: `socket` → `bind` → `listen` → `accept` (new fd per connection) →
  `read`/`write` → `close`.
- Client: `socket` → `connect` → `read`/`write` → graceful `shutdown`/`close`.
- Handshake happens inside `connect`/`accept`; handle short reads/writes in loops.
- TIME_WAIT and backlog sizing are production tuning knobs (Part 6.5).

Next: [6.3 — UDP sockets](03-udp-sockets.md)
