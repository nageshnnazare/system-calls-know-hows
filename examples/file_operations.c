/*
 * file_operations.c - Demonstrates file system calls
 * 
 * Compile: gcc -o file_operations file_operations.c
 * Usage: ./file_operations
 */

#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <errno.h>
#include <time.h>

#define TEST_FILE "test_syscall.txt"
#define BUF_SIZE 1024

void print_file_info(const char *filename) {
    struct stat sb;
    
    if (stat(filename, &sb) == -1) {
        perror("stat");
        return;
    }
    
    printf("\n=== File Information: %s ===\n", filename);
    printf("Inode: %lu\n", sb.st_ino);
    printf("Size: %ld bytes\n", sb.st_size);
    printf("Blocks: %ld x %ld = %ld bytes\n", 
           sb.st_blocks, (long)sb.st_blksize, 
           sb.st_blocks * 512);
    printf("Links: %lu\n", sb.st_nlink);
    printf("Permissions: %o\n", sb.st_mode & 0777);
    
    char *type;
    if (S_ISREG(sb.st_mode))       type = "Regular file";
    else if (S_ISDIR(sb.st_mode))  type = "Directory";
    else if (S_ISCHR(sb.st_mode))  type = "Character device";
    else if (S_ISBLK(sb.st_mode))  type = "Block device";
    else if (S_ISFIFO(sb.st_mode)) type = "FIFO/pipe";
    else if (S_ISLNK(sb.st_mode))  type = "Symbolic link";
    else if (S_ISSOCK(sb.st_mode)) type = "Socket";
    else                           type = "Unknown";
    
    printf("Type: %s\n", type);
    printf("Last modified: %s", ctime(&sb.st_mtime));
}

int main() {
    int fd;
    ssize_t bytes_written, bytes_read;
    char write_buf[] = "Hello from low-level I/O!\n"
                       "This is line 2.\n"
                       "This is line 3.\n";
    char read_buf[BUF_SIZE];
    off_t offset;
    
    printf("=== File Operations Demo ===\n");
    
    // 1. Open/Create file
    printf("\n1. Creating file with open()...\n");
    fd = open(TEST_FILE, O_CREAT | O_WRONLY | O_TRUNC, 0644);
    if (fd == -1) {
        perror("open");
        return 1;
    }
    printf("   File descriptor: %d\n", fd);
    
    // 2. Write to file
    printf("\n2. Writing to file...\n");
    bytes_written = write(fd, write_buf, strlen(write_buf));
    if (bytes_written == -1) {
        perror("write");
        close(fd);
        return 1;
    }
    printf("   Wrote %zd bytes\n", bytes_written);
    
    // 3. Close and reopen for reading
    close(fd);
    
    printf("\n3. Opening file for reading...\n");
    fd = open(TEST_FILE, O_RDONLY);
    if (fd == -1) {
        perror("open");
        return 1;
    }
    
    // 4. Read from file
    printf("\n4. Reading from file:\n");
    printf("   ---\n");
    bytes_read = read(fd, read_buf, sizeof(read_buf) - 1);
    if (bytes_read > 0) {
        read_buf[bytes_read] = '\0';
        printf("%s", read_buf);
    }
    printf("   ---\n");
    printf("   Read %zd bytes\n", bytes_read);
    
    // 5. lseek demo
    printf("\n5. Using lseek()...\n");
    offset = lseek(fd, 0, SEEK_END);
    printf("   File size: %ld bytes\n", offset);
    
    lseek(fd, 7, SEEK_SET);  // Skip "Hello f"
    bytes_read = read(fd, read_buf, 20);
    read_buf[bytes_read] = '\0';
    printf("   Reading from offset 7: \"%s\"\n", read_buf);
    
    // 6. Get file information
    print_file_info(TEST_FILE);
    
    // 7. dup2 demo - redirect stdout to file
    printf("\n6. Redirecting output with dup2()...\n");
    int stdout_copy = dup(STDOUT_FILENO);  // Save stdout
    
    int fd_write = open("redirect_output.txt", O_WRONLY | O_CREAT | O_TRUNC, 0644);
    dup2(fd_write, STDOUT_FILENO);  // Redirect stdout to file
    close(fd_write);
    
    printf("This goes to the file!\n");
    printf("And this too!\n");
    
    dup2(stdout_copy, STDOUT_FILENO);  // Restore stdout
    close(stdout_copy);
    
    printf("   Output redirected to redirect_output.txt\n");
    
    // 8. fcntl demo
    printf("\n7. Using fcntl()...\n");
    int flags = fcntl(fd, F_GETFL);
    if (flags == -1) {
        perror("fcntl F_GETFL");
    } else {
        printf("   File flags: ");
        if ((flags & O_ACCMODE) == O_RDONLY) printf("O_RDONLY ");
        if ((flags & O_ACCMODE) == O_WRONLY) printf("O_WRONLY ");
        if ((flags & O_ACCMODE) == O_RDWR)   printf("O_RDWR ");
        printf("\n");
    }
    
    // Cleanup
    close(fd);
    
    printf("\n=== Demo Complete ===\n");
    printf("Created files: %s, redirect_output.txt\n", TEST_FILE);
    
    return 0;
}

