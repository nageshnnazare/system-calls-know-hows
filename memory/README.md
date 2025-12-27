# Memory Management System Calls

## Overview

Memory management system calls provide low-level control over process memory. This tutorial covers heap management, memory mapping, and shared memory.

## Process Memory Layout

```
┌─────────────────────────────────────────────────────────┐
│                    KERNEL SPACE                         │
│              (0xFFFF... on x86-64)                      │
│        Not accessible from user space                   │
└─────────────────────────────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────┐
│                    USER SPACE                           │
│                                                         │
│  High Addresses (0x7FFF... on x86-64)                   │
│  ┌────────────────────────────────────────────────┐     │
│  │  Stack (grows downward ▼)                      │     │
│  │  ┌──────────────────────────────────────────┐  │     │
│  │  │ Local variables                          │  │     │
│  │  │ Function parameters                      │  │     │
│  │  │ Return addresses                         │  │     │
│  │  └──────────────────────────────────────────┘  │     │
│  │                    │                           │     │
│  │                    ▼                           │     │
│  └────────────────────────────────────────────────┘     │
│                                                         │
│  ┌────────────────────────────────────────────────┐     │
│  │         Empty / Available Space                │     │
│  │              ░░░░░░░░░░░░░░░                   │     │
│  └────────────────────────────────────────────────┘     │
│                                                         │
│  ┌────────────────────────────────────────────────┐     │
│  │  Memory Mapped Region                          │     │
│  │  ┌──────────────────────────────────────────┐  │     │
│  │  │ mmap() allocations                       │  │     │
│  │  │ Shared libraries (.so files)             │  │     │
│  │  │ Anonymous mappings                       │  │     │
│  │  └──────────────────────────────────────────┘  │     │
│  └────────────────────────────────────────────────┘     │
│                                                         │
│  ┌────────────────────────────────────────────────┐     │
│  │  Heap (grows upward ▲)                         │     │
│  │  ┌──────────────────────────────────────────┐  │     │
│  │  │ malloc() allocations                     │  │     │
│  │  │ new allocations (C++)                    │  │     │
│  │  │ Managed by brk/sbrk                      │  │     │
│  │  │         ▲                                │  │     │
│  │  │         │ Program break                  │  │     │
│  │  └──────────────────────────────────────────┘  │     │
│  └────────────────────────────────────────────────┘     │
│                                                         │
│  ┌────────────────────────────────────────────────┐     │
│  │  BSS Segment (Uninitialized Data)              │     │
│  │  int global_uninit;                            │     │
│  │  static int static_uninit;                     │     │
│  │  (Initialized to 0 by kernel)                  │     │
│  └────────────────────────────────────────────────┘     │
│                                                         │
│  ┌────────────────────────────────────────────────┐     │
│  │  Data Segment (Initialized Data)               │     │
│  │  int global_init = 10;                         │     │
│  │  static int static_init = 20;                  │     │
│  └────────────────────────────────────────────────┘     │
│                                                         │
│  ┌────────────────────────────────────────────────┐     │
│  │  Text Segment (Code)                           │     │
│  │  Program instructions (read-only, shareable)   │     │
│  └────────────────────────────────────────────────┘     │
│  Low Addresses (0x400000 on x86-64)                     │
└─────────────────────────────────────────────────────────┘
```

## 1. brk() and sbrk() - Heap Management

### Synopsis
```c
#include <unistd.h>

int brk(void *addr);
void *sbrk(intptr_t increment);
```

### How brk/sbrk Works

```
Initial state:
┌───────────────────────────────────────┐
│  Data Segment                         │
│  int x = 10;                          │
├───────────────────────────────────────┤ ← Program break (brk)
│                                       │
│  Available for heap                   │
│                                       │
└───────────────────────────────────────┘

After malloc(100) → uses sbrk(100):
┌───────────────────────────────────────┐
│  Data Segment                         │
│  int x = 10;                          │
├───────────────────────────────────────┤
│  Allocated (100 bytes)                │
│  ████████████████████████████         │
├───────────────────────────────────────┤ ← New program break
│                                       │
│  Available for heap                   │
│                                       │
└───────────────────────────────────────┘

After another malloc(50):
┌───────────────────────────────────────┐
│  Data Segment                         │
├───────────────────────────────────────┤
│  Allocated (100 bytes)                │
│  ████████████████████████████         │
├───────────────────────────────────────┤
│  Allocated (50 bytes)                 │
│  ██████████████                       │
├───────────────────────────────────────┤ ← Program break moves up
│                                       │
│  Available for heap                   │
└───────────────────────────────────────┘

Note: free() usually doesn't call brk() to shrink heap
      (memory is cached for future allocations)
```

### Example
```c
#include <unistd.h>
#include <stdio.h>
#include <string.h>

int main() {
    void *current_brk, *new_brk;
    char *buffer;
    
    // Get current program break
    current_brk = sbrk(0);
    printf("Current break: %p\n", current_brk);
    
    // Allocate 1024 bytes
    buffer = sbrk(1024);
    if (buffer == (void *)-1) {
        perror("sbrk");
        return 1;
    }
    
    printf("Allocated at: %p\n", buffer);
    
    // Use the memory
    strcpy(buffer, "Hello from heap!");
    printf("Content: %s\n", buffer);
    
    // Check new break
    new_brk = sbrk(0);
    printf("New break: %p\n", new_brk);
    printf("Increased by: %ld bytes\n", 
           (char *)new_brk - (char *)current_brk);
    
    // Note: Cannot easily free with sbrk
    // Use malloc/free for proper memory management
    
    return 0;
}
```

### malloc() Implementation Concept

```
Simplified malloc() using sbrk():

┌────────────────────────────────────────────────┐
│ Memory Block Structure:                        │
│ ┌─────────────┬─────────────────────────────┐  │
│ │  Header     │  User Data                  │  │
│ │  (size,     │  (returned to user)         │  │
│ │   flags)    │                             │  │
│ └─────────────┴─────────────────────────────┘  │
└────────────────────────────────────────────────┘

Free List (for reusing freed blocks):
┌─────────┐    ┌─────────┐    ┌─────────┐
│ Free    │───►│ Free    │───►│ Free    │───► NULL
│ Block 1 │    │ Block 2 │    │ Block 3 │
└─────────┘    └─────────┘    └─────────┘

malloc(size):
  1. Search free list for suitable block
  2. If found: remove from free list, return it
  3. If not: call sbrk(size + header_size)
  4. Return pointer to user data

free(ptr):
  1. Add block back to free list
  2. Optionally merge with adjacent free blocks
  3. Usually doesn't call brk() to shrink heap
```

## 2. mmap() - Memory Mapping

### Synopsis
```c
#include <sys/mman.h>

void *mmap(void *addr, size_t length, int prot, int flags,
           int fd, off_t offset);
int munmap(void *addr, size_t length);
int msync(void *addr, size_t length, int flags);
int mprotect(void *addr, size_t length, int prot);
```

### Protection Flags

```
PROT_NONE   - Pages cannot be accessed
PROT_READ   - Pages can be read
PROT_WRITE  - Pages can be written
PROT_EXEC   - Pages can be executed

Example: PROT_READ | PROT_WRITE
```

### Mapping Flags

```
MAP_SHARED     - Share mapping with other processes
               - Changes written to file
               
MAP_PRIVATE    - Private copy-on-write mapping
               - Changes not written to file
               
MAP_ANONYMOUS  - Not backed by file (memory only)
MAP_FIXED      - Place mapping at exact address
MAP_LOCKED     - Lock pages in memory (no swap)
```

### mmap() Use Cases

```
1. File Mapping:
┌─────────────────────────────────────────────────┐
│ File on Disk: data.bin (1 MB)                   │
└───────────────────┬─────────────────────────────┘
                    │
              mmap(file_fd)
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│ Process Address Space                           │
│ ┌────────────────────────────────────────────┐  │
│ │ Mapped Region: 0x7f0000000000              │  │
│ │ (can read/write like array)                │  │
│ │ data[0] = 'A';  ← modifies file!           │  │
│ └────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘

2. Anonymous Mapping (like malloc for large allocations):
┌─────────────────────────────────────────────────┐
│ mmap(NULL, size, PROT_READ|PROT_WRITE,          │
│      MAP_PRIVATE|MAP_ANONYMOUS, -1, 0)          │
│                                                 │
│ Returns: Large block of zeroed memory           │
│ No file backing                                 │
│ More efficient than brk for large sizes         │
└─────────────────────────────────────────────────┘

3. Shared Memory (IPC):
Process A                          Process B
┌─────────────────────┐           ┌─────────────────────┐
│ mmap(MAP_SHARED)    │           │ mmap(MAP_SHARED)    │
│        │            │           │        │            │
│        └────────────┼───────────┼────────┘            │
└─────────────────────┘           └─────────────────────┘
                     │             │
                     ▼             ▼
              ┌────────────────────────┐
              │   Shared Memory Region │
              │   Both see changes     │
              └────────────────────────┘
```

### Example: File Mapping
```c
#include <sys/mman.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>

int main() {
    int fd;
    char *mapped;
    struct stat sb;
    const char *filename = "test_mmap.txt";
    
    // Create and write to file
    fd = open(filename, O_RDWR | O_CREAT | O_TRUNC, 0644);
    if (fd == -1) {
        perror("open");
        return 1;
    }
    
    const char *text = "Hello, mmap!\n";
    write(fd, text, strlen(text));
    
    // Get file size
    if (fstat(fd, &sb) == -1) {
        perror("fstat");
        return 1;
    }
    
    // Map file into memory
    mapped = mmap(NULL, sb.st_size, PROT_READ | PROT_WRITE,
                  MAP_SHARED, fd, 0);
    if (mapped == MAP_FAILED) {
        perror("mmap");
        return 1;
    }
    
    printf("File content: %.*s", (int)sb.st_size, mapped);
    
    // Modify through mapping (modifies file!)
    mapped[0] = 'h';  // "Hello" → "hello"
    
    // Ensure changes are written to disk
    if (msync(mapped, sb.st_size, MS_SYNC) == -1) {
        perror("msync");
    }
    
    // Cleanup
    munmap(mapped, sb.st_size);
    close(fd);
    
    return 0;
}
```

### Example: Anonymous Mapping
```c
#include <sys/mman.h>
#include <stdio.h>
#include <string.h>

int main() {
    size_t size = 4096;  // One page
    char *memory;
    
    // Allocate anonymous memory
    memory = mmap(NULL, size, 
                  PROT_READ | PROT_WRITE,
                  MAP_PRIVATE | MAP_ANONYMOUS,
                  -1, 0);
    
    if (memory == MAP_FAILED) {
        perror("mmap");
        return 1;
    }
    
    printf("Allocated %zu bytes at %p\n", size, memory);
    
    // Use the memory
    strcpy(memory, "Anonymous mapping!");
    printf("Content: %s\n", memory);
    
    // Free the memory
    munmap(memory, size);
    
    return 0;
}
```

## 3. Memory Protection - mprotect()

### Synopsis
```c
#include <sys/mman.h>

int mprotect(void *addr, size_t len, int prot);
```

### Protection Example

```
Memory Protection Stages:

1. Initial: Read-Write
┌────────────────────────────────┐
│ Memory Region                  │
│ PROT_READ | PROT_WRITE         │
│ char buf[1024];                │
│ buf[0] = 'A';  ✓ OK            │
└────────────────────────────────┘

2. After mprotect(buf, 1024, PROT_READ):
┌────────────────────────────────┐
│ Memory Region                  │
│ PROT_READ (read-only)          │
│ char c = buf[0];  ✓ OK         │
│ buf[0] = 'A';     ✗ SIGSEGV    │
└────────────────────────────────┘

3. After mprotect(buf, 1024, PROT_NONE):
┌────────────────────────────────┐
│ Memory Region                  │
│ PROT_NONE (no access)          │
│ char c = buf[0];  ✗ SIGSEGV    │
│ buf[0] = 'A';     ✗ SIGSEGV    │
└────────────────────────────────┘
```

### Example
```c
#include <sys/mman.h>
#include <stdio.h>
#include <signal.h>
#include <string.h>
#include <unistd.h>

void segfault_handler(int sig) {
    printf("Caught segmentation fault! (expected)\n");
    _exit(0);
}

int main() {
    size_t page_size = sysconf(_SC_PAGESIZE);
    char *memory;
    
    // Set up signal handler
    signal(SIGSEGV, segfault_handler);
    
    // Allocate memory with read/write
    memory = mmap(NULL, page_size,
                  PROT_READ | PROT_WRITE,
                  MAP_PRIVATE | MAP_ANONYMOUS,
                  -1, 0);
    
    if (memory == MAP_FAILED) {
        perror("mmap");
        return 1;
    }
    
    // Write to memory (OK)
    strcpy(memory, "Hello");
    printf("Wrote: %s\n", memory);
    
    // Change protection to read-only
    if (mprotect(memory, page_size, PROT_READ) == -1) {
        perror("mprotect");
        return 1;
    }
    
    printf("Changed to read-only. Reading: %s\n", memory);
    
    // Try to write (will cause SIGSEGV)
    printf("Attempting write to read-only memory...\n");
    memory[0] = 'h';  // This will trigger signal handler
    
    munmap(memory, page_size);
    return 0;
}
```

## 4. Shared Memory - POSIX and System V

### System V Shared Memory

```c
#include <sys/shm.h>

int shmget(key_t key, size_t size, int shmflg);
void *shmat(int shmid, const void *shmaddr, int shmflg);
int shmdt(const void *shmaddr);
int shmctl(int shmid, int cmd, struct shmid_ds *buf);
```

### Shared Memory Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  KERNEL                                 │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Shared Memory Segment (ID: 12345)                │  │
│  │  Key: 0x1234                                      │  │
│  │  Size: 4096 bytes                                 │  │
│  │  ┌─────────────────────────────────────────────┐  │  │
│  │  │  Data: "Shared between processes"           │  │  │
│  │  └─────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────┘  │
│                  ▲                    ▲                 │
└──────────────────┼────────────────────┼─────────────────┘
                   │                    │
        ┌──────────┴──────────┐  ┌──────┴─────────────┐
        │ Process A           │  │ Process B          │
        │ attached at:        │  │ attached at:       │
        │ 0x7f0000000000      │  │ 0x7f0000000000     │
        │                     │  │                    │
        │ data[0] = 'H';      │  │ char c = data[0];  │
        │                     │  │ (sees 'H')         │
        └─────────────────────┘  └────────────────────┘
```

### Example: Shared Memory
```c
#include <sys/shm.h>
#include <sys/stat.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#define SHM_SIZE 1024

int main() {
    key_t key = 1234;
    int shmid;
    char *shared_memory;
    pid_t pid;
    
    // Create shared memory segment
    shmid = shmget(key, SHM_SIZE, IPC_CREAT | 0666);
    if (shmid == -1) {
        perror("shmget");
        return 1;
    }
    
    printf("Shared memory ID: %d\n", shmid);
    
    // Attach to shared memory
    shared_memory = shmat(shmid, NULL, 0);
    if (shared_memory == (char *)-1) {
        perror("shmat");
        return 1;
    }
    
    pid = fork();
    
    if (pid == 0) {
        // Child process - write to shared memory
        strcpy(shared_memory, "Hello from child!");
        printf("Child wrote: %s\n", shared_memory);
        shmdt(shared_memory);
        return 0;
    }
    else {
        // Parent process - read from shared memory
        sleep(1);  // Wait for child to write
        printf("Parent read: %s\n", shared_memory);
        
        // Cleanup
        shmdt(shared_memory);
        shmctl(shmid, IPC_RMID, NULL);  // Remove segment
    }
    
    return 0;
}
```

## 5. Memory Locking - mlock()

### Synopsis
```c
#include <sys/mman.h>

int mlock(const void *addr, size_t len);
int munlock(const void *addr, size_t len);
int mlockall(int flags);
int munlockall(void);
```

### Memory Locking Concept

```
Without mlock():
┌─────────────────────────────────────┐
│ Process Memory                      │
│ ┌─────────────────────────────────┐ │
│ │ Sensitive data (e.g., crypto    │ │
│ │ keys, passwords)                │ │
│ └─────────────────────────────────┘ │
└──────────────┬──────────────────────┘
               │
               │ May be swapped to disk!
               ▼
┌───────────────────────────────────┐
│ Swap File/Partition               │
│ (disk - INSECURE!)                │
│ Sensitive data exposed            │
└───────────────────────────────────┘

With mlock():
┌─────────────────────────────────────┐
│ Physical RAM                        │
│ ┌─────────────────────────────────┐ │
│ │ Locked: Sensitive data          │ │
│ │ (never swapped to disk)         │ │
│ └─────────────────────────────────┘ │
└─────────────────────────────────────┘
         ▲
         │ Stays in RAM
         │ Protected from swap
```

### Example
```c
#include <sys/mman.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>

int main() {
    size_t page_size = sysconf(_SC_PAGESIZE);
    char *secure_memory;
    
    // Allocate memory
    secure_memory = mmap(NULL, page_size,
                         PROT_READ | PROT_WRITE,
                         MAP_PRIVATE | MAP_ANONYMOUS,
                         -1, 0);
    
    if (secure_memory == MAP_FAILED) {
        perror("mmap");
        return 1;
    }
    
    // Lock memory (prevent swapping)
    if (mlock(secure_memory, page_size) == -1) {
        perror("mlock (may need root privileges)");
        // Continue anyway for demo
    } else {
        printf("Memory locked (won't be swapped)\n");
    }
    
    // Store sensitive data
    strcpy(secure_memory, "SecretPassword123");
    printf("Stored sensitive data\n");
    
    // Use the data...
    
    // Clear before releasing
    memset(secure_memory, 0, page_size);
    
    // Unlock and free
    munlock(secure_memory, page_size);
    munmap(secure_memory, page_size);
    
    return 0;
}
```

## 6. Memory Advice - madvise()

### Synopsis
```c
#include <sys/mman.h>

int madvise(void *addr, size_t length, int advice);
```

### Advice Flags

```
MADV_NORMAL      - No special treatment
MADV_RANDOM      - Random access pattern
MADV_SEQUENTIAL  - Sequential access (read-ahead)
MADV_WILLNEED    - Will need soon (prefetch)
MADV_DONTNEED    - Won't need (can free)
MADV_FREE        - Can reuse (lazy free)
```

### Performance Optimization

```
Sequential File Processing:
┌────────────────────────────────────────┐
│ madvise(MADV_SEQUENTIAL)               │
│                                        │
│ File: [████░░░░░░░░░░░░░░░░░░░░░░]     │
│        ▲                               │
│        │ Read position                 │
│        │                               │
│  Kernel reads ahead: [████████]        │
│  (prefetches into cache)               │
└────────────────────────────────────────┘

Random Access:
┌────────────────────────────────────────┐
│ madvise(MADV_RANDOM)                   │
│                                        │
│ File: [██░░██░░░░██░░░░░██░░░░░░]      │
│        ▲  ▲     ▲     ▲                │
│        Random access pattern           │
│                                        │
│  Kernel: minimal read-ahead            │
│  (saves cache for actual accesses)     │
└────────────────────────────────────────┘
```

## Complete Example Programs

See [examples/](../examples/) directory:
- `memory_allocator.c` - Custom allocator using sbrk
- `mmap_ipc.c` - Inter-process communication with mmap
- `memory_mapper.c` - File mapping utilities
- `secure_memory.c` - Secure memory handling

## Memory Management Best Practices

```
1. Always check return values
   ✓ if (ptr == NULL) or if (ptr == MAP_FAILED)
   
2. Match allocation with deallocation
   ✓ brk/sbrk → brk
   ✓ mmap → munmap
   ✓ malloc → free
   
3. Handle out-of-memory gracefully
   ✓ Check ENOMEM errno
   ✓ Have fallback strategy
   
4. Be aware of alignment
   ✓ mmap returns page-aligned addresses
   ✓ Some operations require alignment
   
5. Use appropriate method:
   ✓ Small allocations → malloc (brk)
   ✓ Large allocations → mmap
   ✓ File I/O → mmap for large files
   ✓ IPC → shared memory
```

## Common Pitfalls

1. **Memory leaks** - Not freeing/unmapping memory
2. **Segmentation faults** - Accessing unmapped memory
3. **Alignment issues** - Not aligning to page boundaries
4. **Shared memory cleanup** - Not removing segments
5. **Permission errors** - Incorrect mmap protection flags
6. **Partial writes** - Not handling msync failures

## Practice Exercises

1. Implement a memory pool allocator
2. Create a shared memory logger
3. Build a memory-mapped file database
4. Implement copy-on-write using mprotect
5. Create a memory profiler using /proc/self/maps

## See Also
- `man 2 brk`
- `man 2 mmap`
- `man 2 mprotect`
- `man 2 shmget`
- `man 5 proc` (for /proc/self/maps)

