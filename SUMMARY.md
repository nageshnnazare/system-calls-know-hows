# Linux System Calls Tutorial - Complete Summary

## Tutorial Structure

```
sysc/
├── README.md                 # Main overview and introduction
├── QUICKSTART.md            # Quick start guide for beginners
├── CHEATSHEET.md            # Complete cheat sheet with code examples
├── SYSCALL_REFERENCE.md     # Quick reference table of all system calls
├── SUMMARY.md               # This file - complete summary
│
├── processes/               # Process Management
│   └── README.md            # fork, exec, wait, signals, priorities
│
├── files/                   # File Operations
│   └── README.md            # open, read, write, stat, directories
│
├── memory/                  # Memory Management
│   └── README.md            # brk, mmap, mprotect, shared memory
│
├── resources/               # Resource Management
│   └── README.md            # limits, rusage, priorities, scheduling
│
├── ipc/                     # Inter-Process Communication
│   └── README.md            # pipes, signals, message queues, semaphores
│
├── threads/                 # POSIX Threads
│   └── README.md            # pthreads, mutexes, condition variables
│
├── sockets/                 # Socket Programming
│   └── README.md            # TCP, UDP, Unix domain sockets
│
├── kernel/                  # Linux Kernel Internals
│   └── README.md            # syscall mechanism, /proc, /sys, kernel
│
└── examples/                # Complete Working Examples
    ├── Makefile
    ├── process_manager.c
    ├── file_operations.c
    ├── memory_demo.c
    ├── pipe_demo.c
    ├── signal_demo.c
    ├── resource_limits.c
    ├── shm_demo.c
    ├── threads_demo.c
    ├── tcp_server.c
    └── tcp_client.c
```

## What's Covered

### 1. Process Management (processes/)
- **Process Creation**: `fork()`, `vfork()`, `clone()`
- **Program Execution**: `exec()` family
- **Process Termination**: `exit()`, `_exit()`, `wait()`, `waitpid()`
- **Process IDs**: `getpid()`, `getppid()`, `gettid()`
- **Priority**: `nice()`, `getpriority()`, `setpriority()`
- **Process Groups**: `setpgid()`, `setsid()`

**Key Concepts**: Process lifecycle, fork-exec pattern, zombie processes, orphans

### 2. File Operations (files/)
- **Basic I/O**: `open()`, `read()`, `write()`, `close()`, `lseek()`
- **File Descriptors**: `dup()`, `dup2()`, `dup3()`
- **File Control**: `fcntl()`, `ioctl()`
- **File Information**: `stat()`, `fstat()`, `lstat()`
- **Permissions**: `chmod()`, `chown()`, `umask()`
- **Links**: `link()`, `unlink()`, `symlink()`, `readlink()`
- **Directories**: `mkdir()`, `rmdir()`, `opendir()`, `readdir()`, `closedir()`
- **Navigation**: `chdir()`, `getcwd()`

**Key Concepts**: File descriptor table, inode, VFS, hard vs soft links

### 3. Memory Management (memory/)
- **Heap Management**: `brk()`, `sbrk()`
- **Memory Mapping**: `mmap()`, `munmap()`, `mremap()`, `msync()`
- **Protection**: `mprotect()`, `mlock()`, `munlock()`
- **Advice**: `madvise()`
- **Shared Memory**: `shmget()`, `shmat()`, `shmdt()`, `shmctl()`

**Key Concepts**: Process memory layout, page faults, copy-on-write, shared memory

### 4. Resource Management (resources/)
- **Limits**: `getrlimit()`, `setrlimit()`, `prlimit()`
- **Usage**: `getrusage()`, `times()`
- **Priority**: `getpriority()`, `setpriority()`
- **Scheduling**: `sched_setscheduler()`, `sched_getscheduler()`
- **CPU Affinity**: `sched_setaffinity()`, `sched_getaffinity()`

**Key Concepts**: Soft vs hard limits, resource accounting, CPU scheduling policies

### 5. Inter-Process Communication (ipc/)
- **Pipes**: `pipe()`, `pipe2()` - unidirectional byte streams
- **FIFOs**: `mkfifo()` - named pipes
- **Signals**: `signal()`, `sigaction()`, `kill()`, `sigprocmask()` - async notifications
- **Message Queues**: `msgget()`, `msgsnd()`, `msgrcv()` - message passing
- **Semaphores**: `semget()`, `semop()`, `semctl()` - synchronization
- **POSIX IPC**: Modern alternatives with better semantics

**Key Concepts**: IPC mechanisms comparison, synchronization, signal safety

### 6. POSIX Threads (threads/)
- **Thread Management**: `pthread_create()`, `pthread_join()`, `pthread_detach()`
- **Mutexes**: `pthread_mutex_lock()`, `pthread_mutex_unlock()` - mutual exclusion
- **Condition Variables**: `pthread_cond_wait()`, `pthread_cond_signal()` - signaling
- **Read-Write Locks**: `pthread_rwlock_*` - multiple readers, single writer
- **Barriers**: `pthread_barrier_wait()` - synchronization point
- **Spin Locks**: `pthread_spin_*` - busy-wait locks
- **Thread-Local Storage**: `pthread_key_*`, `__thread` keyword
- **Attributes**: Stack size, detach state, scheduling

**Key Concepts**: Threads vs processes, race conditions, deadlocks, synchronization patterns

### 7. Socket Programming (sockets/)
- **TCP Sockets**: Connection-oriented, reliable communication
  - Server: `socket()`, `bind()`, `listen()`, `accept()`
  - Client: `socket()`, `connect()`
  - I/O: `send()`, `recv()`, `read()`, `write()`
- **UDP Sockets**: Connectionless, message-based
  - `sendto()`, `recvfrom()`
- **Unix Domain Sockets**: Local IPC, faster than TCP
- **Socket Options**: `setsockopt()`, `getsockopt()`
- **I/O Multiplexing**: `select()`, `poll()`, `epoll()` - handle multiple sockets

**Key Concepts**: Client-server architecture, blocking vs non-blocking I/O, socket states

### 8. Linux Kernel Internals (kernel/)
- **System Call Mechanism**: How syscalls work, syscall numbers
- **/proc Filesystem**: Virtual filesystem exposing process/kernel info
  - `/proc/[pid]/` - per-process information
  - `/proc/sys/` - kernel parameters
- **/sys Filesystem**: Device and kernel object information
- **Kernel Parameters**: `sysctl()`, reading/writing kernel settings
- **Performance Monitoring**: `perf_event_open()`, hardware counters
- **Tracing**: ftrace, strace, system call tracing
- **eBPF**: Extended Berkeley Packet Filter for kernel programming

**Key Concepts**: User space vs kernel space, privilege levels, kernel data structures

### 9. Advanced Topics (CHEATSHEET.md)
- **I/O Multiplexing**: `select()`, `poll()`, `epoll()` - scalable servers
- **POSIX IPC**: Modern message queues, semaphores, shared memory
- **Advanced Patterns**: Producer-consumer, reader-writer locks, connection pooling
- **Async I/O**: `aio_read()`, `aio_write()`, `io_uring`
- **Event Notification**: `eventfd()`, `signalfd()`, `timerfd()`
- **File System Events**: `inotify`, `fanotify`

## Complete Example Programs

All examples compile and run on Linux:

```bash
cd examples/
make all

# Process management
./process_manager          # Fork, exec, wait demonstrations

# File operations
./file_operations          # File I/O, stat, dup2, fcntl

# Memory management
./memory_demo              # brk, mmap, mprotect demonstrations

# IPC
./pipe_demo                # Pipe communication examples
./signal_demo              # Signal handling (interactive)
./shm_demo                 # Shared memory with processes

# Resources
./resource_limits          # Resource limits and usage

# Threads
./threads_demo             # Pthreads, mutexes, condition variables

# Sockets
./tcp_server 8080          # TCP echo server (in one terminal)
./tcp_client localhost 8080 # TCP client (in another terminal)
```

## Learning Path

### Beginner (Start Here)
1. **Read**: [QUICKSTART.md](QUICKSTART.md)
2. **Try**: File operations (`file_operations.c`)
3. **Practice**: Process management (`process_manager.c`)
4. **Learn**: Pipes (`pipe_demo.c`)

### Intermediate
5. **Read**: Memory management tutorial
6. **Try**: Memory demo (`memory_demo.c`)
7. **Learn**: Signals (`signal_demo.c`)
8. **Practice**: Resource limits (`resource_limits.c`)

### Advanced
9. **Read**: Threads tutorial
10. **Try**: Thread synchronization (`threads_demo.c`)
11. **Learn**: Socket programming (`tcp_server.c`, `tcp_client.c`)
12. **Practice**: Shared memory (`shm_demo.c`)
13. **Explore**: Kernel internals tutorial

### Expert
14. **Study**: CHEATSHEET.md for advanced patterns
15. **Read**: SYSCALL_REFERENCE.md for complete API
16. **Practice**: Build your own projects using system calls
17. **Explore**: Linux kernel source code

## Key Takeaways

### System Call Fundamentals
- System calls are the interface between user space and kernel
- Always check return values (usually -1 on error)
- Check `errno` and use `strerror()` or `perror()` for errors
- System calls are low-level, atomic operations

### Error Handling Pattern
```c
if (syscall(...) == -1) {
    perror("syscall_name");
    // Handle error appropriately
}
```

### Common Patterns

**Fork-Exec Pattern**
```c
pid_t pid = fork();
if (pid == 0) {
    execl("/bin/program", "program", NULL);
    perror("exec");
    exit(1);
} else {
    wait(NULL);
}
```

**Producer-Consumer Pattern**
```c
pthread_mutex_lock(&mutex);
while (condition_not_met) {
    pthread_cond_wait(&cond, &mutex);
}
// Process item
pthread_mutex_unlock(&mutex);
```

**Client-Server Pattern**
```c
// Server
int server_fd = socket(...);
bind(server_fd, ...);
listen(server_fd, ...);
int client_fd = accept(server_fd, ...);
// Handle client
close(client_fd);

// Client
int sock = socket(...);
connect(sock, ...);
// Communicate
close(sock);
```

## Common Pitfalls to Avoid

1. ✗ Not checking return values
2. ✗ Forgetting to close file descriptors
3. ✗ Not freeing allocated memory
4. ✗ Ignoring partial reads/writes
5. ✗ Race conditions in multithreaded code
6. ✗ Deadlocks from incorrect locking order
7. ✗ Buffer overflows
8. ✗ Not handling EINTR (interrupted system calls)
9. ✗ Zombie processes from not calling wait()
10. ✗ Memory leaks from IPC resources

## Quick Reference

### File I/O
```c
int fd = open(path, O_RDWR | O_CREAT, 0644);
ssize_t n = read(fd, buf, size);
ssize_t n = write(fd, buf, size);
close(fd);
```

### Process Management
```c
pid_t pid = fork();
if (pid == 0) { /* child */ }
else { wait(NULL); /* parent */ }
```

### Threads
```c
pthread_t thread;
pthread_create(&thread, NULL, func, arg);
pthread_join(thread, NULL);
```

### Sockets
```c
int sock = socket(AF_INET, SOCK_STREAM, 0);
connect(sock, &addr, sizeof(addr));
send(sock, data, len, 0);
recv(sock, buf, size, 0);
close(sock);
```

## Compilation

```bash
# Basic
gcc -o program program.c

# With threads
gcc -pthread -o program program.c

# With sockets (sometimes needed)
gcc -o program program.c -lrt

# Full flags
gcc -Wall -Wextra -pthread -g -O2 -o program program.c
```

## Debugging Tools

```bash
strace ./program              # Trace system calls
ltrace ./program              # Trace library calls
gdb ./program                 # Debugger
valgrind ./program            # Memory checker
perf stat ./program           # Performance counters
```

## Additional Resources

### Man Pages
```bash
man 2 syscall_name           # System call manual
man 3 function_name          # Library function manual
man 7 overview_topic         # Overview/concepts
man syscalls                 # List all system calls
```

### Online Resources
- Linux man-pages: https://man7.org/
- Linux kernel source: https://kernel.org/
- POSIX specifications: https://pubs.opengroup.org/
- GNU libc manual: https://gnu.org/software/libc/manual/

### Books
- "Advanced Programming in the UNIX Environment" (APUE) - W. Richard Stevens
- "The Linux Programming Interface" - Michael Kerrisk
- "Linux System Programming" - Robert Love
- "Understanding the Linux Kernel" - Daniel P. Bovet

## Statistics

This tutorial contains:
- **8 main topics** with detailed explanations
- **100+ system calls** covered with examples
- **11 complete example programs** (2000+ lines of code)
- **50+ ASCII diagrams** for visualization
- **200+ code examples** throughout documentation
- **Comprehensive cheat sheet** with all major syscalls

## Contributing

This is an educational resource. To use:
1. Read the tutorials in order
2. Compile and run the examples
3. Modify examples to experiment
4. Build your own programs
5. Refer to cheat sheet and reference as needed

## License

Educational and learning purposes. Feel free to use, modify, and share.

---

**Start your journey**: Begin with [QUICKSTART.md](QUICKSTART.md)

**Need quick reference?**: See [CHEATSHEET.md](CHEATSHEET.md)

**Looking for specific syscall?**: Check [SYSCALL_REFERENCE.md](SYSCALL_REFERENCE.md)

