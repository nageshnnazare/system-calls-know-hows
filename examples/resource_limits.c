/*
 * resource_limits.c - Demonstrates resource limit system calls
 * 
 * Compile: gcc -o resource_limits resource_limits.c
 * Usage: ./resource_limits
 */

#include <sys/resource.h>
#include <sys/time.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>

void print_limit(const char *name, int resource) {
    struct rlimit limit;
    
    if (getrlimit(resource, &limit) == -1) {
        perror("getrlimit");
        return;
    }
    
    printf("%-25s ", name);
    
    if (limit.rlim_cur == RLIM_INFINITY)
        printf("Soft: unlimited       ");
    else
        printf("Soft: %-15lu ", limit.rlim_cur);
    
    if (limit.rlim_max == RLIM_INFINITY)
        printf("Hard: unlimited\n");
    else
        printf("Hard: %-15lu\n", limit.rlim_max);
}

void demonstrate_limits() {
    printf("\n=== Current Resource Limits ===\n\n");
    
    print_limit("CPU time (seconds)", RLIMIT_CPU);
    print_limit("File size (bytes)", RLIMIT_FSIZE);
    print_limit("Data segment (bytes)", RLIMIT_DATA);
    print_limit("Stack size (bytes)", RLIMIT_STACK);
    print_limit("Core file (bytes)", RLIMIT_CORE);
    print_limit("Open files", RLIMIT_NOFILE);
    print_limit("Address space (bytes)", RLIMIT_AS);
    print_limit("Max processes", RLIMIT_NPROC);
    print_limit("Locked memory (bytes)", RLIMIT_MEMLOCK);
}

void demonstrate_modify_limits() {
    printf("\n=== Modifying File Descriptor Limit ===\n\n");
    
    struct rlimit limit;
    
    if (getrlimit(RLIMIT_NOFILE, &limit) == -1) {
        perror("getrlimit");
        return;
    }
    
    printf("Original limits:\n");
    printf("  Soft: %lu\n", limit.rlim_cur);
    printf("  Hard: %lu\n", limit.rlim_max);
    
    // Try to increase soft limit to hard limit
    rlim_t old_soft = limit.rlim_cur;
    limit.rlim_cur = limit.rlim_max;
    
    printf("\nAttempting to set soft limit to %lu...\n", limit.rlim_cur);
    
    if (setrlimit(RLIMIT_NOFILE, &limit) == -1) {
        perror("setrlimit");
        printf("Failed to increase limit\n");
    } else {
        printf("Successfully increased soft limit!\n");
    }
    
    // Verify
    if (getrlimit(RLIMIT_NOFILE, &limit) == -1) {
        perror("getrlimit");
        return;
    }
    
    printf("\nNew limits:\n");
    printf("  Soft: %lu\n", limit.rlim_cur);
    printf("  Hard: %lu\n", limit.rlim_max);
}

void demonstrate_rusage() {
    printf("\n=== Resource Usage (getrusage) ===\n\n");
    
    struct rusage usage;
    
    // Do some work
    printf("Performing CPU-intensive work...\n");
    long sum = 0;
    for (long i = 0; i < 50000000; i++) {
        sum += i;
    }
    
    // Get resource usage
    if (getrusage(RUSAGE_SELF, &usage) == -1) {
        perror("getrusage");
        return;
    }
    
    printf("\nResource usage:\n");
    printf("  User CPU time:        %ld.%06ld seconds\n",
           usage.ru_utime.tv_sec, usage.ru_utime.tv_usec);
    printf("  System CPU time:      %ld.%06ld seconds\n",
           usage.ru_stime.tv_sec, usage.ru_stime.tv_usec);
    printf("  Max RSS:              %ld KB\n", usage.ru_maxrss);
    printf("  Page faults (soft):   %ld\n", usage.ru_minflt);
    printf("  Page faults (hard):   %ld\n", usage.ru_majflt);
    printf("  Block inputs:         %ld\n", usage.ru_inblock);
    printf("  Block outputs:        %ld\n", usage.ru_oublock);
    printf("  Voluntary switches:   %ld\n", usage.ru_nvcsw);
    printf("  Involuntary switches: %ld\n", usage.ru_nivcsw);
}

void demonstrate_cpu_limit() {
    printf("\n=== CPU Time Limit Demo ===\n\n");
    
    struct rlimit limit;
    
    // Set CPU time limit to 2 seconds
    limit.rlim_cur = 2;  // 2 seconds
    limit.rlim_max = 2;
    
    printf("Setting CPU time limit to 2 seconds...\n");
    printf("Process will be killed with SIGXCPU if exceeded\n");
    printf("(This demo won't actually exceed it)\n\n");
    
    if (setrlimit(RLIMIT_CPU, &limit) == -1) {
        perror("setrlimit");
        return;
    }
    
    // Do a little work
    printf("Doing some work...\n");
    long sum = 0;
    for (long i = 0; i < 10000000; i++) {
        sum += i;
    }
    
    printf("Work completed without hitting CPU limit\n");
    
    // Reset CPU limit to unlimited
    limit.rlim_cur = RLIM_INFINITY;
    limit.rlim_max = RLIM_INFINITY;
    setrlimit(RLIMIT_CPU, &limit);
}

void demonstrate_priority() {
    printf("\n=== Process Priority (nice values) ===\n\n");
    
    int priority;
    
    errno = 0;
    priority = getpriority(PRIO_PROCESS, 0);
    if (errno != 0) {
        perror("getpriority");
        return;
    }
    
    printf("Current nice value: %d\n", priority);
    printf("  (Lower values = higher priority)\n");
    printf("  Range: -20 (highest) to +19 (lowest)\n\n");
    
    // Try to increase nice value (decrease priority)
    printf("Increasing nice value by 5 (lowering priority)...\n");
    errno = 0;
    int new_nice = nice(5);
    
    if (new_nice == -1 && errno != 0) {
        perror("nice");
        return;
    }
    
    priority = getpriority(PRIO_PROCESS, 0);
    printf("New nice value: %d\n", priority);
    
    // Note: decreasing nice value (increasing priority) requires privileges
    printf("\nNote: To decrease nice value (increase priority),\n");
    printf("      you need root privileges or CAP_SYS_NICE capability\n");
}

int main() {
    printf("=== Resource Management System Calls Demo ===\n");
    
    demonstrate_limits();
    demonstrate_modify_limits();
    demonstrate_rusage();
    demonstrate_cpu_limit();
    demonstrate_priority();
    
    printf("\n=== Demo Complete ===\n");
    
    return 0;
}

