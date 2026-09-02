# 5.5 — Atomics & the futex

Mutexes and condition variables feel like pure library magic, but on Linux they bottom
out in **atomics** (lock-free CPU instructions) and the **`futex()`** syscall (fast
userspace sleeping). Part 5.3 showed the fast/slow mutex path; this chapter gives you
the C11 tools to build synchronization yourself and the kernel primitive that makes
blocking efficient.

---

## 5.5.1 C11 atomics and stdatomic.h

> **The call ▸**
> ```c
> #include <stdatomic.h>
>
> atomic_int counter = ATOMIC_VAR_INIT(0);
> atomic_load(&counter);
> atomic_store(&counter, 42);
> atomic_fetch_add(&counter, 1);
> bool atomic_compare_exchange_strong(atomic_int *obj, int *expected, int desired);
> ```

C11 `_Atomic` types and `<stdatomic.h>` expose **well-defined** concurrent access — unlike
plain `int`, which races are undefined behavior (Part 5.6). C++ has `<atomic>` with
equivalent semantics.

```c
#include <stdatomic.h>
#include <stdio.h>

int main(void) {
    atomic_int x = 0;
    atomic_store_explicit(&x, 1, memory_order_release);
    int v = atomic_load_explicit(&x, memory_order_acquire);
    printf("x = %d\n", v);
    return 0;
}
```

Compile with `-std=c11` (or newer). No `-pthread` required for single-threaded atomics;
multi-threaded use still needs threads linked with `-pthread`.

---

## 5.5.2 Memory ordering intuition

Modern CPUs and compilers reorder memory operations for speed. Atomics carry an
explicit **memory order** that constrains visibility:

```
   thread A                          thread B
   ────────                          ────────
   store data = 42                   load flag
   store flag = 1  (release)    →    if flag: read data  (acquire)
                                     must see 42 if flag seen
```

| Order | Guarantee (simplified) |
|-------|------------------------|
| `memory_order_relaxed` | Atomicity only; no cross-thread ordering |
| `memory_order_acquire` | Subsequent loads/stores not hoisted before this load |
| `memory_order_release` | Prior loads/stores not sunk after this store |
| `memory_order_acq_rel` | Both acquire + release (read-modify-write ops) |
| `memory_order_seq_cst` | Global sequential consistency (default; strongest, often slowest) |

**Trade-offs ▸** Default `seq_cst` is correct and easy to reason about. Hot paths
(lock internals, reference counts) use acquire/release pairs on specific words.
Mis-ordered relaxed atomics cause Heisenbugs — reach for TSan (Part 5.6) when tuning.

**Pitfall ▸** Using `relaxed` for a flag guarding non-atomic data → data race on the
payload even if the flag itself is atomic. Pair release (publisher) with acquire
(consumer).

---

## 5.5.3 Compare-and-swap (CAS)

CAS is the workhorse of lock-free algorithms:

> **The call ▸**
> ```c
> bool atomic_compare_exchange_strong(atomic_int *obj,
>                                     int *expected,
>                                     int desired);
> ```
> Atomically: if `*obj == *expected`, set `*obj = desired` and return `true`; else
> write current `*obj` into `*expected` and return `false`.

```
   CAS(&lock, 0, 1):
   lock was 0  →  now 1, return success  (acquired)
   lock was 1  →  unchanged, return fail  (someone else holds)
```

Mutex fast paths, lock-free stacks, and hazard pointers all build on CAS loops.

---

## 5.5.4 The futex syscall

![Futex: userspace atomic + kernel wait queue](figures/futex.svg)

> **The call ▸**
> ```c
> #include <linux/futex.h>
> #include <sys/syscall.h>
> #include <unistd.h>
>
> long futex(uint32_t *uaddr, int futex_op, uint32_t val,
>            const struct timespec *timeout, uint32_t *uaddr2, uint32_t val3);
> /* glibc wraps this; application code rarely calls futex directly */
> ```

**Under the hood ▸** "Futex" = **FU**tex = **F**ast **U**serspace mu**TEX**. The
userspace word (typically `0` = free, `1` = locked, `2` = locked + waiters) is
updated with atomics. **`futex()` is only called when you must sleep or wake.**

Common operations:

| op | Role |
|----|------|
| `FUTEX_WAIT` | If `*uaddr == val`, sleep until woken |
| `FUTEX_WAKE` | Wake up to `val` waiters on `*uaddr` |
| `FUTEX_WAIT_BITSET` / `WAKE_BITSET` | Priority inheritance, PI mutexes |

```
   pthread_mutex_lock (contended):
   ───────────────────────────────
   1. CAS lock word 0→1 failed
   2. futex(FUTEX_WAIT, uaddr, 1)   /* sleep while word == 1 */

   pthread_mutex_unlock:
   ────────────────────
   1. atomic store 0
   2. futex(FUTEX_WAKE, uaddr, 1)     /* wake one waiter */
```

**Systems ▸** `strace -e futex -f ./prog` is the microscope for pthread contention.
Thousands of futex waits per second → lock granularity or hold time problem.

---

## 5.5.5 Spinlock vs futex-backed lock

**Spinlock** — CAS in a tight loop; no syscall while waiting:

```c
#include <stdatomic.h>
#include <sched.h>

typedef atomic_int spinlock_t;

void spin_lock(spinlock_t *s) {
    while (!atomic_compare_exchange_strong(s, &(int){0}, 1))
        sched_yield();   /* or pause instruction on x86 */
}

void spin_unlock(spinlock_t *s) {
    atomic_store(s, 0);
}
```

**Trade-offs ▸**

| Spinlock | Futex-backed mutex |
|----------|-------------------|
| ✓ microsecond waits, low overhead | ✓ doesn't burn CPU when blocked |
| ✗ wastes cores under contention | ✗ syscall + context switch on contention |
| ✗ unfair, priority inversion risk | ✓ integrates with scheduler |

Rule of thumb: spin only if hold time is **shorter than** roughly 2× context-switch
cost *and* you have spare cores. Otherwise use `pthread_mutex`.

**Futex-style lock sketch** (simplified educational version):

```c
#include <errno.h>
#include <linux/futex.h>
#include <stdatomic.h>
#include <sys/syscall.h>
#include <unistd.h>

static long sys_futex(uint32_t *uaddr, int op, uint32_t val) {
    return syscall(SYS_futex, uaddr, op, val, NULL, NULL, 0);
}

typedef atomic_uint futex_lock_t;

void futex_lock(futex_lock_t *lock) {
    uint32_t expected = 0;
    while (!atomic_compare_exchange_strong(lock, &expected, 1)) {
        expected = 1;   /* wait while locked */
        sys_futex((uint32_t *)lock, FUTEX_WAIT, 1);
        expected = 0;
    }
}

void futex_unlock(futex_lock_t *lock) {
    atomic_store(lock, 0);
    sys_futex((uint32_t *)lock, FUTEX_WAKE, 1);
}
```

Real glibc mutexes add fairness, PI, adaptive spinning, and error checking — do not
ship this as production locking.

---

## 5.5.6 How the pieces connect

```
   your code:  pthread_mutex_lock()
                      │
                      ▼
   glibc:  atomic ops on futex word
                      │
            uncontended ──▶ return (no syscall)
                      │
            contended  ──▶ futex(FUTEX_WAIT)
                      │
                      ▼
   kernel: wait queue on the futex address, schedule other threads
```

Condition variables use the same foundation: waiters sleep on a futex tied to the
cond's internal state; `signal`/`broadcast` issue `FUTEX_WAKE` (Part 5.4).

---

## Summary

- C11 `<stdatomic.h>` provides race-free operations; choose memory orders deliberately
  (`relaxed` / `acquire` / `release` / `seq_cst`).
- CAS enables lock-free structures and mutex fast paths.
- `futex()` sleeps and wakes on a userspace word — pthread mutexes and condvars use it
  only on contention.
- Spinlocks for very short critical sections; futex-backed mutexes for general use.

Next: [5.6 — Concurrency pitfalls](06-concurrency-pitfalls.md)
