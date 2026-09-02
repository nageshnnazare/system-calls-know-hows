# 4.4 — POSIX IPC

POSIX IPC modernizes the SysV trio (Part 4.3) with **name-based objects** that
appear as **file descriptors** (message queues) or **`sem_t*`** handles
(semaphores), living under **`/dev/mqueue`** and **`/dev/shm`**. They integrate
with **`poll`/`epoll`** (Part 6.6) and follow unlink-for-cleanup semantics closer
to ordinary files (Part 2.1).

---

## 4.4.1 Why POSIX IPC exists

```
   SysV                          POSIX
   ────                          ─────
   integer id (47)               fd (42) or named sem_t*
   ftok collisions               /name with O_CREAT|O_EXCL
   ipcs/ipcrm                    mq_unlink / sem_unlink / shm_unlink
   no poll on queue              mq_notify + signalfd/eventfd patterns
```

**Trade-offs ▸** POSIX mq carries **priority-ordered messages** and **async
notification**; POSIX semaphores have a simpler API than `semop` arrays. Linux
adopted POSIX shm/mq relatively late — always check `#ifdef` and runtime support.

---

## 4.4.2 POSIX message queues

> **The call ▸**
> ```c
> #include <mqueue.h>
>
> mqd_t mq_open(const char *name, int oflag, ...);
> int mq_close(mqd_t mqdes);
> int mq_unlink(const char *name);
> int mq_send(mqd_t mqdes, const char *msg_ptr, size_t msg_len, unsigned msg_prio);
> ssize_t mq_receive(mqd_t mqdes, char *msg_ptr, size_t msg_len, unsigned *msg_prio);
> int mq_notify(mqd_t mqdes, const struct sigevent *notification);
> ```
> **`name`** — must begin with `/` (e.g. `/myapp_jobs`). **`mqd_t`** is a **fd**
> on Linux — usable with `poll` after `mq_notify` registers interest.

```
   producer                         /dev/mqueue/myapp_jobs
   mq_send(mq, buf, len, prio)  ──▶ kernel priority queue
                                           │
   consumer                                 ▼
   mq_receive(mq, buf, cap, &prio) ◀── ordered by prio, FIFO within prio
```

Attributes via `mq_setattr`/`mq_getattr`: `mq_maxmsg`, `mq_msgsize`, `mq_flags`
(`O_NONBLOCK`).

**Errors ▸**

| `errno` | When |
|---------|------|
| `EEXIST` | `O_CREAT|O_EXCL` and name exists |
| `ENOSPC` | Queue or message limits hit (`/proc/sys/fs/mqueue/*`) |
| `EMFILE` | Per-process mq limit |
| `EAGAIN` | `O_NONBLOCK` and queue full/empty |

```bash
ls /dev/mqueue/
cat /proc/sys/fs/mqueue/msg_max
```

---

## 4.4.3 mq_notify — waking an event loop

```
   mq_notify(mq, &ev)  where ev.sigev_notify = SIGEV_THREAD or SIGEV_SIGNAL
        │
   message arrives while queue was empty
        │
        └─ notification fires once → re-register in handler/thread
```

For **`epoll`** integration, Linux patterns include **`signalfd`** (Part 4.2) or
dedicated threads blocked on `mq_receive`. Some code uses a **pipe self-kick** when
notification arrives.

**Pitfall ▸** `mq_notify` is **one-shot** — must re-arm after each delivery or you
miss wakeups when messages batch.

---

## 4.4.4 POSIX semaphores

> **The call ▸**
> ```c
> #include <semaphore.h>
>
> sem_t *sem_open(const char *name, int oflag, ...);
> int sem_close(sem_t *sem);
> int sem_unlink(const char *name);
> int sem_init(sem_t *sem, int pshared, unsigned value);
> int sem_destroy(sem_t *sem);
> int sem_wait(sem_t *sem);
> int sem_trywait(sem_t *sem);
> int sem_post(sem_t *sem);
> int sem_getvalue(sem_t *sem, int *sval);
> ```

| Kind | API | Sharing |
|------|-----|---------|
| **Named** | `sem_open("/name", ...)` | Unrelated processes |
| **Unnamed** | `sem_init(&sem, pshared, 1)` | Threads or shm if `pshared=1` |

Named semaphores persist until **`sem_unlink`** (like POSIX shm, Part 3.5).

**Errors ▸**

| `errno` | When |
|---------|------|
| `EAGAIN` | `sem_trywait` would block |
| `EINTR` | Interrupted by signal |
| `EINVAL` | Uninitialized or destroyed sem |

> **Under the hood ▸** Linux implements POSIX semaphores with a **futex** fast path
> in user space and kernel wait only on contention (Part 5.5).

---

## 4.4.5 Comparison to System V

| Feature | SysV (Part 4.3) | POSIX |
|---------|-----------------|-------|
| Identity | `ftok` + integer id | Path name + fd/`sem_t*` |
| Message priority | No | Yes (`mq_send` prio) |
| Poll integration | Poor | mq is fd on Linux |
| Persistence | Until `IPC_RMID` | Until `*_unlink` |
| Portability | Ubiquitous legacy | Needs `_POSIX_*` macros |
| Admin | `ipcs`/`ipcrm` | `ls /dev/mqueue`, `rm` shm files |

---

## 4.4.6 fd-based integration example

```c
#define _POSIX_C_SOURCE 200809L
#include <fcntl.h>
#include <mqueue.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

#define MQ_NAME "/sc_mq_demo"

int main(void) {
    mq_unlink(MQ_NAME);

    struct mq_attr attr = {
        .mq_flags   = 0,
        .mq_maxmsg  = 10,
        .mq_msgsize = 256,
        .mq_curmsgs = 0,
    };

    mqd_t mq = mq_open(MQ_NAME, O_CREAT | O_RDWR, 0600, &attr);
    if (mq == (mqd_t)-1) {
        perror("mq_open");
        return 1;
    }

    /* On Linux, mqd_t is int fd — suitable for poll/epoll in larger servers */
    printf("mq descriptor (fd): %d\n", (int)mq);

    pid_t pid = fork();
    if (pid == -1) {
        perror("fork");
        mq_close(mq);
        mq_unlink(MQ_NAME);
        return 1;
    }

    if (pid == 0) {
        char buf[256];
        ssize_t n = mq_receive(mq, buf, sizeof buf, NULL);
        if (n == -1) {
            perror("mq_receive");
            mq_close(mq);
            _exit(1);
        }
        buf[n] = '\0';
        printf("[child] received: %s\n", buf);
        mq_close(mq);
        _exit(0);
    }

    const char *msg = "posix mq hello";
    if (mq_send(mq, msg, strlen(msg) + 1, 10) == -1) {
        perror("mq_send");
        mq_close(mq);
        mq_unlink(MQ_NAME);
        return 1;
    }

    if (waitpid(pid, NULL, 0) == -1)
        perror("waitpid");

    if (mq_close(mq) == -1)
        perror("mq_close");
    if (mq_unlink(MQ_NAME) == -1)
        perror("mq_unlink");

    return 0;
}
```

Compile with `-lrt` on older glibc (`gcc -lrt mq_demo.c`).

---

## Summary

- **POSIX message queues** (`mq_open`, `/dev/mqueue`) provide named, prioritized,
  fd-like message passing with **`mq_notify`** for async wakeups.
- **POSIX semaphores** come in **named** (`sem_open`) and **unnamed** (`sem_init`)
  forms — simpler than SysV `semop` arrays.
- Cleanup is explicit via **`mq_unlink`/`sem_unlink`/`shm_unlink`** — fewer stale
  kernel objects than SysV, but names can still leak if programs crash.
- On Linux, POSIX IPC aligns with **fd event loops** and **futex**-backed
  semaphores; prefer it over SysV for new components.

Next: [4.5 — Choosing an IPC mechanism](05-choosing-ipc.md)
