# 3.5 — Shared Memory

**Shared memory** is the fastest IPC path: multiple processes map the **same
physical pages** into their address spaces and read/write them like ordinary memory.
The kernel is not involved per access — only at setup and teardown. That speed comes
with a cost: **you must synchronize** (mutexes, semaphores, futex — Parts 5.3,
4.3–4.4, 5.5) or accept data races.

---

## 3.5.1 The core idea

```
   process A                          process B
   ┌─────────────┐                    ┌─────────────┐
   │ VA 0x7f..   │                    │ VA 0x7f..   │   (addresses may differ)
   │   shared    │                    │   shared    │
   └──────┬──────┘                    └──────┬──────┘
          │                                  │
          └──────────▶ same physical frames ◀┘
```

Two families on Linux:

| API | Naming | Persistence | Modern preference |
|-----|--------|-------------|-------------------|
| **POSIX** | `shm_open` + `mmap` | Until unlinked | ✓ preferred for new code |
| **System V** | `shmget`/`shmat` | Until `shmctl(IPC_RMID)` | Legacy, still common |

Both ultimately use **`mmap(MAP_SHARED)`** under the hood.

---

## 3.5.2 tmpfs and /dev/shm

POSIX shared memory objects and many anonymous shared regions live on **tmpfs** — a
RAM-backed filesystem:

```bash
ls -la /dev/shm          # visible POSIX shm object names
df -h /dev/shm           # size limited by half RAM typically (shm_size mount opt)
```

```
   shm_open("/my_ring", ...)  →  file in /dev/shm/my_ring (leading / stripped)
        │
        mmap(MAP_SHARED)       →  shared anonymous/file-backed pages in RAM
```

**Trade-offs ▸** tmpfs is fast but counts against memory limits; huge shm segments
can trigger OOM killer behaviour under pressure.

---

## 3.5.3 POSIX shared memory: shm_open + mmap

> **The call ▸**
> ```c
> #include <sys/mman.h>
> #include <sys/stat.h>
> #include <fcntl.h>
>
> int shm_open(const char *name, int oflag, mode_t mode);
> int shm_unlink(const char *name);
> ```
> **`name`** — must start with `/` and contain no other slashes (e.g. `/myapp_buf`).
> Returns an **fd** suitable for `ftruncate` + `mmap(MAP_SHARED)` (Part 0.5).

Workflow:

```
   shm_open("/demo", O_CREAT|O_RDWR, 0600)  → fd
   ftruncate(fd, sizeof(struct payload))    → set size
   mmap(..., MAP_SHARED, fd, 0)             → pointer
   close(fd)                                → mapping persists
   shm_unlink("/demo")                      → name removed; segment until last unmap
```

**Errors ▸**

| `errno` | When |
|---------|------|
| `EEXIST` | `O_CREAT|O_EXCL` and name exists |
| `ENOENT` | Open without `O_CREAT` and name missing |
| `EINVAL` | Invalid name format |
| `EMFILE` | Process fd table full |

---

## 3.5.4 System V shared memory

> **The call ▸**
> ```c
> #include <sys/shm.h>
>
> int shmget(key_t key, size_t size, int shmflg);
> void *shmat(int shmid, const void *shmaddr, int shmflg);
> int shmdt(const void *shmaddr);
> int shmctl(int shmid, int cmd, struct shmid_ds *buf);
> ```
> **`key`** — from `ftok(path, id)` or **`IPC_PRIVATE`** (private to creating process
> until passed via fork or explicit send). **`shmat`** returns pointer; **`(void *)-1`**
> on error with `errno`.

```
   ftok("/tmp/mykey", 1)  → 0x12345678
   shmget(key, size, IPC_CREAT|0666)  → shmid (global integer id)
   shmat(shmid, NULL, 0)              → mapped address
```

**Pitfall ▸** SysV IPC objects **persist after crash** until `ipcrm` or
`shmctl(IPC_RMID)` with last detach — classic stale-segment footgun (Part 4.3).

---

## 3.5.5 MAP_SHARED anonymous + fork

The simplest shared memory requires no named object:

```c
void *p = mmap(NULL, size, PROT_READ|PROT_WRITE,
               MAP_SHARED|MAP_ANONYMOUS, -1, 0);
pid_t pid = fork();
/* parent and child share pages COW until write — then split per page */
```

After **write**, pages become private copies (COW, Part 1.2). For true shared
writable state across unrelated processes, use `MAP_SHARED` on a **file** or
**shm_open** object, not anonymous post-fork writes without a shared backing.

---

## 3.5.6 Synchronization requirement

Shared memory provides **no** ordering or atomicity:

```
   process A: counter++     \
   process B: counter++      → races without sync
```

Use:

- **POSIX semaphores** (`sem_open` / `sem_wait`, Part 4.4).
- **System V semaphores** (`semop`, Part 4.3).
- **pthread mutex in shared memory** with `PTHREAD_PROCESS_SHARED` (Part 5.3).
- **C11 atomics** or **futex** (Part 5.5) for expert paths.

**Pitfall ▸** Placing a normal `pthread_mutex_t` in shm without
`pthread_mutexattr_setpshared` → undefined behaviour.

---

## 3.5.7 POSIX shm example: parent/child counter

```c
#define _POSIX_C_SOURCE 200809L
#include <fcntl.h>
#include <semaphore.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

#define SHM_NAME "/sc_shm_demo"
#define SEM_NAME "/sc_sem_demo"

struct shared {
    int counter;
};

int main(void) {
    shm_unlink(SHM_NAME);
    sem_unlink(SEM_NAME);

    int fd = shm_open(SHM_NAME, O_CREAT | O_RDWR, 0600);
    if (fd == -1) {
        perror("shm_open");
        return 1;
    }

    if (ftruncate(fd, sizeof(struct shared)) == -1) {
        perror("ftruncate");
        close(fd);
        return 1;
    }

    struct shared *mem = mmap(NULL, sizeof(struct shared),
                              PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (mem == MAP_FAILED) {
        perror("mmap");
        close(fd);
        return 1;
    }
    if (close(fd) == -1) {
        perror("close");
        munmap(mem, sizeof *mem);
        return 1;
    }

    mem->counter = 0;

    sem_t *sem = sem_open(SEM_NAME, O_CREAT | O_EXCL, 0600, 1);
    if (sem == SEM_FAILED) {
        perror("sem_open");
        munmap(mem, sizeof *mem);
        shm_unlink(SHM_NAME);
        return 1;
    }

    pid_t pid = fork();
    if (pid == -1) {
        perror("fork");
        sem_close(sem);
        sem_unlink(SEM_NAME);
        munmap(mem, sizeof *mem);
        shm_unlink(SHM_NAME);
        return 1;
    }

    for (int i = 0; i < 10000; i++) {
        if (sem_wait(sem) == -1) {
            perror("sem_wait");
            exit(1);
        }
        mem->counter++;
        if (sem_post(sem) == -1) {
            perror("sem_post");
            exit(1);
        }
    }

    if (pid == 0) {
        _exit(0);
    }

    if (waitpid(pid, NULL, 0) == -1) {
        perror("waitpid");
        return 1;
    }

    printf("final counter (expect 20000): %d\n", mem->counter);

    if (sem_close(sem) == -1)
        perror("sem_close");
    if (sem_unlink(SEM_NAME) == -1)
        perror("sem_unlink");
    if (munmap(mem, sizeof *mem) == -1)
        perror("munmap");
    if (shm_unlink(SHM_NAME) == -1)
        perror("shm_unlink");

    return mem->counter == 20000 ? 0 : 1;
}
```

Without the semaphore, the counter would be far below 20000.

---

## Summary

- Shared memory maps **identical physical pages** into multiple address spaces —
  zero-copy IPC at the cost of explicit synchronization.
- **POSIX `shm_open` + `mmap`** is the modern fd-based path; objects live in
  **tmpfs** (`/dev/shm`).
- **System V `shmget`/`shmat`** uses integer ids and `ftok` keys — persistent and
  clunky (Part 4.3).
- **`MAP_SHARED` anonymous + `fork()`** shares until first write (COW).
- Always pair shared writable memory with **semaphores, mutexes, or atomics**.

Next: [4.1 — Pipes & FIFOs](../04-ipc/01-pipes-and-fifos.md)
