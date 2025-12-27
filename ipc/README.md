# Inter-Process Communication (IPC) System Calls

## Overview

Inter-Process Communication allows processes to exchange data and coordinate activities. This tutorial covers pipes, FIFOs, signals, message queues, semaphores, and sockets.

## IPC Mechanisms Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    IPC MECHANISMS                            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Pipes (unnamed)                                             │
│  ┌─────────────┐       ┌────────┐       ┌─────────────┐      │
│  │  Process A  │──────►│  Pipe  │──────►│  Process B  │      │
│  │  (parent)   │ write │(buffer)│ read  │  (child)    │      │
│  └─────────────┘       └────────┘       └─────────────┘      │ 
│                                                              │
│  FIFOs (named pipes)                                         │
│  ┌─────────────┐                         ┌─────────────┐     │
│  │  Process A  │──┐                  ┌──►│  Process B  │     │
│  └─────────────┘  │   ┌──────────┐   │   └─────────────┘     │
│                   └──►│   FIFO   │───┘                       │
│                       │ (in /tmp)│                           │
│                       └──────────┘                           │
│                                                              │
│  Signals                                                     │
│  ┌─────────────┐                         ┌─────────────┐     │
│  │  Process A  │────── SIGTERM ─────────►│  Process B  │     │
│  │ kill(pid)   │                         │ (handler)   │     │
│  └─────────────┘                         └─────────────┘     │
│                                                              │
│  Message Queues                                              │
│  ┌─────────────┐       ┌────────────┐   ┌─────────────┐      │
│  │  Process A  │──────►│ Message    │──►│  Process B  │      │
│  │  msgsnd()   │ msgs  │ Queue      │   │  msgrcv()   │      │
│  └─────────────┘       │ [msg][msg] │   └─────────────┘      │
│                        └────────────┘                        │
│                                                              │
│  Shared Memory (fastest)                                     │
│  ┌─────────────┐       ┌────────────┐   ┌─────────────┐      │
│  │  Process A  │──────►│  Shared    │◄──│  Process B  │      │
│  │  (write)    │       │  Memory    │   │  (read)     │      │
│  └─────────────┘       └────────────┘   └─────────────┘      │
│                                                              │
│  Semaphores (synchronization)                                │
│  ┌─────────────┐       ┌────────────┐   ┌─────────────┐      │
│  │  Process A  │◄─────►│ Semaphore  │◄─►│  Process B  │      │
│  │  semop()    │ lock  │  (counter) │   │  semop()    │      │
│  └─────────────┘       └────────────┘   └─────────────┘      │
│                                                              │
│  Sockets (network & local)                                   │
│  ┌─────────────┐       ┌────────────┐   ┌─────────────┐      │
│  │  Server     │◄─────►│  Socket    │◄─►│  Client     │      │
│  │  accept()   │ conn  │  (endpoint)│   │  connect()  │      │
│  └─────────────┘       └────────────┘   └─────────────┘      │
└──────────────────────────────────────────────────────────────┘
```

## 1. Pipes - Unidirectional Communication

### Synopsis
```c
#include <unistd.h>

int pipe(int pipefd[2]);
int pipe2(int pipefd[2], int flags);
```

### Pipe Structure

```
pipe(pipefd):

pipefd[0] ────► Read end
pipefd[1] ────► Write end

┌────────────────────────────────────────────────────────┐
│                    Kernel Space                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Pipe Buffer (typically 64KB)                    │  │
│  │  ┌────┬────┬────┬────┬────┬────┬────┐            │  │
│  │  │ D1 │ D2 │ D3 │ D4 │    │    │    │  FIFO      │  │
│  │  └────┴────┴────┴────┴────┴────┴────┘            │  │
│  │    ▲                              ▲              │  │
│  └────┼──────────────────────────────┼──────────────┘  │
└───────┼──────────────────────────────┼─────────────────┘
        │                              │
     read(pipefd[0])             write(pipefd[1])
        │                              │
┌───────┴────────────┐        ┌────────┴──────────┐
│  Reader Process    │        │  Writer Process   │
│  (usually child)   │        │  (usually parent) │
└────────────────────┘        └───────────────────┘

Data Flow: Writer → Pipe Buffer → Reader (one direction only)
```

### fork() and Pipes

```
Before fork():
┌───────────────────────────────┐
│ Parent Process                │
│                               │
│ pipefd[0] (read)  ──────┐     │
│ pipefd[1] (write) ──────┼───► Pipe
└─────────────────────────┼─────┘
                          │

After fork():
┌────────────────────────────────┐    ┌───────────────────────┐
│ Parent Process                 │    │ Child Process         │
│                                │    │                       │
│ pipefd[0] ─────┐               │    │ pipefd[0] ─────┐      │
│ pipefd[1] ─────┼───┐           │    │ pipefd[1] ─────┼───┐  │
└────────────────┼───┼───────────┘    └────────────────┼───┼──┘
                 │   │                                 │   │
                 ▼   ▼                                 ▼   ▼
              ┌─────────────────────────────────────────────┐
              │           Shared Pipe                       │
              └─────────────────────────────────────────────┘

Typical Pattern:
  Parent: close(pipefd[0]), use pipefd[1] for writing
  Child:  close(pipefd[1]), use pipefd[0] for reading
```

### Example: Basic Pipe
```c
#include <unistd.h>
#include <stdio.h>
#include <string.h>
#include <sys/wait.h>

int main() {
    int pipefd[2];
    pid_t pid;
    char write_msg[] = "Hello through pipe!";
    char read_msg[100];
    
    // Create pipe
    if (pipe(pipefd) == -1) {
        perror("pipe");
        return 1;
    }
    
    pid = fork();
    
    if (pid == -1) {
        perror("fork");
        return 1;
    }
    
    if (pid == 0) {
        // Child process - reader
        close(pipefd[1]);  // Close unused write end
        
        ssize_t n = read(pipefd[0], read_msg, sizeof(read_msg));
        if (n > 0) {
            read_msg[n] = '\0';
            printf("Child received: %s\n", read_msg);
        }
        
        close(pipefd[0]);
        return 0;
    }
    else {
        // Parent process - writer
        close(pipefd[0]);  // Close unused read end
        
        printf("Parent sending: %s\n", write_msg);
        write(pipefd[1], write_msg, strlen(write_msg));
        
        close(pipefd[1]);
        wait(NULL);  // Wait for child
    }
    
    return 0;
}
```

### Example: Pipe with exec (shell-like)
```c
#include <unistd.h>
#include <stdio.h>
#include <sys/wait.h>

// Implements: ls | wc -l

int main() {
    int pipefd[2];
    pid_t pid1, pid2;
    
    if (pipe(pipefd) == -1) {
        perror("pipe");
        return 1;
    }
    
    // First child: ls
    pid1 = fork();
    if (pid1 == 0) {
        close(pipefd[0]);           // Close read end
        dup2(pipefd[1], STDOUT_FILENO);  // Redirect stdout to pipe
        close(pipefd[1]);
        execlp("ls", "ls", "-l", NULL);
        perror("execlp ls");
        return 1;
    }
    
    // Second child: wc -l
    pid2 = fork();
    if (pid2 == 0) {
        close(pipefd[1]);           // Close write end
        dup2(pipefd[0], STDIN_FILENO);   // Redirect stdin from pipe
        close(pipefd[0]);
        execlp("wc", "wc", "-l", NULL);
        perror("execlp wc");
        return 1;
    }
    
    // Parent
    close(pipefd[0]);
    close(pipefd[1]);
    
    waitpid(pid1, NULL, 0);
    waitpid(pid2, NULL, 0);
    
    return 0;
}
```

## 2. FIFOs (Named Pipes)

### Synopsis
```c
#include <sys/stat.h>

int mkfifo(const char *pathname, mode_t mode);
int mkfifoat(int dirfd, const char *pathname, mode_t mode);
```

### FIFO vs Pipe

```
Unnamed Pipe:
  • Only between related processes (parent-child)
  • Exists only while processes run
  • No filesystem name
  
Named Pipe (FIFO):
  • Between any processes (unrelated)
  • Persists in filesystem
  • Has a pathname
  
FIFO in Filesystem:
/tmp/
  ├── myfifo  ←── prw-r--r-- (p indicates FIFO)
  ├── file.txt
  └── ...

Process A: open("/tmp/myfifo", O_WRONLY);
Process B: open("/tmp/myfifo", O_RDONLY);
```

### Example: FIFO Writer
```c
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>

int main() {
    const char *fifo_path = "/tmp/my_fifo";
    int fd;
    const char *message = "Hello via FIFO!\n";
    
    // Create FIFO
    if (mkfifo(fifo_path, 0666) == -1) {
        perror("mkfifo (may already exist)");
    }
    
    printf("Opening FIFO for writing...\n");
    fd = open(fifo_path, O_WRONLY);  // Blocks until reader opens
    if (fd == -1) {
        perror("open");
        return 1;
    }
    
    printf("Writing to FIFO: %s", message);
    write(fd, message, strlen(message));
    
    close(fd);
    return 0;
}
```

### Example: FIFO Reader
```c
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>

int main() {
    const char *fifo_path = "/tmp/my_fifo";
    int fd;
    char buffer[100];
    ssize_t bytes;
    
    printf("Opening FIFO for reading...\n");
    fd = open(fifo_path, O_RDONLY);  // Blocks until writer opens
    if (fd == -1) {
        perror("open");
        return 1;
    }
    
    printf("Reading from FIFO:\n");
    while ((bytes = read(fd, buffer, sizeof(buffer))) > 0) {
        write(STDOUT_FILENO, buffer, bytes);
    }
    
    close(fd);
    unlink(fifo_path);  // Clean up
    return 0;
}
```

## 3. Signals

### Synopsis
```c
#include <signal.h>

typedef void (*sighandler_t)(int);
sighandler_t signal(int signum, sighandler_t handler);
int sigaction(int signum, const struct sigaction *act,
              struct sigaction *oldact);

int kill(pid_t pid, int sig);
int raise(int sig);
int killpg(int pgrp, int sig);

int sigemptyset(sigset_t *set);
int sigfillset(sigset_t *set);
int sigaddset(sigset_t *set, int signum);
int sigdelset(sigset_t *set, int signum);
int sigismember(const sigset_t *set, int signum);

int sigprocmask(int how, const sigset_t *set, sigset_t *oldset);
int sigpending(sigset_t *set);
int sigsuspend(const sigset_t *mask);
```

### Common Signals

```
┌──────────┬─────────────────────────────────────────────────┐
│ Signal   │ Description                                     │
├──────────┼─────────────────────────────────────────────────┤
│ SIGHUP   │ Hangup (terminal closed)                        │
│ SIGINT   │ Interrupt (Ctrl+C)                              │
│ SIGQUIT  │ Quit (Ctrl+\)                                   │
│ SIGILL   │ Illegal instruction                             │
│ SIGABRT  │ Abort signal from abort()                       │
│ SIGFPE   │ Floating point exception                        │
│ SIGKILL  │ Kill signal (cannot be caught)                  │
│ SIGSEGV  │ Segmentation fault                              │
│ SIGPIPE  │ Broken pipe                                     │
│ SIGALRM  │ Alarm clock                                     │
│ SIGTERM  │ Termination signal                              │
│ SIGUSR1  │ User-defined signal 1                           │
│ SIGUSR2  │ User-defined signal 2                           │
│ SIGCHLD  │ Child process terminated                        │
│ SIGCONT  │ Continue if stopped                             │
│ SIGSTOP  │ Stop process (cannot be caught)                 │
│ SIGTSTP  │ Stop typed at terminal (Ctrl+Z)                 │
└──────────┴─────────────────────────────────────────────────┘
```

### Signal Handling Flow

```
1. Signal Delivery:
┌────────────────┐         ┌──────────────────┐
│ Sending Process│         │ Receiving Process│
│                │         │                  │
│ kill(pid, SIG) │────────►│                  │
└────────────────┘         └────────┬─────────┘
                                    │
                                    ▼
                           ┌────────────────┐
                           │ Kernel         │
                           │ Signal Pending │
                           └────────┬───────┘
                                    │
2. Signal Handling:                 │
                                    ▼
                    ┌───────────────────────────┐
                    │ Process resumes           │
                    │ Check pending signals     │
                    └───────────┬───────────────┘
                                │
                    ┌───────────┴──────────┬──────────┐
                    ▼                      ▼          ▼
              ┌──────────┐          ┌──────────┐  ┌──────────┐
              │ Default  │          │ Ignore   │  │ Handler  │
              │ Action   │          │          │  │ Function │
              └──────────┘          └──────────┘  └──────────┘
              (term/stop/                          signal_handler()
               core/ignore)                        { ... }
```

### Example: Signal Handler
```c
#include <signal.h>
#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>

volatile sig_atomic_t signal_received = 0;

void signal_handler(int signum) {
    printf("\nReceived signal %d\n", signum);
    signal_received = 1;
}

int main() {
    struct sigaction sa;
    
    // Set up signal handler using sigaction (preferred)
    sa.sa_handler = signal_handler;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = 0;
    
    if (sigaction(SIGINT, &sa, NULL) == -1) {
        perror("sigaction");
        return 1;
    }
    
    printf("Process PID: %d\n", getpid());
    printf("Press Ctrl+C to send SIGINT...\n");
    printf("Waiting for signal...\n");
    
    while (!signal_received) {
        sleep(1);
        printf(".");
        fflush(stdout);
    }
    
    printf("\nSignal handled, exiting.\n");
    return 0;
}
```

### Example: Signal Masking
```c
#include <signal.h>
#include <stdio.h>
#include <unistd.h>

int main() {
    sigset_t new_mask, old_mask, pending;
    
    // Initialize empty signal set
    sigemptyset(&new_mask);
    
    // Add SIGINT to the set
    sigaddset(&new_mask, SIGINT);
    
    // Block SIGINT
    printf("Blocking SIGINT for 5 seconds...\n");
    printf("Try pressing Ctrl+C now (it will be queued)\n");
    
    if (sigprocmask(SIG_BLOCK, &new_mask, &old_mask) == -1) {
        perror("sigprocmask");
        return 1;
    }
    
    sleep(5);
    
    // Check for pending signals
    if (sigpending(&pending) == -1) {
        perror("sigpending");
        return 1;
    }
    
    if (sigismember(&pending, SIGINT)) {
        printf("SIGINT is pending!\n");
    }
    
    // Unblock SIGINT
    printf("Unblocking SIGINT...\n");
    if (sigprocmask(SIG_SETMASK, &old_mask, NULL) == -1) {
        perror("sigprocmask");
        return 1;
    }
    
    printf("SIGINT unblocked. Signal delivered now.\n");
    sleep(2);
    
    return 0;
}
```

## 4. Message Queues (System V)

### Synopsis
```c
#include <sys/msg.h>

int msgget(key_t key, int msgflg);
int msgsnd(int msqid, const void *msgp, size_t msgsz, int msgflg);
ssize_t msgrcv(int msqid, void *msgp, size_t msgsz, long msgtyp,
               int msgflg);
int msgctl(int msqid, int cmd, struct msqid_ds *buf);
```

### Message Queue Structure

```
Message Queue (in kernel):

┌─────────────────────────────────────────────────────┐
│ Message Queue ID: 12345                             │
│ Key: 0x1234                                         │
│                                                     │
│ ┌────────────────┐  ┌────────────────┐              │
│ │ Message 1      │  │ Message 2      │              │
│ │ Type: 1        │→ │ Type: 2        │→ ...         │
│ │ Data: "Hello"  │  │ Data: "World"  │              │
│ └────────────────┘  └────────────────┘              │
│  ▲                                        ▲         │
│  │ msgsnd()                    msgrcv()   │         │
└──┼────────────────────────────────────────┼─────────┘
   │                                        │
┌──┴──────────────┐              ┌─────────┴───────┐
│ Sender Process  │              │ Receiver Process│
│ (any process)   │              │ (any process)   │
└─────────────────┘              └─────────────────┘

Message Types allow selective retrieval:
  msgrcv(msgtyp=0)  : Get first message
  msgrcv(msgtyp>0)  : Get message of that type
  msgrcv(msgtyp<0)  : Get message with lowest type ≤ |msgtyp|
```

### Example: Message Queue
```c
#include <sys/msg.h>
#include <sys/ipc.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

struct message {
    long msg_type;
    char msg_text[100];
};

int main() {
    key_t key = 1234;
    int msgid;
    struct message msg;
    pid_t pid;
    
    // Create message queue
    msgid = msgget(key, IPC_CREAT | 0666);
    if (msgid == -1) {
        perror("msgget");
        return 1;
    }
    
    pid = fork();
    
    if (pid == 0) {
        // Child - receiver
        sleep(1);
        
        if (msgrcv(msgid, &msg, sizeof(msg.msg_text), 1, 0) == -1) {
            perror("msgrcv");
            return 1;
        }
        
        printf("Child received (type %ld): %s\n", 
               msg.msg_type, msg.msg_text);
        return 0;
    }
    else {
        // Parent - sender
        msg.msg_type = 1;
        strcpy(msg.msg_text, "Hello via message queue!");
        
        printf("Parent sending: %s\n", msg.msg_text);
        
        if (msgsnd(msgid, &msg, strlen(msg.msg_text) + 1, 0) == -1) {
            perror("msgsnd");
            return 1;
        }
        
        wait(NULL);
        
        // Remove message queue
        msgctl(msgid, IPC_RMID, NULL);
    }
    
    return 0;
}
```

## 5. Semaphores (System V)

### Synopsis
```c
#include <sys/sem.h>

int semget(key_t key, int nsems, int semflg);
int semop(int semid, struct sembuf *sops, size_t nsops);
int semctl(int semid, int semnum, int cmd, ...);
```

### Semaphore Operations

```
Binary Semaphore (mutex):
┌─────────────────────────────────────┐
│ Semaphore Value: 1 (available)      │
└─────────────────────────────────────┘
           │
Process A: semop(-1)  [P operation, wait, lock]
           │
           ▼
┌─────────────────────────────────────┐
│ Semaphore Value: 0 (locked)         │
└─────────────────────────────────────┘
           │
Process B: semop(-1)  → BLOCKS (waits)
           │
Process A: semop(+1)  [V operation, signal, unlock]
           │
           ▼
┌─────────────────────────────────────┐
│ Semaphore Value: 1 (available)      │
└─────────────────────────────────────┘
           │
Process B: unblocks, continues

Counting Semaphore (resource pool):
┌─────────────────────────────────────┐
│ Semaphore Value: 3 (3 resources)    │
└─────────────────────────────────────┘
           │
  3 processes can acquire simultaneously
  4th process blocks until one releases
```

### Example: Semaphore
```c
#include <sys/sem.h>
#include <sys/ipc.h>
#include <stdio.h>
#include <unistd.h>

union semun {
    int val;
    struct semid_ds *buf;
    unsigned short *array;
};

// P operation (wait, acquire)
void sem_wait(int semid) {
    struct sembuf op = {0, -1, 0};  // sem_num, sem_op, sem_flg
    semop(semid, &op, 1);
}

// V operation (signal, release)
void sem_signal(int semid) {
    struct sembuf op = {0, +1, 0};
    semop(semid, &op, 1);
}

int main() {
    key_t key = 1234;
    int semid;
    union semun arg;
    pid_t pid;
    
    // Create semaphore
    semid = semget(key, 1, IPC_CREAT | 0666);
    if (semid == -1) {
        perror("semget");
        return 1;
    }
    
    // Initialize semaphore to 1 (binary semaphore/mutex)
    arg.val = 1;
    semctl(semid, 0, SETVAL, arg);
    
    pid = fork();
    
    if (pid == 0) {
        // Child
        for (int i = 0; i < 5; i++) {
            sem_wait(semid);  // Enter critical section
            printf("Child: %d\n", i);
            sleep(1);
            sem_signal(semid);  // Leave critical section
        }
        return 0;
    }
    else {
        // Parent
        for (int i = 0; i < 5; i++) {
            sem_wait(semid);  // Enter critical section
            printf("Parent: %d\n", i);
            sleep(1);
            sem_signal(semid);  // Leave critical section
        }
        
        wait(NULL);
        
        // Remove semaphore
        semctl(semid, 0, IPC_RMID);
    }
    
    return 0;
}
```

## 6. Sockets (Brief Overview)

### Synopsis
```c
#include <sys/socket.h>

int socket(int domain, int type, int protocol);
int bind(int sockfd, const struct sockaddr *addr, socklen_t addrlen);
int listen(int sockfd, int backlog);
int accept(int sockfd, struct sockaddr *addr, socklen_t *addrlen);
int connect(int sockfd, const struct sockaddr *addr, socklen_t addrlen);
ssize_t send(int sockfd, const void *buf, size_t len, int flags);
ssize_t recv(int sockfd, void *buf, size_t len, int flags);
```

### Socket Types

```
Stream Sockets (SOCK_STREAM):
  • TCP-like
  • Reliable, ordered, connection-oriented
  • Byte stream

Datagram Sockets (SOCK_DGRAM):
  • UDP-like
  • Unreliable, unordered, connectionless
  • Message boundaries preserved

Unix Domain Sockets:
  • Local IPC (not network)
  • Faster than TCP
  • Can pass file descriptors
```

### Socket Communication Flow

```
Server                          Client
  │                               │
  │ socket()                      │ socket()
  ├─► sockfd                      ├─► sockfd
  │                               │
  │ bind(port)                    │
  ├─► bound to address            │
  │                               │
  │ listen()                      │
  ├─► listening                   │
  │                               │
  │ accept()                      │
  ├─► BLOCKED                     │
  │                               │
  │                               │ connect(server_addr)
  │ ◄─────────────────────────────┤
  │                               │
  ├─► connection established      │
  │   new_sockfd                  │
  │                               │
  │ recv(new_sockfd)              │ send(sockfd, "Hello")
  │ ◄─────────────────────────────┤
  │                               │
  │ send(new_sockfd, "Hi")        │ recv(sockfd)
  ├──────────────────────────────►│
  │                               │
  │ close(new_sockfd)             │ close(sockfd)
  │ close(sockfd)                 │
  ▼                               ▼
```

## IPC Comparison

```
┌──────────────┬────────┬────────┬─────────┬───────────┬────────┐
│ Mechanism    │ Speed  │ Setup  │ Persist │ Capacity  │ Usage  │
├──────────────┼────────┼────────┼─────────┼───────────┼────────┤
│ Pipe         │ Fast   │ Easy   │ No      │ Limited   │ Common │
│ FIFO         │ Fast   │ Easy   │ Yes     │ Limited   │ Common │
│ Signals      │ Fast   │ Easy   │ No      │ Minimal   │ Common │
│ Msg Queue    │ Medium │ Medium │ Yes     │ Medium    │ Less   │
│ Shared Mem   │ Fastest│ Medium │ Yes     │ Large     │ Common │
│ Semaphore    │ Fast   │ Medium │ Yes     │ Counter   │ Common │
│ Socket       │ Slower │ Complex│ No      │ Large     │ Common │
└──────────────┴────────┴────────┴─────────┴───────────┴────────┘

Best for:
  • Related processes, streaming data → Pipe
  • Unrelated processes → FIFO, Socket
  • Notifications → Signals
  • Large data sharing → Shared Memory (+ Semaphores)
  • Network communication → Sockets
```

## Complete Example Programs

See [examples/](../examples/) directory:
- `pipe_demo.c` - Advanced pipe usage
- `fifo_server.c` / `fifo_client.c` - FIFO example
- `signal_demo.c` - Comprehensive signal handling
- `msgq_demo.c` - Message queue example
- `shm_demo.c` - Shared memory with semaphores

## Best Practices

```
1. Clean up IPC resources
   ✓ Remove message queues, semaphores, shared memory
   ✓ Close pipes and FIFOs
   
2. Handle signals properly
   ✓ Use sigaction, not signal
   ✓ Keep handlers short and simple
   ✓ Use sig_atomic_t for shared variables
   
3. Synchronize shared resources
   ✓ Use semaphores with shared memory
   ✓ Handle race conditions
   
4. Check all return values
   ✓ IPC calls can fail in many ways
   
5. Consider security
   ✓ Set appropriate permissions
   ✓ Validate data from IPC
```

## Common Pitfalls

1. **Resource leaks** - Not cleaning up IPC objects
2. **Deadlocks** - Incorrect synchronization
3. **Signal handler safety** - Using non-async-safe functions
4. **Broken pipe** - Writing to closed pipe (SIGPIPE)
5. **Buffer sizes** - Message queue/pipe capacity limits

## Practice Exercises

1. Implement a producer-consumer using pipes
2. Build a simple chat system with FIFOs
3. Create a signal-based notification system
4. Implement a shared memory cache with semaphores
5. Build a multi-client server with sockets

## See Also
- `man 2 pipe`
- `man 3 mkfifo`
- `man 7 signal`
- `man 2 msgget`
- `man 2 semget`
- `man 2 socket`
- `man 7 ipc` (IPC overview)

