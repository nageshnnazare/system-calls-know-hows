/*
 * tcp_client.c - Simple TCP client
 * 
 * Compile: gcc -o tcp_client tcp_client.c
 * Usage: ./tcp_client [host] [port]
 */

#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define DEFAULT_PORT 8080
#define DEFAULT_HOST "127.0.0.1"
#define BUFFER_SIZE 1024

int main(int argc, char *argv[]) {
    int sock;
    struct sockaddr_in server_addr;
    char buffer[BUFFER_SIZE];
    const char *host = DEFAULT_HOST;
    int port = DEFAULT_PORT;
    
    if (argc > 1) {
        host = argv[1];
    }
    if (argc > 2) {
        port = atoi(argv[2]);
    }
    
    printf("=== TCP Client ===\n");
    printf("[Client] Connecting to %s:%d\n", host, port);
    
    // 1. Create socket
    sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock == -1) {
        perror("socket");
        exit(1);
    }
    
    // 2. Set up server address
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(port);
    
    if (inet_pton(AF_INET, host, &server_addr.sin_addr) <= 0) {
        fprintf(stderr, "Invalid address: %s\n", host);
        close(sock);
        exit(1);
    }
    
    // 3. Connect to server
    if (connect(sock, (struct sockaddr *)&server_addr, 
                sizeof(server_addr)) == -1) {
        perror("connect");
        close(sock);
        exit(1);
    }
    
    printf("[Client] Connected!\n");
    printf("[Client] Type messages (Ctrl+D to quit):\n\n");
    
    // 4. Communication loop
    while (1) {
        printf("> ");
        fflush(stdout);
        
        // Read from stdin
        if (fgets(buffer, sizeof(buffer), stdin) == NULL) {
            printf("\n");
            break;  // EOF (Ctrl+D)
        }
        
        // Send to server
        size_t len = strlen(buffer);
        ssize_t bytes_sent = send(sock, buffer, len, 0);
        
        if (bytes_sent == -1) {
            perror("send");
            break;
        }
        
        // Receive response
        ssize_t bytes_read = recv(sock, buffer, sizeof(buffer) - 1, 0);
        
        if (bytes_read <= 0) {
            if (bytes_read == 0) {
                printf("[Client] Server closed connection\n");
            } else {
                perror("recv");
            }
            break;
        }
        
        buffer[bytes_read] = '\0';
        printf("Server echo: %s", buffer);
    }
    
    // 5. Close connection
    printf("[Client] Closing connection\n");
    close(sock);
    
    return 0;
}

