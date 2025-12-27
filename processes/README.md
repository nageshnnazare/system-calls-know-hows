# Process Management System Calls

## Overview

Process management is fundamental to Unix/Linux systems. This tutorial covers all major system calls for creating, managing, and terminating processes.

## Process Lifecycle

```
                    ┌─────────────────────────────────────┐
                    │   Parent Process (PID: 1000)        │
                    │                                     │
                    │   int main() {                      │
                    │       pid_t pid = fork();           │
                    │       ...                           │
                    │   }                                 │
                    └──────────────┬──────────────────────┘
                                   │
                         fork() system call
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
                    ▼                             ▼
    ┌───────────────────────────┐   ┌───────────────────────────┐
    │  Parent (PID: 1000)       │   │  Child (PID: 1001)        │
    │  fork() returns 1001      │   │  fork() returns 0         │
    │                           │   │                           │
    │  if (pid > 0) {           │   │  if (pid == 0) {          │
    │      // parent code       │   │      // child code        │
    │      wait(&status);       │   │      exec("/bin/ls");     │
    │  }                        │   │  }                        │
    └───────────────────────────┘   └───────────────────────────┘
              │                                   │
              │                                   │
              │         Child terminates          │
              │  ◄────────────────────────────────┘
              │    exit(0) / _exit(0)
              │
              ▼
    ┌───────────────────────────┐
    │  wait() returns           │
    │  Process continues...     │
    └───────────────────────────┘
```

## 1. fork() - Create a New Process

### Synopsis
```c
#include <unistd.h>
pid_t fork(void);
```

### Description
Creates a new process by duplicating the calling process. The new process (child) is an exact copy of the parent, except:
- Different PID
- Different PPID (parent PID)
- Copy of file descriptors
- Copy of memory (copy-on-write)

### Return Value
- **Parent process**: Returns child's PID (positive number)
- **Child process**: Returns 0
- **Error**: Returns -1

### Memory Layout After fork()

```
Before fork():
┌─────────────────────────────────────┐
│  Process (PID: 1000)                │
│  ┌───────────────────────────────┐  │
│  │  Text (Code) Segment          │  │
│  ├───────────────────────────────┤  │
│  │  Data Segment                 │  │
│  │  int x = 10;                  │  │
│  ├───────────────────────────────┤  │
│  │  Heap                         │  │
│  │  (dynamic memory)             │  │
│  ├───────────────────────────────┤  │
│  │  Stack                        │  │
│  │  (local variables)            │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘

After fork():
┌─────────────────────────────────────┐    ┌─────────────────────────────────────┐
│  Parent (PID: 1000)                 │    │  Child (PID: 1001)                  │
│  ┌───────────────────────────────┐  │    │  ┌───────────────────────────────┐  │
│  │  Text (Code) Segment          │◄─┼────┼─►│  Text (Code) Segment (shared) │  │
│  ├───────────────────────────────┤  │    │  ├───────────────────────────────┤  │
│  │  Data Segment                 │  │    │  │  Data Segment (copy)          │  │
│  │  int x = 10;                  │  │    │  │  int x = 10;                  │  │
│  ├───────────────────────────────┤  │    │  ├───────────────────────────────┤  │
│  │  Heap (copy)                  │  │    │  │  Heap (copy)                  │  │
│  ├───────────────────────────────┤  │    │  ├───────────────────────────────┤  │
│  │  Stack (copy)                 │  │    │  │  Stack (copy)                 │  │
│  └───────────────────────────────┘  │    │  └───────────────────────────────┘  │
└─────────────────────────────────────┘    └─────────────────────────────────────┘
```

### Example
```c
#include <stdio.h>
#include <unistd.h>
#include <sys/types.h>
#include <stdlib.h>

int main() {
    pid_t pid;
    int x = 10;
    
    printf("Before fork: PID=%d, x=%d\n", getpid(), x);
    
    pid = fork();
    
    if (pid < 0) {
        perror("fork failed");
        exit(1);
    }
    else if (pid == 0) {
        // Child process
        x = 20;
        printf("Child:  PID=%d, PPID=%d, x=%d\n", getpid(), getppid(), x);
        exit(0);
    }
    else {
        // Parent process
        x = 30;
        printf("Parent: PID=%d, Child PID=%d, x=%d\n", getpid(), pid, x);
        wait(NULL);  // Wait for child to finish
    }
    
    return 0;
}
```

## 2. exec() Family - Execute a Program

### Synopsis
```c
#include <unistd.h>

int execl(const char *path, const char *arg, ...);
int execlp(const char *file, const char *arg, ...);
int execle(const char *path, const char *arg, ..., char *const envp[]);
int execv(const char *path, char *const argv[]);
int execvp(const char *file, char *const argv[]);
int execve(const char *path, char *const argv[], char *const envp[]);
```

### exec() Memory Transformation

```
Before exec():                        After exec():
┌─────────────────────────────┐      ┌─────────────────────────────┐
│ Process (PID: 1001)         │      │ Process (PID: 1001) ← same  │
│ ┌─────────────────────────┐ │      │ ┌─────────────────────────┐ │
│ │ OLD Text Segment        │ │      │ │ NEW Text Segment        │ │
│ │ (original program code) │ │  →   │ │ (new program code)      │ │
│ ├─────────────────────────┤ │      │ ├─────────────────────────┤ │
│ │ OLD Data                │ │      │ │ NEW Data                │ │
│ ├─────────────────────────┤ │      │ ├─────────────────────────┤ │
│ │ OLD Heap                │ │      │ │ NEW Heap                │ │
│ ├─────────────────────────┤ │      │ ├─────────────────────────┤ │
│ │ OLD Stack               │ │      │ │ NEW Stack               │ │
│ └─────────────────────────┘ │      │ └─────────────────────────┘ │
│                             │      │                             │
│ File Descriptors: 0,1,2...  │  →   │ Same FDs (unless FD_CLOEXEC)│
│ PID: 1001                   │      │ PID: 1001                   │
│ PPID: 1000                  │      │ PPID: 1000                  │
└─────────────────────────────┘      └─────────────────────────────┘
```

### Example
```c
#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>

int main() {
    pid_t pid = fork();
    
    if (pid == 0) {
        // Child process - replace with 'ls' command
        printf("Child: About to exec ls\n");
        execl("/bin/ls", "ls", "-l", NULL);
        
        // This line only executes if exec fails
        perror("exec failed");
        exit(1);
    }
    else {
        // Parent waits for child
        wait(NULL);
        printf("Parent: Child completed\n");
    }
    
    return 0;
}
```

## 3. wait() Family - Wait for Process Termination

### Synopsis
```c
#include <sys/wait.h>

pid_t wait(int *status);
pid_t waitpid(pid_t pid, int *status, int options);
pid_t wait3(int *status, int options, struct rusage *rusage);
pid_t wait4(pid_t pid, int *status, int options, struct rusage *rusage);
```

### Wait Flow Diagram

```
Parent Process                          Child Process
     │                                       │
     │  fork()                               │
     ├───────────────────────────────────►   │
     │                                       │
     │                                       │ Running...
     │  wait() ◄─┐                           │ Doing work...
     │           │                           │
     │  BLOCKED  │                           │
     │           │                           │
     │           │                           ▼
     │           │                      exit(status)
     │           │                           │
     │           │                      ┌────┴─────┐
     │           │                      │  ZOMBIE  │
     │           │                      │  Process │
     │           │                      └────┬─────┘
     │           │                           │
     │  ◄────────┴───────────────────────────┘
     │  wait() returns                  (Zombie reaped)
     │  Receives exit status
     ▼  
  Continue...
```

### Status Macros

```c
WIFEXITED(status)    // True if child terminated normally
WEXITSTATUS(status)  // Exit status of child
WIFSIGNALED(status)  // True if child terminated by signal
WTERMSIG(status)     // Signal that terminated child
WIFSTOPPED(status)   // True if child is stopped
WSTOPSIG(status)     // Signal that stopped child
```

### Example
```c
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/wait.h>

int main() {
    pid_t pid = fork();
    
    if (pid == 0) {
        // Child process
        printf("Child: PID=%d, sleeping 2 seconds\n", getpid());
        sleep(2);
        exit(42);  // Exit with status 42
    }
    else {
        // Parent process
        int status;
        printf("Parent: Waiting for child %d\n", pid);
        
        pid_t child = wait(&status);
        
        if (WIFEXITED(status)) {
            printf("Child %d exited with status %d\n", 
                   child, WEXITSTATUS(status));
        }
        else if (WIFSIGNALED(status)) {
            printf("Child %d killed by signal %d\n", 
                   child, WTERMSIG(status));
        }
    }
    
    return 0;
}
```

## 4. Process IDs

### System Calls
```c
#include <unistd.h>

pid_t getpid(void);   // Get process ID
pid_t getppid(void);  // Get parent process ID
pid_t gettid(void);   // Get thread ID
```

### Process Tree Example

```
                    init/systemd (PID: 1)
                           │
            ┌──────────────┼──────────────┐
            │              │              │
       bash (PID: 500)  sshd (PID: 600)  ...
            │
            ├─── my_program (PID: 1000) ← Parent
            │         │
            │         ├─── child1 (PID: 1001)
            │         │
            │         └─── child2 (PID: 1002)
            │
            └─── ...
```

## 5. exit() and _exit() - Terminate Process

### Synopsis
```c
#include <stdlib.h>
void exit(int status);

#include <unistd.h>
void _exit(int status);
```

### Differences

```
exit() - Library Function                _exit() - System Call
        │                                         │
        ▼                                         ▼
┌─────────────────────┐              ┌─────────────────────┐
│ Flush I/O buffers   │              │ Skip I/O flush      │
│ Call atexit() funcs │              │ Skip atexit()       │
│ Close FILE* streams │              │ Keep streams open   │
└──────────┬──────────┘              └──────────┬──────────┘
           │                                    │
           ▼                                    ▼
        ┌────────────────────────────────────────┐
        │      _exit() system call               │
        │  (Terminate process immediately)       │
        └────────────────────────────────────────┘
```

### Example
```c
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

void cleanup(void) {
    printf("Cleanup function called\n");
}

int main() {
    atexit(cleanup);
    
    pid_t pid = fork();
    
    if (pid == 0) {
        printf("Child: Using _exit() - ");
        printf("this may not be fully printed");
        _exit(0);  // Immediate exit, no flush
    }
    else {
        wait(NULL);
        printf("Parent: Using exit()\n");
        exit(0);   // Calls cleanup(), flushes buffers
    }
}
```

## 6. Process Priority - nice()

### Synopsis
```c
#include <unistd.h>
int nice(int inc);

#include <sys/resource.h>
int getpriority(int which, id_t who);
int setpriority(int which, id_t who, int prio);
```

### Nice Values

```
Priority Scale:  -20 ←──────────── 0 ───────────→ +19
                 │                  │               │
              Highest           Default          Lowest
              Priority          Priority         Priority
              (more CPU)                       (less CPU)
                 
Process Scheduling:
┌────────────────────────────────────────────────────┐
│  CPU Scheduler                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │ High Priority (nice: -20 to -1)              │  │
│  │ ████████████████░░░░  More CPU time          │  │
│  ├──────────────────────────────────────────────┤  │
│  │ Normal Priority (nice: 0)                    │  │
│  │ ██████░░░░░░░░░░░░░░  Normal CPU time        │  │
│  ├──────────────────────────────────────────────┤  │
│  │ Low Priority (nice: 1 to 19)                 │  │
│  │ ██░░░░░░░░░░░░░░░░░░  Less CPU time          │  │
│  └──────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────┘
```

### Example
```c
#include <stdio.h>
#include <unistd.h>
#include <sys/resource.h>
#include <errno.h>

int main() {
    int current_nice;
    
    // Get current nice value
    errno = 0;
    current_nice = getpriority(PRIO_PROCESS, 0);
    if (errno == 0) {
        printf("Current nice value: %d\n", current_nice);
    }
    
    // Increase nice value (lower priority)
    if (nice(10) == -1) {
        perror("nice");
    }
    
    current_nice = getpriority(PRIO_PROCESS, 0);
    printf("New nice value: %d\n", current_nice);
    
    return 0;
}
```

## 7. Process Groups and Sessions

### System Calls
```c
#include <unistd.h>

pid_t getpgid(pid_t pid);
int setpgid(pid_t pid, pid_t pgid);
pid_t getsid(pid_t pid);
pid_t setsid(void);
```

### Process Group Hierarchy

```
Session Leader (sshd, PID: 100, SID: 100)
    │
    └─── Session (SID: 100)
            │
            ├─── Process Group 1 (PGID: 200) ← Foreground
            │       ├─── Process (PID: 200) ← Group Leader
            │       ├─── Process (PID: 201)
            │       └─── Process (PID: 202)
            │
            └─── Process Group 2 (PGID: 300) ← Background
                    ├─── Process (PID: 300) ← Group Leader
                    └─── Process (PID: 301)

Signal to Group:  kill(-PGID, SIGTERM)
    → All processes in group receive signal
```

## Complete Example: Process Manager

See [process_manager.c](../examples/process_manager.c) for a complete example demonstrating multiple process system calls.

## Common Pitfalls

1. **Zombie Processes**: Always `wait()` for children
2. **Orphan Processes**: Children whose parent didn't wait and died
3. **Fork Bombs**: Unlimited forking can crash system
4. **File Descriptor Leaks**: Close unused FDs in child after fork
5. **Signal Handling**: Signals can interrupt system calls

## Practice Exercises

1. Write a program that creates 5 child processes
2. Implement a simple shell using fork() and exec()
3. Create a daemon process using setsid()
4. Build a process tree viewer
5. Implement a job control system with process groups

## See Also
- `man 2 fork`
- `man 2 exec`
- `man 2 wait`
- `man 2 nice`

