# Glossary

Alphabetized definitions for terms used throughout this guide. Each entry links to
the chapter where the concept is developed with diagrams and examples.

---

## A

**ABI (Application Binary Interface)** — The machine-level contract between compiled
code and the OS: register assignments for syscall arguments, struct layouts, calling
conventions, and errno encoding. On x86-64 Linux, syscall number goes in `%rax`, args in
`%rdi/%rsi/%rdx/%r10/%r8/%r9`. Breaking the ABI requires recompiling — unlike an API,
which is source-level. See [Part 0.3](../00-foundations/03-syscall-mechanism.md).

**Address space** — The range of virtual addresses a process may reference, from
`0` to the architecture limit (e.g. 128 TiB on x86-64 user space). The kernel maps
virtual pages to physical frames (or leaves them unmapped to trigger faults). Each
process has its own independent address space after `fork` (with COW sharing).
See [Part 3.1](../03-memory/01-virtual-address-space.md).

**Atomic** — An operation that completes entirely or not at all from the perspective
of other CPUs — no observer sees a half-updated value. User-space atomics (`__atomic_*`,
C11 `_Atomic`) compile to single instructions or LL/SC sequences; when contention
requires sleeping, the kernel's **futex** backs pthread mutexes. See
[Part 5.5](../05-threads/05-atomics-and-futex.md).

---

## B

**Backlog** — The queue length argument to `listen(sockfd, backlog)`: the maximum
number of completed TCP connections waiting for `accept()` before the kernel may drop
or refuse new SYNs (exact policy is kernel-version-dependent). Not the same as the
rate of incoming connections. See [Part 6.2](../06-sockets/02-tcp-sockets.md).

**Blocking** — I/O or sleep syscalls that park the calling thread in the kernel until
an event occurs (data arrives, timer fires, child exits). The thread consumes no CPU
while blocked but cannot do other work on that thread. Contrast **non-blocking**.
See [Part 7.1](../07-io-performance/01-blocking-nonblocking.md).

---

## C

**Capability** — A fine-grained privilege (e.g. `CAP_NET_BIND_SERVICE`,
`CAP_SYS_PTRACE`) that splits traditional root into independent bits. Checked by the
kernel instead of a single uid==0 test. Containers often drop all capabilities except
a minimal set. See [Part 8.6](../08-kernel-interfaces/06-seccomp-and-security.md).

**Cgroup (control group)** — A kernel mechanism to group tasks and apply limits
(CPU, memory, I/O, pids) and accounting. Combined with namespaces, cgroups are the
resource half of containers. Exposed under `/sys/fs/cgroup/`. See
[Part 8.5](../08-kernel-interfaces/05-namespaces-and-cgroups.md).

**Context switch** — Saving one thread's CPU register state and restoring another's
so a different task runs. Triggered by preemption, blocking syscalls, interrupts, or
explicit `sched_yield`. Each switch flushes hot cache state — a reason to minimize
unnecessary blocking and syscall churn. See
[Part 1.6](../01-processes/06-scheduling-and-priority.md).

**Copy-on-write (COW)** — After `fork()`, parent and child share physical pages marked
read-only; the first write to either side triggers a page fault and a private copy.
Makes fork cheap even for large address spaces. Also used in `MAP_PRIVATE` **mmap**.
See [Part 1.2](../01-processes/02-fork-and-clone.md) and
[Part 3.3](../03-memory/03-mmap.md).

---

## D

**Daemon** — A long-lived background process, usually detached from a terminal: double-
`fork`, `setsid()`, close stdio, chdir to `/`, umask. Daemons must handle signals
(`SIGHUP` reload), **reaping** children, and pid files carefully. See
[Part 1.5](../01-processes/05-pids-groups-sessions.md).

**Descriptor table** — Per-process array (indexed by **file descriptor** integer)
pointing to open file description entries in the kernel's system-wide table. `dup`
shares descriptions; `close` removes one table slot. See
[Part 0.5](../00-foundations/05-file-descriptors.md).

---

## E

**Edge-triggered** — An `epoll` delivery mode (`EPOLLET`): notify once when the fd
transitions to ready, not while data remains available. Requires draining the fd fully
on each wakeup or you miss events. Contrast **level-triggered**. See
[Part 6.6](../06-sockets/06-io-multiplexing.md) and
[Part 7.2](../07-io-performance/02-epoll-deep-dive.md).

**errno** — Thread-local integer set when a libc syscall wrapper indicates failure
(typically `return -1`). Must be read immediately after detecting failure; success
does not clear stale values. See
[Part 0.4](../00-foundations/04-errno-and-error-handling.md) and
[errno reference](errno-reference.md).

---

## F

**File descriptor (`fd`)** — A small non-negative integer (`0`, `1`, `2` for
stdin/stdout/stderr) indexing the process **descriptor table**. The integer is not the
file — it is a handle to a kernel **open file description** (offset, flags, inode ref).
See [Part 0.5](../00-foundations/05-file-descriptors.md).

**File offset** — Byte position within an open file description where the next
`read`/`write` occurs. Shared by all fds duplicated from the same description;
independent for `pread`/`pwrite`. See
[Part 2.3](../02-file-io/03-seek-and-offsets.md).

**FIFO** — A named pipe: a filesystem path (`mkfifo`) backed by a kernel buffer,
allowing unrelated processes to communicate byte-stream data. Anonymous **pipes** lack
a directory entry. See [Part 4.1](../04-ipc/01-pipes-and-fifos.md).

**Futex (fast userspace mutex)** — Kernel-assisted wait/wake on a userspace integer.
Threads spin in user space while uncontended; on contention, `futex()` syscalls park
and wake waiters. Foundation of pthread mutexes and condition variables. See
[Part 5.5](../05-threads/05-atomics-and-futex.md).

---

## I

**Inode** — Filesystem metadata object: permissions, owner, size, timestamps, pointers
to data blocks. Directory entries are names → inode numbers. Hard links are multiple
names for one inode. See [Part 2.7](../02-file-io/07-vfs-and-inodes.md).

**IPC (inter-process communication)** — Mechanisms for data and control flow between
processes: pipes, signals, shared memory, message queues, semaphores, sockets. Each
differs in boundaries crossed, persistence, and ordering guarantees. See
[Part 4](../04-ipc/01-pipes-and-fifos.md) and
[Part 4.5](../04-ipc/05-choosing-ipc.md).

---

## K

**Kernel mode** — CPU privilege level (ring 0 on x86) where the OS runs: unrestricted
memory access, MMU programming, device I/O. Entered via interrupts, exceptions, and
**syscalls**. Contrast **user mode**. See
[Part 0.2](../00-foundations/02-user-kernel-boundary.md).

---

## L

**Level-triggered** — Default `epoll`/`poll` behavior: fd reported ready as long as
the condition holds (e.g. bytes in socket buffer). Easier to use than **edge-triggered**
but may report repeatedly until data consumed. See
[Part 7.2](../07-io-performance/02-epoll-deep-dive.md).

---

## M

**mmap** — Syscall mapping file bytes or anonymous pages into the virtual **address
space**. Enables file-as-array access, lazy loading via **page faults**, and
shared mappings. Failure returns `MAP_FAILED`, not `-1`. See
[Part 3.3](../03-memory/03-mmap.md).

**Mode switch** — CPU transition between **user mode** and **kernel mode** (privilege
level change, stack switch, register save). Every **syscall** pays this cost (~100–300 ns
on modern hardware, plus cache effects). Same mechanism as trap for page faults.
See [Part 0.2](../00-foundations/02-user-kernel-boundary.md).

**MMU (Memory Management Unit)** — Hardware that translates virtual addresses to
physical frames using page tables; enforces **PROT_*** permissions. A violation raises
a **page fault** handled by the kernel. See
[Part 3.1](../03-memory/01-virtual-address-space.md).

---

## N

**Namespace** — Kernel view isolation: separate mount, PID, network, UTS, IPC, user,
cgroup, time views per group of tasks. `unshare()` / `setns()` / `clone(CLONE_NEW*)`
create container boundaries. See
[Part 8.5](../08-kernel-interfaces/05-namespaces-and-cgroups.md).

**Non-blocking** — Fd flag (`O_NONBLOCK`) or socket state where I/O syscalls return
immediately with `EAGAIN`/`EWOULDBLOCK` if the operation would wait. Required for
single-threaded event loops and `epoll`-driven servers. See
[Part 7.1](../07-io-performance/01-blocking-nonblocking.md).

---

## O

**Open file description** — Kernel object holding file offset, status flags (`O_APPEND`,
`O_NONBLOCK`), and reference to inode or socket. Multiple **fds** (via `dup` or
inheritance across `fork`) can point to one description — they share offset. See
[Part 0.5](../00-foundations/05-file-descriptors.md).

**Orphan** — Child process whose parent has exited without **reaping** it; inherited
by `init` (PID 1) or a subreaper, which eventually `wait`s. Not the same as a
**zombie**. See [Part 1.4](../01-processes/04-wait-zombies-orphans.md).

---

## P

**Page** — Fixed-size chunk of virtual memory (typically 4096 bytes on x86-64),
the granularity of MMU mapping and protection. The kernel tracks residency, dirty
state, and backing store per page. See
[Part 3.1](../03-memory/01-virtual-address-space.md).

**Page cache** — Kernel cache of file data in RAM: `read`/`write` often hit cached
pages instead of disk; `mmap` maps the same pages. `fsync`/`msync` push dirty pages
to storage. See [Part 2.2](../02-file-io/02-read-write.md) and
[Part 3.3](../03-memory/03-mmap.md).

**Page fault** — CPU exception when accessing unmapped, protected, or not-yet-populated
pages. The kernel may allocate a frame, load from disk (major fault), COW-break a
shared page, or send `SIGSEGV`/`SIGBUS`. See
[Part 3.1](../03-memory/01-virtual-address-space.md).

**PID (Process ID)** — Unique kernel identifier for a process (technically a thread
group leader in modern Linux). Used by `kill`, `waitpid`, `/proc`, and scheduling.
PIDs are recycled after exit. See
[Part 1.1](../01-processes/01-process-model.md) and
[Part 1.5](../01-processes/05-pids-groups-sessions.md).

**Pipe** — Unidirectional byte stream between two **fds** created by `pipe()`: kernel
buffer, no filesystem name, **file offset** irrelevant (`ESPIPE` on `lseek`). See
[Part 4.1](../04-ipc/01-pipes-and-fifos.md).

**POSIX** — Portable Unix standard (IEEE 1003): APIs, semantics, and errno behavior
libc and kernels approximate. Linux adds extensions (`epoll`, `timerfd`, `io_uring`).
See [Part 4.4](../04-ipc/04-posix-ipc.md).

**Preemption** — Kernel forcibly suspending a running task (timer interrupt, higher
priority wake) to run another. Makes execution interleaved and non-deterministic without
synchronization. See [Part 1.6](../01-processes/06-scheduling-and-priority.md).

**Privilege ring** — x86 hardware protection levels: ring 3 = **user mode**, ring 0 =
**kernel mode**. Syscalls are the intentional gateway from 3 to 0. See
[Part 0.1](../00-foundations/01-what-is-a-syscall.md).

**Process** — An instance of a running program: virtual **address space**, **descriptor
table**, signal dispositions, credentials, one or more threads sharing these. Created
by `fork`/`clone`, replaced by `exec`. See
[Part 1.1](../01-processes/01-process-model.md).

**Process group** — Set of related processes (same **PGID**), signaled together via
`kill(-pgid, sig)`. Job control shells put pipelines in one group. See
[Part 1.5](../01-processes/05-pids-groups-sessions.md).

---

## R

**Reaping** — Parent calling `wait`/`waitpid` to read a terminated child's exit status
and free its kernel `task_struct` slot. Failure to reap leaves a **zombie**. See
[Part 1.4](../01-processes/04-wait-zombies-orphans.md).

---

## S

**Scheduler** — Kernel subsystem picking which runnable thread runs on each CPU,
weighted by nice value, cgroup limits, and real-time policies. Blocking syscalls
voluntarily yield; timers drive preemption. See
[Part 1.6](../01-processes/06-scheduling-and-priority.md).

**seccomp (secure computing mode)** — Kernel filter restricting which **syscalls** a
thread may invoke; violations kill the thread or trap to a supervisor (`SECCOMP_RET_TRAP`).
Used heavily in browsers and containers. See
[Part 8.6](../08-kernel-interfaces/06-seccomp-and-security.md).

**Session** — Collection of **process groups** established by `setsid()`; typically
one controlling terminal. Session leader manages foreground/background job control. See
[Part 1.5](../01-processes/05-pids-groups-sessions.md).

**Signal** — Asynchronous notification to a process/thread (`SIGINT`, `SIGCHLD`,
`SIGSEGV`, …): default action, ignore, or handler installed via `sigaction`. Delivery
can interrupt syscalls (`EINTR`). Async-signal-safe rules restrict handler code. See
[Part 4.2](../04-ipc/02-signals.md).

**Socket** — Bidirectional communication endpoint represented as an **fd**: network
(`AF_INET`) or local (`AF_UNIX`), stream or datagram. Created by `socket()`, bound,
connected, and multiplexed with `epoll`. See
[Part 6.1](../06-sockets/01-socket-model.md).

**Spurious wakeup** — A waiting thread returns from `pthread_cond_wait` or `futex` wait
without the condition being true — often because another thread signaled or the kernel
requeued waiters. Always re-check predicate in a loop. See
[Part 5.4](../05-threads/04-condition-variables.md).

**Syscall (system call)** — Controlled trap from **user mode** to **kernel mode**
executing a numbered kernel service (`read`, `mmap`, `fork`, …). The only legitimate
path to privileged operations. See
[Part 0.1](../00-foundations/01-what-is-a-syscall.md).

**System call number** — Integer index into the kernel's `sys_call_table` (e.g. `read`
= 0 on x86-64 Linux — numbers vary by arch). Loaded into `%rax` before the `SYSCALL`
instruction. See [Part 0.3](../00-foundations/03-syscall-mechanism.md).

---

## T

**task_struct** — Kernel data structure representing a schedulable entity (process or
kernel thread): registers, mm pointer, **fd** table, signal state, cgroup membership.
One per thread in Linux; thread group shares `mm` and many fields. See
[Part 1.1](../01-processes/01-process-model.md) and
[Part 5.1](../05-threads/01-threads-vs-processes.md).

**Thread** — Unit of CPU scheduling within a process: shares **address space** and **fd**
table with siblings, has its own stack, register context, and TLS (including **errno**).
Created via `pthread_create` → `clone`. See
[Part 5.1](../05-threads/01-threads-vs-processes.md).

**TLB (Translation Lookaside Buffer)** — CPU cache of virtual→physical translations.
**Context switches** and `munmap`/`mprotect` can invalidate TLB entries (cost of
remapping). See [Part 3.1](../03-memory/01-virtual-address-space.md).

---

## U

**User mode** — Unprivileged CPU ring (ring 3): normal program execution. Cannot access
hardware or kernel memory directly; must use **syscalls**. See
[Part 0.2](../00-foundations/02-user-kernel-boundary.md).

---

## V

**vDSO (virtual dynamic shared object)** — Kernel-mapped user-readable page exporting
fast implementations of syscalls like `clock_gettime` and `gettimeofday` without full
trap overhead. Visible in `/proc/self/maps`. See
[Part 0.3](../00-foundations/03-syscall-mechanism.md).

**VFS (Virtual File System)** — Kernel layer unifying `ext4`, `tmpfs`, `proc`, `socket`,
and device nodes behind common `open`/`read`/`write`/`ioctl` operations and **inode**
abstractions. See [Part 2.7](../02-file-io/07-vfs-and-inodes.md).

**Virtual memory** — Abstraction giving each process its own contiguous **address space**
backed by physical RAM, swap, or files; enforced by the **MMU**. Enables isolation,
overcommit, and **mmap**. See [Part 3.1](../03-memory/01-virtual-address-space.md).

---

## Z

**Zero-copy** — Data path avoiding redundant copies through user-space buffers:
`sendfile`, `splice`, `MSG_ZEROCOPY`, DMA from NIC to pinned pages. Reduces CPU and
cache pressure on high-throughput servers. See
[Part 7.4](../07-io-performance/04-zero-copy.md).

**Zombie** — Terminated child still listed in the process table because the parent
has not **reaped** it (`wait`). Consumes a PID slot but no memory. Fixed by parent
calling `waitpid` or parent dying (child becomes **orphan**). See
[Part 1.4](../01-processes/04-wait-zombies-orphans.md).

---

Back to [README](../README.md)
