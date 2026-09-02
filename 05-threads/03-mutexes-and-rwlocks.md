# 5.3 — Mutexes & Read-Write Locks

When threads share mutable state, you need **mutual exclusion**: a critical section
where at most one thread executes at a time. POSIX **mutexes** provide that guarantee;
**read-write locks** refine it for read-heavy workloads. Part 5.2 created concurrent
threads; this chapter makes shared updates correct — and explains the fast atomic path
vs the futex slow path (Part 5.5).

---

## 5.3.1 Critical sections and mutex basics

![Mutex: one holder at a time](figures/mutex.svg)

```
   thread A          mutex           thread B
      │               🔒                │
      │── lock() ────▶│                 │
      │   [critical   │   lock() blocks │
      │    section]   │◀────────────────│
      │── unlock() ──▶│                 │
      │               🔓                │── now acquires ──▶ [critical section]
```

> **The call ▸**
> ```c
> #include <pthread.h>
>
> int pthread_mutex_init(pthread_mutex_t *mutex,
>                        const pthread_mutexattr_t *attr);
> int pthread_mutex_destroy(pthread_mutex_t *mutex);
> int pthread_mutex_lock(pthread_mutex_t *mutex);
> int pthread_mutex_trylock(pthread_mutex_t *mutex);
> int pthread_mutex_unlock(pthread_mutex_t *mutex);
>
> /* static initializer (default attrs): */
> pthread_mutex_t m = PTHREAD_MUTEX_INITIALIZER;
> ```
> **Returns:** `0` on success; errno value on failure (`pthread_*` contract — Part 5.2).

| Operation | Behavior |
|-----------|----------|
| `lock` | Acquire; block if held |
| `trylock` | Acquire or return `EBUSY` immediately |
| `unlock` | Release; undefined if caller doesn't hold lock |

**Pitfall ▸** Locking twice in the same thread with a **normal** mutex → deadlock
(self-deadlock). Unlocking without holding → undefined behavior.

---

## 5.3.2 Mutex types

> **The call ▸**
> ```c
> int pthread_mutexattr_settype(pthread_mutexattr_t *attr, int type);
> ```
> Types: `PTHREAD_MUTEX_NORMAL`, `PTHREAD_MUTEX_ERRORCHECK`,
> `PTHREAD_MUTEX_RECURSIVE`, `PTHREAD_MUTEX_DEFAULT`.

| Type | Double-lock in same thread | Unlock without holding |
|------|---------------------------|------------------------|
| NORMAL (default) | Deadlock | Undefined |
| ERRORCHECK | Returns `EDEADLK` | Returns `EPERM` |
| RECURSIVE | Succeeds (counted) | Must unlock same # of times |

**Trade-offs ▸** ERRORCHECK costs extra checks — use in debug builds. RECURSIVE hides
design smells (re-entrant call paths) but is sometimes required for callbacks.

---

## 5.3.3 Fast path vs futex slow path

> **Under the hood ▸** An uncontended mutex lock is a few **atomic instructions** in
> user space — no syscall. On contention, glibc falls through to the **`futex()`**
> syscall (Part 5.5): the kernel puts the waiter to sleep until the holder unlocks
> and wakes waiters.

```
   pthread_mutex_lock()
         │
         ▼
   atomic CAS: 0 → 1  ──success──▶  return 0   (fast, ~tens of ns)
         │
       fail (contended)
         │
         ▼
   futex(FUTEX_WAIT)  ──▶  block in kernel until unlock wakes you
```

This is why mutexes are cheap when nobody fights over them, and why **hold time**
matters: long critical sections force syscalls and context switches.

**Systems ▸** `strace -e futex ./prog` shows the slow path. A spin-then-futex hybrid
is what you get internally; don't spin in application code unless you know contention
is microseconds-long (Part 5.5).

---

## 5.3.4 Mutex-protected counter example

```c
#include <errno.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define NUM_THREADS 4
#define INCREMENTS  250000

static pthread_mutex_t counter_mutex = PTHREAD_MUTEX_INITIALIZER;
static long counter = 0;

static void check(int err, const char *what) {
    if (err != 0) {
        fprintf(stderr, "%s: %s\n", what, strerror(err));
        exit(1);
    }
}

static void *incrementer(void *arg) {
    (void)arg;
    for (int i = 0; i < INCREMENTS; i++) {
        check(pthread_mutex_lock(&counter_mutex), "pthread_mutex_lock");
        counter++;
        check(pthread_mutex_unlock(&counter_mutex), "pthread_mutex_unlock");
    }
    return NULL;
}

int main(void) {
    pthread_t threads[NUM_THREADS];

    for (int i = 0; i < NUM_THREADS; i++)
        check(pthread_create(&threads[i], NULL, incrementer, NULL),
              "pthread_create");

    for (int i = 0; i < NUM_THREADS; i++)
        check(pthread_join(threads[i], NULL), "pthread_join");

    long expected = (long)NUM_THREADS * INCREMENTS;
    printf("counter = %ld (expected %ld) %s\n",
           counter, expected, counter == expected ? "OK" : "RACE");
    return counter == expected ? 0 : 1;
}
```

Without the mutex, `counter` would be corrupted by lost updates (Part 5.6). With it,
the result is deterministic.

```bash
gcc -Wall -Wextra -pthread -o counter counter.c
./counter
```

---

## 5.3.5 Read-write locks

> **The call ▸**
> ```c
> int pthread_rwlock_init(pthread_rwlock_t *rwlock,
>                         const pthread_rwlockattr_t *attr);
> int pthread_rwlock_destroy(pthread_rwlock_t *rwlock);
> int pthread_rwlock_rdlock(pthread_rwlock_t *rwlock);
> int pthread_rwlock_wrlock(pthread_rwlock_t *rwlock);
> int pthread_rwlock_tryrdlock(pthread_rwlock_t *rwlock);
> int pthread_rwlock_trywrlock(pthread_rwlock_t *rwlock);
> int pthread_rwlock_unlock(pthread_rwlock_t *rwlock);
> ```

```
   many readers OR one writer
   ┌─────────────────────────────────────┐
   │  rdlock  rdlock  rdlock   (OK)      │
   │  wrlock  ────────────────── blocks all │
   │  rdlock while writer active ── blocks  │
   └─────────────────────────────────────┘
```

Use rwlocks when reads dominate (config snapshot, cache lookup). Writes still
exclude everyone. **Trade-offs ▸** rwlocks have higher constant overhead than
mutexes; under heavy write contention they can be *slower* than a plain mutex.

**Pitfall ▸** A thread holding a read lock must not upgrade to a write lock on the
same rwlock (deadlock on glibc/Linux). Drop read lock first, or re-design.

---

## 5.3.6 Lock ordering and deadlock

Deadlock requires a cycle of waits:

```
   thread 1:  lock(A) ──▶ wait(B)
   thread 2:  lock(B) ──▶ wait(A)
                  └── cycle ──┘
```

**Rules to avoid deadlock:**

1. **Global lock order** — always acquire `A` before `B` if both are ever needed.
2. **Trylock + backoff** — `pthread_mutex_trylock`, release held locks, retry.
3. **Hold fewer locks, shorter** — shrink critical sections.
4. **One lock** — sometimes a coarser mutex beats a deadlock-prone fine-grained graph.

```
   ✓  all threads: mutex1 → mutex2 → mutex3
   ✗  thread A: m1→m2    thread B: m2→m1
```

Condition variables (Part 5.4) add a rule: **always wait while holding the mutex**
associated with that cond, and use the same lock ordering when multiple conds exist.

---

## Summary

- Mutexes serialize access to critical sections; pthread returns errno values, not `-1`.
- Uncontended locks are user-space atomics; contention triggers `futex()` sleeps.
- Mutex types: normal (default), errorcheck (debug), recursive (re-entrant).
- Rwlocks allow concurrent readers or one writer; pick based on read/write ratio.
- Establish a global lock order to prevent deadlock; keep critical sections short.

Next: [5.4 — Condition variables](04-condition-variables.md)
