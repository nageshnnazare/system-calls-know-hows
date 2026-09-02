# 6.3 — UDP Sockets

UDP (`SOCK_DGRAM`) sends **self-contained datagrams** — no connection setup, no byte-stream
merging, no kernel retransmission. You get message boundaries and low latency; you accept
loss, duplication, and reordering unless your application fixes them. Part 6.2 covered TCP;
this chapter covers `sendto`/`recvfrom`, server `bind`, connected UDP, and MTU realities.

---

## 6.3.1 Connectionless datagram model

```
   UDP server                         UDP client
   ──────────                         ──────────
   socket(SOCK_DGRAM)                 socket(SOCK_DGRAM)
   bind(fixed port)                   (optional bind)
   recvfrom() ◀──── datagram ──────── sendto(server_addr)
   sendto(client_addr, reply) ─────▶ recvfrom()
   no listen(), no accept()
```

> **The call ▸**
> ```c
> #include <sys/socket.h>
>
> ssize_t sendto(int sockfd, const void *buf, size_t len, int flags,
>                const struct sockaddr *dest_addr, socklen_t addrlen);
> ssize_t recvfrom(int sockfd, void *buf, size_t len, int flags,
>                  struct sockaddr *src_addr, socklen_t *addrlen);
> ```
> **Returns:** byte count on success; **-1** + `errno` on error.

Each `sendto` becomes **one datagram** (up to size limits). Each `recvfrom` returns **one
complete datagram** — if your buffer is too small, excess bytes are **discarded** (many
stacks set `MSG_TRUNC` flag so you can detect truncation).

**Pitfall ▸** Assuming `recvfrom` fills a stream like TCP — message boundaries are
preserved; one send = one recv (unless truncation).

---

## 6.3.2 Server bind, no accept

A UDP server must **`bind()`** to a well-known port so clients can address it:

```c
struct sockaddr_in addr;
memset(&addr, 0, sizeof addr);
addr.sin_family = AF_INET;
addr.sin_addr.s_addr = htonl(INADDR_ANY);
addr.sin_port = htons(53);   /* example: DNS */

if (bind(fd, (struct sockaddr *)&addr, sizeof addr) == -1)
    perror("bind");
```

There is no connection queue — datagrams arrive and sit in the socket receive buffer until
you `recvfrom` or the buffer overflows (silent drop).

**Errors ▸**

| errno | When |
|-------|------|
| `EADDRINUSE` | Port already bound |
| `EMSGSIZE` | Datagram exceeds path MTU without fragmentation (platform-dependent send path) |

---

## 6.3.3 Unreliability and ordering

```
   sender:  D1  D2  D3
   network: D1  ✗   D3  D2  D2(duplicate)
   receiver must handle:
            • loss (timeout + retry)
            • reorder
            • duplication (IDs / dedup)
```

**Trade-offs ▸** UDP shines when stale data is worthless (live video), when you implement
your own protocol (QUIC, game state), or when one request → one response fits in one
datagram (DNS). Use TCP when you want the kernel to handle reliability (Part 6.2).

---

## 6.3.4 Connected UDP sockets

> **The call ▸** `int connect(int sockfd, const struct sockaddr *addr, socklen_t addrlen);`

On a **datagram** socket, `connect()` does **not** perform a TCP handshake. It sets a
**default peer address** so you can use `send`/`write` and `recv`/`read` instead of
`sendto`/`recvfrom`:

```c
connect(udp_fd, (struct sockaddr *)&server, sizeof server);
send(udp_fd, "ping", 4, 0);           /* always to server */
recv(udp_fd, buf, sizeof buf, 0);     /* only from connected peer (Linux) */
```

Benefits: simpler code, ICMP errors delivered as `ECONNREFUSED` on subsequent ops,
slightly faster sends (kernel caches route). You can `connect()` to change peer or
`connect(fd, NULL, 0)` on Linux to disconnect.

---

## 6.3.5 MTU and fragmentation

Typical Ethernet MTU = **1500 bytes** → UDP payload ≈ **1472 bytes** (20 B IP + 8 B UDP
header). Larger datagrams may be **IP-fragmented** (bad for loss — lose one fragment,
lose whole datagram) or rejected.

**Systems ▸** Stay under path MTU or implement path MTU discovery at application layer.
For LAN benchmarks, jumbo frames change the math. Loopback often allows larger sizes.

**Pitfall ▸** Broadcasting/multicasting with oversized payloads — fragmentation + loss =
silent failure modes. Keep DNS-sized (≤512 legacy) or modern EDNS0 limits in mind.

---

## 6.3.6 UDP echo example

```c
#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

#define PORT 9091

static void die(const char *msg) {
    perror(msg);
    exit(1);
}

int main(void) {
    int fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (fd == -1)
        die("socket");

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof addr);
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(PORT);

    if (bind(fd, (struct sockaddr *)&addr, sizeof addr) == -1)
        die("bind");

    for (;;) {
        char buf[2048];
        struct sockaddr_in peer;
        socklen_t peer_len = sizeof peer;

        ssize_t n = recvfrom(fd, buf, sizeof buf, 0,
                             (struct sockaddr *)&peer, &peer_len);
        if (n == -1) {
            if (errno == EINTR)
                continue;
            die("recvfrom");
        }

        char ip[INET_ADDRSTRLEN];
        inet_ntop(AF_INET, &peer.sin_addr, ip, sizeof ip);
        fprintf(stderr, "%zd bytes from %s:%u\n",
                n, ip, (unsigned)ntohs(peer.sin_port));

        ssize_t sent = sendto(fd, buf, (size_t)n, 0,
                              (struct sockaddr *)&peer, peer_len);
        if (sent != n)
            perror("sendto");
    }
}
```

Client one-liner test: `echo hello | nc -u 127.0.0.1 9091`

---

## Summary

- UDP is datagram-oriented: `sendto`/`recvfrom`, server `bind`, no `listen`/`accept`.
- Message boundaries preserved; undersized `recvfrom` buffers truncate and drop excess.
- Connected UDP (`connect` on datagram socket) sets default peer for `send`/`recv`.
- Respect MTU; fragmentation hurts reliability; application owns retries and ordering.

Next: [6.4 — Unix domain sockets](04-unix-domain-sockets.md)
