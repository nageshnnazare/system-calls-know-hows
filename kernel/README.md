# Linux Kernel Internals and System Calls

## Overview

This guide covers Linux kernel internals, how system calls work, and kernel interfaces available to user-space programs.

## Kernel Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      USER SPACE                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Applications (bash, firefox, vim, etc.)               │  │
│  └─────────────────────┬──────────────────────────────────┘  │
│  ┌─────────────────────┴──────────────────────────────────┐  │
│  │  C Library (glibc, musl)                               │  │
│  │  - Wrapper functions for system calls                  │  │
│  │  - printf, malloc, pthread_create, etc.                │  │
│  └─────────────────────┬──────────────────────────────────┘  │
└────────────────────────┼─────────────────────────────────────┘
                         │ System Call Interface
                         │ (int 0x80 or syscall instruction)
┌────────────────────────┼─────────────────────────────────────┐
│                        ▼     KERNEL SPACE                    │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  System Call Handler                                 │    │
│  │  - syscall table (sys_call_table)                    │    │
│  │  - Parameter validation                              │    │
│  │  - Permission checks                                 │    │
│  └────────────────┬─────────────────────────────────────┘    │
│                   ▼                                          │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Kernel Subsystems                                   │    │
│  │  ┌────────────┬────────────┬──────────┬────────────┐ │    │
│  │  │ VFS        │ Process    │ Memory   │ Network    │ │    │
│  │  │ (files)    │ Management │Management│ Stack      │ │    │
│  │  └────────────┴────────────┴──────────┴────────────┘ │    │
│  └────────────────┬─────────────────────────────────────┘    │
│                   ▼                                          │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Device Drivers                                      │    │
│  │  - Character devices, Block devices, Network devices │    │
│  └────────────────┬─────────────────────────────────────┘    │
└───────────────────┼──────────────────────────────────────────┘
                    ▼
               Hardware (CPU, Memory, Disk, Network)
```

## System Call Mechanism

### How System Calls Work

```
User Space:                          Kernel Space:
┌──────────────────┐                 ┌───────────────────┐
│ Application      │                 │ Kernel            │
│                  │                 │                   │
│ int fd = open(); │                 │                   │
│      │           │                 │                   │
│      ▼           │                 │                   │
│ glibc wrapper    │                 │                   │
│ syscall(__NR_open)                 │                   │
│      │           │                 │                   │
│      ▼           │                 │                   │
│ Setup registers: │                 │                   │
│ - rax = syscall# │                 │                   │
│ - rdi = filename │                 │                   │
│ - rsi = flags    │                 │                   │
│ - rdx = mode     │                 │                   │
│      │           │                 │                   │
│      ▼           │                 │                   │
│ syscall instr.   ├────────────────►│ entry_SYSCALL_64  │
└──────────────────┘ Mode switch     │      │            │
  (user mode)       (privilege       │      ▼            │
                     escalation)     │ sys_call_table    │
                                     │   [rax]           │
                                     │      │            │
                                     │      ▼            │
                                     │ sys_open()        │
                                     │      │            │
                                     │      ▼            │
                                     │ do_sys_open()     │
                                     │      │            │
                                     │      ▼            │
                                     │ vfs_open()        │
                                     │      │            │
                                     │      ▼            │
                                     │ Return to user    │
                                     └───────────────────┘
```

### System Call Numbers

```c
// Defined in /usr/include/asm/unistd_64.h (x86_64)

#define __NR_read                0
#define __NR_write               1
#define __NR_open                2
#define __NR_close               3
#define __NR_stat                4
#define __NR_fstat               5
#define __NR_lstat               6
#define __NR_poll                7
#define __NR_lseek               8
#define __NR_mmap                9
#define __NR_mprotect           10
// ... hundreds more

// Making a raw system call (without libc)
#include <unistd.h>
#include <sys/syscall.h>

// Method 1: Using syscall() wrapper
long result = syscall(__NR_write, 1, "Hello\n", 6);

// Method 2: Inline assembly (x86_64)
long result;
asm volatile (
    "syscall"
    : "=a" (result)
    : "a" (__NR_write), "D" (1), "S" ("Hello\n"), "d" (6)
    : "rcx", "r11", "memory"
);
```

## /proc Filesystem

### Process Information

```
/proc - Virtual filesystem exposing kernel data

/proc/[pid]/          - Per-process information
├── cmdline           - Command line
├── cwd               - Current working directory (symlink)
├── environ           - Environment variables
├── exe               - Executable (symlink)
├── fd/               - Open file descriptors
│   ├── 0 → /dev/pts/0
│   ├── 1 → /dev/pts/0
│   └── 2 → /dev/pts/0
├── maps              - Memory mappings
├── stat              - Process status
├── status            - Human-readable status
├── limits            - Resource limits
├── io                - I/O statistics
├── mem               - Process memory
├── mountinfo         - Mount points
├── net/              - Network information
└── task/             - Threads

/proc/sys/            - Kernel parameters (sysctl)
├── kernel/
│   ├── hostname
│   ├── osrelease
│   └── pid_max
├── vm/
│   ├── swappiness
│   └── dirty_ratio
└── net/
    ├── ipv4/
    │   ├── ip_forward
    │   └── tcp_syncookies
    └── core/
        └── somaxconn
```

### Reading /proc

```c
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

// Read process status
void read_proc_status(pid_t pid) {
    char path[256];
    snprintf(path, sizeof(path), "/proc/%d/status", pid);
    
    FILE *fp = fopen(path, "r");
    if (fp == NULL) {
        perror("fopen");
        return;
    }
    
    char line[256];
    while (fgets(line, sizeof(line), fp)) {
        if (strncmp(line, "VmSize:", 7) == 0 ||
            strncmp(line, "VmRSS:", 6) == 0) {
            printf("%s", line);
        }
    }
    
    fclose(fp);
}

// Read memory mappings
void read_proc_maps(pid_t pid) {
    char path[256];
    snprintf(path, sizeof(path), "/proc/%d/maps", pid);
    
    FILE *fp = fopen(path, "r");
    if (fp == NULL) {
        perror("fopen");
        return;
    }
    
    char line[512];
    printf("Memory mappings:\n");
    while (fgets(line, sizeof(line), fp)) {
        printf("%s", line);
    }
    
    fclose(fp);
}

// List open file descriptors
void list_open_fds(pid_t pid) {
    char path[256];
    snprintf(path, sizeof(path), "/proc/%d/fd", pid);
    
    DIR *dir = opendir(path);
    if (dir == NULL) {
        perror("opendir");
        return;
    }
    
    struct dirent *entry;
    printf("Open file descriptors:\n");
    
    while ((entry = readdir(dir)) != NULL) {
        if (entry->d_name[0] == '.') continue;
        
        char fdpath[512], target[512];
        snprintf(fdpath, sizeof(fdpath), "%s/%s", path, entry->d_name);
        
        ssize_t len = readlink(fdpath, target, sizeof(target) - 1);
        if (len != -1) {
            target[len] = '\0';
            printf("  fd %s -> %s\n", entry->d_name, target);
        }
    }
    
    closedir(dir);
}

int main() {
    pid_t pid = getpid();
    
    printf("Process info for PID %d:\n\n", pid);
    
    read_proc_status(pid);
    printf("\n");
    
    list_open_fds(pid);
    printf("\n");
    
    // Read command line
    char cmdline_path[256];
    snprintf(cmdline_path, sizeof(cmdline_path), "/proc/%d/cmdline", pid);
    
    FILE *fp = fopen(cmdline_path, "r");
    if (fp) {
        char cmdline[1024];
        size_t n = fread(cmdline, 1, sizeof(cmdline) - 1, fp);
        
        // Replace null bytes with spaces
        for (size_t i = 0; i < n; i++) {
            if (cmdline[i] == '\0') cmdline[i] = ' ';
        }
        cmdline[n] = '\0';
        
        printf("Command line: %s\n", cmdline);
        fclose(fp);
    }
    
    return 0;
}
```

## /sys Filesystem

### Device and Kernel Information

```
/sys - Exposes kernel objects, devices, and drivers

/sys/block/           - Block devices
├── sda/
│   ├── size
│   ├── queue/
│   └── stat

/sys/class/           - Device classes
├── net/              - Network interfaces
│   ├── eth0/
│   │   ├── address   - MAC address
│   │   ├── mtu
│   │   └── statistics/
│   │       ├── rx_bytes
│   │       └── tx_bytes
│   └── lo/
└── input/            - Input devices

/sys/devices/         - Physical devices
├── system/
│   ├── cpu/
│   │   ├── cpu0/
│   │   │   ├── online
│   │   │   └── cpufreq/
│   │   │       ├── scaling_governor
│   │   │       └── scaling_cur_freq
│   └── memory/

/sys/kernel/          - Kernel parameters
├── debug/            - Debug interface
└── security/         - Security modules (SELinux, AppArmor)

/sys/module/          - Loaded kernel modules
```

### Reading /sys

```c
#include <stdio.h>
#include <stdlib.h>

// Read network statistics
void read_net_stats(const char *interface) {
    char path[256];
    FILE *fp;
    long long value;
    
    printf("Network stats for %s:\n", interface);
    
    // RX bytes
    snprintf(path, sizeof(path), 
             "/sys/class/net/%s/statistics/rx_bytes", interface);
    fp = fopen(path, "r");
    if (fp) {
        fscanf(fp, "%lld", &value);
        printf("  RX bytes: %lld\n", value);
        fclose(fp);
    }
    
    // TX bytes
    snprintf(path, sizeof(path), 
             "/sys/class/net/%s/statistics/tx_bytes", interface);
    fp = fopen(path, "r");
    if (fp) {
        fscanf(fp, "%lld", &value);
        printf("  TX bytes: %lld\n", value);
        fclose(fp);
    }
}

// Read CPU information
void read_cpu_info() {
    FILE *fp;
    char line[256];
    
    fp = fopen("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq", "r");
    if (fp) {
        fgets(line, sizeof(line), fp);
        printf("CPU frequency: %s kHz\n", line);
        fclose(fp);
    }
    
    fp = fopen("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor", "r");
    if (fp) {
        fgets(line, sizeof(line), fp);
        printf("CPU governor: %s", line);
        fclose(fp);
    }
}
```

## Kernel Parameters (sysctl)

### Reading and Writing Kernel Parameters

```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Read sysctl value
int sysctl_read(const char *param, char *value, size_t size) {
    char path[256];
    snprintf(path, sizeof(path), "/proc/sys/%s", param);
    
    // Replace '.' with '/'
    for (char *p = path + strlen("/proc/sys/"); *p; p++) {
        if (*p == '.') *p = '/';
    }
    
    FILE *fp = fopen(path, "r");
    if (fp == NULL) {
        return -1;
    }
    
    fgets(value, size, fp);
    
    // Remove trailing newline
    size_t len = strlen(value);
    if (len > 0 && value[len - 1] == '\n') {
        value[len - 1] = '\0';
    }
    
    fclose(fp);
    return 0;
}

// Write sysctl value (requires root)
int sysctl_write(const char *param, const char *value) {
    char path[256];
    snprintf(path, sizeof(path), "/proc/sys/%s", param);
    
    // Replace '.' with '/'
    for (char *p = path + strlen("/proc/sys/"); *p; p++) {
        if (*p == '.') *p = '/';
    }
    
    FILE *fp = fopen(path, "w");
    if (fp == NULL) {
        return -1;
    }
    
    fprintf(fp, "%s", value);
    fclose(fp);
    
    return 0;
}

int main() {
    char value[256];
    
    // Read kernel parameters
    if (sysctl_read("kernel.hostname", value, sizeof(value)) == 0) {
        printf("Hostname: %s\n", value);
    }
    
    if (sysctl_read("vm.swappiness", value, sizeof(value)) == 0) {
        printf("Swappiness: %s\n", value);
    }
    
    if (sysctl_read("net.ipv4.ip_forward", value, sizeof(value)) == 0) {
        printf("IP forwarding: %s\n", value);
    }
    
    // Write (requires root)
    // sysctl_write("vm.swappiness", "60");
    
    return 0;
}
```

### Using sysctl() System Call

```c
#include <sys/sysctl.h>
#include <stdio.h>

int main() {
    // Get hostname
    char hostname[256];
    size_t len = sizeof(hostname);
    
    int mib[2] = {CTL_KERN, KERN_HOSTNAME};
    
    if (sysctl(mib, 2, hostname, &len, NULL, 0) == 0) {
        printf("Hostname: %s\n", hostname);
    }
    
    // Get OS release
    char osrelease[256];
    len = sizeof(osrelease);
    
    mib[0] = CTL_KERN;
    mib[1] = KERN_OSRELEASE;
    
    if (sysctl(mib, 2, osrelease, &len, NULL, 0) == 0) {
        printf("OS Release: %s\n", osrelease);
    }
    
    return 0;
}
```

## Kernel Modules

### Loading and Unloading Modules

```c
#include <sys/syscall.h>
#include <unistd.h>
#include <fcntl.h>

// Load kernel module (requires root)
int load_module(const char *filename, const char *params) {
    int fd = open(filename, O_RDONLY);
    if (fd == -1) {
        return -1;
    }
    
    int ret = syscall(__NR_finit_module, fd, params, 0);
    close(fd);
    
    return ret;
}

// Unload kernel module (requires root)
int unload_module(const char *name, int flags) {
    return syscall(__NR_delete_module, name, flags);
}

// List loaded modules
void list_modules() {
    FILE *fp = fopen("/proc/modules", "r");
    if (fp == NULL) {
        perror("fopen");
        return;
    }
    
    char line[512];
    printf("Loaded kernel modules:\n");
    
    while (fgets(line, sizeof(line), fp)) {
        // Format: name size refcount deps status offset
        char name[64];
        int size, refcount;
        
        sscanf(line, "%s %d %d", name, &size, &refcount);
        printf("  %-20s Size: %d  Refcount: %d\n", 
               name, size, refcount);
    }
    
    fclose(fp);
}
```

## eBPF (Extended Berkeley Packet Filter)

### Introduction to eBPF

```
eBPF allows running sandboxed programs in kernel space without
changing kernel source code or loading kernel modules.

Use cases:
- Performance monitoring
- Security policies
- Network packet filtering
- Tracing and debugging

┌────────────────────────────────────────────────────┐
│ User Space                                         │
│ ┌────────────────────────────────────────────────┐ │
│ │ BPF Program (C code)                           │ │
│ └─────────────────┬──────────────────────────────┘ │
│                   │                                │
│                   ▼                                │
│ ┌────────────────────────────────────────────────┐ │
│ │ LLVM/Clang → BPF bytecode                      │ │
│ └─────────────────┬──────────────────────────────┘ │
│                   │ bpf() syscall                  │
└───────────────────┼────────────────────────────────┘
                    │
┌───────────────────┼────────────────────────────────┐
│ Kernel Space      ▼                                │
│ ┌────────────────────────────────────────────────┐ │
│ │ BPF Verifier                                   │ │
│ │ - Checks for safety                            │ │
│ │ - Ensures termination                          │ │
│ └─────────────────┬──────────────────────────────┘ │
│                   ▼                                │
│ ┌────────────────────────────────────────────────┐ │
│ │ JIT Compiler → Native code                     │ │
│ └─────────────────┬──────────────────────────────┘ │
│                   ▼                                │
│ ┌────────────────────────────────────────────────┐ │
│ │ Attach to hook point                           │ │
│ │ - Tracepoints, kprobes, network, etc.          │ │
│ └────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────┘
```

## Performance Monitoring

### perf_event_open() - Hardware Performance Counters

```c
#include <linux/perf_event.h>
#include <sys/syscall.h>
#include <unistd.h>
#include <string.h>

long perf_event_open(struct perf_event_attr *attr,
                     pid_t pid, int cpu, int group_fd,
                     unsigned long flags) {
    return syscall(__NR_perf_event_open, attr, pid, cpu, group_fd, flags);
}

int main() {
    struct perf_event_attr attr;
    memset(&attr, 0, sizeof(attr));
    
    attr.type = PERF_TYPE_HARDWARE;
    attr.size = sizeof(attr);
    attr.config = PERF_COUNT_HW_CPU_CYCLES;
    attr.disabled = 1;
    attr.exclude_kernel = 1;
    attr.exclude_hv = 1;
    
    // Monitor current process
    int fd = perf_event_open(&attr, 0, -1, -1, 0);
    if (fd == -1) {
        perror("perf_event_open");
        return 1;
    }
    
    // Start counting
    ioctl(fd, PERF_EVENT_IOC_RESET, 0);
    ioctl(fd, PERF_EVENT_IOC_ENABLE, 0);
    
    // Do some work
    long sum = 0;
    for (long i = 0; i < 10000000; i++) {
        sum += i;
    }
    
    // Stop counting
    ioctl(fd, PERF_EVENT_IOC_DISABLE, 0);
    
    // Read result
    long long count;
    read(fd, &count, sizeof(count));
    
    printf("CPU cycles: %lld\n", count);
    
    close(fd);
    return 0;
}
```

## Kernel Tracing

### ftrace - Function Tracing

```bash
# Enable function tracer
echo function > /sys/kernel/debug/tracing/current_tracer

# Set filter
echo 'sys_open' > /sys/kernel/debug/tracing/set_ftrace_filter

# Enable tracing
echo 1 > /sys/kernel/debug/tracing/tracing_on

# View trace
cat /sys/kernel/debug/tracing/trace

# Disable tracing
echo 0 > /sys/kernel/debug/tracing/tracing_on
```

### strace - Trace System Calls

```bash
# Trace all system calls
strace ls

# Trace specific syscalls
strace -e open,read,write cat file.txt

# Attach to running process
strace -p <pid>

# Count syscalls
strace -c ./program

# Trace with timestamps
strace -t ./program
```

## Memory Management Internals

### Page Faults

```
Page Fault Handling:

1. Process accesses memory at address X
2. MMU checks page table
3. Page not present → Page fault exception
4. CPU switches to kernel mode
5. Kernel page fault handler (do_page_fault):
   - Valid address in valid VMA?
     Yes: Allocate page, update page table
     No: Send SIGSEGV to process
6. Return to user mode
7. Retry instruction
```

### Viewing Page Faults

```c
#include <sys/resource.h>

int main() {
    struct rusage usage;
    
    getrusage(RUSAGE_SELF, &usage);
    
    printf("Page faults (minor): %ld\n", usage.ru_minflt);
    printf("Page faults (major): %ld\n", usage.ru_majflt);
    
    // Allocate and touch memory to cause page faults
    size_t size = 100 * 1024 * 1024;  // 100 MB
    char *mem = malloc(size);
    
    for (size_t i = 0; i < size; i += 4096) {
        mem[i] = 0;  // Touch each page
    }
    
    getrusage(RUSAGE_SELF, &usage);
    
    printf("After allocation:\n");
    printf("Page faults (minor): %ld\n", usage.ru_minflt);
    printf("Page faults (major): %ld\n", usage.ru_majflt);
    
    free(mem);
    return 0;
}
```

## Kernel Configuration

### Checking Kernel Configuration

```bash
# View current kernel config
cat /boot/config-$(uname -r)

# Check if feature is enabled
grep CONFIG_SOME_FEATURE /boot/config-$(uname -r)

# Common configs:
CONFIG_SMP=y              # Symmetric Multi-Processing
CONFIG_PREEMPT=y          # Preemptible kernel
CONFIG_HIGH_RES_TIMERS=y  # High resolution timers
CONFIG_CGROUPS=y          # Control groups
CONFIG_NAMESPACES=y       # Namespaces (containers)
```

## Best Practices

```
1. ✓ Always check permissions before accessing kernel interfaces
2. ✓ Handle errors gracefully
3. ✓ Close file descriptors to /proc and /sys
4. ✓ Be careful with sysctl writes (requires root, can break system)
5. ✓ Use appropriate tools (strace, perf, ftrace)
6. ✓ Understand security implications
7. ✓ Test kernel parameter changes before making permanent
8. ✓ Monitor system behavior after changes
```

## See Also

- `man 2 syscall`
- `man 2 syscalls`
- `man 5 proc`
- `man 5 sysfs`
- `man 8 sysctl`
- Linux kernel source: https://kernel.org/
- Linux man-pages: https://man7.org/linux/man-pages/

