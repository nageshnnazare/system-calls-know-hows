# 1.6 — Scheduling & Priority

The kernel **scheduler** decides which `task_struct` runs on each CPU and for how
long. User space influences that decision through **nice values**, **scheduling
policies**, and **CPU affinity** — not by picking cores directly. Every process
you fork (Part 1.2) enters a run queue; understanding scheduling explains latency
spikes, priority inversion symptoms, and why real-time policies can freeze a machine.

---

## 1.6.1 Who runs next?

```
   runnable tasks (per-CPU runqueues, simplified)
   ┌──────────────────────────────────────────────────────────┐
   │  SCHED_FIFO/RR (real-time)  ← highest priority band      │
   │  SCHED_OTHER (CFS)          ← most normal processes      │
   │  SCHED_BATCH / SCHED_IDLE   ← lowest preference          │
   └──────────────────────────────────────────────────────────┘
        │
        │  timer tick / wakeup → pick next task
        ▼
   CPU runs one task's register state until preempted or it blocks
```

> **Under the hood ▸** Linux 2.6+ uses **CFS (Completely Fair Scheduler)** for
> `SCHED_OTHER`. Each runnable task accumulates **virtual runtime (`vruntime`)**;
> the task with the smallest vruntime runs next. **Nice** adjusts how fast
> vruntime grows — lower nice → slower growth → more CPU time.

Blocking syscalls (`read`, `futex`, etc.) remove the task from the run queue until
the event completes (Part 0.1). **`sched_yield()`** voluntarily gives up the
remainder of the time slice.

---

## 1.6.2 nice, getpriority, setpriority

> **The call ▸**
> ```c
> #include <unistd.h>
> int nice(int inc);   /* inc ∈ [-20, 19] relative to current nice */
> ```
> Returns the **new nice value** on success; on error returns **-1** and sets `errno`.
> (Ambiguous if nice was already -1 — check `errno`.)

> **The call ▸**
> ```c
> #include <sys/resource.h>
> int getpriority(int which, id_t who);
> int setpriority(int which, id_t who, int prio);
> ```
> `which`: `PRIO_PROCESS`, `PRIO_PGRP`, or `PRIO_USER`. `prio` for setpriority:
> **0 (highest) to 19 (lowest)** — *not* the same sign as `nice` (-20..19) but
> the same axis.

| Nice | Meaning |
|------|---------|
| **-20** | highest CPU preference (needs `CAP_SYS_NICE` for lower nice) |
| **0** | default |
| **19** | lowest CPU preference — "when idle" |

```c
#include <stdio.h>
#include <unistd.h>
#include <errno.h>
#include <sys/resource.h>

int main(void) {
    errno = 0;
    int n = nice(5);   /* lower priority by 5 */
    if (n == -1 && errno != 0) {
        perror("nice");
        return 1;
    }
    printf("nice = %d\n", n);

    if (setpriority(PRIO_PROCESS, 0, 10) == -1) {
        perror("setpriority");
        return 1;
    }

    errno = 0;
    int p = getpriority(PRIO_PROCESS, 0);
    if (p == -1 && errno != 0) {
        perror("getpriority");
        return 1;
    }
    printf("priority = %d\n", p);
    return 0;
}
```

**Errors ▸**

| `errno` | when it happens |
|---------|-----------------|
| `EACCES` / `EPERM` | unprivileged process tries to raise priority (lower nice) |
| `EINVAL` | invalid `which` or out-of-range priority |
| `ESRCH` | no process(es) matching `who` |

**Pitfall ▸** **`nice`/`setpriority` do not guarantee latency** — they bias CFS
under contention. A CPU-bound task at nice 19 still starves nothing if it is alone
on the core.

---

## 1.6.3 Scheduling policies: sched_setscheduler

> **The call ▸**
> ```c
> #define _GNU_SOURCE
> #include <sched.h>
>
> int sched_setscheduler(pid_t pid, int policy, const struct sched_param *param);
> int sched_getscheduler(pid_t pid);
> ```

| Policy | Behavior |
|--------|----------|
| **`SCHED_OTHER`** | Default CFS time-sharing |
| **`SCHED_BATCH`** | CFS tuned for CPU-bound batch workloads — less preemptive wakeups |
| **`SCHED_IDLE`** | Runs only when no other runnable task exists |
| **`SCHED_FIFO`** | Real-time: run until block or preemption by **higher** RT priority |
| **`SCHED_RR`** | Real-time round-robin with a time quantum |

```c
#define _GNU_SOURCE
#include <stdio.h>
#include <sched.h>
#include <errno.h>

int main(void) {
    struct sched_param param = { .sched_priority = 0 };

    if (sched_setscheduler(0, SCHED_BATCH, &param) == -1) {
        perror("sched_setscheduler");
        return 1;
    }

    int pol = sched_getscheduler(0);
    if (pol == -1) {
        perror("sched_getscheduler");
        return 1;
    }
    printf("policy = %d (SCHED_BATCH=%d)\n", pol, SCHED_BATCH);
    return 0;
}
```

For **`SCHED_FIFO`/`SCHED_RR`**, `sched_priority` is **1–99** (higher = more
important). Setting RT scheduling requires **`CAP_SYS_NICE`** or `RLIMIT_RTPRIO`.

**Errors ▸** (`sched_setscheduler`)

| `errno` | when it happens |
|---------|-----------------|
| `EINVAL` | invalid policy or priority for policy |
| `EPERM` | insufficient privilege |
| `ESRCH` | pid not found |

**Systems ▸** **`chrt`** manipulates policy from the shell: `chrt -f 50 ./rt_app`
runs with `SCHED_FIFO` priority 50.

---

## 1.6.4 Real-time caveats

```
   one SCHED_FIFO task at priority 50 in a busy loop
        │
        ▼
   never yields → kernel preemption still exists, but user space may monopolize CPU
        │
        ▼
   system feels "frozen" — SSH, watchdog, ksoftirqd starved on that CPU
```

**Pitfall ▸** Real-time policies are for **controlled** systems with bounded,
audited RT threads — not for making a web server "faster." Always bound work, use
the lowest sufficient RT priority, and pin sparingly.

**Trade-offs ▸** **`SCHED_BATCH`** reduces scheduler overhead for long CPU jobs;
**`SCHED_IDLE`** is ideal for low-priority background crunch (indexers, backups).

---

## 1.6.5 CPU affinity: sched_setaffinity

> **The call ▸**
> ```c
> #define _GNU_SOURCE
> #include <sched.h>
>
> int sched_setaffinity(pid_t pid, size_t cpusetsize, const cpu_set_t *mask);
> int sched_getaffinity(pid_t pid, size_t cpusetsize, cpu_set_t *mask);
> ```

Pin a process or thread to specific CPUs:

```c
#define _GNU_SOURCE
#include <stdio.h>
#include <sched.h>
#include <unistd.h>
#include <errno.h>

int main(void) {
    cpu_set_t cpuset;
    CPU_ZERO(&cpuset);
    CPU_SET(2, &cpuset);   /* allow only CPU 2 */

    if (sched_setaffinity(0, sizeof(cpuset), &cpuset) == -1) {
        perror("sched_setaffinity");
        return 1;
    }

    CPU_ZERO(&cpuset);
    if (sched_getaffinity(0, sizeof(cpuset), &cpuset) == -1) {
        perror("sched_getaffinity");
        return 1;
    }

    printf("running on CPUs:");
    for (int i = 0; i < CPU_SETSIZE; i++)
        if (CPU_ISSET(i, &cpuset))
            printf(" %d", i);
    printf("\n");

    /* hot loop will not migrate off CPU 2 */
    for (volatile long i = 0; i < 100000000L; i++)
        ;
    return 0;
}
```

Use **`pthread_setaffinity_np`** (Part 5) for individual threads. Containers and
cgroups v2 **`cpuset`** controllers further restrict allowed CPUs (Part 8.5).

**Errors ▸**

| `errno` | when it happens |
|---------|-----------------|
| `EINVAL` | invalid cpuset or cpusetsize |
| `EPERM` | no permission to set target pid |
| `ESRCH` | pid not found |

**Trade-offs ▸** Pinning reduces cache migration and NUMA surprises but can
**create imbalance** if hot tasks pile on one core while others idle.

---

## 1.6.6 sched_yield

> **The call ▸**
> ```c
> #include <sched.h>
> int sched_yield(void);
> ```
> Moves the caller to the **back of its priority run queue** without sleeping.
> Returns 0; rarely fails (`errno` set on error).

Use sparingly for **cooperative** hinting (old pthread spin locks); modern code
prefers **`futex` waits** (Part 5.5). Busy-yielding burns CPU and rarely fixes
contention.

---

## 1.6.7 Putting it together with Part 1

```
   fork()  → child inherits parent's nice and scheduler policy
   exec()  → policy/nice preserved (unless prctl or wrapper changes them)
   wait4() → can read ru_utime/ru_stime (CPU time consumed — Part 1.4)
```

Trace scheduling behavior: **`perf stat ./program`**, **`/proc/[pid]/sched`**, and
**`chrt -p [pid]`** for live policy inspection.

---

## Summary

- **CFS** (`SCHED_OTHER`) fairly shares CPU via virtual runtime; **nice** biases
  share under load.
- **`SCHED_BATCH`/`SCHED_IDLE`** tune non-interactive workloads; **`SCHED_FIFO`/`RR`**
  are real-time and dangerous without care.
- **`sched_setaffinity`** pins tasks to CPUs; combine with thread affinity and
  cgroups for NUMA-aware layouts.
- **`sched_yield`** voluntarily surrenders the remainder of a slice — rarely the
  right fix for contention.
- Scheduling attributes **survive `exec`**; use **`chrt`**, **`nice`**, or
  **`sched_set*`** before or after fork depending on your daemon model.

Next: [Part 2 — File I/O & the VFS](../02-file-io/01-open-close.md)
