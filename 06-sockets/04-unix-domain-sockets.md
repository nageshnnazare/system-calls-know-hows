# 6.4 — Unix Domain Sockets

**Unix domain sockets** (`AF_UNIX`) communicate between processes on the **same host** via
kernel memory — no IP stack, no port exhaustion, often half the latency of TCP loopback.
They support stream and datagram modes like TCP/UDP, plus superpowers: **passing file
descriptors** and **peer credentials**. Part 6.1's socket model applies; addressing uses
filesystem paths or the abstract namespace.

---

## 6.4.1 AF_UNIX stream and datagram

> **The call ▸**
> ```c
> #include <sys/un.h>
>
> struct sockaddr_un {
>     sa_family_t sun_family;   /* AF_UNIX */
>     char        sun_path[108];  /* pathname or abstract name */
> };
> ```

| Type | Behavior |
|------|----------|
| `SOCK_STREAM` | Reliable byte stream (like TCP) — `listen`/`accept`/`connect` |
| `SOCK_DGRAM` | Datagram boundaries preserved (like UDP) — `sendto`/`recvfrom` |

```
   process A                    kernel                    process B
   unix stream socket ◀════ socket buffer ════▶ unix stream socket
   (no network stack traversal)
```

**Trade-offs ▸** vs TCP `127.0.0.1`: lower overhead, fd passing, credential checks.
vs shared memory (Part 3.5): socket API gives framing + fd delivery; shm wins on bulk
throughput with careful synchronization.

---

## 6.4.2 Filesystem path vs abstract namespace

**Path-bound** — bind to a path in the filesystem:

```c
struct sockaddr_un addr;
memset(&addr, 0, sizeof addr);
addr.sun_family = AF_UNIX;
snprintf(addr.sun_path, sizeof addr.sun_path, "/tmp/myapp.sock");

unlink(addr.sun_path);   /* remove stale socket file */
bind(fd, (struct sockaddr *)&addr, sizeof addr);
```

Clients `connect()` to the same path. The inode persists until `unlink` + last `close`.

**Abstract namespace** — Linux-specific; **leading NUL** in `sun_path[0]`, name in
`sun_path[1…]` (no filesystem entry):

```c
addr.sun_path[0] = '\0';
strncpy(addr.sun_path + 1, "myapp.session", sizeof addr.sun_path - 2);
bind(fd, (struct sockaddr *)&addr,
     offsetof(struct sockaddr_un, sun_path) + 1 + strlen("myapp.session"));
```

No stale files on crash; not visible in `ls`. **Pitfall ▸** Abstract sockets are
Linux-only — not portable to BSD/macOS the same way.

---

## 6.4.3 socketpair()

> **The call ▸**
> ```c
> #include <sys/socket.h>
>
> int socketpair(int domain, int type, int protocol, int sv[2]);
> ```
> **Returns:** `0` on success; **-1** + `errno`. `sv[0]` and `sv[1]` are connected
> `AF_UNIX` sockets.

```
   parent                                 child (after fork)
   sv[0] ◀══════════════════════════════▶ sv[1]
         bidirectional pipe-like channel
```

Classic pattern: `socketpair` + `fork` — parent keeps one end, child the other (Part 4.1
pipes compare). Unlike pipes, `socketpair` is **full-duplex** and supports `sendmsg` fd
passing.

```c
int sv[2];
if (socketpair(AF_UNIX, SOCK_STREAM, 0, sv) == -1) {
    perror("socketpair");
    exit(1);
}
/* sv[0] ↔ sv[1] already connected — no bind/connect */
```

---

## 6.4.4 Passing file descriptors: SCM_RIGHTS

Send an **already open fd** from one process to another via `sendmsg`/`recvmsg` and
**ancillary data** (`struct cmsghdr`).

> **The call ▸**
> ```c
> #include <sys/socket.h>
>
> ssize_t sendmsg(int sockfd, const struct msghdr *msg, int flags);
> ssize_t recvmsg(int sockfd, struct msghdr *msg, int flags);
> ```

```
   sender                              receiver
   sendmsg(data + SCM_RIGHTS fd=7)  →  recvmsg → new fd=3 (different number!)
                                       same open file description (Part 0.5)
```

Sender sketch:

```c
char byte = 'F';
struct iovec io = { .iov_base = &byte, .iov_len = 1 };

char cmsgbuf[CMSG_SPACE(sizeof(int))];
struct msghdr msg = { 0 };
msg.msg_iov = &io;
msg.msg_iovlen = 1;
msg.msg_control = cmsgbuf;
msg.msg_controllen = sizeof cmsgbuf;

struct cmsghdr *c = CMSG_FIRSTHDR(&msg);
c->cmsg_level = SOL_SOCKET;
c->cmsg_type  = SCM_RIGHTS;
c->cmsg_len   = CMSG_LEN(sizeof(int));
*(int *)CMSG_DATA(c) = fd_to_pass;

if (sendmsg(sock, &msg, 0) == -1)
    perror("sendmsg");
```

Receiver: `recvmsg`, parse `CMSG_FIRSTHDR`, copy `*(int *)CMSG_DATA(c)` — a **new**
fd in the receiving process pointing at the shared file description.

**Pitfall ▸** Must send at least one byte of regular data (some stacks require it) so
the receiver can distinguish fd-pass messages. Pass `O_CLOEXEC` fds if the child might
exec (Part 2.1).

---

## 6.4.5 SCM_CREDENTIALS

Linux can pass **process credentials** (PID, UID, GID) over `AF_UNIX` sockets for
authentication:

```c
struct ucred cred = { .pid = getpid(), .uid = getuid(), .gid = getgid() };
struct cmsghdr *c = CMSG_FIRSTHDR(&msg);
c->cmsg_level = SOL_SOCKET;
c->cmsg_type  = SCM_CREDENTIALS;
c->cmsg_len   = CMSG_LEN(sizeof cred);
memcpy(CMSG_DATA(c), &cred, sizeof cred);
```

Enable on receiver with `setsockopt(SOL_SOCKET, SO_PASSCRED, …)` and verify peer before
trusting. **Systems ▸** systemd, D-Bus, and container runtimes use this pattern.

---

## 6.4.6 Performance vs TCP loopback

Benchmarks vary by message size, but Unix sockets typically win on small messages because
data stays in-kernel without IP/TCP processing. For **large bulk transfers**, shared
memory or `splice`/`sendfile` (Part 7.4) may dominate.

| Mechanism | fd passing | cross-host | typical latency |
|-----------|------------|------------|---------------|
| TCP loopback | ✗ | ✗ (same host only in practice) | higher |
| Unix stream | ✓ SCM_RIGHTS | ✗ | lower |
| Pipe | ✗ | ✗ | similar, half-duplex |

---

## Summary

- `AF_UNIX` sockets use `sockaddr_un` — filesystem path or Linux abstract namespace.
- Stream mode mirrors TCP; datagram mode mirrors UDP; `socketpair` gives connected pairs.
- `sendmsg`/`recvmsg` with `SCM_RIGHTS` duplicate fds across processes (same open file
  description, new fd number — Part 0.5).
- `SCM_CREDENTIALS` authenticates peers on local sockets; faster than TCP loopback for
  control-plane IPC.

Next: [6.5 — Socket options](05-socket-options.md)
