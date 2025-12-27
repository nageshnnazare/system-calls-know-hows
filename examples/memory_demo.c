/*
 * memory_demo.c - Demonstrates memory management system calls
 * 
 * Compile: gcc -o memory_demo memory_demo.c
 * Usage: ./memory_demo
 */

#include <unistd.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <errno.h>

void print_separator(const char *title) {
    printf("\n=== %s ===\n", title);
}

void demonstrate_brk_sbrk() {
    print_separator("brk/sbrk Demo");
    
    void *current_brk = sbrk(0);
    printf("Current program break: %p\n", current_brk);
    
    // Allocate 4KB
    size_t size = 4096;
    void *new_space = sbrk(size);
    
    if (new_space == (void *)-1) {
        perror("sbrk");
        return;
    }
    
    printf("Allocated %zu bytes at: %p\n", size, new_space);
    
    void *new_brk = sbrk(0);
    printf("New program break: %p\n", new_brk);
    printf("Difference: %ld bytes\n", (char *)new_brk - (char *)current_brk);
    
    // Use the allocated memory
    char *buffer = (char *)new_space;
    strcpy(buffer, "Hello from heap!");
    printf("Content: %s\n", buffer);
}

void demonstrate_mmap() {
    print_separator("mmap Anonymous Memory Demo");
    
    size_t size = 4096;  // One page
    
    // Allocate anonymous memory
    void *memory = mmap(NULL, size,
                       PROT_READ | PROT_WRITE,
                       MAP_PRIVATE | MAP_ANONYMOUS,
                       -1, 0);
    
    if (memory == MAP_FAILED) {
        perror("mmap");
        return;
    }
    
    printf("Allocated %zu bytes at: %p\n", size, memory);
    
    // Use the memory
    char *data = (char *)memory;
    strcpy(data, "Hello from mmap!");
    printf("Content: %s\n", data);
    
    // Check memory is zeroed
    int is_zeroed = 1;
    for (size_t i = strlen(data) + 1; i < size; i++) {
        if (data[i] != 0) {
            is_zeroed = 0;
            break;
        }
    }
    printf("Remaining memory is zero-filled: %s\n", is_zeroed ? "Yes" : "No");
    
    // Cleanup
    if (munmap(memory, size) == -1) {
        perror("munmap");
    } else {
        printf("Memory unmapped successfully\n");
    }
}

void demonstrate_mmap_file() {
    print_separator("mmap File Mapping Demo");
    
    const char *filename = "mmap_test.txt";
    const char *content = "This is mapped file content!\nLine 2 here.\n";
    
    // Create file
    FILE *fp = fopen(filename, "w");
    if (fp == NULL) {
        perror("fopen");
        return;
    }
    fwrite(content, 1, strlen(content), fp);
    fclose(fp);
    
    // Open file for mapping
    int fd = open(filename, O_RDWR);
    if (fd == -1) {
        perror("open");
        return;
    }
    
    struct stat sb;
    if (fstat(fd, &sb) == -1) {
        perror("fstat");
        close(fd);
        return;
    }
    
    printf("File size: %ld bytes\n", sb.st_size);
    
    // Map file into memory
    char *mapped = mmap(NULL, sb.st_size,
                       PROT_READ | PROT_WRITE,
                       MAP_SHARED,
                       fd, 0);
    
    if (mapped == MAP_FAILED) {
        perror("mmap");
        close(fd);
        return;
    }
    
    close(fd);  // Can close fd after mapping
    
    printf("File mapped at: %p\n", (void *)mapped);
    printf("Original content:\n%.*s\n", (int)sb.st_size, mapped);
    
    // Modify through mapping
    if (sb.st_size > 5) {
        mapped[0] = 't';  // "This" -> "this"
        mapped[5] = 'I';  // "is" -> "Is"
    }
    
    // Sync changes to disk
    if (msync(mapped, sb.st_size, MS_SYNC) == -1) {
        perror("msync");
    }
    
    printf("Modified content:\n%.*s\n", (int)sb.st_size, mapped);
    printf("Changes written to file via mmap!\n");
    
    // Cleanup
    munmap(mapped, sb.st_size);
}

void demonstrate_mprotect() {
    print_separator("mprotect Demo");
    
    size_t page_size = sysconf(_SC_PAGESIZE);
    printf("Page size: %zu bytes\n", page_size);
    
    // Allocate memory with read/write
    char *memory = mmap(NULL, page_size,
                       PROT_READ | PROT_WRITE,
                       MAP_PRIVATE | MAP_ANONYMOUS,
                       -1, 0);
    
    if (memory == MAP_FAILED) {
        perror("mmap");
        return;
    }
    
    // Write to memory (OK)
    strcpy(memory, "Read-Write Memory");
    printf("Wrote: %s\n", memory);
    
    // Change to read-only
    printf("Changing to read-only with mprotect()...\n");
    if (mprotect(memory, page_size, PROT_READ) == -1) {
        perror("mprotect");
        munmap(memory, page_size);
        return;
    }
    
    // Read from memory (OK)
    printf("Read: %s\n", memory);
    
    printf("Memory is now read-only\n");
    printf("(Attempting write would cause SIGSEGV)\n");
    
    // Uncomment to test (will crash):
    // memory[0] = 'r';
    
    // Cleanup
    munmap(memory, page_size);
}

void demonstrate_memory_info() {
    print_separator("Memory Information");
    
    long page_size = sysconf(_SC_PAGESIZE);
    long phys_pages = sysconf(_SC_PHYS_PAGES);
    long avail_pages = sysconf(_SC_AVPHYS_PAGES);
    
    printf("Page size: %ld bytes (%ld KB)\n", page_size, page_size / 1024);
    printf("Physical pages: %ld\n", phys_pages);
    printf("Total RAM: %ld MB\n", (phys_pages * page_size) / (1024 * 1024));
    printf("Available pages: %ld\n", avail_pages);
    printf("Available RAM: %ld MB\n", (avail_pages * page_size) / (1024 * 1024));
}

int main() {
    printf("=== Memory Management System Calls Demo ===\n");
    
    demonstrate_brk_sbrk();
    demonstrate_mmap();
    demonstrate_mmap_file();
    demonstrate_mprotect();
    demonstrate_memory_info();
    
    printf("\n=== Demo Complete ===\n");
    printf("Created file: mmap_test.txt\n");
    
    return 0;
}

