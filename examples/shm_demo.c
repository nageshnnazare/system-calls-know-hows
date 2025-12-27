/*
 * shm_demo.c - Demonstrates shared memory system calls
 * 
 * Compile: gcc -o shm_demo shm_demo.c
 * Usage: ./shm_demo
 */

#include <sys/shm.h>
#include <sys/ipc.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define SHM_SIZE 1024
#define SHM_KEY 0x1234

struct shared_data {
    int counter;
    char message[100];
    pid_t writer_pid;
};

void demonstrate_basic_shm() {
    printf("\n=== Basic Shared Memory Demo ===\n");
    
    int shmid;
    struct shared_data *shared;
    pid_t pid;
    
    // Create shared memory segment
    shmid = shmget(SHM_KEY, sizeof(struct shared_data), IPC_CREAT | 0666);
    if (shmid == -1) {
        perror("shmget");
        return;
    }
    
    printf("Created shared memory segment, ID: %d\n", shmid);
    
    // Attach shared memory
    shared = (struct shared_data *)shmat(shmid, NULL, 0);
    if (shared == (void *)-1) {
        perror("shmat");
        shmctl(shmid, IPC_RMID, NULL);
        return;
    }
    
    printf("Attached shared memory at address: %p\n", (void *)shared);
    
    // Initialize shared data
    shared->counter = 0;
    strcpy(shared->message, "Initial message");
    shared->writer_pid = 0;
    
    pid = fork();
    
    if (pid == -1) {
        perror("fork");
        shmdt(shared);
        shmctl(shmid, IPC_RMID, NULL);
        return;
    }
    
    if (pid == 0) {
        // Child process
        printf("\n[Child] PID: %d\n", getpid());
        printf("[Child] Reading initial data:\n");
        printf("        Counter: %d\n", shared->counter);
        printf("        Message: %s\n", shared->message);
        
        // Modify shared data
        shared->counter = 42;
        strcpy(shared->message, "Modified by child!");
        shared->writer_pid = getpid();
        
        printf("[Child] Updated shared memory\n");
        
        // Detach
        shmdt(shared);
        exit(0);
    }
    else {
        // Parent process
        sleep(1);  // Wait for child to modify
        
        printf("\n[Parent] Reading data after child modified:\n");
        printf("         Counter: %d\n", shared->counter);
        printf("         Message: %s\n", shared->message);
        printf("         Writer PID: %d\n", shared->writer_pid);
        
        wait(NULL);  // Wait for child to finish
        
        // Detach
        shmdt(shared);
        
        // Remove shared memory segment
        if (shmctl(shmid, IPC_RMID, NULL) == -1) {
            perror("shmctl IPC_RMID");
        } else {
            printf("\n[Parent] Removed shared memory segment\n");
        }
    }
}

void demonstrate_shm_info() {
    printf("\n=== Shared Memory Information ===\n");
    
    int shmid;
    struct shmid_ds shm_info;
    
    // Create shared memory
    shmid = shmget(IPC_PRIVATE, SHM_SIZE, IPC_CREAT | 0666);
    if (shmid == -1) {
        perror("shmget");
        return;
    }
    
    // Get information
    if (shmctl(shmid, IPC_STAT, &shm_info) == -1) {
        perror("shmctl IPC_STAT");
        shmctl(shmid, IPC_RMID, NULL);
        return;
    }
    
    printf("Segment ID: %d\n", shmid);
    printf("Size: %lu bytes\n", shm_info.shm_segsz);
    printf("Attached processes: %lu\n", (unsigned long)shm_info.shm_nattch);
    printf("Creator PID: %d\n", shm_info.shm_cpid);
    printf("Last shmat PID: %d\n", shm_info.shm_lpid);
    printf("Permissions: %o\n", shm_info.shm_perm.mode);
    
    // Cleanup
    shmctl(shmid, IPC_RMID, NULL);
}

void demonstrate_multiple_attachments() {
    printf("\n=== Multiple Process Attachments ===\n");
    
    int shmid;
    int *shared;
    pid_t pid1, pid2;
    
    // Create shared memory for counter
    shmid = shmget(IPC_PRIVATE, sizeof(int), IPC_CREAT | 0666);
    if (shmid == -1) {
        perror("shmget");
        return;
    }
    
    shared = (int *)shmat(shmid, NULL, 0);
    if (shared == (void *)-1) {
        perror("shmat");
        shmctl(shmid, IPC_RMID, NULL);
        return;
    }
    
    *shared = 0;
    
    printf("Initial counter value: %d\n", *shared);
    
    // Create first child
    pid1 = fork();
    if (pid1 == 0) {
        printf("[Child 1] Incrementing counter 3 times\n");
        for (int i = 0; i < 3; i++) {
            (*shared)++;
            printf("[Child 1] Counter = %d\n", *shared);
            usleep(100000);  // 0.1 second
        }
        shmdt(shared);
        exit(0);
    }
    
    // Create second child
    pid2 = fork();
    if (pid2 == 0) {
        printf("[Child 2] Incrementing counter 3 times\n");
        for (int i = 0; i < 3; i++) {
            (*shared)++;
            printf("[Child 2] Counter = %d\n", *shared);
            usleep(100000);
        }
        shmdt(shared);
        exit(0);
    }
    
    // Parent waits
    waitpid(pid1, NULL, 0);
    waitpid(pid2, NULL, 0);
    
    printf("\n[Parent] Final counter value: %d\n", *shared);
    printf("[Parent] Note: Without synchronization, results may vary!\n");
    
    // Cleanup
    shmdt(shared);
    shmctl(shmid, IPC_RMID, NULL);
}

int main() {
    printf("=== Shared Memory System Calls Demo ===\n");
    
    demonstrate_basic_shm();
    demonstrate_shm_info();
    demonstrate_multiple_attachments();
    
    printf("\n=== Demo Complete ===\n");
    printf("Note: For production use, shared memory should be\n");
    printf("      protected with semaphores or other synchronization!\n");
    
    return 0;
}

