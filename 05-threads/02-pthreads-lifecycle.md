# 5.2 — The pthread Lifecycle

POSIX threads (`pthreads`) are the portable C interface to kernel threads on Linux.
Every `pthread_*` call is a **library wrapper** around `clone()`, futexes, and
scheduling — not a syscall you invoke directly, but the layer systems engineers use
daily. Part 5.1 explained *why* threads share memory; this chapter covers *creating,
running, joining, and destroying* them correctly.

---

## 5.2.1 The pthread error contract (read this first)

Syscalls return `-1` and set `errno` (Part 0.4). **Pthread functions do not.**

> **The call ▸** — return convention for all `pthread_*` functions:
> ```c
> int pthread_create(...);   /* 0 on success, otherwise an errno *value* */
> int pthread_join(...);
> int pthread_mutex_lock(...);
> ```
> On failure, pthread returns a **positive errno code directly** (e.g. `EAGAIN`,
> `EINVAL`). It does **not** set the global `errno` variable and does **not**
> return `-1`.

```c
int err = pthread_create(&t, NULL, start, arg);
if (err != 0) {
    fprintf(stderr, "pthread_create: %s\n", strerror(err));  /* use err, not errno */
    exit(1);
}
```

**Pitfall ▸** Writing `if (pthread_create(...) == -1) perror("pthread_create")` is
wrong twice: pthread never returns `-1`, and `perror` reads `errno`, which pthread
did not set.

---

## 5.2.2 pthread_create and the start routine

> **The call ▸**
> ```c
> #include <pthread.h>
>
> int pthread_create(pthread_t *thread,
>                    const pthread_attr_t *attr,
>                    void *(*start_routine)(void *),
>                    void *arg);
> ```
> **Returns:** `0` on success; otherwise an errno value (`EAGAIN`, `EINVAL`, `EPERM`, …).
> **Compile/link:** `gcc -Wall -Wextra -pthread -o prog prog.c`

```
   main thread                          new thread
   ┌──────────────┐                    ┌──────────────┐
   │ pthread_create ─────────────────▶│ start_routine│
   │ returns 0      (async)           │   (arg)      │
   │ continues...                     │     ...      │
   └──────────────┘                    └──────────────┘
```

The start routine receives `void *arg` (you cast to your type), runs concurrently
with the creator, and terminates by **returning** or calling `pthread_exit()`.

> **Under the hood ▸** glibc allocates a stack (default often 8 MB on Linux, overridable
> via `ulimit -s` or attributes), sets up TLS, and calls `clone()` with sharing flags.
> The new task enters at a glibc trampoline that calls your `start_routine`.

**Errors ▸**

| Return value | When |
|--------------|------|
| `EAGAIN` | Insufficient resources (kernel limit on tasks, or RLIMIT_NPROC) |
| `EINVAL` | Invalid attributes |
| `EPERM` | Insufficient permission (e.g. scheduling policy) |

---

## 5.2.3 Joinable vs detached

Every thread is either **joinable** (default) or **detached**.

```
   JOINABLE (default)                 DETACHED
   ─────────────────                  ────────
   must be pthread_join()'d           resources freed automatically on exit
   or pthread_detach()'d              cannot pthread_join()
   else → leak (kernel task slot,     good for fire-and-forget workers
           stack memory until joined)
```

> **The call ▸**
> ```c
> int pthread_join(pthread_t thread, void **retval);
> int pthread_detach(pthread_t thread);
> void pthread_exit(void *retval);
> pthread_t pthread_self(void);
> ```

| Function | Semantics |
|----------|-----------|
| `pthread_join(t, &rp)` | Block until `t` exits; optionally collect return value via `rp` |
| `pthread_detach(t)` | Mark `t` as detached; no join needed |
| `pthread_exit(val)` | Terminate **calling** thread; `val` available to joiner |
| `pthread_self()` | Return caller's `pthread_t` handle |

**Pitfall ▸** Returning a pointer to a **stack local** from the start routine and
reading it in the joiner is use-after-free. Return heap memory, static storage, or
pass results through a structure protected by a mutex.

**Pitfall ▸** Joining a detached thread, joining twice, or joining yourself →
undefined behavior / `EINVAL`.

---

## 5.2.4 Returning values

```c
static void *worker(void *arg) {
    long id = (long)arg;
    long *result = malloc(sizeof *result);
    if (result == NULL)
        pthread_exit(NULL);
    *result = id * id;
    return result;              /* equivalent to pthread_exit(result) */
}

void *rp = NULL;
if (pthread_join(t, &rp) != 0) { /* handle error */ }
if (rp != NULL) {
    printf("result = %ld\n", *(long *)rp);
    free(rp);
}
```

Only `pthread_join` (or `pthread_exit` in a cancellation handler) communicates the
return value. There is no global "thread return register."

---

## 5.2.5 Thread attributes

> **The call ▸**
> ```c
> int pthread_attr_init(pthread_attr_t *attr);
> int pthread_attr_destroy(pthread_attr_t *attr);
> int pthread_attr_setdetachstate(pthread_attr_t *attr, int detachstate);
> int pthread_attr_setstacksize(pthread_attr_t *attr, size_t stacksize);
> int pthread_attr_getstacksize(const pthread_attr_t *attr, size_t *stacksize);
> ```
> `detachstate`: `PTHREAD_CREATE_JOINABLE` or `PTHREAD_CREATE_DETACHED`.

Default stack size is platform-dependent (often 2–8 MB on Linux). Deep recursion or
large stack frames may need an explicit increase — but thousands of 8 MB stacks will
exhaust virtual memory.

**Trade-offs ▸** Larger stacks → simpler C code, higher memory footprint. Detached
threads → no join latency, but harder to propagate errors back to main.

---

## 5.2.6 Complete create + join example

```c
#include <errno.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void *worker(void *arg) {
    const char *name = arg;
    fprintf(stderr, "[%s] TID via pthread_self: %lu\n",
            name, (unsigned long)pthread_self());
    return (void *)(strlen(name));   /* return value = length */
}

static void check_pthread(int err, const char *what) {
    if (err != 0) {
        fprintf(stderr, "%s: %s\n", what, strerror(err));
        exit(1);
    }
}

int main(void) {
    pthread_t t1, t2;

    check_pthread(pthread_create(&t1, NULL, worker, "alpha"), "pthread_create");
    check_pthread(pthread_create(&t2, NULL, worker, "beta"),  "pthread_create");

    void *rv1 = NULL, *rv2 = NULL;
    check_pthread(pthread_join(t1, &rv1), "pthread_join");
    check_pthread(pthread_join(t2, &rv2), "pthread_join");

    printf("alpha returned %ld, beta returned %ld\n",
           (long)rv1, (long)rv2);
    return 0;
}
```

```bash
gcc -Wall -Wextra -pthread -o lifecycle lifecycle.c
./lifecycle
```

---

## 5.2.7 Lifecycle diagram

```
   pthread_create
         │
         ▼
   ┌─────────────┐
   │   RUNNING   │◀── pthread_self() identifies this thread
   └──────┬──────┘
          │ return from start_routine OR pthread_exit()
          ▼
   ┌─────────────┐
   │  TERMINATED │
   └──────┬──────┘
          │
    joinable? ──yes──▶ pthread_join() reaps thread resources
          │
          no (detached) ──▶ glibc/kernel reaps automatically
```

After all threads exit, only the **main thread** remaining allows clean process exit.
If main returns from `main()` while joinable threads still run, behavior is undefined
unless you join or detach them first.

---

## Summary

- Pthread functions return `0` on success or a **positive errno value** on failure —
  they do not use the `-1`/`errno` syscall pattern.
- `pthread_create` starts a concurrent start routine; `pthread_join` waits and collects
  a return value; `pthread_detach` opts out of joining.
- Use attributes for stack size and detach state; never return pointers to stack
  locals to the joiner.
- Link with `-pthread`; under the hood, each thread is a `clone()`'d task (Part 5.1).

Next: [5.3 — Mutexes & read-write locks](03-mutexes-and-rwlocks.md)
