# 0.3 — The Syscall Mechanism & ABI

Part 0.2 established *where* the wall is. This chapter covers *how* you cross it on
x86-64 Linux: which registers carry what, what the `SYSCALL`/`SYSRET` instructions do,
how the kernel dispatches to `sys_write()` and friends, and the fast paths (vDSO) that
avoid a full trap when possible.

```
   libc wrapper                CPU                         kernel
   ─────────────               ───                         ──────
   rax = __NR_write (1)        SYSCALL  ────────────────▶  entry_SYSCALL_64
   rdi = fd                    (ring 3→0)                  sys_call_table[1]
   rsi = buf                                               └─▶ sys_write()
   rdx = count                 SYSRET   ◀────────────────   rax = bytes written
                               (ring 0→3)
```

---

## 0.3.1 The x86-64 Linux syscall ABI

When you call `write(1, "hi\n", 3)` in C, glibc's wrapper sets up registers according
to the **x86-64 Linux ABI** before executing `SYSCALL`:

| Register | Role on syscall entry |
|----------|----------------------|
| `rax` | Syscall number |
| `rdi` | 1st argument |
| `rsi` | 2nd argument |
| `rdx` | 3rd argument |
| `r10` | 4th argument (note: **not** `rcx` — `rcx` holds user `%rip` after `SYSCALL`) |
| `r8` | 5th argument |
| `r9` | 6th argument |

Return value comes back in `rax`:

- **Success:** non-negative count, descriptor, or `0`.
- **Failure:** value in `[-4095, -1]` representing `-errno` (e.g. `-EBADF` = -9).

> **The call ▸** From user space you normally never touch these registers yourself —
> libc does. The raw interface is:
>
> ```c
> #include <unistd.h>
> long syscall(long number, ...);   /* glibc extension; see unistd.h / sys/syscall.h */
> ```
>
> Example: `syscall(SYS_write, 1, "hi\n", 3);` — same register layout as above.

**Pitfall ▸** The 4th syscall argument goes in **`r10`**, not `rcx`. This differs from
the user-space function-call convention (which would use `rcx` for arg 4). If you hand-
write assembly or use `syscall()` with more than three args, remember `r10`.

---

## 0.3.2 The SYSCALL and SYSRET instructions

On 32-bit x86, Linux historically used `int 0x80` — a software interrupt that looked up
vector 0x80 in the IDT. On x86-64, Linux uses the dedicated **`SYSCALL`** / **`SYSRET`**
pair:

```
   SYSCALL (user → kernel)
   ───────────────────────
   • %cpl must be 3; target must be ring 0
   • %rip  ← MSR_LSTAR   (entry_SYSCALL_64)
   • %cs   ← MSR_STAR (kernel code segment)
   • saves user %rip in %rcx, user %rflags in %r11
   • masks flags per MSR_SFMASK (clears IF, etc.)
   • %rsp  ← per-thread kernel stack pointer

   SYSRET (kernel → user)
   ──────────────────────
   • %rip  ← %rcx
   • %rsp  ← %r11  (user stack, saved by entry code)
   • restores ring 3
```

![How a syscall is dispatched on x86-64: registers, SYSCALL, sys_call_table, SYSRET](figures/syscall-mechanism.svg)

> **Under the hood ▸** `entry_SYSCALL_64` (arch/x86/entry/entry_64.S) builds a
> `struct pt_regs` on the kernel stack, runs `syscall_enter()` (seccomp, tracing,
> audit), indexes `sys_call_table[rax]`, invokes the handler, then reverses the path.
> On return, if `%rax` is between -4095 and -1, glibc sets `errno = -rax` and returns
> -1 to your C code.

**Trade-offs ▸** `SYSCALL`/`SYSRET` is faster than `int 0x80` (no IDT lookup, fewer
pipeline flushes), but it requires careful MSR setup at boot and does not save as much
state automatically — the kernel entry stub must save/restore everything it needs.

---

## 0.3.3 Syscall numbers and the dispatch table

Every Linux syscall has a **number**. On x86-64 they are defined in:

```c
#include <asm/unistd_64.h>   /* or <sys/syscall.h> which wraps it */
/* __NR_read   0  */
/* __NR_write  1  */
/* __NR_open   2  */
/* __NR_close  3  */
/* ... ~350+ entries, kernel-version-dependent */
```

Inspect them on your system:

```bash
grep __NR_write /usr/include/asm/unistd_64.h
# or: ausyscall --dump   (if audit-tools installed)
```

The kernel holds an array of function pointers:

```
   sys_call_table[__NR_write]  →  sys_write()
   sys_call_table[__NR_read]   →  sys_read()
   sys_call_table[__NR_openat] →  sys_openat()
   ...
```

New syscalls are added across kernel versions; numbers are **stable per architecture**
but differ between x86-64, aarch64, etc. Portable code uses libc wrappers or `SYS_*`
macros, never hard-coded integers (unless you enjoy breaking on the next distro upgrade).

> **Under the hood ▸** Many `sys_*()` functions are thin wrappers around `ksys_*()` or
> `SYSCALL_DEFINE*` macros. `sys_write()` validates the fd, then calls into the VFS
> (`vfs_write` → file-specific `->write`). Part 2.2 traces that path byte by byte.

**Errors ▸** (returned as negative errno in `%rax`, translated by libc)

| `errno` | when it happens |
|---------|-------------------|
| `ENOSYS` | Syscall number not implemented (or blocked by seccomp) |
| `EPERM` | Valid syscall, caller lacks capability / permission |
| `EFAULT` | User pointer argument points to invalid/unmapped memory |
| `EINVAL` | Syscall number valid but arguments nonsense |

---

## 0.3.4 What libc actually does (write example)

A simplified picture of glibc's `write()` (actual code is in
`sysdeps/unix/sysv/linux/write.c` + architecture-specific syscall stubs):

```c
/* conceptual — real glibc uses inline asm */
ssize_t write(int fd, const void *buf, size_t count) {
    long ret;
    register long rax __asm__("rax") = __NR_write;
    register long rdi __asm__("rdi") = fd;
    register long rsi __asm__("rsi") = (long)buf;
    register long rdx __asm__("rdx") = count;
    __asm__ volatile("syscall" : "=a"(ret) : "a"(rax), "D"(rdi), "S"(rsi), "d"(rdx)
                     : "rcx", "r11", "memory");
    if (ret < 0 && ret > -4096) {
        errno = (int)-ret;
        return -1;
    }
    return (ssize_t)ret;
}
```

The `-4096` threshold is the kernel's convention: error codes are small negative
integers; successful returns of very large sizes are handled separately (rare edge case
for some syscalls).

---

## 0.3.5 The vDSO: syscalls without a trap

Not every "syscall-shaped" operation crosses the full boundary. The kernel maps a
special ELF shared object — the **vDSO** (virtual Dynamic Shared Object) — into every
process at a random address:

```bash
grep vdso /proc/self/maps
# [vdso]  — contains clock_gettime, gettimeofday, getcpu, ...
```

For `clock_gettime(CLOCK_MONOTONIC, &ts)`, glibc often calls a vDSO function that reads
the **Time Stamp Counter** and kernel-maintained data in user-readable pages — **zero
ring transition**.

```
   slow path:  clock_gettime  →  SYSCALL  →  sys_clock_gettime  (~100+ ns)
   fast path:  clock_gettime  →  vDSO stub in user space       (~20–40 ns)
```

**Systems ▸** `strace ./prog` will not show vDSO-served calls. Use `ltrace` or inspect
`/proc/self/maps` to confirm the vDSO is mapped. High-frequency timing loops should
always use `clock_gettime` (not `gettimeofday`) so glibc picks the vDSO path.

**Trade-offs ▸** The vDSO is read-only and carefully validated; you cannot add your own
entries. It covers a tiny set of kernel-exported fast paths, not general I/O.

---

## 0.3.6 The raw syscall() function

When libc has no wrapper (new kernel syscall, or you're in a minimal runtime):

```c
#include <sys/syscall.h>
#include <unistd.h>
#include <stdio.h>
#include <errno.h>

int main(void) {
    const char msg[] = "raw syscall\n";
    long n = syscall(SYS_write, STDOUT_FILENO, msg, sizeof msg - 1);
    if (n == -1) {
        perror("syscall(SYS_write)");
        return 1;
    }
    return 0;
}
```

Use `SYS_*` macros from `<sys/syscall.h>` — they expand to the correct `__NR_*` for your
architecture. This is how musl, glibc, and language runtimes bootstrap support for new
kernel features before high-level wrappers land.

**Pitfall ▸** `syscall()` is a variadic function; the compiler still sets up registers
correctly on x86-64 via inline asm inside glibc, but **calling conventions for 7+
arguments** or odd types (struct passing) may differ from what the kernel expects.
Prefer official wrappers when they exist.

---

## 0.3.7 int 0x80 vs SYSCALL (historical and practical)

| Aspect | `int 0x80` (legacy) | `SYSCALL`/`SYSRET` (x86-64 native) |
|--------|---------------------|-------------------------------------|
| Mechanism | Software interrupt, IDT vector 0x80 | Dedicated fast-syscall instructions |
| Register ABI | Different (ebx, ecx, edx, …) | rax, rdi, rsi, rdx, r10, r8, r9 |
| 64-bit args | Not native; compat layer | Full 64-bit |
| Still used? | 32-bit compat processes on x86-64 | All native 64-bit Linux programs |

You may still see `int 0x80` in `strace` output for **i386 executables** running under
`linux32`/compat. Native x86-64 binaries always use `SYSCALL`.

---

## 0.3.8 Example: tracing the full path

Compile and trace a minimal program:

```c
#include <unistd.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>

int main(void) {
    /* Path 1: libc wrapper */
    if (write(STDERR_FILENO, "via write()\n", 12) == -1) {
        perror("write");
        exit(1);
    }

    /* Path 2: raw syscall() */
    const char msg[] = "via syscall()\n";
    if (syscall(SYS_write, STDERR_FILENO, msg, sizeof msg - 1) == -1) {
        perror("syscall");
        exit(1);
    }

    /* Path 3: open + read via wrappers (multi-syscall) */
    int fd = open("/proc/self/status", O_RDONLY);
    if (fd == -1) {
        perror("open");
        exit(1);
    }
    char buf[64];
    ssize_t n = read(fd, buf, sizeof buf);
    if (n == -1) {
        perror("read");
        close(fd);
        exit(1);
    }
    if (write(STDERR_FILENO, buf, (size_t)n) != n) {
        perror("write");
        close(fd);
        exit(1);
    }
    close(fd);
    return 0;
}
```

```bash
gcc -Wall -Wextra -o trace_me trace_me.c
strace -e trace=write,open,read,close ./trace_me 2>&1 | head -20
```

You should see `write(2, ...)` twice (same `SYSCALL` mechanism underneath), then
`openat`, `read`, `close` — each line one mode switch (Part 0.2.4).

---

## Summary

- x86-64 Linux passes the syscall number in `rax` and up to six arguments in
  `rdi`, `rsi`, `rdx`, `r10`, `r8`, `r9`; the result returns in `rax`.
- `SYSCALL`/`SYSRET` replace legacy `int 0x80` on native 64-bit; the kernel entry
  point dispatches via `sys_call_table[nr]`.
- Syscall numbers live in `/usr/include/asm/unistd_64.h` (`__NR_*` / `SYS_*`).
- The vDSO serves selected calls (`clock_gettime`, etc.) entirely in user space.
- `syscall()` is the escape hatch when libc has no wrapper; prefer `SYS_*` macros.
- libc translates kernel errors: if `rax ∈ [-4095,-1]`, set `errno = -rax`, return -1
  (Part 0.4 expands error handling).

Next: [0.4 — errno & error handling](04-errno-and-error-handling.md)
