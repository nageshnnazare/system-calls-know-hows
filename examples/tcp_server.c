/*
 * tcp_server.c - Simple TCP echo server
 * 
 * Compile: gcc -o tcp_server tcp_server.c
 * Usage: ./tcp_server [port]
 * Test: telnet localhost 8080
 */

#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>

#define DEFAULT_PORT 8080
#define BACKLOG 5
#define BUFFER_SIZE 1024

int main(int argc, char *argv[]) {
    int server_fd, client_fd;
    struct sockaddr_in server_addr, client_addr;
    socklen_t client_len;
    char buffer[BUFFER_SIZE];
    int port = DEFAULT_PORT;
    
    if (argc > 1) {
        port = atoi(argv[1]);
    }
    
    printf("=== TCP Echo Server ===\n");
    
    // 1. Create socket
    server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd == -1) {
        perror("socket");
        exit(1);
    }
    
    printf("[Server] Socket created\n");
    
    // Set socket options
    int opt = 1;
    if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, 
                   &opt, sizeof(opt)) == -1) {
        perror("setsockopt");
    }
    
    // 2. Bind to address and port
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = INADDR_ANY;
    server_addr.sin_port = htons(port);
    
    if (bind(server_fd, (struct sockaddr *)&server_addr, 
             sizeof(server_addr)) == -1) {
        perror("bind");
        close(server_fd);
        exit(1);
    }
    
    printf("[Server] Bound to port %d\n", port);
    
    // 3. Listen for connections
    if (listen(server_fd, BACKLOG) == -1) {
        perror("listen");
        close(server_fd);
        exit(1);
    }
    
    printf("[Server] Listening for connections...\n");
    printf("[Server] Press Ctrl+C to stop\n\n");
    
    // 4. Accept loop
    while (1) {
        client_len = sizeof(client_addr);
        client_fd = accept(server_fd, (struct sockaddr *)&client_addr, 
                          &client_len);
        
        if (client_fd == -1) {
            if (errno == EINTR) {
                continue;  // Interrupted by signal
            }
            perror("accept");
            continue;
        }
        
        // Get client info
        char client_ip[INET_ADDRSTRLEN];
        inet_ntop(AF_INET, &client_addr.sin_addr, client_ip, sizeof(client_ip));
        int client_port = ntohs(client_addr.sin_port);
        
        printf("[Client %s:%d] Connected\n", client_ip, client_port);
        
        // 5. Echo loop
        while (1) {
            ssize_t bytes_read = recv(client_fd, buffer, sizeof(buffer) - 1, 0);
            
            if (bytes_read <= 0) {
                if (bytes_read == 0) {
                    printf("[Client %s:%d] Disconnected\n", client_ip, client_port);
                } else {
                    perror("recv");
                }
                break;
            }
            
            buffer[bytes_read] = '\0';
            printf("[Client %s:%d] Received %zd bytes: %s", 
                   client_ip, client_port, bytes_read, buffer);
            
            // Echo back
            ssize_t bytes_sent = send(client_fd, buffer, bytes_read, 0);
            if (bytes_sent == -1) {
                perror("send");
                break;
            }
            
            printf("[Client %s:%d] Echoed %zd bytes\n", 
                   client_ip, client_port, bytes_sent);
        }
        
        // 6. Close client connection
        close(client_fd);
        printf("[Client %s:%d] Connection closed\n\n", client_ip, client_port);
    }
    
    close(server_fd);
    return 0;
}

