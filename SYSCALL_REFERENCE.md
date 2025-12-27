# System Call Quick Reference

## Process Management

| System Call | Header | Description | Returns |
|------------|--------|-------------|---------|
| `fork()` | `<unistd.h>` | Create child process | PID in parent, 0 in child, -1 on error |
| `vfork()` | `<unistd.h>` | Create child (shares memory) | Same as fork |
| `execve()` | `<unistd.h>` | Execute program | Does not return on success, -1 on error |
| `execl()` | `<unistd.h>` | Execute program (list args) | Same as execve |
| `execv()` | `<unistd.h>` | Execute program (vector args) | Same as execve |
| `wait()` | `<sys/wait.h>` | Wait for any child | Child PID, -1 on error |
| `waitpid()` | `<sys/wait.h>` | Wait for specific child | Child PID, -1 on error |
| `exit()` | `<stdlib.h>` | Exit process (with cleanup) | Does not return |
| `_exit()` | `<unistd.h>` | Exit immediately | Does not return |
| `getpid()` | `<unistd.h>` | Get process ID | PID (always succeeds) |
| `getppid()` | `<unistd.h>` | Get parent process ID | Parent PID |
| `getpgid()` | `<unistd.h>` | Get process group ID | PGID, -1 on error |
| `setpgid()` | `<unistd.h>` | Set process group ID | 0 on success, -1 on error |
| `setsid()` | `<unistd.h>` | Create session | Session ID, -1 on error |
| `nice()` | `<unistd.h>` | Change priority | New nice value, -1 on error |

## File Operations

| System Call | Header | Description | Returns |
|------------|--------|-------------|---------|
| `open()` | `<fcntl.h>` | Open file | FD on success, -1 on error |
| `creat()` | `<fcntl.h>` | Create file | FD on success, -1 on error |
| `close()` | `<unistd.h>` | Close file descriptor | 0 on success, -1 on error |
| `read()` | `<unistd.h>` | Read from FD | Bytes read, 0 on EOF, -1 on error |
| `write()` | `<unistd.h>` | Write to FD | Bytes written, -1 on error |
| `lseek()` | `<unistd.h>` | Reposition file offset | New offset, -1 on error |
| `pread()` | `<unistd.h>` | Read from offset | Bytes read, -1 on error |
| `pwrite()` | `<unistd.h>` | Write to offset | Bytes written, -1 on error |
| `dup()` | `<unistd.h>` | Duplicate FD | New FD, -1 on error |
| `dup2()` | `<unistd.h>` | Duplicate to specific FD | New FD, -1 on error |
| `fcntl()` | `<fcntl.h>` | File control operations | Varies, -1 on error |
| `ioctl()` | `<sys/ioctl.h>` | Device control | 0 on success, -1 on error |
| `stat()` | `<sys/stat.h>` | Get file status | 0 on success, -1 on error |
| `fstat()` | `<sys/stat.h>` | Get file status by FD | 0 on success, -1 on error |
| `lstat()` | `<sys/stat.h>` | Get link status | 0 on success, -1 on error |
| `chmod()` | `<sys/stat.h>` | Change permissions | 0 on success, -1 on error |
| `chown()` | `<unistd.h>` | Change owner | 0 on success, -1 on error |
| `link()` | `<unistd.h>` | Create hard link | 0 on success, -1 on error |
| `unlink()` | `<unistd.h>` | Remove file | 0 on success, -1 on error |
| `symlink()` | `<unistd.h>` | Create symbolic link | 0 on success, -1 on error |
| `readlink()` | `<unistd.h>` | Read symbolic link | Bytes read, -1 on error |
| `rename()` | `<stdio.h>` | Rename file | 0 on success, -1 on error |
| `mkdir()` | `<sys/stat.h>` | Create directory | 0 on success, -1 on error |
| `rmdir()` | `<unistd.h>` | Remove directory | 0 on success, -1 on error |
| `chdir()` | `<unistd.h>` | Change directory | 0 on success, -1 on error |
| `getcwd()` | `<unistd.h>` | Get current directory | Pointer, NULL on error |
| `truncate()` | `<unistd.h>` | Truncate file | 0 on success, -1 on error |
| `ftruncate()` | `<unistd.h>` | Truncate file by FD | 0 on success, -1 on error |

## Memory Management

| System Call | Header | Description | Returns |
|------------|--------|-------------|---------|
| `brk()` | `<unistd.h>` | Change data segment size | 0 on success, -1 on error |
| `sbrk()` | `<unistd.h>` | Increment data segment | Previous break, -1 on error |
| `mmap()` | `<sys/mman.h>` | Map memory | Address, MAP_FAILED on error |
| `munmap()` | `<sys/mman.h>` | Unmap memory | 0 on success, -1 on error |
| `mremap()` | `<sys/mman.h>` | Remap memory | Address, MAP_FAILED on error |
| `mprotect()` | `<sys/mman.h>` | Set memory protection | 0 on success, -1 on error |
| `mlock()` | `<sys/mman.h>` | Lock memory pages | 0 on success, -1 on error |
| `munlock()` | `<sys/mman.h>` | Unlock memory pages | 0 on success, -1 on error |
| `mlockall()` | `<sys/mman.h>` | Lock all memory | 0 on success, -1 on error |
| `munlockall()` | `<sys/mman.h>` | Unlock all memory | 0 on success, -1 on error |
| `madvise()` | `<sys/mman.h>` | Give memory advice | 0 on success, -1 on error |
| `msync()` | `<sys/mman.h>` | Sync memory with storage | 0 on success, -1 on error |
| `shmget()` | `<sys/shm.h>` | Get shared memory | Segment ID, -1 on error |
| `shmat()` | `<sys/shm.h>` | Attach shared memory | Address, -1 on error |
| `shmdt()` | `<sys/shm.h>` | Detach shared memory | 0 on success, -1 on error |
| `shmctl()` | `<sys/shm.h>` | Shared memory control | 0 on success, -1 on error |

## Resource Management

| System Call | Header | Description | Returns |
|------------|--------|-------------|---------|
| `getrlimit()` | `<sys/resource.h>` | Get resource limits | 0 on success, -1 on error |
| `setrlimit()` | `<sys/resource.h>` | Set resource limits | 0 on success, -1 on error |
| `prlimit()` | `<sys/resource.h>` | Get/set resource limits | 0 on success, -1 on error |
| `getrusage()` | `<sys/resource.h>` | Get resource usage | 0 on success, -1 on error |
| `getpriority()` | `<sys/resource.h>` | Get priority | Priority, -1 on error |
| `setpriority()` | `<sys/resource.h>` | Set priority | 0 on success, -1 on error |

## Inter-Process Communication

### Pipes

| System Call | Header | Description | Returns |
|------------|--------|-------------|---------|
| `pipe()` | `<unistd.h>` | Create pipe | 0 on success, -1 on error |
| `pipe2()` | `<unistd.h>` | Create pipe with flags | 0 on success, -1 on error |
| `mkfifo()` | `<sys/stat.h>` | Create named pipe | 0 on success, -1 on error |

### Signals

| System Call | Header | Description | Returns |
|------------|--------|-------------|---------|
| `signal()` | `<signal.h>` | Set signal handler | Previous handler, SIG_ERR on error |
| `sigaction()` | `<signal.h>` | Set signal action | 0 on success, -1 on error |
| `kill()` | `<signal.h>` | Send signal | 0 on success, -1 on error |
| `raise()` | `<signal.h>` | Send signal to self | 0 on success, -1 on error |
| `alarm()` | `<unistd.h>` | Set alarm | Seconds until previous alarm |
| `pause()` | `<unistd.h>` | Wait for signal | Always returns -1 |
| `sigprocmask()` | `<signal.h>` | Change signal mask | 0 on success, -1 on error |
| `sigpending()` | `<signal.h>` | Get pending signals | 0 on success, -1 on error |
| `sigsuspend()` | `<signal.h>` | Wait for signal | Always returns -1 |

### Message Queues

| System Call | Header | Description | Returns |
|------------|--------|-------------|---------|
| `msgget()` | `<sys/msg.h>` | Create/get message queue | Queue ID, -1 on error |
| `msgsnd()` | `<sys/msg.h>` | Send message | 0 on success, -1 on error |
| `msgrcv()` | `<sys/msg.h>` | Receive message | Bytes received, -1 on error |
| `msgctl()` | `<sys/msg.h>` | Message queue control | 0 on success, -1 on error |

### Semaphores

| System Call | Header | Description | Returns |
|------------|--------|-------------|---------|
| `semget()` | `<sys/sem.h>` | Create/get semaphore | Semaphore ID, -1 on error |
| `semop()` | `<sys/sem.h>` | Semaphore operations | 0 on success, -1 on error |
| `semctl()` | `<sys/sem.h>` | Semaphore control | Varies, -1 on error |

### Sockets

| System Call | Header | Description | Returns |
|------------|--------|-------------|---------|
| `socket()` | `<sys/socket.h>` | Create socket | FD on success, -1 on error |
| `bind()` | `<sys/socket.h>` | Bind socket to address | 0 on success, -1 on error |
| `listen()` | `<sys/socket.h>` | Listen for connections | 0 on success, -1 on error |
| `accept()` | `<sys/socket.h>` | Accept connection | FD on success, -1 on error |
| `connect()` | `<sys/socket.h>` | Connect to address | 0 on success, -1 on error |
| `send()` | `<sys/socket.h>` | Send data | Bytes sent, -1 on error |
| `recv()` | `<sys/socket.h>` | Receive data | Bytes received, -1 on error |
| `sendto()` | `<sys/socket.h>` | Send to address | Bytes sent, -1 on error |
| `recvfrom()` | `<sys/socket.h>` | Receive from address | Bytes received, -1 on error |
| `shutdown()` | `<sys/socket.h>` | Shut down connection | 0 on success, -1 on error |
| `setsockopt()` | `<sys/socket.h>` | Set socket options | 0 on success, -1 on error |
| `getsockopt()` | `<sys/socket.h>` | Get socket options | 0 on success, -1 on error |

## Time and Date

| System Call | Header | Description | Returns |
|------------|--------|-------------|---------|
| `time()` | `<time.h>` | Get current time | Seconds since epoch, -1 on error |
| `gettimeofday()` | `<sys/time.h>` | Get time with microseconds | 0 on success, -1 on error |
| `clock_gettime()` | `<time.h>` | Get time (various clocks) | 0 on success, -1 on error |
| `nanosleep()` | `<time.h>` | Sleep with nanoseconds | 0 on success, -1 on error |
| `times()` | `<sys/times.h>` | Get process times | Clock ticks, -1 on error |

## System Information

| System Call | Header | Description | Returns |
|------------|--------|-------------|---------|
| `uname()` | `<sys/utsname.h>` | Get system information | 0 on success, -1 on error |
| `sysinfo()` | `<sys/sysinfo.h>` | Get system statistics | 0 on success, -1 on error |
| `sysconf()` | `<unistd.h>` | Get system configuration | Value, -1 on error |

## Common Flags and Constants

### open() Flags
```
O_RDONLY    - Read only
O_WRONLY    - Write only
O_RDWR      - Read and write
O_CREAT     - Create if not exists
O_EXCL      - Exclusive create
O_TRUNC     - Truncate to 0
O_APPEND    - Append mode
O_NONBLOCK  - Non-blocking I/O
O_SYNC      - Synchronous writes
```

### mmap() Protection Flags
```
PROT_NONE   - No access
PROT_READ   - Read access
PROT_WRITE  - Write access
PROT_EXEC   - Execute access
```

### mmap() Mapping Flags
```
MAP_SHARED     - Share changes
MAP_PRIVATE    - Private copy-on-write
MAP_ANONYMOUS  - No file backing
MAP_FIXED      - Fixed address
```

### Signal Actions
```
SIG_DFL     - Default action
SIG_IGN     - Ignore signal
handler     - Custom handler function
```

### Resource Limits
```
RLIMIT_CPU      - CPU time
RLIMIT_FSIZE    - File size
RLIMIT_DATA     - Data segment
RLIMIT_STACK    - Stack size
RLIMIT_CORE     - Core file size
RLIMIT_NOFILE   - Open files
RLIMIT_AS       - Address space
RLIMIT_NPROC    - Process count
```

## Error Codes (errno)

```
EPERM       - Operation not permitted
ENOENT      - No such file or directory
ESRCH       - No such process
EINTR       - Interrupted system call
EIO         - I/O error
ENXIO       - No such device or address
EBADF       - Bad file descriptor
ECHILD      - No child processes
EAGAIN      - Resource temporarily unavailable
ENOMEM      - Out of memory
EACCES      - Permission denied
EFAULT      - Bad address
EBUSY       - Device or resource busy
EEXIST      - File exists
ENOTDIR     - Not a directory
EISDIR      - Is a directory
EINVAL      - Invalid argument
EMFILE      - Too many open files
ENOSPC      - No space left on device
EPIPE       - Broken pipe
```

## Usage Examples

### File Operations
```c
int fd = open("file.txt", O_RDONLY);
if (fd == -1) {
    perror("open");
    exit(1);
}

char buf[1024];
ssize_t n = read(fd, buf, sizeof(buf));
close(fd);
```

### Process Management
```c
pid_t pid = fork();
if (pid == 0) {
    // Child process
    execlp("ls", "ls", "-l", NULL);
} else {
    // Parent process
    wait(NULL);
}
```

### Memory Mapping
```c
void *addr = mmap(NULL, 4096,
                  PROT_READ | PROT_WRITE,
                  MAP_PRIVATE | MAP_ANONYMOUS,
                  -1, 0);
if (addr == MAP_FAILED) {
    perror("mmap");
    exit(1);
}
munmap(addr, 4096);
```

### Signals
```c
struct sigaction sa;
sa.sa_handler = signal_handler;
sigemptyset(&sa.sa_mask);
sa.sa_flags = 0;
sigaction(SIGINT, &sa, NULL);
```

## Man Page Sections

- **Section 1**: User commands
- **Section 2**: System calls ← Use this for syscalls
- **Section 3**: Library functions
- **Section 5**: File formats
- **Section 7**: Miscellaneous (overviews)

```bash
man 2 open     # System call
man 3 printf   # Library function
man 7 signal   # Overview
```

## Quick Tips

1. **Always check return values**
2. **Use errno and strerror() for errors**
3. **Close file descriptors when done**
4. **Free/unmap allocated memory**
5. **Use sigaction() instead of signal()**
6. **Read man pages: `man 2 syscall_name`**
7. **Use strace to debug: `strace ./program`**

