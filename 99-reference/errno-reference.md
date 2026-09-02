# errno Reference

Comprehensive lookup for the `errno` values you will encounter on Linux when system
calls fail. For the full failure contract — check return value first, read `errno`
immediately, success never clears stale values — see
[Part 0.4 — errno & error handling](../00-foundations/04-errno-and-error-handling.md).

---

## The -1 / errno contract (quick recap)

Almost every libc syscall wrapper follows the same pattern:

```c
ssize_t n = read(fd, buf, count);
if (n == -1) {
    /* errno is valid *only now* — capture before other calls */
    if (errno == EINTR) { /* retry? */ }
    else { perror("read"); }
}
```

On the kernel side, failure is encoded as a negative errno in `%rax`; libc translates
that to `return -1; errno = …`. Exceptions (`mmap` → `MAP_FAILED`, `getpriority`
ambiguous `-1`) are documented in Part 0.4 and in the per-syscall **Errors ▸** tables
throughout the guide.

`errno` is **thread-local** (TLS). Another thread's syscalls do not clobber yours, but
signal handlers and library calls between your failure return and your `errno` read can.

---

## errno values (Linux / glibc on x86-64)

Numeric values below are the usual Linux x86-64 assignments from `<errno.h>`. Portable
code should always compare the symbolic constants, not hard-coded integers.

| Symbol | # | Meaning | Typical syscalls |
|--------|---|---------|------------------|
| `EPERM` | 1 | Operation not permitted (missing capability or policy) | `kill`, `mount`, `setuid`, `sched_setscheduler`, `mlock` |
| `ENOENT` | 2 | No such file, directory, or IPC object | `open`, `stat`, `unlink`, `msgget`, `semget` |
| `ESRCH` | 3 | No such process (PID does not exist or already reaped) | `kill`, `waitpid`, `ptrace`, `getpriority` |
| `EINTR` | 4 | Slow syscall interrupted by signal before completion | `read`, `write`, `connect`, `accept`, `poll`, `nanosleep` |
| `EIO` | 5 | I/O error (driver/hardware/filesystem failure) | `read`, `write`, `fsync`, `ioctl` |
| `ENXIO` | 6 | No such device or address (special file / seek past end) | `lseek`, `read` on certain devices |
| `E2BIG` | 7 | Argument list too long | `execve` |
| `ENOEXEC` | 8 | Exec format error (not a valid executable) | `execve` |
| `EBADF` | 9 | Bad file descriptor (closed, never opened, wrong type) | `read`, `write`, `close`, `fcntl`, `epoll_ctl` |
| `ECHILD` | 10 | No child processes to wait for | `wait`, `waitpid` |
| `EAGAIN` | 11 | Resource temporarily unavailable; try again later | Non-blocking `read`/`write`, `fork` under `RLIMIT_NPROC`, `flock` with `LOCK_NB` |
| `EWOULDBLOCK` | 11 | Same numeric value as `EAGAIN` on Linux | Same as `EAGAIN` |
| `ENOMEM` | 12 | Cannot allocate kernel memory for the operation | `fork`, `mmap`, `malloc` via `brk`, `socket` |
| `EACCES` | 13 | Permission denied (DAC, mount options, credentials) | `open`, `execve`, `connect` to low port without `CAP_NET_BIND_SERVICE` |
| `EFAULT` | 14 | Invalid user-space pointer passed to kernel | Any syscall copying to/from user buffer |
| `ENOTBLK` | 15 | Block device required | `mount` on non-block source |
| `EBUSY` | 16 | Resource busy (in use, mounted, locked) | `umount`, `unlink` of busy file, `ioctl` on active device |
| `EEXIST` | 17 | File/object already exists | `open` with `O_CREAT\|O_EXCL`, `mkdir`, `link` |
| `EXDEV` | 18 | Cross-device link not permitted | `link`, `rename` across filesystems |
| `ENODEV` | 19 | No such device | `open` of missing `/dev` node, `ioctl` on wrong fd type |
| `ENOTDIR` | 20 | Component of path is not a directory | `open("file/sub", …)`, `chdir` |
| `EISDIR` | 21 | Is a directory (operation needs regular file) | `open` with `O_WRONLY` on directory (without `O_DIRECTORY`) |
| `EINVAL` | 22 | Invalid argument (flags, size, state) | Nearly every syscall when args are wrong |
| `ENFILE` | 23 | System-wide open file table full | `open`, `socket`, `pipe` |
| `EMFILE` | 24 | Per-process fd table full (`RLIMIT_NOFILE`) | `open`, `dup`, `accept` |
| `ENOTTY` | 25 | Not a tty (ioctl inappropriate for fd type) | `ioctl` on pipe/file, `tcgetattr` on non-terminal |
| `ETXTBSY` | 26 | Text file busy (executable mapped and being written) | `write` to running binary, `unlink` of executing file |
| `EFBIG` | 27 | File too large (exceeds size limit or filesystem max) | `write`, `lseek`, `ftruncate` |
| `ENOSPC` | 28 | No space left on device | `write`, `mkdir`, `mmap` file extension |
| `ESPIPE` | 29 | Illegal seek (fd is not seekable — pipe, socket) | `lseek` on pipe/socket |
| `EROFS` | 30 | Read-only filesystem | `write`, `unlink`, `mkdir` on ro mount |
| `EMLINK` | 31 | Too many hard links to file | `link` |
| `EPIPE` | 32 | Broken pipe (no readers on write end) | `write` to pipe/socket with readers gone; also triggers `SIGPIPE` |
| `EDOM` | 33 | Math argument out of domain (libc math, rare in syscalls) | — |
| `ERANGE` | 34 | Result too large (libc math) | — |
| `EDEADLK` | 35 | Resource deadlock avoided (e.g. file locking) | `fcntl` advisory lock would deadlock |
| `ENAMETOOLONG` | 36 | Path or filename too long | `open`, `mkdir`, `execve` |
| `ENOLCK` | 37 | No record locks available (System V locks exhausted) | `fcntl` locks |
| `ENOSYS` | 38 | Function not implemented (missing syscall or driver) | Obsolete or optional syscalls, old kernels |
| `ENOTEMPTY` | 39 | Directory not empty | `rmdir` |
| `ELOOP` | 40 | Too many symbolic links (loop or depth limit) | `open`, `stat` resolving symlinks |
| `ENOMSG` | 42 | No message of desired type | `msgrcv` |
| `EIDRM` | 43 | Identifier removed (IPC object deleted) | `msgsnd`, `msgrcv`, `semop` |
| `ECHRNG` | 44 | Channel number out of range | Device ioctls |
| `EL2NSYNC` | 45 | Level 2 not synchronized | Obsolete |
| `EL3HLT` | 46 | Level 3 halted | Obsolete |
| `EL3RST` | 47 | Level 3 reset | Obsolete |
| `ELNRNG` | 48 | Link number out of range | Obsolete |
| `EUNATCH` | 49 | Protocol driver not attached | Obsolete |
| `ENOCSI` | 50 | No CSI structure available | Obsolete |
| `EL2HLT` | 51 | Level 2 halted | Obsolete |
| `EBADE` | 52 | Invalid exchange | Obsolete |
| `EBADR` | 53 | Invalid request descriptor | Obsolete |
| `EXFULL` | 54 | Exchange full | Obsolete |
| `ENOANO` | 55 | No anode | Obsolete |
| `EBADRQC` | 56 | Invalid request code | Obsolete |
| `EBADSLT` | 57 | Invalid slot | Obsolete |
| `EBFONT` | 59 | Bad font file format | Obsolete |
| `ENOSTR` | 60 | Device not a stream | STREAMS (rare on Linux) |
| `ENODATA` | 61 | No data available | STREAMS |
| `ETIME` | 62 | Timer expired | STREAMS |
| `ENOSR` | 63 | Out of streams resources | STREAMS |
| `ENONET` | 64 | Machine is not on the network | Obsolete |
| `ENOPKG` | 65 | Package not installed | Obsolete |
| `EREMOTE` | 66 | Object is remote | NFS / distributed fs |
| `ENOLINK` | 67 | Link has been severed | STREAMS |
| `EADV` | 68 | Advertise error | Obsolete |
| `ESRMNT` | 69 | Srmount error | Obsolete |
| `ECOMM` | 70 | Communication error on send | Obsolete |
| `EPROTO` | 71 | Protocol error | Socket layer |
| `EMULTIHOP` | 72 | Multihop attempted | NFS |
| `EDOTDOT` | 73 | RFS specific error | Obsolete |
| `EBADMSG` | 74 | Not a data message | STREAMS |
| `EOVERFLOW` | 75 | Value too large for defined data type | `stat` on huge file with 32-bit fields, `read` count overflow |
| `ENOTUNIQ` | 76 | Name not unique on network | Obsolete |
| `EBADFD` | 77 | File descriptor in bad state | `accept` on unconnected socket, fcntl lock misuse |
| `EREMCHG` | 78 | Remote address changed | Obsolete |
| `ELIBACC` | 79 | Cannot access shared library | Dynamic linker |
| `ELIBBAD` | 80 | Accessing corrupted shared library | Dynamic linker |
| `ELIBSCN` | 81 | `.lib` section corrupted | Dynamic linker |
| `ELIBMAX` | 82 | Too many shared libraries | Dynamic linker |
| `ELIBEXEC` | 83 | Cannot exec shared library directly | Dynamic linker |
| `EILSEQ` | 84 | Illegal byte sequence | `iconv`, locale |
| `ERESTART` | 85 | Interrupted system call should be restarted | Internal kernel restart (rare in user-visible errno) |
| `ESTRPIPE` | 86 | Streams pipe error | STREAMS |
| `EUSERS` | 87 | Too many users | Quota / licensing (rare) |
| `ENOTSOCK` | 88 | Operation on non-socket | `bind`, `listen` on regular file fd |
| `EDESTADDRREQ` | 89 | Destination address required | `sendto` without address on unconnected UDP |
| `EMSGSIZE` | 90 | Message too long | `send` datagram exceeds path MTU / socket buffer |
| `EPROTOTYPE` | 91 | Protocol wrong type for socket | `socket` domain/type mismatch |
| `ENOPROTOOPT` | 92 | Protocol not available | `setsockopt` unknown option |
| `EPROTONOSUPPORT` | 93 | Protocol not supported | `socket` |
| `ESOCKTNOSUPPORT` | 94 | Socket type not supported | `socket` |
| `EOPNOTSUPP` | 95 | Operation not supported on socket (or `ENOTSUP`) | `listen` on UDP, `accept` on non-listening fd |
| `ENOTSUP` | 95 | Same as `EOPNOTSUPP` on Linux | Same |
| `EPFNOSUPPORT` | 96 | Protocol family not supported | `socket` |
| `EAFNOSUPPORT` | 97 | Address family not supported | `socket`, `bind` |
| `EADDRINUSE` | 98 | Address already in use | `bind`, `connect` (local port taken) |
| `EADDRNOTAVAIL` | 99 | Cannot assign requested address | `bind` to non-local IP, ephemeral port exhaustion |
| `ENETDOWN` | 100 | Network is down | `send`, `connect` |
| `ENETUNREACH` | 101 | Network unreachable | `connect`, routing failure |
| `ENETRESET` | 102 | Network dropped connection on reset | `send` after network reset |
| `ECONNABORTED` | 103 | Software caused connection abort | `accept` after aborted handshake |
| `ECONNRESET` | 104 | Connection reset by peer | `read`, `write`, `send`, `recv` on TCP |
| `ENOBUFS` | 105 | No buffer space available | `socket`, high load on network stack |
| `EISCONN` | 106 | Transport endpoint already connected | `connect` on connected socket |
| `ENOTCONN` | 107 | Transport endpoint not connected | `send` on unconnected socket |
| `ESHUTDOWN` | 108 | Cannot send after shutdown | `send` after `shutdown(SHUT_WR)` |
| `ETOOMANYREFS` | 109 | Too many references (cannot splice) | Obsolete |
| `ETIMEDOUT` | 110 | Connection timed out | `connect`, `read` with `SO_RCVTIMEO`, blocking ops |
| `ECONNREFUSED` | 111 | Connection refused (nothing listening / RST) | `connect` |
| `EHOSTDOWN` | 112 | Host is down | `send`, routing |
| `EHOSTUNREACH` | 113 | No route to host | `connect`, `send` |
| `EALREADY` | 114 | Operation already in progress | Non-blocking `connect` completing |
| `EINPROGRESS` | 115 | Operation now in progress | Non-blocking `connect` started, not finished |
| `ESTALE` | 116 | Stale NFS file handle | NFS client |
| `EUCLEAN` | 117 | Structure needs cleaning | Filesystem-specific |
| `ENOTNAM` | 118 | Not a XENIX named type file | Obsolete |
| `ENAVAIL` | 119 | No XENIX semaphores available | Obsolete |
| `EISNAM` | 120 | Is a named type file | Obsolete |
| `EREMOTEIO` | 121 | Remote I/O error | NFS / block layer |
| `EDQUOT` | 122 | Quota exceeded | `write` on quota-enabled fs |
| `ENOMEDIUM` | 123 | No medium found | Removable media |
| `EMEDIUMTYPE` | 124 | Wrong medium type | Removable media |
| `ECANCELED` | 125 | Operation canceled | AIO, `pthread_cancel`, `timerfd` |
| `ENOKEY` | 126 | Required key not available | Keyring |
| `EKEYEXPIRED` | 127 | Key has expired | Keyring |
| `EKEYREVOKED` | 128 | Key has been revoked | Keyring |
| `EKEYREJECTED` | 129 | Key was rejected by service | Keyring |
| `EOWNERDEAD` | 130 | Owner died (robust mutex) | `pthread_mutex` / futex robust |
| `ENOTRECOVERABLE` | 131 | State not recoverable (robust mutex) | `pthread_mutex` after owner death |
| `ERFKILL` | 132 | Operation prevented by RF-kill | Wireless interfaces |
| `EHWPOISON` | 133 | Memory page has hardware error | `read`, fault on poisoned page |

For human-readable text: `perror("tag")`, `strerror(errno)`, or thread-safe
`strerror_r(3)`.

---

## EINTR — interrupted system calls

`EINTR` means a **signal was delivered** while the thread was blocked inside the
kernel waiting for a slow operation — not that the operation permanently failed.

```
   read(fd, buf, n)  ──blocking──▶  kernel waits
                                        │
                                   signal (e.g. SIGCHLD, SIGWINCH)
                                        │
                                   return -1, errno = EINTR
```

**When to retry:** For idempotent or restart-safe syscalls (`read`, `write`, `close`,
`connect` in some setups, `poll`, `nanosleep`), loop on `EINTR` unless you
*intentionally* use signals to break out of I/O.

```c
ssize_t n;
do {
    n = read(fd, buf, count);
} while (n == -1 && errno == EINTR);
```

**When not to retry blindly:** If the syscall is not restart-safe or partial progress
occurred, consult the man page. Do **not** retry on `EINVAL`, `EBADF`, etc.

**`SA_RESTART`:** Setting `SA_RESTART` in `sigaction()` (Part 4.2) asks the kernel to
automatically restart certain syscalls so `EINTR` never reaches user space. Robust
libraries still handle `EINTR` explicitly — do not rely on `SA_RESTART` alone.

**glibc helper:** `TEMP_FAILURE_RETRY(expr)` retries once on `EINTR` (GNU extension).

See [Part 0.4.5](../00-foundations/04-errno-and-error-handling.md) and
[Part 4.2](../04-ipc/02-signals.md).

---

## EAGAIN / EWOULDBLOCK — non-blocking I/O

On Linux, `EAGAIN` and `EWOULDBLOCK` are the **same value** (11). They mean: the
operation would block, but the fd is in **non-blocking** mode (or the resource is
temporarily unavailable).

Typical cases:

| Situation | Example |
|-----------|---------|
| Non-blocking read, no data yet | `fcntl(fd, F_SETFL, O_NONBLOCK)` then `read` → `EAGAIN` |
| Non-blocking write, send buffer full | `write` on busy socket |
| Non-blocking connect in progress | First `connect` returns `EINPROGRESS`; later `EAGAIN` on incomplete path |
| `accept` with no pending connections | Listening socket + `O_NONBLOCK` |
| `fork` under process limit | Transient — retry or backoff |
| `flock(..., LOCK_NB)` | Lock held by another process |

**Pattern for event-driven servers** (Part 7.1):

```c
ssize_t n = read(fd, buf, sizeof buf);
if (n == -1 && (errno == EAGAIN || errno == EWOULDBLOCK))
    return;   /* not ready — wait for epoll EPOLLIN, then retry */
if (n == -1) { perror("read"); /* real error */ }
```

Do **not** spin in a tight loop on `EAGAIN` — that burns CPU. Register the fd with
`poll`/`epoll`/`io_uring` and retry when the reactor says the fd is ready.

Distinguish:

| errno | Meaning | Action |
|-------|---------|--------|
| `EINTR` | Signal interrupted blocking call | Retry (usually) |
| `EAGAIN` | Non-blocking would block | Wait for readiness, then retry |
| `EINPROGRESS` | Non-blocking `connect` started | `select`/`poll` for writability, check `SO_ERROR` |

See [Part 7.1 — Blocking vs non-blocking I/O](../07-io-performance/01-blocking-nonblocking.md).

---

Back to [README](../README.md)
