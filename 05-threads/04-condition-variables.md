# 5.4 — Condition Variables

A mutex protects shared **data**; a **condition variable** lets threads **wait for a
state change** on that data without burning CPU. The canonical pattern is
**mutex + predicate**: lock, check a condition in a loop, wait if false, mutate,
signal, unlock. Part 5.3 covered mutexes; this chapter covers `pthread_cond_*` and
why the predicate loop is mandatory, not optional.

---

## 5.4.1 Why condition variables exist

```
   WITHOUT cond var                    WITH cond var
   ─────────────────                   ─────────────
   lock(m)                             lock(m)
   while (!ready) {                    while (!ready)
     unlock(m);                          pthread_cond_wait(&c, &m);
     usleep(1000);  /* poll */         /* atomically: unlock + sleep */
     lock(m);                         }
   }                                   /* re-lock on wake */
   /* wasted CPU, latency */           /* kernel sleep until signal */
```

> **The call ▸**
> ```c
> #include <pthread.h>
>
> int pthread_cond_init(pthread_cond_t *cond, const pthread_condattr_t *attr);
> int pthread_cond_destroy(pthread_cond_t *cond);
> int pthread_cond_wait(pthread_cond_t *cond, pthread_mutex_t *mutex);
> int pthread_cond_timedwait(pthread_cond_t *restrict cond,
>                            pthread_mutex_t *restrict mutex,
>                            const struct timespec *restrict abstime);
> int pthread_cond_signal(pthread_cond_t *cond);
> int pthread_cond_broadcast(pthread_cond_t *cond);
> ```
> **Returns:** `0` on success; errno value on failure.


---

## 5.4.2 The mutex + predicate pattern

A condition variable has **no memory of its own** — it does not store "ready" or
"queue non-empty." All state lives in your shared variables, protected by the mutex.

```c
pthread_mutex_lock(&m);
while (!predicate()) {          /* NOT if — always while */
    pthread_cond_wait(&cv, &m);
}
/* predicate true: act */
pthread_mutex_unlock(&m);
```

Producer side:

```c
pthread_mutex_lock(&m);
/* make predicate true */
pthread_cond_signal(&cv);       /* or broadcast */
pthread_mutex_unlock(&m);
```

> **Under the hood ▸** `pthread_cond_wait` atomically:
> 1. Adds caller to the cond's wait queue.
> 2. **Unlocks** `mutex`.
> 3. Blocks (futex sleep — Part 5.5).
> 4. On wake, **re-acquires** `mutex` before returning.

You must re-check the predicate after wake because you re-acquire the lock in a
racy world where other threads may have changed state.

---

## 5.4.3 Why you must loop: spurious wakeups

POSIX permits **`pthread_cond_wait` to return even though nobody signaled** —
a *spurious wakeup*. The loop handles it:

```c
while (queue_empty(&q))
    pthread_cond_wait(&q_not_empty, &q_mutex);
/* now queue_empty is reliably false under the lock */
```

Without the loop, a spurious wake would proceed with a false predicate → corruption.

---

## 5.4.4 Why you must loop: lost wakeups

Consider a broken `if` instead of `while`:

```
   consumer                          producer
   lock(m)                           lock(m)
   if (count == 0)  /* true */       enqueue item; count = 1
   /* about to wait... */            signal(cv)
   wait(cv)  ← signal already sent   unlock(m)
   /* sleeps forever */              (lost wakeup)
```

The signal does not queue for the future — it wakes threads **already waiting**. If
you check the predicate, fail to wait, or wait after the signal without re-checking,
you can miss the event. **`while` fixes both** spurious wakeups and lost-wakeup races
when combined with re-checking under the lock.

**Pitfall ▸** Calling `signal` **before** the waiter holds the mutex and enters
`wait` is fine **if** the predicate is already true when the waiter locks — the
`while` exits immediately without sleeping. Signals are hints, not counted semaphores.

---

## 5.4.5 signal vs broadcast

| Call | Effect |
|------|--------|
| `pthread_cond_signal` | Wake **one** waiter (efficient if one consumer suffices) |
| `pthread_cond_broadcast` | Wake **all** waiters (shutdown, multiple consumers, predicate change affects everyone) |

Use broadcast when all waiters must re-evaluate (e.g. `shutdown = true`). Excess
wakeups cost scheduler work — signal is preferred for thread-pool job dispatch when
one worker will handle one job.

---

## 5.4.6 pthread_cond_timedwait

> **The call ▸**
> ```c
> int pthread_cond_timedwait(pthread_cond_t *cond, pthread_mutex_t *mutex,
>                            const struct timespec *abstime);
> ```
> `abstime` is **CLOCK_REALTIME** absolute time (legacy POSIX); prefer
> `pthread_cond_clockwait` with `CLOCK_MONOTONIC` on glibc ≥ 2.30 to avoid clock
> adjustment surprises.

**Errors ▸**

| Return | When |
|--------|------|
| `ETIMEDOUT` | Absolute timeout expired before predicate became true |
| `EINVAL` | Invalid timespec or uninitialized objects |

Timed wait still requires the `while` loop:

```c
struct timespec deadline;
clock_gettime(CLOCK_REALTIME, &deadline);
deadline.tv_sec += 5;

pthread_mutex_lock(&m);
while (!done) {
    int err = pthread_cond_timedwait(&cv, &m, &deadline);
    if (err == ETIMEDOUT)
        break;
    if (err != 0) { /* handle */ }
}
pthread_mutex_unlock(&m);
```

---

## 5.4.7 Bounded producer/consumer queue

Fixed-size ring buffer: producers block when full, consumers when empty.

```c
#include <errno.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CAP 8
#define ITEMS 20

typedef struct {
    int buf[CAP];
    int head, tail, count;
    int shutdown;
    pthread_mutex_t m;
    pthread_cond_t not_full;
    pthread_cond_t not_empty;
} queue_t;

static void queue_init(queue_t *q) {
    q->head = q->tail = q->count = q->shutdown = 0;
    pthread_mutex_init(&q->m, NULL);
    pthread_cond_init(&q->not_full, NULL);
    pthread_cond_init(&q->not_empty, NULL);
}

static void check(int err, const char *what) {
    if (err != 0) {
        fprintf(stderr, "%s: %s\n", what, strerror(err));
        exit(1);
    }
}

static void queue_push(queue_t *q, int val) {
    check(pthread_mutex_lock(&q->m), "lock");
    while (q->count == CAP && !q->shutdown)
        check(pthread_cond_wait(&q->not_full, &q->m), "wait not_full");
    if (q->shutdown) {
        check(pthread_mutex_unlock(&q->m), "unlock");
        return;
    }
    q->buf[q->tail] = val;
    q->tail = (q->tail + 1) % CAP;
    q->count++;
    check(pthread_cond_signal(&q->not_empty), "signal");
    check(pthread_mutex_unlock(&q->m), "unlock");
}

static int queue_pop(queue_t *q, int *out) {
    check(pthread_mutex_lock(&q->m), "lock");
    while (q->count == 0 && !q->shutdown)
        check(pthread_cond_wait(&q->not_empty, &q->m), "wait not_empty");
    if (q->count == 0 && q->shutdown) {
        check(pthread_mutex_unlock(&q->m), "unlock");
        return 0;   /* drained + shutdown */
    }
    *out = q->buf[q->head];
    q->head = (q->head + 1) % CAP;
    q->count--;
    check(pthread_cond_signal(&q->not_full), "signal");
    check(pthread_mutex_unlock(&q->m), "unlock");
    return 1;
}

static void *producer(void *arg) {
    queue_t *q = arg;
    for (int i = 1; i <= ITEMS; i++)
        queue_push(q, i);
    check(pthread_mutex_lock(&q->m), "lock");
    q->shutdown = 1;
    check(pthread_cond_broadcast(&q->not_empty), "broadcast");
    check(pthread_cond_broadcast(&q->not_full), "broadcast");
    check(pthread_mutex_unlock(&q->m), "unlock");
    return NULL;
}

static void *consumer(void *arg) {
    queue_t *q = arg;
    for (;;) {
        int val;
        if (!queue_pop(q, &val))
            break;
        printf(" consumed %d\n", val);
    }
    return NULL;
}

int main(void) {
    queue_t q;
    queue_init(&q);
    pthread_t prod, cons;
    check(pthread_create(&prod, NULL, producer, &q), "create prod");
    check(pthread_create(&cons, NULL, consumer, &q), "create cons");
    check(pthread_join(prod, NULL), "join prod");
    check(pthread_join(cons, NULL), "join cons");
    return 0;
}
```

Compile: `gcc -Wall -Wextra -pthread -o pcqueue pcqueue.c`

---

## Summary

- Condition variables coordinate on shared state; they do not store that state — your
  predicate does, under the mutex.
- Always use `while (predicate) wait`, never `if`, to handle spurious wakeups and
  races with concurrent producers.
- `wait` atomically releases the mutex and sleeps; you hold the mutex again on return.
- Use `signal` for one consumer, `broadcast` for shutdown or many waiters;
  `timedwait` for deadlines.

Next: [5.5 — Atomics & the futex](05-atomics-and-futex.md)
