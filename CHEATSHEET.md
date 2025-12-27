# System Calls Cheat Sheet with Examples

Quick reference guide with code examples for all major Linux system calls.

## Table of Contents

- [Process Management](#process-management)
- [File Operations](#file-operations)
- [Memory Management](#memory-management)
- [Resource Management](#resource-management)
- [Inter-Process Communication](#inter-process-communication)

---

## Process Management

### fork() - Create Process

```c
#include <unistd.h>
#include <sys/wait.h>

pid_t pid = fork();
if (pid == -1) {
    perror("fork");
    exit(1);
}

if (pid == 0) {
    // Child process
    printf("Child PID: %d\n", getpid());
    exit(0);
} else {
    // Parent process
    printf("Parent PID: %d, Child PID: %d\n", getpid(), pid);
    wait(NULL);
}
```

### exec() - Execute Program

```c
#include <unistd.h>

// execl - list arguments
execl("/bin/ls", "ls", "-l", "-a", NULL);
perror("execl");  // Only reached on error

// execlp - search PATH
execlp("ls", "ls", "-l", NULL);

// execv - vector arguments
char *args[] = {"ls", "-l", NULL};
execv("/bin/ls", args);

// execvp - vector + PATH
char *args[] = {"grep", "pattern", "file.txt", NULL};
execvp("grep", args);
```

### wait() - Wait for Child

```c
#include <sys/wait.h>

int status;
pid_t child_pid = wait(&status);

if (child_pid == -1) {
    perror("wait");
    exit(1);
}

if (WIFEXITED(status)) {
    printf("Child exited with status %d\n", WEXITSTATUS(status));
}
if (WIFSIGNALED(status)) {
    printf("Child killed by signal %d\n", WTERMSIG(status));
}
```

### waitpid() - Wait for Specific Child

```c
#include <sys/wait.h>

int status;
pid_t result = waitpid(child_pid, &status, WNOHANG);

if (result == 0) {
    printf("Child still running\n");
} else if (result == child_pid) {
    printf("Child terminated\n");
} else {
    perror("waitpid");
}
```

### getpid/getppid() - Get Process IDs

```c
#include <unistd.h>

pid_t my_pid = getpid();
pid_t parent_pid = getppid();
pid_t group_id = getpgid(0);
pid_t session_id = getsid(0);

printf("PID: %d, PPID: %d, PGID: %d, SID: %d\n",
       my_pid, parent_pid, group_id, session_id);
```

### nice() - Change Priority

```c
#include <unistd.h>
#include <sys/resource.h>

// Increase nice value (lower priority)
errno = 0;
int new_nice = nice(5);
if (new_nice == -1 && errno != 0) {
    perror("nice");
}

// Get current priority
int priority = getpriority(PRIO_PROCESS, 0);
printf("Current nice value: %d\n", priority);

// Set priority
if (setpriority(PRIO_PROCESS, 0, 10) == -1) {
    perror("setpriority");
}
```

### exit() - Terminate Process

```c
#include <stdlib.h>
#include <unistd.h>

// exit() - calls cleanup functions
exit(0);

// _exit() - immediate termination
_exit(1);

// Exit with code
exit(EXIT_SUCCESS);  // 0
exit(EXIT_FAILURE);  // 1
```

---

## File Operations

### open() - Open File

```c
#include <fcntl.h>
#include <unistd.h>

// Open for reading
int fd = open("file.txt", O_RDONLY);
if (fd == -1) {
    perror("open");
    exit(1);
}

// Open for writing (create if needed)
fd = open("file.txt", O_WRONLY | O_CREAT | O_TRUNC, 0644);

// Open for read/write (append mode)
fd = open("file.txt", O_RDWR | O_APPEND);

// Open with exclusive create
fd = open("file.txt", O_WRONLY | O_CREAT | O_EXCL, 0644);
```

### read() - Read from File

```c
#include <unistd.h>

char buf[1024];
ssize_t bytes_read = read(fd, buf, sizeof(buf));

if (bytes_read == -1) {
    perror("read");
    exit(1);
}
if (bytes_read == 0) {
    printf("End of file\n");
}

// Read in loop (handle partial reads)
size_t total = 0;
while (total < sizeof(buf)) {
    ssize_t n = read(fd, buf + total, sizeof(buf) - total);
    if (n <= 0) break;
    total += n;
}
```

### write() - Write to File

```c
#include <unistd.h>
#include <string.h>

const char *msg = "Hello, World!\n";
ssize_t bytes_written = write(fd, msg, strlen(msg));

if (bytes_written == -1) {
    perror("write");
    exit(1);
}

// Write in loop (handle partial writes)
size_t total = 0;
size_t len = strlen(msg);
while (total < len) {
    ssize_t n = write(fd, msg + total, len - total);
    if (n == -1) {
        perror("write");
        break;
    }
    total += n;
}
```

### lseek() - Change File Offset

```c
#include <unistd.h>

// Seek to beginning
off_t pos = lseek(fd, 0, SEEK_SET);

// Seek to end
pos = lseek(fd, 0, SEEK_END);

// Get current position
pos = lseek(fd, 0, SEEK_CUR);

// Seek forward 100 bytes
pos = lseek(fd, 100, SEEK_CUR);

// Seek backward 50 bytes from end
pos = lseek(fd, -50, SEEK_END);

if (pos == -1) {
    perror("lseek");
}
```

### close() - Close File

```c
#include <unistd.h>

if (close(fd) == -1) {
    perror("close");
}
```

### dup/dup2() - Duplicate File Descriptor

```c
#include <unistd.h>

// Duplicate to lowest available FD
int new_fd = dup(old_fd);
if (new_fd == -1) {
    perror("dup");
}

// Duplicate to specific FD
if (dup2(old_fd, new_fd) == -1) {
    perror("dup2");
}

// Redirect stdout to file
int fd = open("output.txt", O_WRONLY | O_CREAT | O_TRUNC, 0644);
dup2(fd, STDOUT_FILENO);
close(fd);
printf("This goes to file\n");
```

### stat() - Get File Information

```c
#include <sys/stat.h>

struct stat sb;

if (stat("file.txt", &sb) == -1) {
    perror("stat");
    exit(1);
}

printf("File size: %ld bytes\n", sb.st_size);
printf("Inode: %lu\n", sb.st_ino);
printf("Permissions: %o\n", sb.st_mode & 0777);
printf("Links: %lu\n", sb.st_nlink);

if (S_ISREG(sb.st_mode))  printf("Regular file\n");
if (S_ISDIR(sb.st_mode))  printf("Directory\n");
if (S_ISLNK(sb.st_mode))  printf("Symbolic link\n");
```

### fstat() - Get File Info by FD

```c
#include <sys/stat.h>

int fd = open("file.txt", O_RDONLY);
struct stat sb;

if (fstat(fd, &sb) == -1) {
    perror("fstat");
    close(fd);
    exit(1);
}

printf("File size: %ld bytes\n", sb.st_size);
close(fd);
```

### chmod() - Change Permissions

```c
#include <sys/stat.h>

// Symbolic: rw-r--r--
if (chmod("file.txt", 0644) == -1) {
    perror("chmod");
}

// Symbolic: rwxr-xr-x
chmod("script.sh", 0755);

// By file descriptor
int fd = open("file.txt", O_RDWR);
fchmod(fd, 0600);
close(fd);
```

### chown() - Change Owner

```c
#include <unistd.h>

// Change owner and group
if (chown("file.txt", 1000, 1000) == -1) {
    perror("chown");
}

// Change only owner (-1 = don't change)
chown("file.txt", 1000, -1);

// By file descriptor
int fd = open("file.txt", O_RDWR);
fchown(fd, 1000, 1000);
close(fd);
```

### link() - Create Hard Link

```c
#include <unistd.h>

if (link("original.txt", "hardlink.txt") == -1) {
    perror("link");
}
```

### unlink() - Remove File

```c
#include <unistd.h>

if (unlink("file.txt") == -1) {
    perror("unlink");
}
```

### symlink() - Create Symbolic Link

```c
#include <unistd.h>

if (symlink("target.txt", "symlink.txt") == -1) {
    perror("symlink");
}
```

### readlink() - Read Symbolic Link

```c
#include <unistd.h>

char buf[1024];
ssize_t len = readlink("symlink.txt", buf, sizeof(buf) - 1);

if (len == -1) {
    perror("readlink");
    exit(1);
}

buf[len] = '\0';
printf("Symlink points to: %s\n", buf);
```

### mkdir() - Create Directory

```c
#include <sys/stat.h>

if (mkdir("newdir", 0755) == -1) {
    perror("mkdir");
}
```

### rmdir() - Remove Directory

```c
#include <unistd.h>

if (rmdir("emptydir") == -1) {
    perror("rmdir");
}
```

### chdir() - Change Directory

```c
#include <unistd.h>

if (chdir("/tmp") == -1) {
    perror("chdir");
}

// By file descriptor
int fd = open("/tmp", O_RDONLY | O_DIRECTORY);
fchdir(fd);
close(fd);
```

### getcwd() - Get Current Directory

```c
#include <unistd.h>

char cwd[1024];
if (getcwd(cwd, sizeof(cwd)) == NULL) {
    perror("getcwd");
    exit(1);
}

printf("Current directory: %s\n", cwd);
```

### opendir/readdir/closedir() - Directory Operations

```c
#include <dirent.h>
#include <stdio.h>

DIR *dir = opendir(".");
if (dir == NULL) {
    perror("opendir");
    exit(1);
}

struct dirent *entry;
while ((entry = readdir(dir)) != NULL) {
    printf("%s\n", entry->d_name);
}

closedir(dir);
```

### fcntl() - File Control

```c
#include <fcntl.h>

// Get file status flags
int flags = fcntl(fd, F_GETFL);
if (flags == -1) {
    perror("fcntl F_GETFL");
}

// Set to non-blocking
flags |= O_NONBLOCK;
if (fcntl(fd, F_SETFL, flags) == -1) {
    perror("fcntl F_SETFL");
}

// Set close-on-exec flag
if (fcntl(fd, F_SETFD, FD_CLOEXEC) == -1) {
    perror("fcntl F_SETFD");
}

// File locking
struct flock lock;
lock.l_type = F_WRLCK;     // Write lock
lock.l_whence = SEEK_SET;
lock.l_start = 0;
lock.l_len = 0;            // Lock entire file

if (fcntl(fd, F_SETLK, &lock) == -1) {
    perror("fcntl F_SETLK");
}
```

### truncate() - Truncate File

```c
#include <unistd.h>

// Truncate to 100 bytes
if (truncate("file.txt", 100) == -1) {
    perror("truncate");
}

// By file descriptor
int fd = open("file.txt", O_RDWR);
ftruncate(fd, 100);
close(fd);
```

---

## Memory Management

### brk/sbrk() - Change Heap Size

```c
#include <unistd.h>

// Get current break
void *current = sbrk(0);

// Allocate 1024 bytes
void *new_mem = sbrk(1024);
if (new_mem == (void *)-1) {
    perror("sbrk");
    exit(1);
}

// Use the memory
char *buffer = (char *)new_mem;
strcpy(buffer, "Hello");

// Set break to specific address
if (brk(new_address) == -1) {
    perror("brk");
}
```

### mmap() - Memory Mapping

```c
#include <sys/mman.h>
#include <fcntl.h>

// Anonymous memory (like malloc)
void *addr = mmap(NULL, 4096,
                  PROT_READ | PROT_WRITE,
                  MAP_PRIVATE | MAP_ANONYMOUS,
                  -1, 0);
if (addr == MAP_FAILED) {
    perror("mmap");
    exit(1);
}

// Map a file
int fd = open("file.txt", O_RDWR);
struct stat sb;
fstat(fd, &sb);

char *mapped = mmap(NULL, sb.st_size,
                   PROT_READ | PROT_WRITE,
                   MAP_SHARED,
                   fd, 0);
close(fd);  // Can close after mapping

if (mapped == MAP_FAILED) {
    perror("mmap");
    exit(1);
}

// Use mapped memory
mapped[0] = 'X';  // Modifies file!
```

### munmap() - Unmap Memory

```c
#include <sys/mman.h>

if (munmap(addr, length) == -1) {
    perror("munmap");
}
```

### mprotect() - Change Memory Protection

```c
#include <sys/mman.h>

// Make read-only
if (mprotect(addr, length, PROT_READ) == -1) {
    perror("mprotect");
}

// Make read-write
mprotect(addr, length, PROT_READ | PROT_WRITE);

// Make no access
mprotect(addr, length, PROT_NONE);

// Make executable
mprotect(addr, length, PROT_READ | PROT_EXEC);
```

### mlock/munlock() - Lock Memory

```c
#include <sys/mman.h>

// Lock pages in RAM (prevent swapping)
if (mlock(addr, length) == -1) {
    perror("mlock");
}

// Lock all pages
if (mlockall(MCL_CURRENT | MCL_FUTURE) == -1) {
    perror("mlockall");
}

// Unlock
munlock(addr, length);
munlockall();
```

### msync() - Sync Memory with Storage

```c
#include <sys/mman.h>

// Sync changes to disk
if (msync(addr, length, MS_SYNC) == -1) {
    perror("msync");
}

// Async sync
msync(addr, length, MS_ASYNC);

// Invalidate cache
msync(addr, length, MS_INVALIDATE);
```

### madvise() - Give Memory Advice

```c
#include <sys/mman.h>

// Sequential access pattern
madvise(addr, length, MADV_SEQUENTIAL);

// Random access pattern
madvise(addr, length, MADV_RANDOM);

// Will need soon (prefetch)
madvise(addr, length, MADV_WILLNEED);

// Won't need (can free)
madvise(addr, length, MADV_DONTNEED);
```

### Shared Memory (System V)

```c
#include <sys/shm.h>
#include <sys/ipc.h>

// Create shared memory
key_t key = ftok("/tmp", 'R');
int shmid = shmget(key, 1024, IPC_CREAT | 0666);
if (shmid == -1) {
    perror("shmget");
    exit(1);
}

// Attach to shared memory
char *shmaddr = shmat(shmid, NULL, 0);
if (shmaddr == (char *)-1) {
    perror("shmat");
    exit(1);
}

// Use shared memory
strcpy(shmaddr, "Hello, shared memory!");

// Detach
if (shmdt(shmaddr) == -1) {
    perror("shmdt");
}

// Remove segment
if (shmctl(shmid, IPC_RMID, NULL) == -1) {
    perror("shmctl");
}
```

---

## Resource Management

### getrlimit/setrlimit() - Resource Limits

```c
#include <sys/resource.h>

struct rlimit limit;

// Get current limits
if (getrlimit(RLIMIT_NOFILE, &limit) == -1) {
    perror("getrlimit");
    exit(1);
}

printf("Soft limit: %lu\n", limit.rlim_cur);
printf("Hard limit: %lu\n", limit.rlim_max);

// Set new limits
limit.rlim_cur = 2048;  // Soft limit
limit.rlim_max = 4096;  // Hard limit (needs root)

if (setrlimit(RLIMIT_NOFILE, &limit) == -1) {
    perror("setrlimit");
}

// Common resources:
// RLIMIT_CPU      - CPU time in seconds
// RLIMIT_FSIZE    - Maximum file size
// RLIMIT_DATA     - Data segment size
// RLIMIT_STACK    - Stack size
// RLIMIT_CORE     - Core file size
// RLIMIT_NOFILE   - Number of open files
// RLIMIT_AS       - Address space (virtual memory)
// RLIMIT_NPROC    - Number of processes
```

### getrusage() - Resource Usage

```c
#include <sys/resource.h>

struct rusage usage;

// Get current process usage
if (getrusage(RUSAGE_SELF, &usage) == -1) {
    perror("getrusage");
    exit(1);
}

printf("User CPU time: %ld.%06ld sec\n",
       usage.ru_utime.tv_sec, usage.ru_utime.tv_usec);
printf("System CPU time: %ld.%06ld sec\n",
       usage.ru_stime.tv_sec, usage.ru_stime.tv_usec);
printf("Max RSS: %ld KB\n", usage.ru_maxrss);
printf("Page faults (minor): %ld\n", usage.ru_minflt);
printf("Page faults (major): %ld\n", usage.ru_majflt);

// Get children's usage
getrusage(RUSAGE_CHILDREN, &usage);
```

### getpriority/setpriority() - Process Priority

```c
#include <sys/resource.h>

// Get priority
errno = 0;
int priority = getpriority(PRIO_PROCESS, 0);
if (errno != 0) {
    perror("getpriority");
}

// Set priority (needs privileges for negative values)
if (setpriority(PRIO_PROCESS, 0, 10) == -1) {
    perror("setpriority");
}

// Priority for process group
setpriority(PRIO_PGRP, pgid, 5);

// Priority for user
setpriority(PRIO_USER, uid, 5);
```

---

## Inter-Process Communication

### pipe() - Create Pipe

**Basic Pipe Example**

```c
#include <unistd.h>
#include <sys/wait.h>

int pipefd[2];
if (pipe(pipefd) == -1) {
    perror("pipe");
    exit(1);
}

pid_t pid = fork();
if (pid == 0) {
    // Child - reader
    close(pipefd[1]);  // Close write end
    
    char buf[100];
    ssize_t n = read(pipefd[0], buf, sizeof(buf));
    buf[n] = '\0';
    printf("Child received: %s\n", buf);
    
    close(pipefd[0]);
    exit(0);
} else {
    // Parent - writer
    close(pipefd[0]);  // Close read end
    
    write(pipefd[1], "Hello", 5);
    
    close(pipefd[1]);
    wait(NULL);
}
```

**Bidirectional Communication (Two Pipes)**

```c
#include <unistd.h>

int pipe1[2], pipe2[2];  // pipe1: parent->child, pipe2: child->parent

if (pipe(pipe1) == -1 || pipe(pipe2) == -1) {
    perror("pipe");
    exit(1);
}

pid_t pid = fork();
if (pid == 0) {
    // Child
    close(pipe1[1]);  // Close unused write end of pipe1
    close(pipe2[0]);  // Close unused read end of pipe2
    
    // Read from parent
    char buf[100];
    read(pipe1[0], buf, sizeof(buf));
    printf("Child received: %s\n", buf);
    
    // Send to parent
    write(pipe2[1], "Reply from child", 16);
    
    close(pipe1[0]);
    close(pipe2[1]);
    exit(0);
} else {
    // Parent
    close(pipe1[0]);  // Close unused read end of pipe1
    close(pipe2[1]);  // Close unused write end of pipe2
    
    // Send to child
    write(pipe1[1], "Hello child", 11);
    
    // Read from child
    char buf[100];
    read(pipe2[0], buf, sizeof(buf));
    printf("Parent received: %s\n", buf);
    
    close(pipe1[1]);
    close(pipe2[0]);
    wait(NULL);
}
```

**Pipe with exec() - Shell Pipeline**

```c
#include <unistd.h>
#include <sys/wait.h>

// Implement: ls -l | grep ".txt"

int pipefd[2];
if (pipe(pipefd) == -1) {
    perror("pipe");
    exit(1);
}

// First child: ls -l
pid_t pid1 = fork();
if (pid1 == 0) {
    close(pipefd[0]);                    // Close read end
    dup2(pipefd[1], STDOUT_FILENO);      // Redirect stdout to pipe
    close(pipefd[1]);
    
    execlp("ls", "ls", "-l", NULL);
    perror("execlp ls");
    exit(1);
}

// Second child: grep ".txt"
pid_t pid2 = fork();
if (pid2 == 0) {
    close(pipefd[1]);                    // Close write end
    dup2(pipefd[0], STDIN_FILENO);       // Redirect stdin from pipe
    close(pipefd[0]);
    
    execlp("grep", "grep", ".txt", NULL);
    perror("execlp grep");
    exit(1);
}

// Parent
close(pipefd[0]);
close(pipefd[1]);

waitpid(pid1, NULL, 0);
waitpid(pid2, NULL, 0);
```

**Non-blocking Pipe**

```c
#include <unistd.h>
#include <fcntl.h>

int pipefd[2];
pipe(pipefd);

// Make read end non-blocking
int flags = fcntl(pipefd[0], F_GETFL);
fcntl(pipefd[0], F_SETFL, flags | O_NONBLOCK);

// Try to read (won't block if no data)
char buf[100];
ssize_t n = read(pipefd[0], buf, sizeof(buf));
if (n == -1 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
    printf("No data available\n");
}
```

**Pipe Capacity Check**

```c
#include <unistd.h>
#include <fcntl.h>

int pipefd[2];
pipe(pipefd);

#ifdef F_GETPIPE_SZ
long capacity = fcntl(pipefd[0], F_GETPIPE_SZ);
printf("Pipe capacity: %ld bytes\n", capacity);

// Set pipe capacity (requires root or sufficient limit)
fcntl(pipefd[0], F_SETPIPE_SZ, 1048576);  // 1MB
#endif
```

### mkfifo() - Create Named Pipe

```c
#include <sys/stat.h>
#include <fcntl.h>

// Create FIFO
if (mkfifo("/tmp/myfifo", 0666) == -1) {
    perror("mkfifo");
    exit(1);
}

// Writer process
int fd = open("/tmp/myfifo", O_WRONLY);
write(fd, "Hello", 5);
close(fd);

// Reader process
int fd = open("/tmp/myfifo", O_RDONLY);
char buf[100];
ssize_t n = read(fd, buf, sizeof(buf));
buf[n] = '\0';
close(fd);

// Cleanup
unlink("/tmp/myfifo");
```

### signal/sigaction() - Signal Handling

```c
#include <signal.h>

// Simple signal handler
void handler(int signum) {
    printf("Caught signal %d\n", signum);
}

// Using signal() (deprecated)
signal(SIGINT, handler);

// Using sigaction() (preferred)
struct sigaction sa;
sa.sa_handler = handler;
sigemptyset(&sa.sa_mask);
sa.sa_flags = 0;

if (sigaction(SIGINT, &sa, NULL) == -1) {
    perror("sigaction");
    exit(1);
}

// Ignore signal
sa.sa_handler = SIG_IGN;
sigaction(SIGTERM, &sa, NULL);

// Default action
sa.sa_handler = SIG_DFL;
sigaction(SIGTERM, &sa, NULL);
```

### kill() - Send Signal

```c
#include <signal.h>

// Send signal to process
if (kill(pid, SIGTERM) == -1) {
    perror("kill");
}

// Send to process group
kill(-pgid, SIGTERM);

// Send to self
kill(getpid(), SIGUSR1);

// Check if process exists
if (kill(pid, 0) == 0) {
    printf("Process exists\n");
}
```

### raise() - Send Signal to Self

```c
#include <signal.h>

if (raise(SIGTERM) == -1) {
    perror("raise");
}
```

### alarm() - Set Alarm

```c
#include <unistd.h>

// Set alarm for 5 seconds
unsigned int prev = alarm(5);

// Cancel alarm
alarm(0);

// Alarm sends SIGALRM when time expires
```

### sigprocmask() - Change Signal Mask

```c
#include <signal.h>

sigset_t new_mask, old_mask;

// Initialize empty set
sigemptyset(&new_mask);

// Add signals to set
sigaddset(&new_mask, SIGINT);
sigaddset(&new_mask, SIGTERM);

// Block signals
if (sigprocmask(SIG_BLOCK, &new_mask, &old_mask) == -1) {
    perror("sigprocmask");
}

// Critical section - signals are blocked
// ...

// Unblock signals
sigprocmask(SIG_UNBLOCK, &new_mask, NULL);

// Restore old mask
sigprocmask(SIG_SETMASK, &old_mask, NULL);
```

### sigpending() - Check Pending Signals

```c
#include <signal.h>

sigset_t pending;
if (sigpending(&pending) == -1) {
    perror("sigpending");
    exit(1);
}

if (sigismember(&pending, SIGINT)) {
    printf("SIGINT is pending\n");
}
```

### Message Queue (System V)

**Basic Message Queue**

```c
#include <sys/msg.h>
#include <sys/ipc.h>
#include <string.h>

struct msgbuf {
    long mtype;
    char mtext[100];
};

// Create message queue
key_t key = ftok("/tmp", 'M');
int msqid = msgget(key, IPC_CREAT | 0666);
if (msqid == -1) {
    perror("msgget");
    exit(1);
}

// Send message
struct msgbuf msg;
msg.mtype = 1;
strcpy(msg.mtext, "Hello");

if (msgsnd(msqid, &msg, strlen(msg.mtext) + 1, 0) == -1) {
    perror("msgsnd");
}

// Receive message
struct msgbuf rcv;
if (msgrcv(msqid, &rcv, sizeof(rcv.mtext), 1, 0) == -1) {
    perror("msgrcv");
}

printf("Received: %s\n", rcv.mtext);

// Remove queue
msgctl(msqid, IPC_RMID, NULL);
```

**Multiple Message Types (Priority Queue)**

```c
#include <sys/msg.h>

struct message {
    long mtype;
    int priority;
    char data[100];
};

int msqid = msgget(IPC_PRIVATE, IPC_CREAT | 0666);

// Send messages with different types
struct message msg;

// High priority (type 1)
msg.mtype = 1;
msg.priority = 10;
strcpy(msg.data, "High priority message");
msgsnd(msqid, &msg, sizeof(msg) - sizeof(long), 0);

// Normal priority (type 2)
msg.mtype = 2;
msg.priority = 5;
strcpy(msg.data, "Normal priority message");
msgsnd(msqid, &msg, sizeof(msg) - sizeof(long), 0);

// Low priority (type 3)
msg.mtype = 3;
msg.priority = 1;
strcpy(msg.data, "Low priority message");
msgsnd(msqid, &msg, sizeof(msg) - sizeof(long), 0);

// Receive specific type
struct message rcv;
msgrcv(msqid, &rcv, sizeof(rcv) - sizeof(long), 1, 0);  // Get type 1

// Receive any type
msgrcv(msqid, &rcv, sizeof(rcv) - sizeof(long), 0, 0);  // Get first message

// Receive lowest type <= 3
msgrcv(msqid, &rcv, sizeof(rcv) - sizeof(long), -3, 0);

// Non-blocking receive
msgrcv(msqid, &rcv, sizeof(rcv) - sizeof(long), 0, IPC_NOWAIT);
```

**Message Queue Information**

```c
#include <sys/msg.h>

struct msqid_ds info;

// Get queue info
if (msgctl(msqid, IPC_STAT, &info) == -1) {
    perror("msgctl IPC_STAT");
    exit(1);
}

printf("Messages in queue: %lu\n", info.msg_qnum);
printf("Queue size (bytes): %lu\n", info.msg_qbytes);
printf("Last send PID: %d\n", info.msg_lspid);
printf("Last recv PID: %d\n", info.msg_lrpid);

// Set queue permissions
info.msg_perm.mode = 0644;
msgctl(msqid, IPC_SET, &info);
```

**Producer-Consumer with Message Queue**

```c
#include <sys/msg.h>
#include <unistd.h>

#define MSG_TYPE_DATA 1
#define MSG_TYPE_DONE 2

struct msg {
    long mtype;
    int data;
};

int msqid = msgget(IPC_PRIVATE, IPC_CREAT | 0666);

pid_t pid = fork();
if (pid == 0) {
    // Producer
    for (int i = 0; i < 10; i++) {
        struct msg m;
        m.mtype = MSG_TYPE_DATA;
        m.data = i * i;
        msgsnd(msqid, &m, sizeof(m.data), 0);
        printf("Produced: %d\n", m.data);
        usleep(100000);
    }
    
    // Send done message
    struct msg done;
    done.mtype = MSG_TYPE_DONE;
    msgsnd(msqid, &done, 0, 0);
    exit(0);
} else {
    // Consumer
    while (1) {
        struct msg m;
        
        // Try to receive done message first (non-blocking)
        if (msgrcv(msqid, &m, sizeof(m.data), MSG_TYPE_DONE, IPC_NOWAIT) != -1) {
            printf("Received done signal\n");
            break;
        }
        
        // Receive data message
        if (msgrcv(msqid, &m, sizeof(m.data), MSG_TYPE_DATA, 0) != -1) {
            printf("Consumed: %d\n", m.data);
        }
    }
    
    wait(NULL);
    msgctl(msqid, IPC_RMID, NULL);
}
```

### Semaphore (System V)

**Binary Semaphore (Mutex)**

```c
#include <sys/sem.h>
#include <sys/ipc.h>

union semun {
    int val;
    struct semid_ds *buf;
    unsigned short *array;
};

// Create semaphore
key_t key = ftok("/tmp", 'S');
int semid = semget(key, 1, IPC_CREAT | 0666);
if (semid == -1) {
    perror("semget");
    exit(1);
}

// Initialize semaphore to 1 (unlocked)
union semun arg;
arg.val = 1;
if (semctl(semid, 0, SETVAL, arg) == -1) {
    perror("semctl");
}

// P operation (wait/lock)
struct sembuf op;
op.sem_num = 0;
op.sem_op = -1;  // Decrement
op.sem_flg = 0;
if (semop(semid, &op, 1) == -1) {
    perror("semop wait");
}

// Critical section
printf("In critical section\n");

// V operation (signal/unlock)
op.sem_op = 1;  // Increment
if (semop(semid, &op, 1) == -1) {
    perror("semop signal");
}

// Remove semaphore
semctl(semid, 0, IPC_RMID);
```

**Counting Semaphore (Resource Pool)**

```c
#include <sys/sem.h>

#define NUM_RESOURCES 5

// Create semaphore
int semid = semget(IPC_PRIVATE, 1, IPC_CREAT | 0666);

// Initialize to number of resources
union semun arg;
arg.val = NUM_RESOURCES;
semctl(semid, 0, SETVAL, arg);

// Acquire resource
struct sembuf acquire;
acquire.sem_num = 0;
acquire.sem_op = -1;
acquire.sem_flg = 0;
semop(semid, &acquire, 1);

printf("Resource acquired. Available: %d\n", 
       semctl(semid, 0, GETVAL));

// Use resource
// ...

// Release resource
struct sembuf release;
release.sem_num = 0;
release.sem_op = 1;
release.sem_flg = 0;
semop(semid, &release, 1);
```

**Non-blocking Semaphore**

```c
#include <sys/sem.h>

struct sembuf op;
op.sem_num = 0;
op.sem_op = -1;
op.sem_flg = IPC_NOWAIT;  // Non-blocking

if (semop(semid, &op, 1) == -1) {
    if (errno == EAGAIN) {
        printf("Semaphore not available\n");
    } else {
        perror("semop");
    }
}
```

**Semaphore with Undo (SEM_UNDO)**

```c
#include <sys/sem.h>

// If process dies, operation is undone automatically
struct sembuf op;
op.sem_num = 0;
op.sem_op = -1;
op.sem_flg = SEM_UNDO;  // Undo if process terminates

semop(semid, &op, 1);

// If process exits without releasing, semaphore is auto-incremented
```

**Multiple Semaphores (Semaphore Set)**

```c
#include <sys/sem.h>

// Create set of 3 semaphores
int semid = semget(IPC_PRIVATE, 3, IPC_CREAT | 0666);

// Initialize all semaphores
union semun arg;
unsigned short values[3] = {1, 1, 1};
arg.array = values;
semctl(semid, 0, SETALL, arg);

// Atomic operation on multiple semaphores
struct sembuf ops[2];

// Lock semaphore 0
ops[0].sem_num = 0;
ops[0].sem_op = -1;
ops[0].sem_flg = 0;

// Lock semaphore 1
ops[1].sem_num = 1;
ops[1].sem_op = -1;
ops[1].sem_flg = 0;

// Both acquire atomically or neither
if (semop(semid, ops, 2) == -1) {
    perror("semop");
}
```

**Producer-Consumer with Semaphores**

```c
#include <sys/sem.h>
#include <sys/shm.h>

#define BUFFER_SIZE 5

struct shared {
    int buffer[BUFFER_SIZE];
    int in;
    int out;
};

// Semaphores: 0=mutex, 1=empty_slots, 2=full_slots
int semid = semget(IPC_PRIVATE, 3, IPC_CREAT | 0666);

union semun arg;
arg.val = 1;
semctl(semid, 0, SETVAL, arg);  // mutex = 1
arg.val = BUFFER_SIZE;
semctl(semid, 1, SETVAL, arg);  // empty = BUFFER_SIZE
arg.val = 0;
semctl(semid, 2, SETVAL, arg);  // full = 0

// Producer
void produce(int semid, struct shared *buf, int item) {
    struct sembuf ops[3];
    
    // Wait for empty slot
    ops[0].sem_num = 1;
    ops[0].sem_op = -1;
    ops[0].sem_flg = 0;
    
    // Acquire mutex
    ops[1].sem_num = 0;
    ops[1].sem_op = -1;
    ops[1].sem_flg = 0;
    
    semop(semid, ops, 2);
    
    // Produce
    buf->buffer[buf->in] = item;
    buf->in = (buf->in + 1) % BUFFER_SIZE;
    
    // Release mutex
    ops[0].sem_num = 0;
    ops[0].sem_op = 1;
    
    // Signal full slot
    ops[1].sem_num = 2;
    ops[1].sem_op = 1;
    
    semop(semid, ops, 2);
}

// Consumer
int consume(int semid, struct shared *buf) {
    struct sembuf ops[3];
    
    // Wait for full slot
    ops[0].sem_num = 2;
    ops[0].sem_op = -1;
    ops[0].sem_flg = 0;
    
    // Acquire mutex
    ops[1].sem_num = 0;
    ops[1].sem_op = -1;
    ops[1].sem_flg = 0;
    
    semop(semid, ops, 2);
    
    // Consume
    int item = buf->buffer[buf->out];
    buf->out = (buf->out + 1) % BUFFER_SIZE;
    
    // Release mutex
    ops[0].sem_num = 0;
    ops[0].sem_op = 1;
    
    // Signal empty slot
    ops[1].sem_num = 1;
    ops[1].sem_op = 1;
    
    semop(semid, ops, 2);
    
    return item;
}
```

### Socket (TCP)

**TCP Server**

```c
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>

// Create socket
int server_fd = socket(AF_INET, SOCK_STREAM, 0);
if (server_fd == -1) {
    perror("socket");
    exit(1);
}

// Set socket options (reuse address)
int opt = 1;
if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, 
               &opt, sizeof(opt)) == -1) {
    perror("setsockopt");
}

// Bind to address
struct sockaddr_in addr;
addr.sin_family = AF_INET;
addr.sin_addr.s_addr = INADDR_ANY;  // All interfaces
addr.sin_port = htons(8080);

if (bind(server_fd, (struct sockaddr *)&addr, sizeof(addr)) == -1) {
    perror("bind");
    exit(1);
}

// Listen for connections
if (listen(server_fd, 5) == -1) {
    perror("listen");
    exit(1);
}

printf("Server listening on port 8080\n");

// Accept connection
struct sockaddr_in client_addr;
socklen_t client_len = sizeof(client_addr);
int client_fd = accept(server_fd, (struct sockaddr *)&client_addr, &client_len);
if (client_fd == -1) {
    perror("accept");
    exit(1);
}

char client_ip[INET_ADDRSTRLEN];
inet_ntop(AF_INET, &client_addr.sin_addr, client_ip, sizeof(client_ip));
printf("Client connected: %s:%d\n", client_ip, ntohs(client_addr.sin_port));

// Receive and send
char buf[1024];
ssize_t n = recv(client_fd, buf, sizeof(buf), 0);
if (n > 0) {
    buf[n] = '\0';
    printf("Received: %s\n", buf);
    send(client_fd, "ACK", 3, 0);
}

close(client_fd);
close(server_fd);
```

**TCP Client**

```c
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

// Create socket
int sock = socket(AF_INET, SOCK_STREAM, 0);
if (sock == -1) {
    perror("socket");
    exit(1);
}

// Connect to server
struct sockaddr_in server_addr;
server_addr.sin_family = AF_INET;
server_addr.sin_port = htons(8080);

if (inet_pton(AF_INET, "127.0.0.1", &server_addr.sin_addr) <= 0) {
    perror("inet_pton");
    exit(1);
}

if (connect(sock, (struct sockaddr *)&server_addr, 
            sizeof(server_addr)) == -1) {
    perror("connect");
    exit(1);
}

printf("Connected to server\n");

// Send and receive
send(sock, "Hello Server", 12, 0);

char buf[1024];
ssize_t n = recv(sock, buf, sizeof(buf), 0);
if (n > 0) {
    buf[n] = '\0';
    printf("Received: %s\n", buf);
}

close(sock);
```

**UDP Socket**

```c
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

// UDP Server
int sockfd = socket(AF_INET, SOCK_DGRAM, 0);

struct sockaddr_in server_addr;
server_addr.sin_family = AF_INET;
server_addr.sin_addr.s_addr = INADDR_ANY;
server_addr.sin_port = htons(8080);

bind(sockfd, (struct sockaddr *)&server_addr, sizeof(server_addr));

// Receive datagram
struct sockaddr_in client_addr;
socklen_t client_len = sizeof(client_addr);
char buf[1024];

ssize_t n = recvfrom(sockfd, buf, sizeof(buf), 0,
                     (struct sockaddr *)&client_addr, &client_len);
buf[n] = '\0';
printf("Received: %s\n", buf);

// Send reply
sendto(sockfd, "ACK", 3, 0,
       (struct sockaddr *)&client_addr, client_len);

close(sockfd);
```

```c
// UDP Client
int sockfd = socket(AF_INET, SOCK_DGRAM, 0);

struct sockaddr_in server_addr;
server_addr.sin_family = AF_INET;
server_addr.sin_port = htons(8080);
inet_pton(AF_INET, "127.0.0.1", &server_addr.sin_addr);

// Send datagram
sendto(sockfd, "Hello", 5, 0,
       (struct sockaddr *)&server_addr, sizeof(server_addr));

// Receive reply
char buf[1024];
ssize_t n = recvfrom(sockfd, buf, sizeof(buf), 0, NULL, NULL);
buf[n] = '\0';
printf("Received: %s\n", buf);

close(sockfd);
```

**Unix Domain Socket (Local IPC)**

```c
#include <sys/socket.h>
#include <sys/un.h>

// Server
int sockfd = socket(AF_UNIX, SOCK_STREAM, 0);

struct sockaddr_un addr;
addr.sun_family = AF_UNIX;
strcpy(addr.sun_path, "/tmp/my_socket");

unlink(addr.sun_path);  // Remove old socket file
bind(sockfd, (struct sockaddr *)&addr, sizeof(addr));
listen(sockfd, 5);

int client_fd = accept(sockfd, NULL, NULL);

// Use like TCP socket
char buf[1024];
recv(client_fd, buf, sizeof(buf), 0);
send(client_fd, "ACK", 3, 0);

close(client_fd);
close(sockfd);
unlink(addr.sun_path);
```

```c
// Client
int sockfd = socket(AF_UNIX, SOCK_STREAM, 0);

struct sockaddr_un addr;
addr.sun_family = AF_UNIX;
strcpy(addr.sun_path, "/tmp/my_socket");

connect(sockfd, (struct sockaddr *)&addr, sizeof(addr));

send(sockfd, "Hello", 5, 0);

char buf[1024];
recv(sockfd, buf, sizeof(buf), 0);

close(sockfd);
```

**Socket Options**

```c
#include <sys/socket.h>

int sockfd = socket(AF_INET, SOCK_STREAM, 0);

// Reuse address
int opt = 1;
setsockopt(sockfd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

// Keep alive
setsockopt(sockfd, SOL_SOCKET, SO_KEEPALIVE, &opt, sizeof(opt));

// Send timeout
struct timeval tv;
tv.tv_sec = 5;
tv.tv_usec = 0;
setsockopt(sockfd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));

// Receive timeout
setsockopt(sockfd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));

// Send buffer size
int bufsize = 65536;
setsockopt(sockfd, SOL_SOCKET, SO_SNDBUF, &bufsize, sizeof(bufsize));

// Receive buffer size
setsockopt(sockfd, SOL_SOCKET, SO_RCVBUF, &bufsize, sizeof(bufsize));

// Get socket error
int error;
socklen_t len = sizeof(error);
getsockopt(sockfd, SOL_SOCKET, SO_ERROR, &error, &len);

// TCP no delay (disable Nagle's algorithm)
setsockopt(sockfd, IPPROTO_TCP, TCP_NODELAY, &opt, sizeof(opt));
```

---

## I/O Multiplexing

### select() - Monitor Multiple File Descriptors

```c
#include <sys/select.h>

int main() {
    fd_set readfds, writefds;
    struct timeval timeout;
    
    // Initialize sets
    FD_ZERO(&readfds);
    FD_ZERO(&writefds);
    
    // Add file descriptors to sets
    FD_SET(STDIN_FILENO, &readfds);  // Monitor stdin
    FD_SET(sockfd, &readfds);         // Monitor socket
    FD_SET(sockfd, &writefds);        // Monitor if writable
    
    // Set timeout (5 seconds)
    timeout.tv_sec = 5;
    timeout.tv_usec = 0;
    
    // Monitor file descriptors
    int ready = select(sockfd + 1, &readfds, &writefds, NULL, &timeout);
    
    if (ready == -1) {
        perror("select");
        exit(1);
    }
    else if (ready == 0) {
        printf("Timeout\n");
    }
    else {
        // Check which fd is ready
        if (FD_ISSET(STDIN_FILENO, &readfds)) {
            printf("stdin is ready for reading\n");
            char buf[1024];
            read(STDIN_FILENO, buf, sizeof(buf));
        }
        
        if (FD_ISSET(sockfd, &readfds)) {
            printf("socket is ready for reading\n");
            char buf[1024];
            recv(sockfd, buf, sizeof(buf), 0);
        }
        
        if (FD_ISSET(sockfd, &writefds)) {
            printf("socket is ready for writing\n");
            send(sockfd, "data", 4, 0);
        }
    }
    
    return 0;
}
```

**Server Using select()**

```c
#include <sys/select.h>

#define MAX_CLIENTS 10

int main() {
    int server_fd, client_fds[MAX_CLIENTS];
    fd_set master_set, read_set;
    int max_fd;
    
    // Initialize
    server_fd = socket(AF_INET, SOCK_STREAM, 0);
    // bind, listen...
    
    FD_ZERO(&master_set);
    FD_SET(server_fd, &master_set);
    max_fd = server_fd;
    
    for (int i = 0; i < MAX_CLIENTS; i++) {
        client_fds[i] = -1;
    }
    
    while (1) {
        read_set = master_set;
        
        if (select(max_fd + 1, &read_set, NULL, NULL, NULL) == -1) {
            perror("select");
            break;
        }
        
        // Check for new connection
        if (FD_ISSET(server_fd, &read_set)) {
            int new_fd = accept(server_fd, NULL, NULL);
            
            // Add to client list
            for (int i = 0; i < MAX_CLIENTS; i++) {
                if (client_fds[i] == -1) {
                    client_fds[i] = new_fd;
                    FD_SET(new_fd, &master_set);
                    if (new_fd > max_fd) max_fd = new_fd;
                    break;
                }
            }
        }
        
        // Check client sockets
        for (int i = 0; i < MAX_CLIENTS; i++) {
            int fd = client_fds[i];
            if (fd != -1 && FD_ISSET(fd, &read_set)) {
                char buf[1024];
                ssize_t n = recv(fd, buf, sizeof(buf), 0);
                
                if (n <= 0) {
                    // Client disconnected
                    close(fd);
                    FD_CLR(fd, &master_set);
                    client_fds[i] = -1;
                } else {
                    // Process data
                    send(fd, buf, n, 0);  // Echo back
                }
            }
        }
    }
    
    return 0;
}
```

### poll() - Alternative to select()

```c
#include <poll.h>

int main() {
    struct pollfd fds[3];
    
    // Monitor stdin
    fds[0].fd = STDIN_FILENO;
    fds[0].events = POLLIN;
    
    // Monitor socket for reading
    fds[1].fd = sockfd;
    fds[1].events = POLLIN;
    
    // Monitor socket for writing
    fds[2].fd = sockfd;
    fds[2].events = POLLOUT;
    
    // Wait indefinitely (-1 timeout)
    int ready = poll(fds, 3, -1);
    
    if (ready == -1) {
        perror("poll");
        exit(1);
    }
    
    // Check events
    if (fds[0].revents & POLLIN) {
        printf("stdin ready\n");
    }
    
    if (fds[1].revents & POLLIN) {
        printf("socket ready for reading\n");
    }
    
    if (fds[2].revents & POLLOUT) {
        printf("socket ready for writing\n");
    }
    
    if (fds[1].revents & (POLLERR | POLLHUP | POLLNVAL)) {
        printf("socket error\n");
    }
    
    return 0;
}
```

### epoll() - Linux-specific, High Performance

```c
#include <sys/epoll.h>

int main() {
    // Create epoll instance
    int epoll_fd = epoll_create1(0);
    if (epoll_fd == -1) {
        perror("epoll_create1");
        exit(1);
    }
    
    // Add file descriptor to epoll
    struct epoll_event event;
    event.events = EPOLLIN | EPOLLOUT;  // Monitor read and write
    event.data.fd = sockfd;
    
    if (epoll_ctl(epoll_fd, EPOLL_CTL_ADD, sockfd, &event) == -1) {
        perror("epoll_ctl");
        exit(1);
    }
    
    // Wait for events
    struct epoll_event events[10];
    int num_events = epoll_wait(epoll_fd, events, 10, 5000);  // 5 sec timeout
    
    if (num_events == -1) {
        perror("epoll_wait");
        exit(1);
    }
    
    for (int i = 0; i < num_events; i++) {
        if (events[i].events & EPOLLIN) {
            printf("fd %d ready for reading\n", events[i].data.fd);
        }
        if (events[i].events & EPOLLOUT) {
            printf("fd %d ready for writing\n", events[i].data.fd);
        }
        if (events[i].events & EPOLLERR) {
            printf("fd %d error\n", events[i].data.fd);
        }
    }
    
    // Modify monitoring
    event.events = EPOLLIN;  // Only read now
    epoll_ctl(epoll_fd, EPOLL_CTL_MOD, sockfd, &event);
    
    // Remove from epoll
    epoll_ctl(epoll_fd, EPOLL_CTL_DEL, sockfd, NULL);
    
    close(epoll_fd);
    return 0;
}
```

**High-Performance Server with epoll()**

```c
#include <sys/epoll.h>

#define MAX_EVENTS 64

int main() {
    int server_fd, epoll_fd;
    struct epoll_event event, events[MAX_EVENTS];
    
    // Create server socket
    server_fd = socket(AF_INET, SOCK_STREAM, 0);
    // bind, listen...
    
    // Make non-blocking
    int flags = fcntl(server_fd, F_GETFL, 0);
    fcntl(server_fd, F_SETFL, flags | O_NONBLOCK);
    
    // Create epoll
    epoll_fd = epoll_create1(0);
    
    // Add server socket
    event.events = EPOLLIN;
    event.data.fd = server_fd;
    epoll_ctl(epoll_fd, EPOLL_CTL_ADD, server_fd, &event);
    
    while (1) {
        int n = epoll_wait(epoll_fd, events, MAX_EVENTS, -1);
        
        for (int i = 0; i < n; i++) {
            if (events[i].data.fd == server_fd) {
                // New connection
                int client_fd = accept(server_fd, NULL, NULL);
                
                // Make non-blocking
                flags = fcntl(client_fd, F_GETFL, 0);
                fcntl(client_fd, F_SETFL, flags | O_NONBLOCK);
                
                // Add to epoll
                event.events = EPOLLIN | EPOLLET;  // Edge-triggered
                event.data.fd = client_fd;
                epoll_ctl(epoll_fd, EPOLL_CTL_ADD, client_fd, &event);
            }
            else {
                // Data from client
                char buf[1024];
                ssize_t count = read(events[i].data.fd, buf, sizeof(buf));
                
                if (count <= 0) {
                    // Connection closed or error
                    epoll_ctl(epoll_fd, EPOLL_CTL_DEL, events[i].data.fd, NULL);
                    close(events[i].data.fd);
                } else {
                    // Echo back
                    write(events[i].data.fd, buf, count);
                }
            }
        }
    }
    
    return 0;
}
```

---

## POSIX IPC (Modern Alternative to System V)

### POSIX Message Queue

```c
#include <mqueue.h>
#include <fcntl.h>

// Open/create queue
mqd_t mq = mq_open("/my_queue", O_CREAT | O_RDWR, 0666, NULL);
if (mq == -1) {
    perror("mq_open");
    exit(1);
}

// Set attributes
struct mq_attr attr;
attr.mq_flags = 0;
attr.mq_maxmsg = 10;
attr.mq_msgsize = 256;
mq_setattr(mq, &attr, NULL);

// Send message with priority
const char *msg = "Hello";
if (mq_send(mq, msg, strlen(msg), 5) == -1) {  // Priority 5
    perror("mq_send");
}

// Receive message
char buf[256];
unsigned int prio;
ssize_t n = mq_receive(mq, buf, sizeof(buf), &prio);
if (n != -1) {
    buf[n] = '\0';
    printf("Received (prio %u): %s\n", prio, buf);
}

// Non-blocking receive
mq_getattr(mq, &attr);
attr.mq_flags = O_NONBLOCK;
mq_setattr(mq, &attr, NULL);

// Timed receive (5 seconds)
struct timespec timeout;
clock_gettime(CLOCK_REALTIME, &timeout);
timeout.tv_sec += 5;
n = mq_timedreceive(mq, buf, sizeof(buf), &prio, &timeout);

// Cleanup
mq_close(mq);
mq_unlink("/my_queue");
```

### POSIX Semaphore (Named)

```c
#include <semaphore.h>
#include <fcntl.h>

// Create/open named semaphore
sem_t *sem = sem_open("/my_sem", O_CREAT, 0666, 1);
if (sem == SEM_FAILED) {
    perror("sem_open");
    exit(1);
}

// Wait (P operation)
if (sem_wait(sem) == -1) {
    perror("sem_wait");
}

// Critical section
printf("In critical section\n");

// Post (V operation)
if (sem_post(sem) == -1) {
    perror("sem_post");
}

// Try wait (non-blocking)
if (sem_trywait(sem) == -1) {
    if (errno == EAGAIN) {
        printf("Semaphore not available\n");
    }
}

// Timed wait
struct timespec timeout;
clock_gettime(CLOCK_REALTIME, &timeout);
timeout.tv_sec += 5;
sem_timedwait(sem, &timeout);

// Get value
int value;
sem_getvalue(sem, &value);
printf("Semaphore value: %d\n", value);

// Cleanup
sem_close(sem);
sem_unlink("/my_sem");
```

### POSIX Semaphore (Unnamed/Memory)

```c
#include <semaphore.h>

// Allocate in shared memory or use mmap
sem_t *sem = mmap(NULL, sizeof(sem_t),
                  PROT_READ | PROT_WRITE,
                  MAP_SHARED | MAP_ANONYMOUS,
                  -1, 0);

// Initialize (pshared=1 for shared between processes)
if (sem_init(sem, 1, 1) == -1) {
    perror("sem_init");
    exit(1);
}

// Use semaphore
sem_wait(sem);
// Critical section
sem_post(sem);

// Destroy
sem_destroy(sem);
munmap(sem, sizeof(sem_t));
```

### POSIX Shared Memory

```c
#include <sys/mman.h>
#include <fcntl.h>
#include <unistd.h>

// Create shared memory object
int fd = shm_open("/my_shm", O_CREAT | O_RDWR, 0666);
if (fd == -1) {
    perror("shm_open");
    exit(1);
}

// Set size
if (ftruncate(fd, 4096) == -1) {
    perror("ftruncate");
    exit(1);
}

// Map to memory
void *addr = mmap(NULL, 4096,
                  PROT_READ | PROT_WRITE,
                  MAP_SHARED,
                  fd, 0);
if (addr == MAP_FAILED) {
    perror("mmap");
    exit(1);
}

close(fd);  // Can close after mapping

// Use shared memory
char *data = (char *)addr;
strcpy(data, "Hello, shared memory!");

// Unmap
munmap(addr, 4096);

// Remove
shm_unlink("/my_shm");
```

---

## Advanced IPC Patterns

### Producer-Consumer with Shared Memory and Semaphores

```c
#include <sys/mman.h>
#include <semaphore.h>
#include <fcntl.h>

#define BUFFER_SIZE 10

struct shared_buffer {
    int buffer[BUFFER_SIZE];
    int in;
    int out;
    sem_t mutex;
    sem_t empty;
    sem_t full;
};

int main() {
    // Create shared memory
    int fd = shm_open("/prod_cons", O_CREAT | O_RDWR, 0666);
    ftruncate(fd, sizeof(struct shared_buffer));
    
    struct shared_buffer *buf = mmap(NULL, sizeof(struct shared_buffer),
                                     PROT_READ | PROT_WRITE,
                                     MAP_SHARED, fd, 0);
    close(fd);
    
    // Initialize semaphores
    sem_init(&buf->mutex, 1, 1);        // Shared, value 1
    sem_init(&buf->empty, 1, BUFFER_SIZE);  // Empty slots
    sem_init(&buf->full, 1, 0);         // Full slots
    
    buf->in = 0;
    buf->out = 0;
    
    pid_t pid = fork();
    
    if (pid == 0) {
        // Producer
        for (int i = 0; i < 20; i++) {
            sem_wait(&buf->empty);
            sem_wait(&buf->mutex);
            
            buf->buffer[buf->in] = i;
            printf("Produced: %d\n", i);
            buf->in = (buf->in + 1) % BUFFER_SIZE;
            
            sem_post(&buf->mutex);
            sem_post(&buf->full);
            
            usleep(100000);
        }
        exit(0);
    }
    else {
        // Consumer
        for (int i = 0; i < 20; i++) {
            sem_wait(&buf->full);
            sem_wait(&buf->mutex);
            
            int item = buf->buffer[buf->out];
            printf("Consumed: %d\n", item);
            buf->out = (buf->out + 1) % BUFFER_SIZE;
            
            sem_post(&buf->mutex);
            sem_post(&buf->empty);
            
            usleep(150000);
        }
        
        wait(NULL);
        
        // Cleanup
        sem_destroy(&buf->mutex);
        sem_destroy(&buf->empty);
        sem_destroy(&buf->full);
        munmap(buf, sizeof(struct shared_buffer));
        shm_unlink("/prod_cons");
    }
    
    return 0;
}
```

### Reader-Writer Lock with Semaphores

```c
#include <semaphore.h>
#include <sys/mman.h>

struct rw_lock {
    sem_t mutex;
    sem_t write_lock;
    int readers;
};

void init_rw_lock(struct rw_lock *lock) {
    sem_init(&lock->mutex, 1, 1);
    sem_init(&lock->write_lock, 1, 1);
    lock->readers = 0;
}

void read_lock(struct rw_lock *lock) {
    sem_wait(&lock->mutex);
    lock->readers++;
    if (lock->readers == 1) {
        sem_wait(&lock->write_lock);  // First reader blocks writers
    }
    sem_post(&lock->mutex);
}

void read_unlock(struct rw_lock *lock) {
    sem_wait(&lock->mutex);
    lock->readers--;
    if (lock->readers == 0) {
        sem_post(&lock->write_lock);  // Last reader allows writers
    }
    sem_post(&lock->mutex);
}

void write_lock(struct rw_lock *lock) {
    sem_wait(&lock->write_lock);
}

void write_unlock(struct rw_lock *lock) {
    sem_post(&lock->write_lock);
}
```

### Event Notification with Pipes

```c
#include <unistd.h>
#include <fcntl.h>

// Event notification pipe (like eventfd)
int event_pipe[2];
pipe(event_pipe);

// Make read end non-blocking
int flags = fcntl(event_pipe[0], F_GETFL);
fcntl(event_pipe[0], F_SETFL, flags | O_NONBLOCK);

// Signal event
void signal_event() {
    write(event_pipe[1], "E", 1);
}

// Wait for event
void wait_event() {
    char buf;
    read(event_pipe[0], &buf, 1);
}

// Check event (non-blocking)
int check_event() {
    char buf;
    return read(event_pipe[0], &buf, 1) > 0;
}
```

---

## Time Functions

### time() - Get Current Time

```c
#include <time.h>

time_t now = time(NULL);
if (now == -1) {
    perror("time");
}

printf("Seconds since epoch: %ld\n", now);
```

### gettimeofday() - Get Time with Microseconds

```c
#include <sys/time.h>

struct timeval tv;
if (gettimeofday(&tv, NULL) == -1) {
    perror("gettimeofday");
}

printf("Time: %ld.%06ld\n", tv.tv_sec, tv.tv_usec);
```

### clock_gettime() - High Resolution Time

```c
#include <time.h>

struct timespec ts;
if (clock_gettime(CLOCK_REALTIME, &ts) == -1) {
    perror("clock_gettime");
}

printf("Time: %ld.%09ld\n", ts.tv_sec, ts.tv_nsec);

// Monotonic clock (not affected by time adjustments)
clock_gettime(CLOCK_MONOTONIC, &ts);
```

### nanosleep() - Sleep with Nanoseconds

```c
#include <time.h>

struct timespec req, rem;
req.tv_sec = 1;
req.tv_nsec = 500000000;  // 1.5 seconds

if (nanosleep(&req, &rem) == -1) {
    perror("nanosleep");
    printf("Remaining: %ld.%09ld\n", rem.tv_sec, rem.tv_nsec);
}
```

---

## System Information

### uname() - Get System Info

```c
#include <sys/utsname.h>

struct utsname info;
if (uname(&info) == -1) {
    perror("uname");
    exit(1);
}

printf("System: %s\n", info.sysname);
printf("Node: %s\n", info.nodename);
printf("Release: %s\n", info.release);
printf("Version: %s\n", info.version);
printf("Machine: %s\n", info.machine);
```

### sysconf() - Get System Configuration

```c
#include <unistd.h>

long page_size = sysconf(_SC_PAGESIZE);
long num_cpus = sysconf(_SC_NPROCESSORS_ONLN);
long phys_pages = sysconf(_SC_PHYS_PAGES);
long avail_pages = sysconf(_SC_AVPHYS_PAGES);
long max_open_files = sysconf(_SC_OPEN_MAX);

printf("Page size: %ld bytes\n", page_size);
printf("CPUs: %ld\n", num_cpus);
printf("Total RAM: %ld MB\n", 
       (phys_pages * page_size) / (1024 * 1024));
```

---

## Error Handling Pattern

### Standard Error Checking

```c
#include <errno.h>
#include <string.h>
#include <stdio.h>

// Pattern 1: Check return value
int fd = open("file.txt", O_RDONLY);
if (fd == -1) {
    fprintf(stderr, "Error opening file: %s\n", strerror(errno));
    exit(1);
}

// Pattern 2: Print to stderr with context
if (write(fd, buf, len) == -1) {
    perror("write");  // Prints "write: Error message"
    exit(1);
}

// Pattern 3: Different actions based on error
ssize_t n = read(fd, buf, sizeof(buf));
if (n == -1) {
    if (errno == EINTR) {
        // Interrupted by signal, retry
    } else if (errno == EAGAIN || errno == EWOULDBLOCK) {
        // Would block, try later
    } else {
        perror("read");
        exit(1);
    }
}
```

---

## Quick Tips

1. **Always check return values** - Most syscalls return -1 on error
2. **Use errno** - Check errno for error details
3. **perror() or strerror()** - Print human-readable errors
4. **Close file descriptors** - Avoid resource leaks
5. **Handle EINTR** - Retry interrupted syscalls
6. **Use sigaction()** - Prefer over signal()
7. **Check man pages** - `man 2 syscall_name` for details

---

## Compilation

```bash
# Basic
gcc -o program program.c

# With warnings
gcc -Wall -Wextra -o program program.c

# With debugging
gcc -g -Wall -o program program.c

# With optimization
gcc -O2 -Wall -o program program.c
```

---

## Debugging Tools

```bash
# Trace system calls
strace ./program

# Trace specific syscall
strace -e open,read,write ./program

# Attach to running process
strace -p <pid>

# Memory debugging
valgrind ./program

# Check for memory leaks
valgrind --leak-check=full ./program
```

---

For complete documentation, see:
- `man 2 <syscall>` - System call manual
- `man errno` - Error codes
- `man syscalls` - List of all system calls

