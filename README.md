# Linux C System Calls Tutorial

A comprehensive guide to low-level Linux system calls in C.

```
╔══════════════════════════════════════════════════════════════╗
║           LINUX SYSTEM CALLS ARCHITECTURE                    ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║   User Space                                                 ║
║   ┌──────────────────────────────────────────────────┐       ║
║   │  Your C Program                                  │       ║
║   │  ┌──────────┐  ┌──────────┐  ┌──────────┐        │       ║
║   │  │ open()   │  │ fork()   │  │ malloc() │  ...   │       ║
║   │  └────┬─────┘  └────┬─────┘  └────┬─────┘        │       ║
║   └───────┼─────────────┼─────────────┼──────────────┘       ║
║           │             │             │                      ║
║   ════════╪═════════════╪═════════════╪═════════════════     ║
║           │  System Call Interface    │  (int 0x80/syscall)  ║ 
║   ════════╪═════════════╪═════════════╪═════════════════     ║
║           │             │             │                      ║
║   Kernel Space                                               ║
║   ┌───────┼─────────────┼─────────────┼──────────────┐       ║
║   │       ▼             ▼             ▼              │       ║
║   │  sys_open()    sys_fork()    sys_brk()           │       ║
║   │       │             │             │              │       ║
║   │       ▼             ▼             ▼              │       ║
║   │  [VFS Layer] [Process Mgmt] [Memory Mgmt]        │       ║
║   │       │             │             │              │       ║
║   │       ▼             ▼             ▼              │       ║
║   │  [Hardware Drivers & Resources]                  │       ║
║   └──────────────────────────────────────────────────┘       ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

## Table of Contents

### 1. [Process Management](processes/README.md)
- `fork()`, `vfork()`, `clone()`
- `exec()` family
- `wait()`, `waitpid()`, `wait3()`, `wait4()`
- `exit()`, `_exit()`
- `getpid()`, `getppid()`, `gettid()`
- Process groups and sessions
- `nice()`, `setpriority()`, `getpriority()`

### 2. [File Operations](files/README.md)
- `open()`, `creat()`, `close()`
- `read()`, `write()`, `pread()`, `pwrite()`
- `lseek()`, `llseek()`
- `dup()`, `dup2()`, `dup3()`
- `fcntl()`, `ioctl()`
- `stat()`, `fstat()`, `lstat()`
- `chmod()`, `fchmod()`, `chown()`, `fchown()`
- `link()`, `unlink()`, `symlink()`, `readlink()`
- `mkdir()`, `rmdir()`, `rename()`
- `chdir()`, `fchdir()`, `getcwd()`
- Directory operations: `opendir()`, `readdir()`, `closedir()`

### 3. [Memory Management](memory/README.md)
- `brk()`, `sbrk()`
- `mmap()`, `munmap()`, `mremap()`, `msync()`
- `mprotect()`, `mlock()`, `munlock()`
- `madvise()`
- Shared memory: `shmget()`, `shmat()`, `shmdt()`, `shmctl()`

### 4. [Resource Management](resources/README.md)
- `getrlimit()`, `setrlimit()`, `prlimit()`
- `getrusage()`
- `ulimit()`
- Resource limits: CPU, memory, file descriptors

### 5. [Inter-Process Communication (IPC)](ipc/README.md)
- Pipes: `pipe()`, `pipe2()`
- FIFOs: `mkfifo()`
- Signals: `signal()`, `sigaction()`, `kill()`, `sigprocmask()`
- Message queues: `msgget()`, `msgsnd()`, `msgrcv()`, `msgctl()`
- Semaphores: `semget()`, `semop()`, `semctl()`

### 6. [POSIX Threads (pthreads)](threads/README.md)
- Thread management: `pthread_create()`, `pthread_join()`, `pthread_detach()`
- Mutexes: `pthread_mutex_lock()`, `pthread_mutex_unlock()`
- Condition variables: `pthread_cond_wait()`, `pthread_cond_signal()`
- Read-write locks: `pthread_rwlock_rdlock()`, `pthread_rwlock_wrlock()`
- Barriers: `pthread_barrier_wait()`
- Thread-local storage: `pthread_key_create()`, `pthread_setspecific()`

### 7. [Socket Programming](sockets/README.md)
- TCP sockets: `socket()`, `bind()`, `listen()`, `accept()`, `connect()`
- UDP sockets: `sendto()`, `recvfrom()`
- Unix domain sockets: Local IPC
- Socket options: `setsockopt()`, `getsockopt()`
- I/O multiplexing: `select()`, `poll()`, `epoll()`

### 8. [Linux Kernel Internals](kernel/README.md)
- System call mechanism
- `/proc` filesystem - Process information
- `/sys` filesystem - Kernel and device information
- Kernel parameters: `sysctl()`
- Performance monitoring: `perf_event_open()`
- Kernel modules and eBPF

## How to Use This Tutorial

1. Each section contains detailed explanations with ASCII diagrams
2. Example code is provided in the `examples/` directory
3. Compile examples with: `gcc -o program program.c`
4. Some examples require root privileges
5. Always check return values in production code

## System Call Conventions

### Return Values
- Success: Usually returns 0 or a positive value (e.g., file descriptor)
- Failure: Returns -1 and sets `errno`

### Error Handling Pattern
```c
#include <errno.h>
#include <string.h>
#include <stdio.h>

if (syscall(...) == -1) {
    fprintf(stderr, "Error: %s\n", strerror(errno));
    // Handle error
}
```

## System Call vs Library Call

```
┌────────────────────────────────────────────────────┐
│  Library Call (e.g., printf, fopen, malloc)        │
│  ┌───────────────────────────────────────────────┐ │
│  │  Higher level, buffered, portable             │ │
│  │  May call multiple system calls               │ │
│  └───────────────────┬───────────────────────────┘ │
└────────────────────────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────┐
│  System Call (e.g., write, open, brk)              │
│  ┌───────────────────────────────────────────────┐ │
│  │  Low level, direct kernel interface           │ │
│  │  Atomic operations                            │ │
│  │  Context switch to kernel mode                │ │
│  └───────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────┘
```

## Prerequisites

- Basic C programming knowledge
- Understanding of Linux/Unix concepts
- GCC compiler installed
- Linux operating system

## Compiling Examples

```bash
# Basic compilation
gcc -o example example.c

# With warnings and debugging
gcc -Wall -Wextra -g -o example example.c

# With optimization
gcc -O2 -o example example.c
```

## References

- `man 2 <syscall>` - System call manual pages
- `man 3 <function>` - Library function manual pages
- Linux Kernel source code
- POSIX specifications


