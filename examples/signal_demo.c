/*
 * signal_demo.c - Demonstrates signal handling system calls
 * 
 * Compile: gcc -o signal_demo signal_demo.c
 * Usage: ./signal_demo
 */

#include <signal.h>
#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>

volatile sig_atomic_t sigint_count = 0;
volatile sig_atomic_t sigusr1_received = 0;

void sigint_handler(int signum) {
    sigint_count++;
    write(STDOUT_FILENO, "\n[Handler] Caught SIGINT (Ctrl+C)\n", 34);
    
    if (sigint_count >= 3) {
        write(STDOUT_FILENO, "[Handler] 3 SIGINTs received. Exiting.\n", 40);
        exit(0);
    }
}

void sigusr1_handler(int signum) {
    sigusr1_received = 1;
    write(STDOUT_FILENO, "[Handler] Caught SIGUSR1\n", 25);
}

void sigchld_handler(int signum) {
    write(STDOUT_FILENO, "[Handler] Child process terminated (SIGCHLD)\n", 45);
    while (waitpid(-1, NULL, WNOHANG) > 0);  // Reap zombie children
}

void demonstrate_basic_signal() {
    printf("\n=== Basic Signal Handling ===\n");
    
    struct sigaction sa;
    
    // Set up SIGINT handler
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = sigint_handler;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = 0;
    
    if (sigaction(SIGINT, &sa, NULL) == -1) {
        perror("sigaction");
        return;
    }
    
    printf("Press Ctrl+C to send SIGINT (3 times to exit)\n");
    printf("Process PID: %d\n", getpid());
    
    for (int i = 0; i < 10 && sigint_count < 3; i++) {
        printf("Waiting... (%d/10)\n", i + 1);
        sleep(1);
    }
    
    if (sigint_count < 3) {
        printf("No interrupts received. Continuing...\n");
    }
}

void demonstrate_signal_between_processes() {
    printf("\n=== Signals Between Processes ===\n");
    
    struct sigaction sa;
    pid_t pid;
    
    // Set up SIGUSR1 handler
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = sigusr1_handler;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = 0;
    
    if (sigaction(SIGUSR1, &sa, NULL) == -1) {
        perror("sigaction");
        return;
    }
    
    pid = fork();
    
    if (pid == -1) {
        perror("fork");
        return;
    }
    
    if (pid == 0) {
        // Child process
        printf("[Child] PID: %d, Parent PID: %d\n", getpid(), getppid());
        printf("[Child] Sending SIGUSR1 to parent...\n");
        sleep(1);
        
        kill(getppid(), SIGUSR1);
        
        printf("[Child] Exiting\n");
        exit(0);
    }
    else {
        // Parent process
        printf("[Parent] PID: %d, waiting for signal...\n", getpid());
        
        while (!sigusr1_received) {
            sleep(1);
        }
        
        printf("[Parent] Received SIGUSR1 from child\n");
        wait(NULL);
    }
}

void demonstrate_signal_masking() {
    printf("\n=== Signal Masking ===\n");
    
    sigset_t new_mask, old_mask, pending_mask;
    
    // Create a mask with SIGINT
    sigemptyset(&new_mask);
    sigaddset(&new_mask, SIGINT);
    
    printf("Blocking SIGINT for 5 seconds...\n");
    printf("Try pressing Ctrl+C (it will be queued)\n");
    
    // Block SIGINT
    if (sigprocmask(SIG_BLOCK, &new_mask, &old_mask) == -1) {
        perror("sigprocmask");
        return;
    }
    
    for (int i = 5; i > 0; i--) {
        printf("%d... ", i);
        fflush(stdout);
        sleep(1);
    }
    printf("\n");
    
    // Check for pending signals
    if (sigpending(&pending_mask) == -1) {
        perror("sigpending");
        return;
    }
    
    if (sigismember(&pending_mask, SIGINT)) {
        printf("SIGINT is pending (you pressed Ctrl+C while blocked)\n");
    } else {
        printf("No SIGINT pending\n");
    }
    
    printf("Unblocking SIGINT now...\n");
    
    // Unblock SIGINT
    if (sigprocmask(SIG_SETMASK, &old_mask, NULL) == -1) {
        perror("sigprocmask");
        return;
    }
    
    printf("SIGINT unblocked (signal delivered if it was pending)\n");
    sleep(1);
}

void demonstrate_sigchld() {
    printf("\n=== SIGCHLD Handler ===\n");
    
    struct sigaction sa;
    pid_t pid;
    
    // Set up SIGCHLD handler
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = sigchld_handler;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = SA_RESTART;  // Restart interrupted system calls
    
    if (sigaction(SIGCHLD, &sa, NULL) == -1) {
        perror("sigaction");
        return;
    }
    
    printf("Creating child process...\n");
    
    pid = fork();
    
    if (pid == 0) {
        // Child
        printf("[Child] PID: %d, sleeping for 2 seconds...\n", getpid());
        sleep(2);
        printf("[Child] Exiting\n");
        exit(42);
    }
    else {
        // Parent
        printf("[Parent] Child PID: %d created\n", pid);
        printf("[Parent] Doing other work...\n");
        
        for (int i = 0; i < 4; i++) {
            printf("[Parent] Working... %d\n", i);
            sleep(1);
        }
        
        printf("[Parent] Done\n");
    }
}

void sigalrm_handler(int signum) {
    write(STDOUT_FILENO, "\n[Handler] Alarm went off! (SIGALRM)\n", 37);
}

void demonstrate_alarm() {
    printf("\n=== Alarm Signal ===\n");
    
    struct sigaction sa;
    
    // Handler for SIGALRM
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = sigalrm_handler;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = 0;
    
    if (sigaction(SIGALRM, &sa, NULL) == -1) {
        perror("sigaction");
        return;
    }
    
    printf("Setting alarm for 3 seconds...\n");
    alarm(3);
    
    printf("Waiting for alarm...\n");
    for (int i = 0; i < 5; i++) {
        sleep(1);
        printf("Tick %d\n", i + 1);
    }
}

int main() {
    printf("=== Signal System Calls Demo ===\n");
    printf("Note: Some demos are interactive\n");
    
    demonstrate_basic_signal();
    
    // Reset SIGINT count for other demos
    sigint_count = 0;
    
    demonstrate_signal_between_processes();
    demonstrate_signal_masking();
    demonstrate_sigchld();
    demonstrate_alarm();
    
    printf("\n=== Demo Complete ===\n");
    
    return 0;
}

