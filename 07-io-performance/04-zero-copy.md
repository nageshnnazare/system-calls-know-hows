# 7.4 — Zero-copy: sendfile, splice & Friends

Every byte copied between kernel buffers and user space costs CPU cycles and cache
lines. A naive static-file HTTP server does **four** copies and **four** context
heavy trips for file→socket service. Zero-copy syscalls keep data in kernel space,
moving pages between subsystems without touching your `buf`. Part 3.3 (`mmap`) and
Part 7.5 (syscall batching) complement this chapter.

---

## 7.4.1 The naive path: read() + write()

![Zero-copy paths vs read/write copies](figures/zero-copy.svg)

```
   DISK ──▶ page cache ──▶ copy ──▶ user buf ──▶ copy ──▶ socket skbuff ──▶ NIC
            (kernel)        ▲                    ▲
                            │                    │
                         read()               write()
                         (syscall)            (syscall)
```

Four copies (DMA → cache → user → cache → DMA) and two full user/kernel round
trips per chunk. For multi-GB file serving at 10 GbE, this dominates.

```
   copy 1: disk → page cache        (DMA, unavoidable for cold cache)
   copy 2: page cache → user buf    (read)
   copy 3: user buf → socket buf    (write)
   copy 4: socket buf → NIC         (DMA)
```

Goal: eliminate copies 2 and 3.

---

## 7.4.2 sendfile()

> **The call ▸**
> ```c
> #include <sys/sendfile.h>
>
> ssize_t sendfile(int out_fd, int in_fd, off_t *offset, size_t count);
> ```
> Transfer up to `count` bytes from `in_fd` (must be readable, usually regular
> file) to `out_fd` (must be socket on Linux historically; now also file→file on
> some kernels). If `offset` non-NULL, reads from `*offset` and advances it.

```
   page cache pages ──▶ splice-like path ──▶ socket skbuff ──▶ NIC
                        (no user-space buffer)
```

> **Under the hood ▸** Kernel wires the file's page cache directly into the socket
> send path (`tcp_sendpage` / `splice` internally). User never maps the bytes.

```c
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/sendfile.h>
#include <sys/socket.h>
#include <unistd.h>

static int send_all_file(int out_fd, int in_fd) {
    off_t offset = 0;
    struct stat st;
    if (fstat(in_fd, &st) == -1) { perror("fstat"); return -1; }

    while (offset < st.st_size) {
        ssize_t n = sendfile(out_fd, in_fd, &offset,
                             (size_t)(st.st_size - offset));
        if (n == -1) {
            if (errno == EINTR) continue;
            perror("sendfile");
            return -1;
        }
        if (n == 0) break;
    }
    return 0;
}
```

**Trade-offs ▸** File must be in page cache for best results; cold reads still hit
disk. TLS encryption requires user-space plaintext — `sendfile` bypasses SSL
libraries. nginx uses `sendfile` for plain HTTP static files.

**Errors ▸**

| errno | when |
|-------|------|
| `EINVAL` | out_fd not socket (older kernels) or unsupported combo |
| `EAGAIN` | non-blocking socket not ready |
| `EPIPE` / `ECONNRESET` | peer closed |

---

## 7.4.3 splice(), vmsplice(), tee()

**splice** moves data between two fds **without** user space, via an internal
kernel pipe buffer:

> **The call ▸**
> ```c
> #include <fcntl.h>
> #define _GNU_SOURCE
> #include <unistd.h>
>
> ssize_t splice(int fd_in, loff_t *off_in, int fd_out, loff_t *off_out,
>                size_t len, unsigned int flags);
> ```

At least one fd must be a pipe. Typical pattern: file → pipe → socket (two
splices) or file → pipe (one splice) depending on kernel support.

Flags:

| flag | effect |
|------|--------|
| `SPLICE_F_MOVE` | hint: move pages instead of copy (best-effort) |
| `SPLICE_F_NONBLOCK` | non-blocking |
| `SPLICE_F_MORE` | more data coming — batch TCP segments |

**vmsplice** maps **user** pages into a pipe (opposite direction — user → kernel
pipe without copy). **tee** duplicates data in a pipe (one reader, two consumers).

```
   file fd ──splice──▶ pipe ──splice──▶ socket fd
          (kernel)         (kernel)
```

**Pitfall ▸** Forgetting the pipe intermediary — `splice` between file and socket
directly is not always supported; check `man splice` for your kernel.

---

## 7.4.4 MSG_ZEROCOPY (send path)

Since Linux 4.14, `send()`/`sendmsg()` with `MSG_ZEROCOPY` on TCP can avoid copying
user buffers into skbuffs — the NIC DMAs from pinned user pages:

```c
send(sockfd, buf, len, MSG_ZEROCOPY);
/* completion notification via SO_EE_ORIGIN_ZEROCOPY / errqueue */
```

You **must** reap completions (via `recvmsg` + `MSG_ERRQUEUE` or `SO_ZEROCOPY`)
before reusing the buffer — async ownership transfer. High complexity; wins at large
payloads and high throughput.

---

## 7.4.5 mmap-based approaches

Part 3.3's `mmap()` maps file pages into your address space:

```
   mmap file ──▶ read by touching pages (no read() syscall per chunk)
   write(sock, mapped_region, len)  ──▶ still copies to socket unless sendfile
```

`mmap` + `write` eliminates the `read()` syscall loop but **not** the copy to
socket. For read-heavy indexing (search engines scanning indices), mmap avoids
copy-to-user; for network egress, prefer `sendfile`/`splice`.

---

## 7.4.6 When zero-copy actually helps

```
   ✓  large static files → socket (CDN, HTTP file server)
   ✓  warm page cache (repeated sends of same file)
   ✓  high bandwidth, CPU-bound copy overhead visible in perf
   ✓  kernel-to-kernel proxy (splice between sockets/pipes)

   ✗  small messages (< few KB) — syscall setup dominates
   ✗  TLS/encryption in user space
   ✗  cold cache streaming (disk I/O bound, not copy bound)
   ✗  need to transform bytes (compression, JSON parsing)
```

**Systems ▸** Measure before optimizing:

```bash
perf stat -e cpu-cycles,instructions,cache-misses ./server
# compare read+write vs sendfile at your target file size
```

Profile with `strace -c` (Part 8.4): zero-copy should drop `read`/`write` counts
and user CPU.

---

## Summary

- Naive `read()` + `write()` file→socket costs four copies and two syscalls per
  chunk; zero-copy removes user-space involvement.
- `sendfile()` is the simplest file→socket path; `splice`/`vmsplice`/`tee` generalize
  kernel-side moves via pipes.
- `MSG_ZEROCOPY` avoids send-side copies but requires completion handling.
- `mmap` avoids read syscalls but not socket copies; use when access pattern is
  random read, not bulk egress.
- Zero-copy helps at large, warm, unencrypted bulk transfers — not every workload.

Next: [7.5 — The Cost of a Syscall & Batching](05-syscall-cost-and-batching.md)
