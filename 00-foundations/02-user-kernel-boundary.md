# 0.2 — The User/Kernel Boundary

Part 0.1 introduced the wall: your program runs in ring 3, the kernel in ring 0, and a
system call is the only controlled crossing. This chapter goes deeper into **why** that
wall is enforced by hardware, how virtual memory splits user from kernel space, what
actually happens when the CPU changes mode, and how that differs from switching between
processes.

```
   ring 3 (user)  ═══════════════════════════════════════  ring 0 (kernel)
        │                                                        │
        │  ordinary loads/stores, branches, arithmetic           │  MMU programming,
        │  ✓ allowed in user space                               │  I/O ports, interrupt
        │                                                        │  controllers, page tables
        │  privileged instructions, kernel VA access             │
        │  ✗ CPU faults immediately                              │
        └──────────────── SYSCALL / SYSRET ──────────────────────┘
                              mode switch
```

---

## 0.2.1 Privilege rings: ring 0 vs ring 3

x86 defines four privilege levels (rings 0–3). Linux uses only two:

```
   ring 0  — kernel mode     drivers, scheduler, VFS, page tables, interrupt handlers
   ring 3  — user mode       your process, libc, every application binary
   rings 1,2 — unused on Linux (historical x86 baggage)
```

The **Current Privilege Level (CPL)** is encoded in the low bits of `%cs` (the code
segment register). When CPL = 3, the CPU refuses to execute instructions that could
reconfigure the machine: `mov cr3`, `cli`/`sti`, `in`/`out` to arbitrary I/O ports,
direct MMU manipulation, and jumps to kernel addresses.

> **The core idea ▸** Privilege is not a software convention the kernel politely
> enforces — it is a **hardware gate**. Attempt a privileged operation from ring 3 and
> the CPU raises **#GP** (general protection fault) before any kernel code runs. The
> only legitimate escalation path is the syscall trap (Part 0.3).

**Systems ▸** You cannot "call into the kernel" like a normal function. Kernel text is
not mapped executable in your page tables (with narrow exceptions like the vDSO — see
Part 0.3). Even if you knew a kernel function's address, jumping there from user space
would fault.

---

## 0.2.2 Why hardware enforces the boundary

Three mechanisms cooperate:

```
   ┌─────────────────────────────────────────────────────────────────┐
   │  1. PRIVILEGE LEVEL (CPL in %cs)                                 │
   │     privileged instructions fault in ring 3                      │
   ├─────────────────────────────────────────────────────────────────┤
   │  2. PAGE TABLES (PTE flags: U/S bit, NX, read/write)             │
   │     user pages marked User; kernel pages marked Supervisor-only  │
   │     user code cannot read/write/execute kernel mappings          │
   ├─────────────────────────────────────────────────────────────────┤
   │  3. SYSCALL ENTRY POINT (MSR_LSTAR on x86-64)                    │
   │     SYSCALL instruction jumps ONLY to the address the kernel     │
   │     programmed — not to arbitrary kernel code                    │
   └─────────────────────────────────────────────────────────────────┘
```

Without hardware enforcement, a single buffer overflow could reprogram the disk
controller or read every process's memory. The wall is the foundation of **process
isolation** and **multi-tenancy** — the same reason containers (Part 8.5) and seccomp
(Part 8.6) build on top of it rather than replace it.

**Pitfall ▸** Do not confuse "running as root" (UID 0 in user space) with ring 0. A
root-owned process is still ring 3. It gets *fewer permission checks* on some syscalls
(e.g. `open("/etc/shadow")`), but it still cannot touch hardware directly or read
kernel memory without asking via a syscall.

---

## 0.2.3 Virtual memory split: user vs kernel address ranges

On x86-64 Linux, each process has its own page tables, but the layout is standardized:

```
   high addresses
   ┌──────────────────────────────────────────┐ 0xFFFF_FFFF_FFFF_FFFF
   │  KERNEL SPACE (supervisor-only)           │
   │  • not accessible from ring 3             │
   │  • shared across all processes            │
   │  • direct map of physical RAM (lowmem)    │
   ├──────────────────────────────────────────┤ ~0xFFFF_8000_0000_0000
   │  canonical hole (non-canonical addresses) │
   ├──────────────────────────────────────────┤ 0x0000_7FFF_FFFF_FFFF
   │  USER SPACE (ring 3)                      │
   │  • stack (high)                           │
   │  • mmap regions                           │
   │  • heap (brk)                             │
   │  • .bss / .data / .text (low)             │
   └──────────────────────────────────────────┘ 0x0000_0000_0000_0000
   low addresses
```

![The system-call boundary: user space above, kernel space below, SYSCALL as the controlled door](figures/syscall-boundary.svg)

The **upper half** of the 64-bit address space is reserved for the kernel. User code
that dereferences a pointer into that range gets a **page fault** (`SIGSEGV`), not a
kernel data leak. Meltdown-class bugs were precisely about breaking this guarantee on
some CPUs — which is why KPTI (Kernel Page Table Isolation) added an extra page-table
switch cost to every syscall on affected systems.

> **Under the hood ▸** On syscall entry the kernel switches `%cr3` to its own page
> tables (or a combined user+kernel set depending on KPTI configuration), so kernel
> code can access both its own data structures and the calling process's user buffers
> (for `read`/`write` copy_to/from_user). On `SYSRET`, `%cr3` switches back so user
> code sees only its own mappings.

Part 3.1 dissects the user portion of this map in detail (heap, stack, mmap).

---

## 0.2.4 Mode switch vs context switch

These terms are often conflated. They are different operations with different costs:

```
   MODE SWITCH (same process, ring 3 → ring 0 → ring 3)
   ─────────────────────────────────────────────────────
   Process A (ring 3)  ──SYSCALL──▶  kernel (ring 0)  ──SYSRET──▶  Process A (ring 3)
   • same PID, same page tables (modulo KPTI flip)
   • same virtual address space
   • swap user stack → kernel stack → user stack
   • ~100–300 ns overhead (Part 0.1.3)

   CONTEXT SWITCH (different processes, both via kernel)
   ─────────────────────────────────────────────────────
   Process A (ring 3)  ──SYSCALL/block──▶  kernel  ──schedule──▶  Process B (ring 3)
   • different PID, different page tables (%cr3 change)
   • save A's full register set + FPU/SSE state
   • restore B's register set
   • flush TLB entries for the old address space
   • microseconds, not nanoseconds
```

| Event | What changes | Typical cost |
|-------|--------------|--------------|
| Mode switch | CPL, stack pointer, some MSRs | ~100–300 ns |
| Context switch | `%cr3`, all GPRs, FPU, run queue | ~1–10 µs |

A syscall that blocks (e.g. `read()` on an empty pipe) causes **both**: first a mode
switch into the kernel, then eventually a context switch to another runnable process.

**Trade-offs ▸** This is why non-blocking I/O + `epoll` (Part 6.6, Part 7.2) matters:
fewer blocking syscalls means fewer opportunities for the scheduler to swap you out.

---

## 0.2.5 The kernel stack per thread

User threads share an address space but each has its own **kernel stack**. When
`SYSCALL` fires:

```
   BEFORE SYSCALL                         AFTER SYSCALL (in kernel)
   ┌─────────────────────┐               ┌─────────────────────┐
   │ user stack (ring 3) │               │ user stack (unused) │
   │  [local vars]       │               ├─────────────────────┤
   │  [return addresses] │               │ kernel stack (ring 0)│
   └─────────────────────┘               │  [saved user regs]  │
   %rsp → user stack top                 │  [struct pt_regs]   │
                                         │  [kernel frames]    │
                                         └─────────────────────┘
                                         %rsp → kernel stack top
```

The hardware `SYSCALL`/`SYSRET` mechanism on x86-64 uses MSRs (`STAR`, `LSTAR`,
`SFMASK`) to atomically:

1. Load `%rsp` from the per-CPU/per-thread **kernel stack pointer** (stored in the
   thread's `task_struct`).
2. Push user `%rip`, `%cs`, `%rflags`, `%rsp` onto that kernel stack.
3. Jump to `entry_SYSCALL_64` (Part 0.3).

The kernel **must not** use the user stack while in ring 0 — user `%rsp` could point
anywhere, including unmapped or attacker-controlled memory.

> **Under the hood ▸** Linux allocates a fixed-size kernel stack per thread (typically
> 8–16 KiB on x86-64, plus guard pages). Overflowing it (deep recursion in a syscall
> handler, or huge `alloca` in kernel code) corrupts adjacent kernel memory — a kernel
> bug, not something your program triggers directly, but it explains why kernel code
> is paranoid about stack usage.

---

## 0.2.6 Preemption and where the boundary matters

While your thread runs in ring 3, the kernel can **preempt** it via timer interrupts:

```
   user code running (ring 3)
        │
        │  timer IRQ → CPU enters ring 0 in interrupt context
        ▼
   kernel interrupt handler
        │
        │  "has this thread's time slice expired?"
        ▼
   maybe schedule() → context switch to another process
        │
        ▼
   eventually return to user (maybe a different process)
```

Key points:

- **Preemption can happen between any two user-space instructions** (unless disabled
  in kernel, or the thread holds a spinlock in kernel context).
- Syscall handlers run in **process context** (can sleep, can be preempted after
  returning from critical sections).
- Interrupt handlers run in **interrupt context** (must not sleep — Part 4.2 on signals
  touches this boundary).

**Pitfall ▸** Assuming your user-space code runs atomically without locks because "no
other thread is in this function" is wrong. Another thread in the same process, or
preemption followed by another process touching shared memory (via `mmap(MAP_SHARED)`,
Part 3.5), can interleave freely. The boundary protects the *kernel* from you; it does
not serialize your threads.

---

## 0.2.7 Observing the boundary

You can see mode switches in `strace` (every line is one crossing — Part 0.1.5). For
deeper inspection:

```bash
# Count syscalls (each is a mode switch)
strace -c ./myprogram

# See kernel/user stack traces together (needs debug symbols)
perf record -g ./myprogram && perf report
```

For the virtual memory split on your machine:

```bash
cat /proc/self/maps    # user mappings only — kernel half never appears here
```

---

## 0.2.8 Example: touching the boundary safely

This program demonstrates that user code cannot peek at kernel addresses, but syscalls
work normally:

```c
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <signal.h>
#include <setjmp.h>

static sigjmp_buf env;

static void segv_handler(int sig) {
    (void)sig;
    siglongjmp(env, 1);
}

int main(void) {
    struct sigaction sa = { .sa_handler = segv_handler };
    sigemptyset(&sa.sa_mask);
    if (sigaction(SIGSEGV, &sa, NULL) == -1) {
        perror("sigaction");
        return 1;
    }

    /* Attempt to read a canonical kernel-range address from user space. */
    volatile char *kernel_ptr = (char *)0xffff880000000000UL;
    if (sigsetjmp(env, 1) == 0) {
        (void)*kernel_ptr;          /* triggers SIGSEGV — hardware boundary */
        fprintf(stderr, "unexpected: read kernel memory\n");
        return 1;
    }
    fprintf(stderr, "✓ kernel address faulted as expected (SIGSEGV)\n");

    /* Same process, legitimate kernel access via syscall: */
    int fd = open("/etc/hostname", O_RDONLY);
    if (fd == -1) {
        perror("open");
        return 1;
    }
    char hostname[256];
    ssize_t n = read(fd, hostname, sizeof hostname - 1);
    if (n == -1) {
        perror("read");
        close(fd);
        return 1;
    }
    close(fd);
    hostname[n] = '\0';
    printf("✓ syscall succeeded: %s", hostname);
    return 0;
}
```

Compile with `gcc -Wall -Wextra -o boundary boundary.c`. The kernel pointer read faults;
the `read()` syscall crosses the wall and succeeds.

---

## Summary

- Ring 0 (kernel) vs ring 3 (user) is enforced by the CPU's CPL, page-table permission
  bits, and the fixed syscall entry point — not by software policy alone.
- The upper canonical half of x86-64 virtual memory is kernel-only; user dereferences
  there fault immediately.
- A **mode switch** (syscall) stays in the same process and costs ~100–300 ns; a
  **context switch** changes processes, page tables, and full CPU state — much more
  expensive.
- Each thread has a dedicated kernel stack; `SYSCALL` swaps to it atomically.
- Preemption can occur in user space at any instruction boundary; the privilege wall
  protects the kernel from processes, not threads from each other.

Next: [0.3 — The syscall mechanism & ABI](03-syscall-mechanism.md)
