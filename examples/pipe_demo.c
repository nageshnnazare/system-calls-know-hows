/*
 * pipe_demo.c - Demonstrates pipe system calls
 * 
 * Compile: gcc -o pipe_demo pipe_demo.c
 * Usage: ./pipe_demo
 */

#include <unistd.h>
#include <stdio.h>
#include <string.h>
#include <sys/wait.h>
#include <stdlib.h>

void simple_pipe_demo() {
    printf("\n=== Simple Pipe Demo ===\n");
    
    int pipefd[2];
    pid_t pid;
    char write_msg[] = "Hello through pipe!";
    char read_msg[100];
    
    if (pipe(pipefd) == -1) {
        perror("pipe");
        return;
    }
    
    printf("Pipe created: read_fd=%d, write_fd=%d\n", pipefd[0], pipefd[1]);
    
    pid = fork();
    
    if (pid == -1) {
        perror("fork");
        return;
    }
    
    if (pid == 0) {
        // Child - reader
        close(pipefd[1]);  // Close write end
        
        printf("[Child] Waiting to read from pipe...\n");
        ssize_t n = read(pipefd[0], read_msg, sizeof(read_msg) - 1);
        
        if (n > 0) {
            read_msg[n] = '\0';
            printf("[Child] Received: '%s' (%zd bytes)\n", read_msg, n);
        }
        
        close(pipefd[0]);
        exit(0);
    }
    else {
        // Parent - writer
        close(pipefd[0]);  // Close read end
        
        printf("[Parent] Sending: '%s'\n", write_msg);
        sleep(1);  // Delay to show child is waiting
        
        write(pipefd[1], write_msg, strlen(write_msg));
        
        close(pipefd[1]);
        wait(NULL);
        printf("[Parent] Child has finished\n");
    }
}

void bidirectional_pipe_demo() {
    printf("\n=== Bidirectional Communication (2 Pipes) ===\n");
    
    int pipe1[2];  // Parent to child
    int pipe2[2];  // Child to parent
    pid_t pid;
    char msg[100];
    
    if (pipe(pipe1) == -1 || pipe(pipe2) == -1) {
        perror("pipe");
        return;
    }
    
    pid = fork();
    
    if (pid == 0) {
        // Child
        close(pipe1[1]);  // Close unused write end of pipe1
        close(pipe2[0]);  // Close unused read end of pipe2
        
        // Read from parent
        read(pipe1[0], msg, sizeof(msg));
        printf("[Child] Received from parent: %s\n", msg);
        close(pipe1[0]);
        
        // Send to parent
        char reply[] = "Hi Parent!";
        write(pipe2[1], reply, strlen(reply) + 1);
        close(pipe2[1]);
        
        exit(0);
    }
    else {
        // Parent
        close(pipe1[0]);  // Close unused read end of pipe1
        close(pipe2[1]);  // Close unused write end of pipe2
        
        // Send to child
        char greeting[] = "Hello Child!";
        write(pipe1[1], greeting, strlen(greeting) + 1);
        close(pipe1[1]);
        
        // Read from child
        read(pipe2[0], msg, sizeof(msg));
        printf("[Parent] Received from child: %s\n", msg);
        close(pipe2[0]);
        
        wait(NULL);
    }
}

void pipe_exec_demo() {
    printf("\n=== Pipe with exec() - Implementing: ls | wc -l ===\n");
    
    int pipefd[2];
    pid_t pid1, pid2;
    
    if (pipe(pipefd) == -1) {
        perror("pipe");
        return;
    }
    
    // First child: ls -l
    pid1 = fork();
    if (pid1 == 0) {
        close(pipefd[0]);  // Close read end
        dup2(pipefd[1], STDOUT_FILENO);  // Redirect stdout to pipe
        close(pipefd[1]);
        
        execlp("ls", "ls", "-l", NULL);
        perror("execlp ls");
        exit(1);
    }
    
    // Second child: wc -l
    pid2 = fork();
    if (pid2 == 0) {
        close(pipefd[1]);  // Close write end
        dup2(pipefd[0], STDIN_FILENO);  // Redirect stdin from pipe
        close(pipefd[0]);
        
        execlp("wc", "wc", "-l", NULL);
        perror("execlp wc");
        exit(1);
    }
    
    // Parent
    close(pipefd[0]);
    close(pipefd[1]);
    
    waitpid(pid1, NULL, 0);
    waitpid(pid2, NULL, 0);
}

void pipe_capacity_demo() {
    printf("\n=== Pipe Capacity Demo ===\n");
    
    int pipefd[2];
    
    if (pipe(pipefd) == -1) {
        perror("pipe");
        return;
    }
    
    // Try to get pipe capacity (Linux-specific)
    #ifdef F_GETPIPE_SZ
    long capacity = fcntl(pipefd[0], F_GETPIPE_SZ);
    if (capacity != -1) {
        printf("Pipe capacity: %ld bytes (%ld KB)\n", 
               capacity, capacity / 1024);
    }
    #else
    printf("Pipe capacity query not supported on this system\n");
    printf("Typical pipe capacity: 64 KB\n");
    #endif
    
    close(pipefd[0]);
    close(pipefd[1]);
}

int main() {
    printf("=== Pipe System Calls Demo ===\n");
    
    simple_pipe_demo();
    bidirectional_pipe_demo();
    pipe_exec_demo();
    pipe_capacity_demo();
    
    printf("\n=== Demo Complete ===\n");
    
    return 0;
}

