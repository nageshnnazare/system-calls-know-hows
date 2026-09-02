# 0.4 — errno & Error Handling

Almost every syscall in this guide signals failure the same way: return `-1` (or a
type-specific sentinel) and set **`errno`** — a small integer explaining *why*. Part
0.3 showed the kernel side (`rax = -errno`); this chapter covers the user-space
contract you must code against: thread-local storage, the fact that success never clears
`errno`, `EINTR` retry loops, and the exceptions that break the `-1` rule.

```
   kernel                          libc                         your code
   ──────                          ────                         ─────────
   sys_open fails                  errno = ENOENT               if (fd == -1)
   return -ENOENT in %rax    →     return -1              →     perror("open");
```

The README states this as the one rule that never changes — we now make it mechanical.

---

## 0.4.1 The -1 / errno contract

> **The call ▸**
>
> ```c
> #include <errno.h>
> extern int errno;   /* thread-local; do not declare yourself on modern glibc */
> ```
>
> After any syscall wrapper returns **indicating failure**:
> 1. Check the return value (`-1`, `MAP_FAILED`, etc.).
> 2. **Immediately** read `errno` before calling anything else.
> 3. Handle or propagate.

Typical pattern:

```c
int fd = open(path, O_RDONLY);
if (fd == -1) {
    if (errno == ENOENT) {
        /* file missing — expected? */
    } else {
        perror("open");
    }
    return -1;
}
```

Success values are syscall-specific:

| Syscall | Success return | Failure return |
|---------|----------------|----------------|
| `open()` | `fd ≥ 0` | `-1` |
| `read()` / `write()` | `byte count ≥ 0` (0 = EOF on read) | `-1` |
| `fork()` | `pid > 0` (parent), `0` (child) | `-1` |
| `mmap()` | pointer `≠ MAP_FAILED` | `MAP_FAILED` |
| `getpriority()` | **non-negative** priority | `-1` **and** `errno` set |

**Pitfall ▸** Checking `errno` when the syscall **succeeded** is meaningless — and
misleading, because success does not reset `errno` (next section).

---

## 0.4.2 errno is thread-local

`errno` is not a single global variable (though ancient Unix was). On Linux with NPTL
pthreads, each thread has its own `errno` via TLS — typically accessed as
`*__errno_location()` inside glibc.

```
   Thread A                    Thread B
   errno = EINTR               errno = 0
   (after interrupted read)    (after successful write)
```

Implications:

- A syscall failure in one thread does not clobber another thread's `errno`.
- **Signal handlers** (Part 4.2): if a handler runs between your syscall return and your
  `errno` read, and the handler calls syscalls, it may change `errno` unless you save/
  restore it in the handler. Async-signal-safe code avoids touching `errno`-setting
  functions entirely.
- Library code that fails may set `errno` on return; always capture it immediately after
  the call you care about.

---

## 0.4.3 Success never clears errno

This is one of the most common production bugs:

```c
/* BUG: errno still holds stale value from earlier failure */
if (some_helper() == 0) {       /* some_helper succeeded */
    if (errno == ENOENT) {      /* WRONG — errno was not cleared */
        ...
    }
}
```

**Rule:** Only trust `errno` **immediately** after a call that explicitly failed
(returned `-1`, `MAP_FAILED`, etc.). If you need to preserve it across further calls:

```c
int saved = errno;   /* save early if you must */
/* ... other calls that might clobber errno ... */
errno = saved;       /* restore — rare; usually just read it first instead */
```

Or use a wrapper that returns errors without going through `errno` (many modern APIs
prefer `int foo(int *err)` — but raw syscalls use `errno` by convention).

**Systems ▸** `strace` shows kernel errors as `-1 EFOO (Text)`. Your program must mirror
that discipline in C.

---

## 0.4.4 perror, strerror, and strerror_r

Turn `errno` into human-readable text:

> **The call ▸**
>
> ```c
> #include <stdio.h>
> void perror(const char *s);   /* prints "s: message\n" to stderr */
>
> #include <string.h>
> char *strerror(int errnum);   /* NOT thread-safe on all systems; glibc ok for single thread */
>
> #include <string.h>
> int strerror_r(int errnum, char *buf, size_t buflen);
> /* GNU version returns char*; POSIX version returns int — check your man page */
> ```

Example:

```c
if (close(fd) == -1) {
    perror("close");                    /* close: Bad file descriptor */
    fprintf(stderr, "%s\n", strerror(errno));
}
```

**Trade-offs ▸**

| Function | Thread-safe? | Notes |
|----------|--------------|-------|
| `perror` | Yes (uses TLS `errno` at call time) | Prints prefix you supply |
| `strerror` | glibc: uses TLS buffer per thread | Do not use in multi-threaded code on exotic libc |
| `strerror_r` | Yes (caller supplies buffer) | Preferred in libraries and threaded servers |

For a full errno list see [99-reference/errno-reference.md](../99-reference/errno-reference.md).

---

## 0.4.5 EINTR and the retry loop

Slow syscalls may return `-1` with `errno == EINTR` when a **signal** is delivered to
the thread while blocked in the kernel:

```
   read(fd, buf, n)  ──blocking──▶  kernel waits for data
                                        │
                                   signal arrives (e.g. SIGCHLD)
                                        │
                                   return -1, errno = EINTR
```

Many syscalls are **restartable** — you should retry unless you intentionally use
signals to interrupt I/O:

```c
ssize_t read_all(int fd, void *buf, size_t count) {
    size_t total = 0;
    char *p = buf;
    while (total < count) {
        ssize_t n = read(fd, p + total, count - total);
        if (n == -1) {
            if (errno == EINTR)
                continue;           /* retry — signal interrupted, not a real error */
            return -1;
        }
        if (n == 0)
            break;                  /* EOF */
        total += (size_t)n;
    }
    return (ssize_t)total;
}
```

**Errors ▸**

| `errno` | when it happens |
|---------|-------------------|
| `EINTR` | Slow syscall interrupted by signal handler |
| `EAGAIN` / `EWOULDBLOCK` | Non-blocking fd would block (Part 7.1) |
| `EBADF` | Invalid fd (already closed, or never opened) |

> **Under the hood ▸** With `SA_RESTART` set in `sigaction()` (Part 4.2), some syscalls
> are automatically restarted by the kernel and never surface `EINTR` to user space.
> Without it, you must handle `EINTR` explicitly — which is why robust libraries always
> retry.

**Pitfall ▸** Do not retry blindly on every error — only on `EINTR` (and sometimes
`EAGAIN` for non-blocking). Retrying on `EINVAL` or `EBADF` spins forever.

---

## 0.4.6 Calls with different sentinels

Not everything uses `-1`:

### mmap()

> **The call ▸**
>
> ```c
> #include <sys/mman.h>
> void *mmap(void *addr, size_t length, int prot, int flags, int fd, off_t offset);
> /* failure: MAP_FAILED ((void *)-1), NOT NULL */
> ```

```c
void *p = mmap(NULL, size, PROT_READ, MAP_PRIVATE, fd, 0);
if (p == MAP_FAILED) {
    perror("mmap");
    return -1;
}
/* p may legitimately be NULL on some rare mappings — still check MAP_FAILED only */
```

Part 3.3 covers `mmap` in depth.

### getpriority()

Returns a **non-negative** priority (0–40, lower = higher priority on Linux). On error
it returns `-1` **and** sets `errno`:

```c
#include <sys/resource.h>
#include <errno.h>
#include <stdio.h>

errno = 0;
int pri = getpriority(PRIO_PROCESS, 0);
if (pri == -1 && errno != 0) {
    perror("getpriority");
}
```

You **must** zero or check `errno` before the call — because a legitimate priority value
can be `-1` on some systems (Linux uses 0–40, but portable code clears `errno` first).

---

## 0.4.7 A robust TEMP_FAILURE_RETRY wrapper

glibc defines a macro (GNU extension):

```c
#include <unistd.h>   /* TEMP_FAILURE_RETRY on glibc */
ssize_t n = TEMP_FAILURE_RETRY(read(fd, buf, sizeof buf));
```

For portable code or when you want explicit control:

```c
#include <errno.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>

#define RETRY_ON_EINTR(expr) \
    ({ \
        __typeof__(expr) _ret; \
        do { \
            _ret = (expr); \
        } while (_ret == -1 && errno == EINTR); \
        _ret; \
    })

static ssize_t write_full(int fd, const void *buf, size_t count) {
    const char *p = buf;
    size_t left = count;
    while (left > 0) {
        ssize_t n = RETRY_ON_EINTR(write(fd, p, left));
        if (n == -1)
            return -1;
        p += n;
        left -= (size_t)n;
    }
    return (ssize_t)count;
}

int main(void) {
    int fd = open("/tmp/errno_demo.txt", O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd == -1) {
        perror("open");
        return 1;
    }

    const char msg[] = "errno handling demo\n";
    if (write_full(fd, msg, sizeof msg - 1) == -1) {
        perror("write_full");
        close(fd);
        return 1;
    }

    if (RETRY_ON_EINTR(close(fd)) == -1) {
        perror("close");
        return 1;
    }
    return 0;
}
```

Compile: `gcc -Wall -Wextra -o errno_demo errno_demo.c`

---

## Summary

- Syscall failure: return `-1` (or sentinel like `MAP_FAILED`) and set thread-local
  `errno`; check the return value first, then read `errno` immediately.
- Successful calls **do not** clear `errno` — stale values are a common bug.
- Use `perror`/`strerror_r` for messages; prefer `strerror_r` in threaded/library code.
- Retry on `EINTR` for slow syscalls; consider `SA_RESTART` (Part 4.2) but do not rely
  on it exclusively.
- Exceptions: `mmap` → `MAP_FAILED`; `getpriority` → check `errno` when result is `-1`.
- Wrap retries in `TEMP_FAILURE_RETRY` or an explicit loop — production I/O always does.

Next: [0.5 — File descriptors: the core abstraction](05-file-descriptors.md)
