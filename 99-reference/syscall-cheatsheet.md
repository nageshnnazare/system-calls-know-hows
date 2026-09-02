# System-Call Cheat Sheet

Dense, scannable reference for the syscalls covered in this guide. Signatures are
**libc wrappers** (what you `#include` and call in C); each maps to a kernel syscall
via the ABI described in [Part 0.3](../00-foundations/03-syscall-mechanism.md). On
failure, almost every call returns `-1` and sets `errno` — see
[Part 0.4](../00-foundations/04-errno-and-error-handling.md).

---

## Process

> Covered in depth: [Part 1 — Process management](../01-processes/01-process-model.md)

| Syscall | Purpose | Headers |
|---------|---------|---------|
| `pid_t fork(void)` | Duplicate the calling process; child gets COW copy of address space | `<unistd.h>` |
| `pid_t vfork(void)` | Create child that borrows parent memory until `exec` or `_exit` | `<unistd.h>` |
| `int clone(int (*fn)(void *), void *stack, int flags, void *arg, ...)` | Fine-grained process/thread creation with shared resources | `<sched.h>` |
| `int execve(const char *path, char *const argv[], char *const envp[])` | Replace process image with a new program | `<unistd.h>` |
| `int execl/execv/execlp/execvp(...)` | `execve` variants with different argument passing / PATH search | `<unistd.h>` |
| `void _exit(int status)` | Terminate immediately — no libc cleanup | `<unistd.h>` |
| `pid_t wait(int *status)` | Block until any child exits; reap zombie | `<sys/wait.h>` |
| `pid_t waitpid(pid_t pid, int *status, int options)` | Wait for specific child; `WNOHANG` for non-blocking poll | `<sys/wait.h>` |
| `pid_t wait4(pid_t pid, int *status, int options, struct rusage *rusage)` | `waitpid` + optional resource usage | `<sys/wait.h>` |
| `pid_t getpid(void)` | Return this process's PID | `<unistd.h>` |
| `pid_t getppid(void)` | Return parent PID | `<unistd.h>` |
| `pid_t getpgid(pid_t pid)` | Get process group ID | `<unistd.h>` |
| `int setpgid(pid_t pid, pid_t pgid)` | Set process group membership | `<unistd.h>` |
| `pid_t getsid(pid_t pid)` | Get session ID | `<unistd.h>` |
| `pid_t setsid(void)` | Create new session; caller becomes session leader | `<unistd.h>` |
| `int kill(pid_t pid, int sig)` | Send signal to process or process group | `<signal.h>` |
| `int nice(int inc)` | Adjust nice value (scheduling priority) | `<unistd.h>` |
| `int getpriority(int which, id_t who)` | Read scheduling priority | `<sys/resource.h>` |
| `int setpriority(int which, id_t who, int prio)` | Set scheduling priority | `<sys/resource.h>` |
| `int sched_yield(void)` | Voluntarily yield CPU to another runnable task | `<sched.h>` |
| `int prctl(int option, ...)` | Process control: name, death signal, seccomp, etc. | `<sys/prctl.h>` |
| `int getrlimit(int resource, struct rlimit *rlim)` | Read resource limits (`RLIMIT_NOFILE`, etc.) | `<sys/resource.h>` |
| `int setrlimit(int resource, const struct rlimit *rlim)` | Set resource limits | `<sys/resource.h>` |

---

## File I/O

> Covered in depth: [Part 2 — File I/O & the VFS](../02-file-io/01-open-close.md)

| Syscall | Purpose | Headers |
|---------|---------|---------|
| `int open(const char *path, int flags, ...)` | Open path; return new fd | `<fcntl.h>`, `<sys/stat.h>` |
| `int openat(int dirfd, const char *path, int flags, ...)` | Open relative to directory fd | `<fcntl.h>`, `<sys/stat.h>` |
| `int creat(const char *path, mode_t mode)` | Create/truncate file (`open` with `O_CREAT\|O_TRUNC\|O_WRONLY`) | `<fcntl.h>` |
| `int close(int fd)` | Release fd; close when last ref to open file description gone | `<unistd.h>` |
| `ssize_t read(int fd, void *buf, size_t count)` | Read up to `count` bytes from current file offset | `<unistd.h>` |
| `ssize_t write(int fd, const void *buf, size_t count)` | Write up to `count` bytes at current offset | `<unistd.h>` |
| `ssize_t pread(int fd, void *buf, size_t count, off_t offset)` | Read at absolute offset without changing fd offset | `<unistd.h>` |
| `ssize_t pwrite(int fd, const void *buf, size_t count, off_t offset)` | Write at absolute offset without changing fd offset | `<unistd.h>` |
| `off_t lseek(int fd, off_t offset, int whence)` | Reposition file offset (`SEEK_SET/CUR/END`) | `<unistd.h>` |
| `int dup(int oldfd)` | Duplicate fd to lowest free slot | `<unistd.h>` |
| `int dup2(int oldfd, int newfd)` | Duplicate fd to specific slot (atomically replacing `newfd`) | `<unistd.h>` |
| `int dup3(int oldfd, int newfd, int flags)` | `dup2` with `O_CLOEXEC` support | `<unistd.h>` |
| `int fcntl(int fd, int cmd, ...)` | Get/set fd flags, `F_DUPFD`, advisory locks | `<fcntl.h>` |
| `int stat(const char *path, struct stat *buf)` | Metadata for path (follows symlinks) | `<sys/stat.h>` |
| `int fstat(int fd, struct stat *buf)` | Metadata via open fd | `<sys/stat.h>` |
| `int lstat(const char *path, struct stat *buf)` | Metadata without following final symlink | `<sys/stat.h>` |
| `int fstatat(int dirfd, const char *path, struct stat *buf, int flags)` | `stat`/`lstat` relative to dir fd | `<sys/stat.h>` |
| `int chmod(const char *path, mode_t mode)` | Change permission bits | `<sys/stat.h>` |
| `int fchmod(int fd, mode_t mode)` | Change permission bits via fd | `<sys/stat.h>` |
| `int chown(const char *path, uid_t owner, gid_t group)` | Change owner/group | `<unistd.h>` |
| `int link(const char *oldpath, const char *newpath)` | Hard link: second name, same inode | `<unistd.h>` |
| `int symlink(const char *target, const char *linkpath)` | Create symbolic link | `<unistd.h>` |
| `ssize_t readlink(const char *path, char *buf, size_t bufsiz)` | Read symlink target | `<unistd.h>` |
| `int unlink(const char *path)` | Remove name; inode freed when last link + no open fds | `<unistd.h>` |
| `int rename(const char *old, const char *new)` | Atomically rename within filesystem | `<stdio.h>` |
| `int mkdir(const char *path, mode_t mode)` | Create directory | `<sys/stat.h>` |
| `int rmdir(const char *path)` | Remove empty directory | `<unistd.h>` |
| `int chdir(const char *path)` | Change process working directory | `<unistd.h>` |
| `char *getcwd(char *buf, size_t size)` | Get current working directory path | `<unistd.h>` |
| `int truncate(const char *path, off_t length)` | Set file size by path | `<unistd.h>` |
| `int ftruncate(int fd, off_t length)` | Set file size by fd | `<unistd.h>` |
| `ssize_t readv(int fd, const struct iovec *iov, int iovcnt)` | Scatter-read into multiple buffers | `<sys/uio.h>` |
| `ssize_t writev(int fd, const struct iovec *iov, int iovcnt)` | Gather-write from multiple buffers | `<sys/uio.h>` |
| `ssize_t sendfile(int out_fd, int in_fd, off_t *offset, size_t count)` | Kernel copy file → socket/pipe (zero-copy path) | `<sys/sendfile.h>` |
| `ssize_t splice(int fd_in, off_t *off_in, int fd_out, off_t *off_out, size_t len, unsigned int flags)` | Move data between fds via kernel pipe buffer | `<fcntl.h>` |

---

## Memory

> Covered in depth: [Part 3 — Memory management](../03-memory/01-virtual-address-space.md)

| Syscall | Purpose | Headers |
|---------|---------|---------|
| `int brk(void *addr)` | Set program break (heap end); rarely called directly | `<unistd.h>` |
| `void *sbrk(intptr_t increment)` | Adjust break pointer (legacy; prefer `malloc`) | `<unistd.h>` |
| `void *mmap(void *addr, size_t len, int prot, int flags, int fd, off_t offset)` | Map file or anonymous pages into address space | `<sys/mman.h>` |
| `int munmap(void *addr, size_t len)` | Unmap mapped region | `<sys/mman.h>` |
| `void *mremap(void *old_addr, size_t old_size, size_t new_size, int flags, ...)` | Grow/shrink/move existing mapping | `<sys/mman.h>` |
| `int mprotect(void *addr, size_t len, int prot)` | Change page protection (`PROT_READ/WRITE/EXEC`) | `<sys/mman.h>` |
| `int madvise(void *addr, size_t len, int advice)` | Hint kernel about access pattern (`MADV_SEQUENTIAL`, etc.) | `<sys/mman.h>` |
| `int msync(void *addr, size_t len, int flags)` | Flush mapped pages to backing store | `<sys/mman.h>` |
| `int mlock(const void *addr, size_t len)` | Pin pages in RAM (no swap) | `<sys/mman.h>` |
| `int munlock(const void *addr, size_t len)` | Unpin pages | `<sys/mman.h>` |
| `int mlockall(int flags)` | Lock all current and future mapped pages | `<sys/mman.h>` |
| `int shmget(key_t key, size_t size, int shmflg)` | Create/get System V shared memory segment | `<sys/shm.h>` |
| `void *shmat(int shmid, const void *shmaddr, int shmflg)` | Attach SHM segment to address space | `<sys/shm.h>` |
| `int shmdt(const void *shmaddr)` | Detach SHM segment | `<sys/shm.h>` |
| `int shmctl(int shmid, int cmd, struct shmid_ds *buf)` | Control SHM segment (IPC_RMID, etc.) | `<sys/shm.h>` |
| `int shm_open(const char *name, int oflag, mode_t mode)` | Open POSIX shared memory object | `<sys/mman.h>`, `<fcntl.h>` |
| `int shm_unlink(const char *name)` | Remove POSIX SHM name | `<sys/mman.h>` |

---

## IPC

> Covered in depth: [Part 4 — Inter-process communication](../04-ipc/01-pipes-and-fifos.md)

| Syscall | Purpose | Headers |
|---------|---------|---------|
| `int pipe(int pipefd[2])` | Create anonymous byte-stream pipe; `pipefd[0]` read, `[1]` write | `<unistd.h>` |
| `int pipe2(int pipefd[2], int flags)` | `pipe` with `O_CLOEXEC`, `O_NONBLOCK` | `<unistd.h>` |
| `int mkfifo(const char *pathname, mode_t mode)` | Create named FIFO (filesystem path) | `<sys/stat.h>` |
| `key_t ftok(const char *pathname, int proj_id)` | Generate SysV IPC key from path + project id | `<sys/ipc.h>` |
| `int msgget(key_t key, int msgflg)` | Create/get System V message queue | `<sys/msg.h>` |
| `int msgsnd(int msqid, const void *msgp, size_t msgsz, int msgflg)` | Send message to queue | `<sys/msg.h>` |
| `ssize_t msgrcv(int msqid, void *msgp, size_t msgsz, long msgtyp, int msgflg)` | Receive message from queue | `<sys/msg.h>` |
| `int msgctl(int msqid, int cmd, struct msqid_ds *buf)` | Control message queue | `<sys/msg.h>` |
| `int semget(key_t key, int nsems, int semflg)` | Create/get semaphore set | `<sys/sem.h>` |
| `int semop(int semid, struct sembuf *sops, size_t nsops)` | Atomic semaphore operations | `<sys/sem.h>` |
| `int semctl(int semid, int cmd, ...)` | Control semaphore set | `<sys/sem.h>` |
| `mqd_t mq_open(const char *name, int oflag, ...)` | Open POSIX message queue | `<mqueue.h>` |
| `int mq_send(mqd_t mqdes, const char *msg_ptr, size_t msg_len, unsigned int msg_prio)` | Send POSIX message | `<mqueue.h>` |
| `ssize_t mq_receive(mqd_t mqdes, char *msg_ptr, size_t msg_len, unsigned int *msg_prio)` | Receive POSIX message | `<mqueue.h>` |
| `int mq_close(mqd_t mqdes)` | Close POSIX message queue descriptor | `<mqueue.h>` |
| `int mq_unlink(const char *name)` | Remove POSIX message queue name | `<mqueue.h>` |
| `int eventfd(unsigned int initval, int flags)` | Counter fd for event notification / wakeups | `<sys/eventfd.h>` |
| `int memfd_create(const char *name, unsigned int flags)` | Anonymous memory-backed file (sealing, sharing) | `<sys/mman.h>` |

---

## Signals

> Covered in depth: [Part 4.2 — Signals](../04-ipc/02-signals.md)

| Syscall | Purpose | Headers |
|---------|---------|---------|
| `sighandler_t signal(int signum, sighandler_t handler)` | Legacy handler install — prefer `sigaction` | `<signal.h>` |
| `int sigaction(int signum, const struct sigaction *act, struct sigaction *oldact)` | Install handler with flags (`SA_RESTART`, `SA_SIGINFO`) | `<signal.h>` |
| `int kill(pid_t pid, int sig)` | Send signal to process or group (`kill(-pgid, sig)`) | `<signal.h>` |
| `int killpg(int pgrp, int sig)` | Send signal to process group | `<signal.h>` |
| `int raise(int sig)` | Send signal to calling thread | `<signal.h>` |
| `int sigprocmask(int how, const sigset_t *set, sigset_t *oldset)` | Block/unblock signals in thread mask | `<signal.h>` |
| `int sigpending(sigset_t *set)` | Return set of pending blocked signals | `<signal.h>` |
| `int sigsuspend(const sigset_t *mask)` | Atomically replace mask and sleep until signal | `<signal.h>` |
| `int sigtimedwait(const sigset_t *set, siginfo_t *info, const struct timespec *timeout)` | Wait for signal with timeout | `<signal.h>` |
| `unsigned int alarm(unsigned int seconds)` | Schedule `SIGALRM` after `seconds` | `<unistd.h>` |
| `int pause(void)` | Block until any signal delivered | `<unistd.h>` |
| `int signalfd(int fd, const sigset_t *mask, int flags)` | Turn signals into readable fd events | `<sys/signalfd.h>` |
| `int timerfd_create(int clockid, int flags)` | Timer as readable fd (`read` returns expirations) | `<sys/timerfd.h>` |
| `int timerfd_settime(int fd, int flags, const struct itimerspec *new, struct itimerspec *old)` | Arm/disarm timerfd | `<sys/timerfd.h>` |

---

## Sockets

> Covered in depth: [Part 6 — Sockets & networking](../06-sockets/01-socket-model.md) ·
> Multiplexing: [Part 6.6](../06-sockets/06-io-multiplexing.md) ·
> Performance: [Part 7](../07-io-performance/01-blocking-nonblocking.md)

| Syscall | Purpose | Headers |
|---------|---------|---------|
| `int socket(int domain, int type, int protocol)` | Create socket fd (`AF_INET`, `SOCK_STREAM`, etc.) | `<sys/socket.h>` |
| `int bind(int sockfd, const struct sockaddr *addr, socklen_t addrlen)` | Assign local address/port | `<sys/socket.h>` |
| `int listen(int sockfd, int backlog)` | Mark socket passive; queue length for pending connections | `<sys/socket.h>` |
| `int accept(int sockfd, struct sockaddr *addr, socklen_t *addrlen)` | Accept incoming connection; return connected fd | `<sys/socket.h>` |
| `int accept4(int sockfd, struct sockaddr *addr, socklen_t *addrlen, int flags)` | `accept` with `SOCK_NONBLOCK` / `SOCK_CLOEXEC` | `<sys/socket.h>` |
| `int connect(int sockfd, const struct sockaddr *addr, socklen_t addrlen)` | Initiate connection (client) | `<sys/socket.h>` |
| `ssize_t send(int sockfd, const void *buf, size_t len, int flags)` | Send on connected socket | `<sys/socket.h>` |
| `ssize_t recv(int sockfd, void *buf, size_t len, int flags)` | Receive on connected socket | `<sys/socket.h>` |
| `ssize_t sendto(int sockfd, const void *buf, size_t len, int flags, const struct sockaddr *dest, socklen_t addrlen)` | Send datagram to address | `<sys/socket.h>` |
| `ssize_t recvfrom(int sockfd, void *buf, size_t len, int flags, struct sockaddr *src, socklen_t *addrlen)` | Receive datagram + sender address | `<sys/socket.h>` |
| `ssize_t sendmsg(int sockfd, const struct msghdr *msg, int flags)` | Send with ancillary data (SCM_RIGHTS, etc.) | `<sys/socket.h>` |
| `ssize_t recvmsg(int sockfd, struct msghdr *msg, int flags)` | Receive with ancillary data | `<sys/socket.h>` |
| `int shutdown(int sockfd, int how)` | Half/full close (`SHUT_RD/WR/RDWR`) | `<sys/socket.h>` |
| `int getsockopt(int sockfd, int level, int optname, void *optval, socklen_t *optlen)` | Read socket option | `<sys/socket.h>` |
| `int setsockopt(int sockfd, int level, int optname, const void *optval, socklen_t optlen)` | Set socket option (`SO_REUSEADDR`, etc.) | `<sys/socket.h>` |
| `int getsockname(int sockfd, struct sockaddr *addr, socklen_t *addrlen)` | Local address of socket | `<sys/socket.h>` |
| `int getpeername(int sockfd, struct sockaddr *addr, socklen_t *addrlen)` | Remote peer address | `<sys/socket.h>` |
| `int select(int nfds, fd_set *readfds, fd_set *writefds, fd_set *exceptfds, struct timeval *timeout)` | Legacy fd-set multiplexing — O(n) scan | `<sys/select.h>` |
| `int poll(struct pollfd *fds, nfds_t nfds, int timeout)` | Poll array of `{fd, events, revents}` | `<poll.h>` |
| `int epoll_create1(int flags)` | Create epoll instance fd | `<sys/epoll.h>` |
| `int epoll_ctl(int epfd, int op, int fd, struct epoll_event *event)` | Add/modify/delete watched fd | `<sys/epoll.h>` |
| `int epoll_wait(int epfd, struct epoll_event *events, int maxevents, int timeout)` | Wait for readiness events | `<sys/epoll.h>` |
| `int epoll_pwait(int epfd, struct epoll_event *events, int maxevents, int timeout, const sigset_t *sigmask)` | `epoll_wait` with signal mask | `<sys/epoll.h>` |

---

## Time

> Clocks and sleeping appear across Parts 1, 4, 6, and 7; vDSO fast paths in
> [Part 0.3](../00-foundations/03-syscall-mechanism.md).

| Syscall | Purpose | Headers |
|---------|---------|---------|
| `time_t time(time_t *t)` | Seconds since Unix epoch (coarse) | `<time.h>` |
| `int gettimeofday(struct timeval *tv, struct timezone *tz)` | Wall time with microseconds (legacy) | `<sys/time.h>` |
| `int clock_gettime(clockid_t clk_id, struct timespec *tp)` | High-resolution clock (`CLOCK_MONOTONIC`, etc.) | `<time.h>` |
| `int clock_getres(clockid_t clk_id, struct timespec *res)` | Resolution of a clock | `<time.h>` |
| `int clock_settime(clockid_t clk_id, const struct timespec *tp)` | Set clock (privileged for most clocks) | `<time.h>` |
| `int clock_nanosleep(clockid_t clk_id, int flags, const struct timespec *req, struct timespec *rem)` | Sleep on specific clock | `<time.h>` |
| `unsigned int sleep(unsigned int seconds)` | Sleep whole seconds; returns unslept on signal | `<unistd.h>` |
| `int usleep(useconds_t usec)` | Sleep microseconds (deprecated; use `nanosleep`) | `<unistd.h>` |
| `int nanosleep(const struct timespec *req, struct timespec *rem)` | Sleep with nanosecond resolution | `<time.h>` |
| `clock_t times(struct tms *buf)` | Process CPU time accounting | `<sys/times.h>` |
| `int getrusage(int who, struct rusage *usage)` | Resource usage (`RUSAGE_SELF`, `RUSAGE_CHILDREN`) | `<sys/resource.h>` |

---

## Kernel / System

> Covered in depth: [Part 8 — Kernel interfaces](../08-kernel-interfaces/01-proc-filesystem.md)

| Syscall | Purpose | Headers |
|---------|---------|---------|
| `int ioctl(int fd, unsigned long request, ...)` | Device/filesystem-specific control operations | `<sys/ioctl.h>` |
| `long syscall(long number, ...)` | Raw syscall by number (bypass libc wrapper) | `<sys/syscall.h>`, `<unistd.h>` |
| `int uname(struct utsname *buf)` | Kernel name, version, machine | `<sys/utsname.h>` |
| `int sysinfo(struct sysinfo *info)` | Uptime, load, memory summary | `<sys/sysinfo.h>` |
| `long sysconf(int name)` | Compile-time/runtime limits (`_SC_PAGESIZE`, etc.) | `<unistd.h>` |
| `int capget/capset(...)` | Thread/process capability sets | `<sys/capability.h>` |
| `int seccomp(unsigned int operation, unsigned int flags, void *args)` | Install syscall filter (legacy API) | `<linux/seccomp.h>` |
| `int prctl(int option, ...)` | Namespaces hint, seccomp, `PR_SET_NAME`, etc. | `<sys/prctl.h>` |
| `int unshare(int flags)` | Detach from shared namespace (mount, net, pid, …) | `<sched.h>` |
| `int setns(int fd, int nstype)` | Join namespace referred to by fd | `<sched.h>` |
| `int mount(const char *source, const char *target, const char *fstype, unsigned long flags, const void *data)` | Attach filesystem | `<sys/mount.h>` |
| `int umount/umount2(const char *target, int flags)` | Detach filesystem | `<sys/mount.h>` |
| `int pivot_root(const char *new_root, const char *put_old)` | Change root filesystem (containers) | `<sys/syscall.h>` |
| `ssize_t getrandom(void *buf, size_t buflen, unsigned int flags)` | Cryptographic random bytes from kernel pool | `<sys/random.h>` |
| `int perf_event_open(struct perf_event_attr *attr, pid_t pid, int cpu, int group_fd, unsigned long flags)` | Hardware/software performance counters | `<linux/perf_event.h>` |
| `int bpf(int cmd, union bpf_attr *attr, unsigned int size)` | Load/manage eBPF programs and maps | `<linux/bpf.h>` |
| `int pidfd_open(pid_t pid, unsigned int flags)` | Obtain fd referring to a process | `<sys/pidfd.h>` |
| `int pidfd_send_signal(int pidfd, int sig, siginfo_t *info, unsigned int flags)` | Send signal via process fd | `<sys/pidfd.h>` |

---

## Appendix — Common flags

### `open()` / `openat()` flags

| Flag | Meaning |
|------|---------|
| `O_RDONLY` | Read-only |
| `O_WRONLY` | Write-only |
| `O_RDWR` | Read and write |
| `O_CREAT` | Create if missing (requires `mode` arg) |
| `O_EXCL` | With `O_CREAT`: fail if file exists |
| `O_TRUNC` | Truncate existing file to zero length |
| `O_APPEND` | Writes always append; offset ignored |
| `O_NONBLOCK` | Non-blocking I/O where supported |
| `O_CLOEXEC` | Set close-on-exec on new fd |
| `O_SYNC` / `O_DSYNC` | Synchronous metadata/data writes |
| `O_DIRECTORY` | Fail if path is not a directory |
| `O_NOFOLLOW` | Do not follow final symlink |
| `O_DIRECT` | Bypass page cache (alignment constraints apply) |

See [Part 2.1](../02-file-io/01-open-close.md) and [Part 2.5](../02-file-io/05-fcntl-and-metadata.md).

### `mmap()` protection (`prot`)

| Flag | Meaning |
|------|---------|
| `PROT_NONE` | No access |
| `PROT_READ` | Pages readable |
| `PROT_WRITE` | Pages writable |
| `PROT_EXEC` | Pages executable |

### `mmap()` mapping (`flags`)

| Flag | Meaning |
|------|---------|
| `MAP_SHARED` | Changes visible to other mappers and backing file |
| `MAP_PRIVATE` | Copy-on-write private mapping |
| `MAP_ANONYMOUS` / `MAP_ANON` | No file backing (fd ignored) |
| `MAP_FIXED` | Map at exact address (dangerous unless you know why) |
| `MAP_POPULATE` | Prefault pages (eager fault) |
| `MAP_LOCKED` | Lock mapped pages into RAM |
| `MAP_NORESERVE` | Do not reserve swap for mapping |

See [Part 3.3](../03-memory/03-mmap.md).

### Socket `domain` / `type`

| Constant | Meaning |
|----------|---------|
| `AF_INET` | IPv4 |
| `AF_INET6` | IPv6 |
| `AF_UNIX` / `AF_LOCAL` | Unix domain (filesystem path or abstract) |
| `SOCK_STREAM` | Reliable byte stream (TCP) |
| `SOCK_DGRAM` | Datagram (UDP) |
| `SOCK_SEQPACKET` | Record-oriented stream (Unix domain) |
| `SOCK_RAW` | Raw protocol access (privileged) |
| `SOCK_NONBLOCK` | Create in non-blocking mode (OR with type) |
| `SOCK_CLOEXEC` | Close-on-exec (OR with type) |

See [Part 6.1](../06-sockets/01-socket-model.md) and [Part 6.5](../06-sockets/05-socket-options.md).

---

Back to [README](../README.md)
