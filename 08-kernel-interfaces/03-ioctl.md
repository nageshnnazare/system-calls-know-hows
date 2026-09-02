# 8.3 — ioctl()

When `read()` and `write()` are too coarse — terminal window sizes, socket non-
blocking toggles, disk geometry, Wi-Fi scans — Unix provides **`ioctl()`**: a typed-
ish catch-all control channel on an open fd. Part 2.5 covered `fcntl`; ioctl is the
parallel path for **devices**, **sockets**, and **ttys**. It is powerful, weakly
typed, and a frequent source of portability bugs.

---

## 8.3.1 The catch-all control syscall

> **The call ▸**
> ```c
> #include <sys/ioctl.h>
>
> int ioctl(int fd, unsigned long request, ... /* arg */ );
> ```
> On success: often `0`, sometimes a non-negative driver-specific value. On failure:
> `-1`, `errno` set.

```
   read/write  ──▶  byte streams (data plane)
   ioctl       ──▶  side operations (control plane)
                    "set MTU", "get window size", "eject tray"
```

Every fd type supports a **different** request set. Passing a terminal ioctl to a
regular file fails with `ENOTTY` ("Not a typewriter" — historical name).

> **Under the hood ▸** The VFS dispatches `ioctl` to the file's `f_op->unlocked_ioctl`
> (or compat variant). Drivers switch on `request` and copy arguments with
> `copy_from_user` / `copy_to_user` (Part 0.2).

---

## 8.3.2 Request encoding: _IO / _IOR / _IOW / _IOWR

Requests are 32-bit integers built from macros in `<sys/ioctl.h>`:

```
   request bits:
   ┌──────────┬──────────┬──────────┬──────────┐
   │ direction│   size   │   type   │    nr    │
   │  2 bits  │ 14 bits  │  8 bits  │  8 bits  │
   └──────────┴──────────┴──────────┴──────────┘

   _IO(type, nr)              no argument
   _IOR(type, nr, struct)     read from kernel → user
   _IOW(type, nr, struct)     write user → kernel
   _IOWR(type, nr, struct)   both directions
```

Example — terminal window size:

```c
#include <sys/ioctl.h>
#include <unistd.h>

struct winsize ws;
if (ioctl(STDOUT_FILENO, TIOCGWINSZ, &ws) == -1) {
    perror("TIOCGWINSZ");
} else {
    /* ws.ws_col, ws.ws_row */
}
```

`'T'` is the magic type byte for terminal ioctls; `TIOCGWINSZ` is `_IOR('T', 104, struct winsize)`.

**Pitfall ▸** Wrong struct size in the macro → kernel rejects or **corrupts** stack.
Always use the macro, never hand-pick integers from old Stack Overflow posts.

---

## 8.3.3 Terminal and socket ioctls

Common terminal requests:

| request | direction | purpose |
|---------|-----------|---------|
| `TIOCGWINSZ` | read | get rows/cols |
| `TIOCSWINSZ` | write | set window size |
| `TIOCGETD` | read | line discipline |
| `TIOCSCTTY` | — | make controlling tty |

Socket-related (also available via `fcntl` / `getsockopt`):

| request | purpose |
|---------|---------|
| `FIONREAD` | bytes available to read |
| `FIONBIO` | set/clear non-blocking (int arg) |
| `SIOCGIFADDR` | get interface IP (via socket fd) |

Part 7.1 non-blocking via `FIONBIO`:

```c
int one = 1;
if (ioctl(fd, FIONBIO, &one) == -1)
    perror("FIONBIO");
```

Equivalent to `fcntl(fd, F_SETFL, flags | O_NONBLOCK)`.

---

## 8.3.4 Device control examples

Block device (`/dev/sda`) ioctls include `BLKGETSIZE64`, `BLKFLSBUF` (flush cache).
Network `SIOCSIF*` / `SIOCGIF*` configure interfaces. DRM/KMS graphics ioctls use
their own type bytes.

Pattern:

```c
struct ifreq ifr;
memset(&ifr, 0, sizeof ifr);
strncpy(ifr.ifr_name, "eth0", IFNAMSIZ - 1);

int sock = socket(AF_INET, SOCK_DGRAM, 0);  /* dummy for ioctl */
if (sock == -1) { perror("socket"); return -1; }

if (ioctl(sock, SIOCGIFFLAGS, &ifr) == -1) {
    perror("SIOCGIFFLAGS");
    close(sock);
    return -1;
}
close(sock);
```

Each subsystem documents its ioctl set in `man 4`, driver headers (`<linux/fs.h>`,
`<sys/mount.h>`), or kernel `Documentation/userspace-api/ioctl/`.

---

## 8.3.5 Why ioctl is untyped and dangerous

```
   problems with ioctl
   ───────────────────
   • request number collisions across drivers (mitigated by type byte)
   • any pointer arg — kernel must validate size + direction
   • 32-bit compat on 64-bit (compat_ioctl handlers)
   • no compile-time check that fd matches request family
   • deprecated ops linger for decades
```

Modern kernels prefer **netlink**, **sysfs attributes**, and **seccomp-safe
read/write protocols** for new features. ioctl remains entrenched for tty, socket,
and block devices.

**Pitfall ▸** Passing a stack struct with wrong layout (32 vs 64 bit, padding) —
use kernel-defined types and zero-init:

```c
struct winsize ws = {0};
```

**Pitfall ▸** `ioctl` on `O_CLOEXEC` fd from child after exec — fine; but ioctl on
wrong duplicated fd after fork without care can change parent's tty settings.

---

## 8.3.6 FIONREAD and pending data

```c
int avail = 0;
if (ioctl(fd, FIONREAD, &avail) == -1) {
    perror("FIONREAD");
} else {
    /* avail bytes in socket/pipe/tty buffer without consuming */
}
```

Useful before allocating a read buffer or deciding whether to drain in an epoll ET
handler (Part 7.2). Not a substitute for `read()` — race window between ioctl and
read as more data arrives.

---

## 8.3.7 Errors

**Errors ▸**

| errno | when |
|-------|------|
| `ENOTTY` | fd doesn't support this ioctl (wrong device type) |
| `EINVAL` | unrecognized request or bad argument |
| `EFAULT` | bad pointer (kernel couldn't copy) |
| `EPERM` | operation not permitted (caps / namespace) |
| `EINTR` | interrupted by signal — retry |

---

## Summary

- `ioctl(fd, request, argp)` is the control-plane syscall for device/tty/socket
  operations that don't fit read/write.
- Requests encode direction, size, type, and number via `_IOR`/`_IOW`/`_IOWR` macros.
- Terminal (`TIOCGWINSZ`), socket (`FIONBIO`, `FIONREAD`), and block device ioctls
  each belong to specific fd types — wrong pairing yields `ENOTTY`.
- ioctl is flexible but unsafe by design — use documented macros, zero-init structs,
  and prefer newer sysfs/netlink APIs when available.

Next: [8.4 — Tracing: strace, ftrace, perf & eBPF](04-tracing-and-perf.md)
