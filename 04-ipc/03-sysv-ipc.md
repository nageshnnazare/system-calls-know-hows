# 4.3 — System V IPC: Message Queues & Semaphores

Before POSIX IPC (Part 4.4), Unix System V gave us a trio of kernel-persistent
objects: **message queues**, **semaphore sets**, and **shared memory** (Part 3.5).
They share a common **key → id** model, `ipcs`/`ipcrm` administration, and a
reputation for footguns. You will still encounter them in legacy codebases and some
embedded deployments.

---

## 4.3.1 The ftok/key model

```
   ftok("/some/path", proj_id)  →  key_t (32-bit, not guaranteed unique)
        │
        ├─ msgget(key, ...)   → msqid
        ├─ semget(key, ...)   → semid
        └─ shmget(key, ...)   → shmid
```

> **The call ▸**
> ```c
> #include <sys/ipc.h>
>
> key_t ftok(const char *pathname, int proj_id);
> ```
> **`pathname`** must name an existing file the kernel can stat. **`proj_id`** — low
> 8 bits distinguish keys for the same file.

**`IPC_PRIVATE`** — special key meaning "create a private object visible only to
caller's descendants until passed explicitly":

```c
int id = msgget(IPC_PRIVATE, IPC_CREAT | 0666);
```

**Pitfall ▸** **Key collisions** — two unrelated programs using the same path +
`proj_id` attach to the **same** queue. Always use unique paths, `IPC_EXCL`, or
prefer POSIX named objects (Part 4.4).

---

## 4.3.2 Message queues

> **The call ▸**
> ```c
> #include <sys/msg.h>
>
> int msgget(key_t key, int msgflg);
> int msgsnd(int msqid, const void *msgp, size_t msgsz, int msgflg);
> ssize_t msgrcv(int msqid, void *msgp, size_t msgsz, long msgtyp, int msgflg);
> int msgctl(int msqid, int cmd, struct msqid_ds *buf);
> ```
> Messages require a **`long mtype`** header as first field (> 0). **`msgsz`** is
> payload size **excluding** the `mtype`.

```
   sender                              receiver
   msgsnd(queue, &{type=1, data})  ──▶ kernel linked list of messages
                                            │
                                       msgrcv(..., typ=1, ...) picks type 1
```

| `msgflg` (send/recv) | Effect |
|----------------------|--------|
| `IPC_NOWAIT` | Return `EAGAIN` if would block |
| `MSG_NOERROR` (recv) | Truncate oversize messages |

**Errors ▸**

| `errno` | When |
|---------|------|
| `EAGAIN` | Queue full (`msgsnd`) or empty (`msgrcv`) with `IPC_NOWAIT` |
| `EIDRM` | Queue removed while blocked |
| `EACCES` | Permission denied |
| `EINVAL` | Invalid id or message size |

> **Under the hood ▸** Messages live in kernel heap linked lists per queue. Size
> limits: `/proc/sys/kernel/msgmax`, `msgmnb`, `msgmni`.

---

## 4.3.3 Semaphores

System V semaphores are **sets** of counters, not POSIX-style binary semaphores.

> **The call ▸**
> ```c
> #include <sys/sem.h>
>
> int semget(key_t key, int nsems, int semflg);
> int semop(int semid, struct sembuf *sops, size_t nsops);
> int semctl(int semid, int sem_num, int cmd, ...);
>
> struct sembuf {
>     unsigned short sem_num;  /* index in set */
>     short          sem_op;   /* +1 increment, -1 decrement, 0 wait zero */
>     short          sem_flg;  /* IPC_NOWAIT, SEM_UNDO */
> };
> ```

```
   sem_op = -1  (wait/decrement)
        │
        ├─ semval > 0  → decrement, continue
        └─ semval == 0 → block until another process increments
```

**`SEM_UNDO`** — kernel tracks adjustments; if process dies, sem values are undone
to avoid deadlocks (not a full safety net).

**Errors ▸**

| `errno` | When |
|---------|------|
| `EAGAIN` | `IPC_NOWAIT` and operation would block |
| `EFBIG` | `sem_num` out of range |
| `EIDRM` | Set removed while waiting |

Pair SysV semaphores with SysV shm (Part 3.5) for classic IPC patterns.

---

## 4.3.4 msgctl / semctl / shmctl commands

| Command | Purpose |
|---------|---------|
| `IPC_STAT` | Fetch `msqid_ds` / `semid_ds` / `shmid_ds` |
| `IPC_SET` | Update permissions/stats (owner/root) |
| `IPC_RMID` | Mark for removal when last attach/detach completes |

**Pitfall ▸** `IPC_RMID` on a shm segment **does not** unmap active processes — it
only prevents new attaches; last `shmdt` destroys it.

---

## 4.3.5 ipcs and ipcrm

```bash
ipcs -a                    # list all SysV msg/sem/shm
ipcs -q                    # message queues only
ipcrm -Q KEY               # remove msg queue by key
ipcrm -q MSQID             # remove by id
ipcrm -S KEY / -s SEMID    # semaphores
ipcrm -M KEY / -m SHMID    # shared memory
```

**Systems ▸** After crashes, stale SysV objects accumulate — `ipcs` shows creators
and attach counts. Automate cleanup in startup scripts or migrate to POSIX IPC with
`shm_unlink`/`mq_unlink`.

---

## 4.3.6 Why SysV IPC feels clunky

```
   SysV object lifetime
   ┌─────────────────────────────────────────────────────────┐
   │ created → survives process exit → survives reboot? NO   │
   │          (unless sysctl kernel.sysvipc or tmpfs rules)   │
   │          until explicit IPC_RMID or ipcrm               │
   └─────────────────────────────────────────────────────────┘
```

| Issue | Detail |
|-------|--------|
| **Global integer ids** | Not fds — can't `poll()`/`select()` easily |
| **Key collisions** | `ftok` is fragile across unrelated apps |
| **No fine-grained ACL** | Octal permission bits only |
| **Kernel limits** | Static tunables; exhaustion = cryptic failures |
| **API age** | `semop` arrays vs simple `sem_wait` |

Modern Linux services prefer **Unix domain sockets** (Part 6.4), **POSIX mq/sem**
(Part 4.4), or **shared memory + futex** (Part 5.5).

---

## 4.3.7 Minimal message queue sketch

```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ipc.h>
#include <sys/msg.h>
#include <sys/wait.h>
#include <unistd.h>

struct msg {
    long mtype;
    char mtext[64];
};

int main(void) {
    key_t key = ftok("/tmp", 'M');
    if (key == -1) {
        perror("ftok");
        return 1;
    }

    int qid = msgget(key, IPC_CREAT | 0666);
    if (qid == -1) {
        perror("msgget");
        return 1;
    }

    pid_t pid = fork();
    if (pid == -1) {
        perror("fork");
        msgctl(qid, IPC_RMID, NULL);
        return 1;
    }

    if (pid == 0) {
        struct msg m;
        if (msgrcv(qid, &m, sizeof m.mtext, 1, 0) == -1) {
            perror("msgrcv");
            _exit(1);
        }
        printf("[child] got: %s\n", m.mtext);
        _exit(0);
    }

    struct msg m = { .mtype = 1 };
    strncpy(m.mtext, "sysv hello", sizeof m.mtext - 1);

    if (msgsnd(qid, &m, strlen(m.mtext) + 1, 0) == -1) {
        perror("msgsnd");
        msgctl(qid, IPC_RMID, NULL);
        return 1;
    }

    if (waitpid(pid, NULL, 0) == -1)
        perror("waitpid");

    if (msgctl(qid, IPC_RMID, NULL) == -1)
        perror("msgctl IPC_RMID");

    return 0;
}
```

---

## Summary

- SysV IPC identifies objects by **`ftok` key** or **`IPC_PRIVATE`**, returning
  global **`msqid`/`semid`/`shmid`** integers.
- **Message queues** carry typed records via **`msgsnd`/`msgrcv`**; **semaphore
  sets** synchronize via **`semop`** operations.
- Objects **persist beyond crashes** until **`IPC_RMID`** or **`ipcrm`** — a common
  operational hazard.
- **Key collisions**, non-fd ids, and coarse permissions push new designs toward
  POSIX IPC (Part 4.4) or sockets (Part 6.4).

Next: [4.4 — POSIX IPC](04-posix-ipc.md)
