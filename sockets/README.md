# Socket Programming Tutorial

## Overview

Sockets provide an interface for network communication between processes, either on the same machine or across a network.

## Socket Architecture

```
┌──────────────────────────────────────────────────────────┐
│                   APPLICATION LAYER                      │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Your Program (Client/Server)                      │  │
│  │  socket(), bind(), connect(), send(), recv()       │  │
│  └────────────────┬───────────────────────────────────┘  │
└───────────────────┼──────────────────────────────────────┘
                    │ Socket API
┌───────────────────┼──────────────────────────────────────┐
│                   ▼      KERNEL SPACE                    │
│  ┌──────────────────────────────────────────────────┐    │
│  │  Socket Layer                                    │    │
│  │  - File descriptor management                    │    │
│  │  - Socket buffers                                │    │
│  └────────────────┬─────────────────────────────────┘    │
│                   ▼                                      │
│  ┌──────────────────────────────────────────────────┐    │
│  │  Protocol Layer (TCP/UDP/Raw)                    │    │
│  │  - TCP: Connection-oriented, reliable            │    │
│  │  - UDP: Connectionless, unreliable               │    │
│  └────────────────┬─────────────────────────────────┘    │
│                   ▼                                      │
│  ┌──────────────────────────────────────────────────┐    │
│  │  IP Layer (IPv4/IPv6)                            │    │
│  │  - Routing                                       │    │
│  │  - Fragmentation                                 │    │
│  └────────────────┬─────────────────────────────────┘    │
│                   ▼                                      │
│  ┌──────────────────────────────────────────────────┐    │
│  │  Network Interface (Ethernet, WiFi, etc.)        │    │
│  └────────────────┬─────────────────────────────────┘    │
└───────────────────┼──────────────────────────────────────┘
                    ▼
               Physical Network
```

## Socket Types

```
┌────────────────┬──────────────┬──────────────────────────┐
│ Type           │ Protocol     │ Characteristics          │
├────────────────┼──────────────┼──────────────────────────┤
│ SOCK_STREAM    │ TCP          │ Connection-oriented      │
│                │              │ Reliable, ordered        │
│                │              │ Byte stream              │
├────────────────┼──────────────┼──────────────────────────┤
│ SOCK_DGRAM     │ UDP          │ Connectionless           │
│                │              │ Unreliable, unordered    │
│                │              │ Message boundaries       │
├────────────────┼──────────────┼──────────────────────────┤
│ SOCK_RAW       │ Raw IP       │ Direct IP access         │
│                │              │ Requires root            │
├────────────────┼──────────────┼──────────────────────────┤
│ SOCK_SEQPACKET │ SCTP         │ Connection-oriented      │
│                │              │ Message boundaries       │
└────────────────┴──────────────┴──────────────────────────┘

Address Families:
  AF_INET      - IPv4
  AF_INET6     - IPv6
  AF_UNIX      - Unix domain sockets (local IPC)
  AF_PACKET    - Low-level packet interface
```

## 1. TCP Client-Server

### TCP Server Flow

```
┌─────────────────────────────────────────────────┐
│ socket()      - Create socket                   │
│      │                                          │
│      ▼                                          │
│ bind()        - Bind to address:port            │
│      │                                          │
│      ▼                                          │
│ listen()      - Mark as passive socket          │
│      │                                          │
│      ▼                                          │
│ accept()      - Wait for connection (blocking)  │
│      │                                          │
│      ▼                                          │
│ read/write()  - Communicate with client         │
│      │                                          │
│      ▼                                          │
│ close()       - Close connection                │
└─────────────────────────────────────────────────┘
```

### TCP Server Example

```c
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define PORT 8080
#define BACKLOG 5

int main() {
    int server_fd, client_fd;
    struct sockaddr_in server_addr, client_addr;
    socklen_t client_len;
    char buffer[1024];
    
    // 1. Create socket
    server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd == -1) {
        perror("socket");
        exit(1);
    }
    
    // Set socket options
    int opt = 1;
    if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, 
                   &opt, sizeof(opt)) == -1) {
        perror("setsockopt");
    }
    
    // 2. Bind to address and port
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = INADDR_ANY;  // All interfaces
    server_addr.sin_port = htons(PORT);
    
    if (bind(server_fd, (struct sockaddr *)&server_addr, 
             sizeof(server_addr)) == -1) {
        perror("bind");
        close(server_fd);
        exit(1);
    }
    
    // 3. Listen for connections
    if (listen(server_fd, BACKLOG) == -1) {
        perror("listen");
        close(server_fd);
        exit(1);
    }
    
    printf("Server listening on port %d\n", PORT);
    
    // 4. Accept connections
    client_len = sizeof(client_addr);
    client_fd = accept(server_fd, (struct sockaddr *)&client_addr, 
                      &client_len);
    if (client_fd == -1) {
        perror("accept");
        close(server_fd);
        exit(1);
    }
    
    // Get client info
    char client_ip[INET_ADDRSTRLEN];
    inet_ntop(AF_INET, &client_addr.sin_addr, client_ip, sizeof(client_ip));
    printf("Client connected: %s:%d\n", client_ip, 
           ntohs(client_addr.sin_port));
    
    // 5. Communicate with client
    ssize_t bytes_read = recv(client_fd, buffer, sizeof(buffer) - 1, 0);
    if (bytes_read > 0) {
        buffer[bytes_read] = '\0';
        printf("Received: %s\n", buffer);
        
        // Echo back
        send(client_fd, buffer, bytes_read, 0);
    }
    
    // 6. Close connections
    close(client_fd);
    close(server_fd);
    
    return 0;
}
```

### TCP Client Flow

```
┌─────────────────────────────────────────────────┐
│ socket()      - Create socket                   │
│      │                                          │
│      ▼                                          │
│ connect()     - Connect to server               │
│      │                                          │
│      ▼                                          │
│ write/read()  - Communicate with server         │
│      │                                          │
│      ▼                                          │
│ close()       - Close connection                │
└─────────────────────────────────────────────────┘
```

### TCP Client Example

```c
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define PORT 8080

int main() {
    int sock;
    struct sockaddr_in server_addr;
    char buffer[1024];
    const char *message = "Hello from client!";
    
    // 1. Create socket
    sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock == -1) {
        perror("socket");
        exit(1);
    }
    
    // 2. Set up server address
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(PORT);
    
    // Convert IP address
    if (inet_pton(AF_INET, "127.0.0.1", &server_addr.sin_addr) <= 0) {
        perror("inet_pton");
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
    
    printf("Connected to server\n");
    
    // 4. Send data
    send(sock, message, strlen(message), 0);
    printf("Message sent: %s\n", message);
    
    // 5. Receive response
    ssize_t bytes_read = recv(sock, buffer, sizeof(buffer) - 1, 0);
    if (bytes_read > 0) {
        buffer[bytes_read] = '\0';
        printf("Server response: %s\n", buffer);
    }
    
    // 6. Close socket
    close(sock);
    
    return 0;
}
```

## 2. UDP Communication

### UDP Server Example

```c
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#define PORT 8080

int main() {
    int sockfd;
    struct sockaddr_in server_addr, client_addr;
    socklen_t client_len;
    char buffer[1024];
    
    // Create UDP socket
    sockfd = socket(AF_INET, SOCK_DGRAM, 0);
    if (sockfd == -1) {
        perror("socket");
        return 1;
    }
    
    // Bind to address
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = INADDR_ANY;
    server_addr.sin_port = htons(PORT);
    
    if (bind(sockfd, (struct sockaddr *)&server_addr, 
             sizeof(server_addr)) == -1) {
        perror("bind");
        close(sockfd);
        return 1;
    }
    
    printf("UDP server listening on port %d\n", PORT);
    
    while (1) {
        client_len = sizeof(client_addr);
        
        // Receive datagram
        ssize_t n = recvfrom(sockfd, buffer, sizeof(buffer) - 1, 0,
                            (struct sockaddr *)&client_addr, &client_len);
        
        if (n > 0) {
            buffer[n] = '\0';
            
            char client_ip[INET_ADDRSTRLEN];
            inet_ntop(AF_INET, &client_addr.sin_addr, 
                     client_ip, sizeof(client_ip));
            
            printf("Received from %s:%d: %s\n", 
                   client_ip, ntohs(client_addr.sin_port), buffer);
            
            // Send reply
            sendto(sockfd, "ACK", 3, 0,
                   (struct sockaddr *)&client_addr, client_len);
        }
    }
    
    close(sockfd);
    return 0;
}
```

### UDP Client Example

```c
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#define PORT 8080

int main() {
    int sockfd;
    struct sockaddr_in server_addr;
    char buffer[1024];
    const char *message = "Hello UDP!";
    
    // Create UDP socket
    sockfd = socket(AF_INET, SOCK_DGRAM, 0);
    if (sockfd == -1) {
        perror("socket");
        return 1;
    }
    
    // Set up server address
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(PORT);
    inet_pton(AF_INET, "127.0.0.1", &server_addr.sin_addr);
    
    // Send datagram
    sendto(sockfd, message, strlen(message), 0,
           (struct sockaddr *)&server_addr, sizeof(server_addr));
    
    printf("Message sent: %s\n", message);
    
    // Receive reply
    ssize_t n = recvfrom(sockfd, buffer, sizeof(buffer) - 1, 0, 
                         NULL, NULL);
    if (n > 0) {
        buffer[n] = '\0';
        printf("Server reply: %s\n", buffer);
    }
    
    close(sockfd);
    return 0;
}
```

## 3. Unix Domain Sockets

### Unix Domain Socket (Stream)

```c
#include <sys/socket.h>
#include <sys/un.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define SOCKET_PATH "/tmp/my_socket"

// Server
int main_server() {
    int server_fd, client_fd;
    struct sockaddr_un addr;
    char buffer[1024];
    
    server_fd = socket(AF_UNIX, SOCK_STREAM, 0);
    
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, SOCKET_PATH, sizeof(addr.sun_path) - 1);
    
    unlink(SOCKET_PATH);  // Remove old socket file
    
    bind(server_fd, (struct sockaddr *)&addr, sizeof(addr));
    listen(server_fd, 5);
    
    printf("Unix socket server listening on %s\n", SOCKET_PATH);
    
    client_fd = accept(server_fd, NULL, NULL);
    
    ssize_t n = recv(client_fd, buffer, sizeof(buffer), 0);
    buffer[n] = '\0';
    printf("Received: %s\n", buffer);
    
    send(client_fd, "ACK", 3, 0);
    
    close(client_fd);
    close(server_fd);
    unlink(SOCKET_PATH);
    
    return 0;
}

// Client
int main_client() {
    int sockfd;
    struct sockaddr_un addr;
    
    sockfd = socket(AF_UNIX, SOCK_STREAM, 0);
    
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, SOCKET_PATH, sizeof(addr.sun_path) - 1);
    
    connect(sockfd, (struct sockaddr *)&addr, sizeof(addr));
    
    send(sockfd, "Hello Unix Socket", 17, 0);
    
    char buffer[1024];
    ssize_t n = recv(sockfd, buffer, sizeof(buffer), 0);
    buffer[n] = '\0';
    printf("Server reply: %s\n", buffer);
    
    close(sockfd);
    
    return 0;
}
```

## 4. Socket Options

### Common Socket Options

```c
#include <sys/socket.h>
#include <netinet/in.h>
#include <netinet/tcp.h>

int sockfd = socket(AF_INET, SOCK_STREAM, 0);

// SO_REUSEADDR - Reuse address immediately
int opt = 1;
setsockopt(sockfd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

// SO_REUSEPORT - Multiple sockets on same port
setsockopt(sockfd, SOL_SOCKET, SO_REUSEPORT, &opt, sizeof(opt));

// SO_KEEPALIVE - Keep connection alive
setsockopt(sockfd, SOL_SOCKET, SO_KEEPALIVE, &opt, sizeof(opt));

// SO_RCVBUF - Receive buffer size
int bufsize = 65536;
setsockopt(sockfd, SOL_SOCKET, SO_RCVBUF, &bufsize, sizeof(bufsize));

// SO_SNDBUF - Send buffer size
setsockopt(sockfd, SOL_SOCKET, SO_SNDBUF, &bufsize, sizeof(bufsize));

// SO_RCVTIMEO - Receive timeout
struct timeval tv = {.tv_sec = 5, .tv_usec = 0};
setsockopt(sockfd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));

// SO_SNDTIMEO - Send timeout
setsockopt(sockfd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));

// TCP_NODELAY - Disable Nagle's algorithm
setsockopt(sockfd, IPPROTO_TCP, TCP_NODELAY, &opt, sizeof(opt));

// TCP_CORK - Cork TCP (batch small packets)
setsockopt(sockfd, IPPROTO_TCP, TCP_CORK, &opt, sizeof(opt));

// SO_LINGER - Control close() behavior
struct linger ling = {.l_onoff = 1, .l_linger = 10};
setsockopt(sockfd, SOL_SOCKET, SO_LINGER, &ling, sizeof(ling));

// Get socket error
int error;
socklen_t len = sizeof(error);
getsockopt(sockfd, SOL_SOCKET, SO_ERROR, &error, &len);
if (error) {
    printf("Socket error: %d\n", error);
}
```

## 5. Non-Blocking Sockets

### Non-Blocking I/O

```c
#include <fcntl.h>
#include <errno.h>

int sockfd = socket(AF_INET, SOCK_STREAM, 0);

// Make socket non-blocking
int flags = fcntl(sockfd, F_GETFL, 0);
fcntl(sockfd, F_SETFL, flags | O_NONBLOCK);

// Non-blocking connect
if (connect(sockfd, (struct sockaddr *)&addr, sizeof(addr)) == -1) {
    if (errno == EINPROGRESS) {
        printf("Connection in progress...\n");
        
        // Use select() or poll() to wait for completion
        fd_set writefds;
        FD_ZERO(&writefds);
        FD_SET(sockfd, &writefds);
        
        struct timeval timeout = {.tv_sec = 5, .tv_usec = 0};
        
        if (select(sockfd + 1, NULL, &writefds, NULL, &timeout) > 0) {
            int error;
            socklen_t len = sizeof(error);
            getsockopt(sockfd, SOL_SOCKET, SO_ERROR, &error, &len);
            
            if (error == 0) {
                printf("Connected!\n");
            } else {
                printf("Connection failed: %d\n", error);
            }
        }
    }
}

// Non-blocking recv
ssize_t n = recv(sockfd, buffer, sizeof(buffer), 0);
if (n == -1) {
    if (errno == EAGAIN || errno == EWOULDBLOCK) {
        printf("Would block - no data available\n");
    } else {
        perror("recv");
    }
}
```

## 6. Multiplexing with select/poll/epoll

See [I/O Multiplexing section in CHEATSHEET.md](../CHEATSHEET.md#io-multiplexing)

## 7. Advanced Socket Patterns

### Multi-threaded Server

```c
#include <pthread.h>

void *handle_client(void *arg) {
    int client_fd = *(int *)arg;
    free(arg);
    
    char buffer[1024];
    ssize_t n = recv(client_fd, buffer, sizeof(buffer), 0);
    
    if (n > 0) {
        send(client_fd, buffer, n, 0);  // Echo
    }
    
    close(client_fd);
    return NULL;
}

int main() {
    int server_fd = socket(AF_INET, SOCK_STREAM, 0);
    // bind, listen...
    
    while (1) {
        int *client_fd = malloc(sizeof(int));
        *client_fd = accept(server_fd, NULL, NULL);
        
        pthread_t thread;
        pthread_create(&thread, NULL, handle_client, client_fd);
        pthread_detach(thread);
    }
    
    return 0;
}
```

### Connection Pool

```c
#define POOL_SIZE 10

struct connection_pool {
    int fds[POOL_SIZE];
    int available[POOL_SIZE];
    pthread_mutex_t mutex;
};

void pool_init(struct connection_pool *pool) {
    pthread_mutex_init(&pool->mutex, NULL);
    
    for (int i = 0; i < POOL_SIZE; i++) {
        pool->fds[i] = socket(AF_INET, SOCK_STREAM, 0);
        // connect to server...
        pool->available[i] = 1;
    }
}

int pool_get(struct connection_pool *pool) {
    pthread_mutex_lock(&pool->mutex);
    
    for (int i = 0; i < POOL_SIZE; i++) {
        if (pool->available[i]) {
            pool->available[i] = 0;
            pthread_mutex_unlock(&pool->mutex);
            return pool->fds[i];
        }
    }
    
    pthread_mutex_unlock(&pool->mutex);
    return -1;  // No available connections
}

void pool_release(struct connection_pool *pool, int fd) {
    pthread_mutex_lock(&pool->mutex);
    
    for (int i = 0; i < POOL_SIZE; i++) {
        if (pool->fds[i] == fd) {
            pool->available[i] = 1;
            break;
        }
    }
    
    pthread_mutex_unlock(&pool->mutex);
}
```

## 8. Socket Security

### TCP Wrappers

```c
#include <tcpd.h>

// Check if connection is allowed
int client_fd = accept(server_fd, (struct sockaddr *)&client_addr, &len);

if (hosts_ctl("my_daemon", STRING_UNKNOWN,
              inet_ntoa(client_addr.sin_addr), STRING_UNKNOWN) == 0) {
    printf("Connection denied by TCP wrappers\n");
    close(client_fd);
    continue;
}
```

### SSL/TLS (OpenSSL)

```c
#include <openssl/ssl.h>
#include <openssl/err.h>

// Initialize SSL
SSL_library_init();
SSL_CTX *ctx = SSL_CTX_new(TLS_server_method());

// Load certificate and key
SSL_CTX_use_certificate_file(ctx, "cert.pem", SSL_FILETYPE_PEM);
SSL_CTX_use_PrivateKey_file(ctx, "key.pem", SSL_FILETYPE_PEM);

// Create SSL socket
int client_fd = accept(server_fd, NULL, NULL);
SSL *ssl = SSL_new(ctx);
SSL_set_fd(ssl, client_fd);

// SSL handshake
if (SSL_accept(ssl) <= 0) {
    ERR_print_errors_fp(stderr);
} else {
    // Read/write using SSL
    char buffer[1024];
    SSL_read(ssl, buffer, sizeof(buffer));
    SSL_write(ssl, "Response", 8);
}

SSL_shutdown(ssl);
SSL_free(ssl);
close(client_fd);
```

## Compilation

```bash
# Basic compilation
gcc -o server server.c
gcc -o client client.c

# With threading
gcc -pthread -o server server.c

# With OpenSSL
gcc -o server server.c -lssl -lcrypto
```

## Common Pitfalls

1. **Not checking return values** - Always check for -1
2. **Forgetting byte order** - Use htons(), ntohs(), htonl(), ntohl()
3. **Not handling partial sends/receives** - Loop until complete
4. **Zombie connections** - Use SO_KEEPALIVE or application-level heartbeats
5. **Buffer overflows** - Always bounds-check
6. **Not closing sockets** - Resource leaks
7. **Ignoring SIGPIPE** - Writing to closed socket crashes program
8. **Mixing IPv4 and IPv6** - Use getaddrinfo() for protocol-independent code

## Best Practices

```c
1. ✓ Use SO_REUSEADDR for servers
2. ✓ Set timeouts on blocking operations
3. ✓ Handle EINTR (interrupted system calls)
4. ✓ Check for partial reads/writes
5. ✓ Use non-blocking I/O with select/poll/epoll for scalability
6. ✓ Implement proper error handling
7. ✓ Close sockets in all error paths
8. ✓ Use connection pooling for clients
9. ✓ Implement graceful shutdown
10. ✓ Monitor socket buffer sizes
```

## See Also

- `man 2 socket`
- `man 2 bind`
- `man 2 connect`
- `man 2 send`
- `man 2 recv`
- `man 7 ip`
- `man 7 tcp`
- `man 7 udp`
- `man 7 unix`

