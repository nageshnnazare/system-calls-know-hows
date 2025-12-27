# Resource Management System Calls

## Overview

Resource management system calls allow processes to query and control resource limits. This includes CPU time, memory, file descriptors, and more.

## Resource Limits Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    PROCESS                              │
│                                                         │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Resource Usage                                    │ │
│  │  ┌──────────────────────────────────────────────┐  │ │
│  │  │  CPU Time:        5.2 seconds                │  │ │
│  │  │  Memory:          45 MB / 100 MB limit       │  │ │
│  │  │  File Descriptors: 15 / 1024 limit           │  │ │
│  │  │  Processes:       3 / 256 limit              │  │ │
│  │  │  Stack Size:      2 MB / 8 MB limit          │  │ │
│  │  └──────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────┘ │
│                           │                             │
└───────────────────────────┼─────────────────────────────┘
                            │
                  ┌─────────┴──────────┐
                  │                    │
                  ▼                    ▼
        ┌──────────────────┐  ┌──────────────────┐
        │ Soft Limit       │  │ Hard Limit       │
        │ (can be raised)  │  │ (absolute max)   │
        │                  │  │                  │
        │ User adjustable  │  │ Requires root    │
        │ up to hard limit │  │ to increase      │
        └──────────────────┘  └──────────────────┘
```

## 1. getrlimit() and setrlimit() - Resource Limits

### Synopsis
```c
#include <sys/resource.h>

int getrlimit(int resource, struct rlimit *rlim);
int setrlimit(int resource, const struct rlimit *rlim);
int prlimit(pid_t pid, int resource, const struct rlimit *new_limit,
            struct rlimit *old_limit);
```

### struct rlimit

```c
struct rlimit {
    rlim_t rlim_cur;  // Soft limit (current)
    rlim_t rlim_max;  // Hard limit (maximum)
};
```

### Resource Types

```
┌──────────────────────────────────────────────────────────┐
│ Resource                Description                      │
├──────────────────────────────────────────────────────────┤
│ RLIMIT_CPU          Max CPU time (seconds)               │
│ RLIMIT_FSIZE        Max file size (bytes)                │
│ RLIMIT_DATA         Max data segment size (bytes)        │
│ RLIMIT_STACK        Max stack size (bytes)               │
│ RLIMIT_CORE         Max core file size (bytes)           │
│ RLIMIT_RSS          Max resident set size (bytes)        │
│ RLIMIT_NOFILE       Max number of open files             │
│ RLIMIT_AS           Max address space (virtual memory)   │
│ RLIMIT_NPROC        Max number of processes              │
│ RLIMIT_MEMLOCK      Max locked memory (bytes)            │
│ RLIMIT_LOCKS        Max file locks                       │
│ RLIMIT_SIGPENDING   Max pending signals                  │
│ RLIMIT_MSGQUEUE     Max bytes in message queues          │
│ RLIMIT_NICE         Max nice value                       │
│ RLIMIT_RTPRIO       Max real-time priority               │
└──────────────────────────────────────────────────────────┘

Special value: RLIM_INFINITY (no limit)
```

### Limit Enforcement

```
Soft vs Hard Limits:

Soft Limit (rlim_cur):
┌─────────────────────────────────────────┐
│ Current Usage:  ████████░░░░░░░░░░      │
│                 40%                     │
│                                         │
│ Soft Limit:     ─────────────────────►  │
│                 Can be increased by     │
│                 process (up to hard)    │
│                                         │
│ Hard Limit:     ════════════════════►   │
│                 Maximum (needs root)    │
└─────────────────────────────────────────┘

What happens when limit exceeded?
┌──────────────────────────────────────────────────┐
│ RLIMIT_CPU      → SIGXCPU signal sent            │
│ RLIMIT_FSIZE    → SIGXFSZ signal, write fails    │
│ RLIMIT_DATA     → malloc/brk fails               │
│ RLIMIT_STACK    → Stack overflow, SIGSEGV        │
│ RLIMIT_NOFILE   → open() fails with EMFILE       │
│ RLIMIT_NPROC    → fork() fails with EAGAIN       │
└──────────────────────────────────────────────────┘
```

### Example: Basic Limits
```c
#include <sys/resource.h>
#include <stdio.h>
#include <stdlib.h>

void print_limit(int resource, const char *name) {
    struct rlimit limit;
    
    if (getrlimit(resource, &limit) == 0) {
        printf("%-20s ", name);
        
        if (limit.rlim_cur == RLIM_INFINITY)
            printf("soft: unlimited  ");
        else
            printf("soft: %-10lu  ", limit.rlim_cur);
        
        if (limit.rlim_max == RLIM_INFINITY)
            printf("hard: unlimited\n");
        else
            printf("hard: %-10lu\n", limit.rlim_max);
    }
}

int main() {
    printf("Current Resource Limits:\n");
    printf("============================================\n");
    
    print_limit(RLIMIT_CPU, "CPU time (sec)");
    print_limit(RLIMIT_FSIZE, "File size (bytes)");
    print_limit(RLIMIT_DATA, "Data segment");
    print_limit(RLIMIT_STACK, "Stack size");
    print_limit(RLIMIT_CORE, "Core file size");
    print_limit(RLIMIT_NOFILE, "Open files");
    print_limit(RLIMIT_AS, "Virtual memory");
    print_limit(RLIMIT_NPROC, "Max processes");
    
    return 0;
}
```

### Example: Modifying Limits
```c
#include <sys/resource.h>
#include <stdio.h>
#include <unistd.h>
#include <fcntl.h>

int main() {
    struct rlimit limit;
    int i, fd;
    
    // Get current file descriptor limit
    if (getrlimit(RLIMIT_NOFILE, &limit) == -1) {
        perror("getrlimit");
        return 1;
    }
    
    printf("Original limit - soft: %lu, hard: %lu\n",
           limit.rlim_cur, limit.rlim_max);
    
    // Try to open many files
    printf("Opening files until limit...\n");
    for (i = 0; i < 10000; i++) {
        fd = dup(STDIN_FILENO);  // Duplicate stdin
        if (fd == -1) {
            printf("Failed at %d open files\n", i + 3);  // +3 for stdin/out/err
            break;
        }
    }
    
    // Increase soft limit
    limit.rlim_cur = limit.rlim_max;  // Set to hard limit
    if (setrlimit(RLIMIT_NOFILE, &limit) == -1) {
        perror("setrlimit");
    } else {
        printf("Increased soft limit to %lu\n", limit.rlim_cur);
    }
    
    // To increase hard limit, need root:
    // limit.rlim_max = 4096;
    // setrlimit(RLIMIT_NOFILE, &limit);
    
    return 0;
}
```

## 2. getrusage() - Resource Usage

### Synopsis
```c
#include <sys/resource.h>

int getrusage(int who, struct rusage *usage);
```

### Who Values

```
RUSAGE_SELF      - Current process
RUSAGE_CHILDREN  - All terminated children (waited for)
RUSAGE_THREAD    - Current thread (Linux-specific)
```

### struct rusage

```c
struct rusage {
    struct timeval ru_utime;    // User CPU time
    struct timeval ru_stime;    // System CPU time
    long   ru_maxrss;          // Max resident set size (KB)
    long   ru_ixrss;           // Shared memory size
    long   ru_idrss;           // Unshared data size
    long   ru_isrss;           // Unshared stack size
    long   ru_minflt;          // Page faults (no I/O)
    long   ru_majflt;          // Page faults (I/O required)
    long   ru_nswap;           // Swaps
    long   ru_inblock;         // Block input operations
    long   ru_oublock;         // Block output operations
    long   ru_msgsnd;          // Messages sent
    long   ru_msgrcv;          // Messages received
    long   ru_nsignals;        // Signals received
    long   ru_nvcsw;           // Voluntary context switches
    long   ru_nivcsw;          // Involuntary context switches
};
```

### Resource Usage Timeline

```
Process Execution Timeline:

T=0    ┌───────────────────────────────────────────────────┐
       │ Start                                             │
T=1    │ CPU Time (user):        ████                      │
       │ Page faults:            ██                        │
T=2    │ CPU Time (system):      ██                        │
       │ Context switches:       █                         │
T=3    │ Block I/O operations:   ███                       │
       │ Memory (RSS):           ████████                  │
T=4    │ Signals received:       █                         │
T=5    │ More CPU time:          █████                     │
       │                                                   │
       └───────────────────────────────────────────────────┘
                                     │
                     getrusage() ────┘
                     Returns cumulative statistics
```

### Example: Measuring Resource Usage
```c
#include <sys/resource.h>
#include <sys/time.h>
#include <stdio.h>
#include <unistd.h>

void do_work() {
    // Simulate CPU-intensive work
    long sum = 0;
    for (long i = 0; i < 100000000; i++) {
        sum += i;
    }
    
    // Simulate memory allocation
    int *array = malloc(10000000 * sizeof(int));
    for (int i = 0; i < 10000000; i++) {
        array[i] = i;
    }
    free(array);
}

void print_rusage(struct rusage *usage) {
    printf("CPU time (user):      %ld.%06ld seconds\n",
           usage->ru_utime.tv_sec, usage->ru_utime.tv_usec);
    printf("CPU time (system):    %ld.%06ld seconds\n",
           usage->ru_stime.tv_sec, usage->ru_stime.tv_usec);
    printf("Max RSS:              %ld KB\n", usage->ru_maxrss);
    printf("Page faults (minor):  %ld\n", usage->ru_minflt);
    printf("Page faults (major):  %ld\n", usage->ru_majflt);
    printf("Block inputs:         %ld\n", usage->ru_inblock);
    printf("Block outputs:        %ld\n", usage->ru_oublock);
    printf("Voluntary switches:   %ld\n", usage->ru_nvcsw);
    printf("Involuntary switches: %ld\n", usage->ru_nivcsw);
}

int main() {
    struct rusage usage_start, usage_end;
    
    // Get initial usage
    getrusage(RUSAGE_SELF, &usage_start);
    
    printf("Starting work...\n");
    do_work();
    printf("Work completed.\n\n");
    
    // Get final usage
    getrusage(RUSAGE_SELF, &usage_end);
    
    printf("Resource Usage:\n");
    printf("================\n");
    print_rusage(&usage_end);
    
    return 0;
}
```

## 3. CPU Time and Process Times

### Synopsis
```c
#include <sys/times.h>
#include <time.h>

clock_t times(struct tms *buf);
clock_t clock(void);
```

### Time Measurement Types

```
┌─────────────────────────────────────────────────────────┐
│ Time Measurement                                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ Real Time (Wall Clock Time)                             │
│ ════════════════════════════════════                    │
│ ├────── Process Running ──────┤                         │
│ ├── Sleep ──┤                                           │
│              ├─ Running ─┤                              │
│                           ├── Sleep ──┤                 │
│                                        ├─ Running ─┤    │
│ Total: 10 seconds                                       │
│                                                         │
│ User Time (CPU in user mode)                            │
│ ████████░░░░░░░░░░░░░░░░░░░░                            │
│ 2 seconds                                               │
│                                                         │
│ System Time (CPU in kernel mode)                        │
│ ███░░░░░░░░░░░░░░░░░░░░░░░░░                            │
│ 0.5 seconds                                             │
│                                                         │
│ Total CPU Time = User + System = 2.5 seconds            │
│ Efficiency = CPU / Real = 25%                           │
└─────────────────────────────────────────────────────────┘
```

### struct tms

```c
struct tms {
    clock_t tms_utime;   // User CPU time of process
    clock_t tms_stime;   // System CPU time of process
    clock_t tms_cutime;  // User CPU time of children
    clock_t tms_cstime;  // System CPU time of children
};
```

### Example: Process Time Measurement
```c
#include <sys/times.h>
#include <unistd.h>
#include <stdio.h>
#include <time.h>

void cpu_intensive_work() {
    long sum = 0;
    for (long i = 0; i < 50000000; i++) {
        sum += i * i;
    }
}

void io_work() {
    FILE *fp = fopen("/dev/null", "w");
    for (int i = 0; i < 10000; i++) {
        fprintf(fp, "Line %d\n", i);
    }
    fclose(fp);
}

int main() {
    struct tms start, end;
    clock_t start_real, end_real;
    long ticks_per_sec = sysconf(_SC_CLK_TCK);
    
    start_real = times(&start);
    
    printf("Performing work...\n");
    cpu_intensive_work();
    io_work();
    sleep(1);  // Intentional sleep
    
    end_real = times(&end);
    
    double real_time = (double)(end_real - start_real) / ticks_per_sec;
    double user_time = (double)(end.tms_utime - start.tms_utime) / ticks_per_sec;
    double sys_time = (double)(end.tms_stime - start.tms_stime) / ticks_per_sec;
    
    printf("\nTime Statistics:\n");
    printf("================\n");
    printf("Real time:   %.2f seconds\n", real_time);
    printf("User time:   %.2f seconds\n", user_time);
    printf("System time: %.2f seconds\n", sys_time);
    printf("CPU time:    %.2f seconds\n", user_time + sys_time);
    printf("CPU usage:   %.1f%%\n", 
           100.0 * (user_time + sys_time) / real_time);
    
    return 0;
}
```

## 4. Priority and Scheduling

### Synopsis
```c
#include <sys/resource.h>
int getpriority(int which, id_t who);
int setpriority(int which, id_t who, int prio);

#include <sched.h>
int sched_getscheduler(pid_t pid);
int sched_setscheduler(pid_t pid, int policy,
                       const struct sched_param *param);
int sched_getparam(pid_t pid, struct sched_param *param);
int sched_setparam(pid_t pid, const struct sched_param *param);
```

### Scheduling Policies

```
┌──────────────────────────────────────────────────────────┐
│ Linux Scheduling Policies                                │
├──────────────────────────────────────────────────────────┤
│                                                          │
│ Real-Time Policies (higher priority):                    │
│ ┌─────────────────────────────────────────────────────┐  │
│ │ SCHED_FIFO     First-in, first-out                  │  │
│ │                Runs until blocks or yields          │  │
│ │                                                     │  │
│ │ SCHED_RR       Round-robin with time slices         │  │
│ │                Preempted after time quantum         │  │
│ └─────────────────────────────────────────────────────┘  │
│                                                          │
│ Normal Policies:                                         │
│ ┌─────────────────────────────────────────────────────┐  │
│ │ SCHED_OTHER    Default time-sharing (CFS)           │  │
│ │                Dynamic priority based on nice       │  │
│ │                                                     │  │
│ │ SCHED_BATCH    For batch processing                 │  │
│ │                Less preemption                      │  │
│ │                                                     │  │
│ │ SCHED_IDLE     Very low priority                    │  │
│ │                Only runs when idle                  │  │
│ └─────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘

Priority Ranges:
┌────────────────────────────────────────┐
│ Real-time: 1 (low) to 99 (high)        │
│ Normal:    Nice values -20 to +19      │
└────────────────────────────────────────┘
```

### CPU Scheduling Visualization

```
CPU Timeline with Different Priorities:

High Priority (nice: -20):
████████████████████████████████  (More CPU time)

Normal Priority (nice: 0):
████████████████░░░░░░░░░░░░░░░░  (Normal CPU time)

Low Priority (nice: +19):
████░░░░░░░░░░░░░░░░░░░░░░░░░░░░  (Less CPU time)

Time →
```

### Example: Scheduling
```c
#include <sched.h>
#include <sys/resource.h>
#include <stdio.h>
#include <unistd.h>
#include <errno.h>

const char *policy_name(int policy) {
    switch (policy) {
        case SCHED_OTHER: return "SCHED_OTHER";
        case SCHED_FIFO:  return "SCHED_FIFO";
        case SCHED_RR:    return "SCHED_RR";
        case SCHED_BATCH: return "SCHED_BATCH";
        case SCHED_IDLE:  return "SCHED_IDLE";
        default:          return "UNKNOWN";
    }
}

int main() {
    int policy;
    struct sched_param param;
    int nice_val;
    
    // Get current scheduling policy
    policy = sched_getscheduler(0);  // 0 = current process
    if (policy == -1) {
        perror("sched_getscheduler");
        return 1;
    }
    
    printf("Current scheduling policy: %s\n", policy_name(policy));
    
    // Get scheduling parameters
    if (sched_getparam(0, &param) == -1) {
        perror("sched_getparam");
        return 1;
    }
    printf("Priority: %d\n", param.sched_priority);
    
    // Get nice value
    errno = 0;
    nice_val = getpriority(PRIO_PROCESS, 0);
    if (errno != 0) {
        perror("getpriority");
    } else {
        printf("Nice value: %d\n", nice_val);
    }
    
    // Try to set real-time priority (requires root)
    printf("\nAttempting to set SCHED_RR (requires root)...\n");
    param.sched_priority = 10;
    if (sched_setscheduler(0, SCHED_RR, &param) == -1) {
        printf("Failed: %s\n", strerror(errno));
        printf("(This is expected without root privileges)\n");
    } else {
        printf("Success! Now using real-time scheduling\n");
    }
    
    // Anyone can decrease priority (increase nice value)
    printf("\nIncreasing nice value by 5...\n");
    if (nice(5) == -1) {
        perror("nice");
    } else {
        nice_val = getpriority(PRIO_PROCESS, 0);
        printf("New nice value: %d\n", nice_val);
    }
    
    return 0;
}
```

## 5. CPU Affinity

### Synopsis
```c
#define _GNU_SOURCE
#include <sched.h>

int sched_setaffinity(pid_t pid, size_t cpusetsize,
                      const cpu_set_t *mask);
int sched_getaffinity(pid_t pid, size_t cpusetsize,
                      cpu_set_t *mask);

// CPU set manipulation macros
void CPU_ZERO(cpu_set_t *set);
void CPU_SET(int cpu, cpu_set_t *set);
void CPU_CLR(int cpu, cpu_set_t *set);
int  CPU_ISSET(int cpu, cpu_set_t *set);
```

### CPU Affinity Concept

```
System with 4 CPUs:
┌──────┬──────┬──────┬──────┐
│ CPU0 │ CPU1 │ CPU2 │ CPU3 │
└──────┴──────┴──────┴──────┘

Default (no affinity):
Process can run on any CPU
┌──────┬──────┬──────┬──────┐
│  ✓   │  ✓   │  ✓   │  ✓   │
└──────┴──────┴──────┴──────┘

Affinity set to CPU 0 and 1:
Process restricted to specific CPUs
┌──────┬──────┬──────┬──────┐
│  ✓   │  ✓   │  ✗   │  ✗   │
└──────┴──────┴──────┴──────┘

Benefits:
  + Better cache locality
  + Predictable performance
  + NUMA awareness
```

### Example: CPU Affinity
```c
#define _GNU_SOURCE
#include <sched.h>
#include <stdio.h>
#include <unistd.h>

int main() {
    cpu_set_t mask;
    int num_cpus = sysconf(_SC_NPROCESSORS_ONLN);
    
    printf("System has %d CPUs\n", num_cpus);
    
    // Get current affinity
    CPU_ZERO(&mask);
    if (sched_getaffinity(0, sizeof(mask), &mask) == -1) {
        perror("sched_getaffinity");
        return 1;
    }
    
    printf("Current affinity: ");
    for (int i = 0; i < num_cpus; i++) {
        if (CPU_ISSET(i, &mask)) {
            printf("CPU%d ", i);
        }
    }
    printf("\n");
    
    // Set affinity to CPU 0 only
    CPU_ZERO(&mask);
    CPU_SET(0, &mask);
    
    if (sched_setaffinity(0, sizeof(mask), &mask) == -1) {
        perror("sched_setaffinity");
        return 1;
    }
    
    printf("Set affinity to CPU 0\n");
    
    // Verify
    CPU_ZERO(&mask);
    sched_getaffinity(0, sizeof(mask), &mask);
    
    printf("New affinity: ");
    for (int i = 0; i < num_cpus; i++) {
        if (CPU_ISSET(i, &mask)) {
            printf("CPU%d ", i);
        }
    }
    printf("\n");
    
    return 0;
}
```

## Complete Example Programs

See [examples/](../examples/) directory:
- `resource_monitor.c` - Complete resource monitoring tool
- `limit_tester.c` - Test various resource limits
- `cpu_benchmark.c` - CPU time measurement
- `priority_test.c` - Priority and scheduling demo

## Best Practices

```
1. Always check current limits before setting
   ✓ getrlimit() before setrlimit()
   
2. Handle limit-exceeded gracefully
   ✓ Check errno for EMFILE, ENOMEM, etc.
   
3. Be conservative with limits
   ✓ Don't set unnecessarily high limits
   
4. Monitor resource usage
   ✓ Use getrusage() for profiling
   
5. Understand privilege requirements
   ✓ Hard limits need root
   ✓ Real-time scheduling needs CAP_SYS_NICE
```

## Common Pitfalls

1. **Exceeding limits** - Not checking before allocation
2. **Hard limit confusion** - Can't increase without root
3. **Time measurement errors** - Confusing real vs CPU time
4. **Priority expectations** - Nice doesn't guarantee behavior
5. **Resource leaks** - File descriptors, memory

## Practice Exercises

1. Build a resource limit manager
2. Create a process profiler
3. Implement a CPU-bound vs I/O-bound detector
4. Build a priority-based task scheduler
5. Create a system resource monitor

## See Also
- `man 2 getrlimit`
- `man 2 getrusage`
- `man 2 times`
- `man 2 sched_setscheduler`
- `man 7 sched` (scheduling overview)

