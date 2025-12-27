/*
 * process_manager.c - Demonstrates process management system calls
 * 
 * Compile: gcc -o process_manager process_manager.c
 * Usage: ./process_manager
 */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <sys/resource.h>
#include <errno.h>
#include <string.h>

void print_process_info() {
    printf("PID: %d, PPID: %d, PGID: %d, SID: %d\n",
           getpid(), getppid(), getpgid(0), getsid(0));
}

void child_task(int child_num, int sleep_time) {
    printf("[Child %d] Started - ", child_num);
    print_process_info();
    
    printf("[Child %d] Working for %d seconds...\n", child_num, sleep_time);
    sleep(sleep_time);
    
    printf("[Child %d] Exiting with status %d\n", child_num, child_num);
    exit(child_num);
}

int main() {
    pid_t pids[3];
    int status;
    struct rusage usage;
    
    printf("=== Process Manager Demo ===\n\n");
    printf("[Parent] Started - ");
    print_process_info();
    
    // Create 3 child processes
    for (int i = 0; i < 3; i++) {
        pids[i] = fork();
        
        if (pids[i] < 0) {
            perror("fork");
            exit(1);
        }
        else if (pids[i] == 0) {
            // Child process
            child_task(i + 1, i + 2);  // Sleep 2, 3, 4 seconds
            // Never reaches here
        }
        else {
            // Parent process
            printf("[Parent] Created child %d with PID %d\n", i + 1, pids[i]);
        }
    }
    
    // Parent waits for all children
    printf("\n[Parent] Waiting for children to complete...\n\n");
    
    for (int i = 0; i < 3; i++) {
        pid_t child_pid = wait(&status);
        
        if (child_pid == -1) {
            perror("wait");
            continue;
        }
        
        printf("[Parent] Child PID %d terminated\n", child_pid);
        
        if (WIFEXITED(status)) {
            printf("         Exit status: %d\n", WEXITSTATUS(status));
        }
        else if (WIFSIGNALED(status)) {
            printf("         Killed by signal: %d\n", WTERMSIG(status));
        }
    }
    
    // Get resource usage
    if (getrusage(RUSAGE_CHILDREN, &usage) == 0) {
        printf("\n[Parent] Children resource usage:\n");
        printf("         User CPU time: %ld.%06ld sec\n",
               usage.ru_utime.tv_sec, usage.ru_utime.tv_usec);
        printf("         System CPU time: %ld.%06ld sec\n",
               usage.ru_stime.tv_sec, usage.ru_stime.tv_usec);
    }
    
    printf("\n[Parent] All children completed. Exiting.\n");
    return 0;
}

