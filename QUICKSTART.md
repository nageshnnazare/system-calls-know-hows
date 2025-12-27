# Quick Start Guide

## Overview

This tutorial provides comprehensive coverage of Linux C system calls, organized by category with examples and ASCII diagrams.

## Directory Structure

```
sysc/
├── README.md                 # Main overview
├── QUICKSTART.md            # This file
├── processes/
│   └── README.md            # Process management (fork, exec, wait, etc.)
├── files/
│   └── README.md            # File operations (open, read, write, stat, etc.)
├── memory/
│   └── README.md            # Memory management (brk, mmap, mprotect, etc.)
├── resources/
│   └── README.md            # Resource limits (getrlimit, getrusage, etc.)
├── ipc/
│   └── README.md            # Inter-process communication (pipes, signals, etc.)
└── examples/
    ├── Makefile             # Build all examples
    ├── process_manager.c    # Process management demo
    ├── file_operations.c    # File operations demo
    ├── memory_demo.c        # Memory management demo
    ├── pipe_demo.c          # Pipe and IPC demo
    ├── signal_demo.c        # Signal handling demo
    ├── resource_limits.c    # Resource limits demo
    └── shm_demo.c           # Shared memory demo
```

## Getting Started

### 1. Explore the Tutorials

Start with the main README:
```bash
cd /tmp/sysc
cat README.md
```

Then explore specific topics:
```bash
# Process management
cat processes/README.md

# File operations
cat files/README.md

# Memory management
cat memory/README.md

# Resource management
cat resources/README.md

# Inter-process communication
cat ipc/README.md
```

### 2. Build and Run Examples

```bash
cd examples

# Build all examples
make all

# Or build individual examples
make process_manager
make file_operations
make memory_demo
make pipe_demo
make signal_demo
make resource_limits
make shm_demo
```

### 3. Run the Examples

```bash
# Process management
./process_manager

# File operations
./file_operations

# Memory management
./memory_demo

# Pipes and IPC
./pipe_demo

# Signal handling (interactive)
./signal_demo

# Resource limits
./resource_limits

# Shared memory
./shm_demo
```

## Learning Path

### Beginner Track

1. **Start with file operations**
   - Read: `files/README.md`
   - Run: `./file_operations`
   - Most familiar concepts (open, read, write)

2. **Learn process management**
   - Read: `processes/README.md`
   - Run: `./process_manager`
   - Understand fork, exec, wait

3. **Explore IPC basics**
   - Read: `ipc/README.md` (pipes and signals sections)
   - Run: `./pipe_demo` and `./signal_demo`
   - Learn inter-process communication

### Intermediate Track

4. **Memory management**
   - Read: `memory/README.md`
   - Run: `./memory_demo`
   - Understand heap, mmap, memory mapping

5. **Resource management**
   - Read: `resources/README.md`
   - Run: `./resource_limits`
   - Learn about limits and monitoring

6. **Advanced IPC**
   - Read: `ipc/README.md` (message queues, semaphores, sockets)
   - Run: `./shm_demo`
   - Shared memory and synchronization

## Key Concepts

### System Call vs Library Function

```
Library Function (printf, malloc, fopen):
  • Higher level abstraction
  • May call multiple system calls
  • Buffered I/O
  • Portable across systems

System Call (write, brk, open):
  • Direct kernel interface
  • Single atomic operation
  • Unbuffered
  • OS-specific
```

### Error Handling

Always check return values:
```c
#include <errno.h>
#include <string.h>

int fd = open("file.txt", O_RDONLY);
if (fd == -1) {
    fprintf(stderr, "Error: %s\n", strerror(errno));
    // Handle error
}
```

### Common Return Patterns

- **Success**: Usually 0 or positive value
- **Failure**: Usually -1
- **Error details**: Check `errno`

## System Call Categories

### Process Management
- `fork()` - Create new process
- `exec()` - Execute program
- `wait()` - Wait for child process
- `exit()` - Terminate process

### File Operations
- `open()` - Open file
- `read()` - Read from file
- `write()` - Write to file
- `close()` - Close file
- `lseek()` - Change file offset
- `stat()` - Get file information

### Memory Management
- `brk()`/`sbrk()` - Change heap size
- `mmap()` - Map memory
- `munmap()` - Unmap memory
- `mprotect()` - Change memory protection

### IPC (Inter-Process Communication)
- `pipe()` - Create pipe
- `signal()` - Set signal handler
- `kill()` - Send signal
- `shmget()` - Create shared memory
- `semget()` - Create semaphore

### Resource Management
- `getrlimit()` - Get resource limits
- `setrlimit()` - Set resource limits
- `getrusage()` - Get resource usage

## Quick Reference Commands

### View System Call Manual
```bash
man 2 open      # System call documentation
man 3 printf    # Library function documentation
man 7 signal    # Overview documentation
```

### Trace System Calls
```bash
strace ./program          # Trace all system calls
strace -e open ./program  # Trace specific syscall
ltrace ./program          # Trace library calls
```

### View Process Information
```bash
cat /proc/self/status     # Current process status
cat /proc/self/limits     # Current process limits
cat /proc/self/maps       # Memory mappings
```

## Compilation Tips

### Basic Compilation
```bash
gcc -o program program.c
```

### With Debugging Symbols
```bash
gcc -g -o program program.c
```

### With All Warnings
```bash
gcc -Wall -Wextra -o program program.c
```

### With Optimization
```bash
gcc -O2 -o program program.c
```

## Common Pitfalls

1. **Not checking return values**
   - Always check for -1 or NULL

2. **File descriptor leaks**
   - Always close() what you open()

3. **Memory leaks**
   - Always free() or munmap() allocated memory

4. **Buffer overflows**
   - Check sizes before copying

5. **Race conditions**
   - Use proper synchronization for shared resources

6. **Signal safety**
   - Only use async-signal-safe functions in handlers

## Helpful Resources

### Man Pages
- `man syscalls` - List of all system calls
- `man 2 intro` - Introduction to system calls
- `man errno` - Error numbers

### Kernel Headers
Located in `/usr/include/`:
- `<unistd.h>` - POSIX system calls
- `<fcntl.h>` - File control
- `<sys/stat.h>` - File status
- `<sys/mman.h>` - Memory management
- `<signal.h>` - Signal handling

### Online Resources
- Linux man pages: https://man7.org/
- POSIX specifications
- Linux kernel source code

## Practice Projects

### Beginner
1. **File copy utility** - Use open/read/write
2. **Process tree viewer** - Use /proc filesystem
3. **Simple shell** - Use fork/exec/wait

### Intermediate
4. **Memory allocator** - Custom malloc using brk/mmap
5. **Log rotator** - File operations with rotation
6. **Signal-based daemon** - Background process with signal handling

### Advanced
7. **Shared memory database** - Use shm* calls with synchronization
8. **Network server** - Socket programming
9. **Resource monitor** - Track system resources

## Next Steps

1. **Read the tutorials** - Start with topics that interest you
2. **Run the examples** - Compile and execute the demo programs
3. **Modify the code** - Experiment with different parameters
4. **Write your own** - Create programs using system calls
5. **Debug issues** - Use strace, gdb, valgrind
6. **Read man pages** - Deep dive into specific calls

## Getting Help

- Use `man 2 <syscall>` for documentation
- Check errno and use `strerror()` for error messages
- Use `strace` to debug system call failures
- Read the kernel source for implementation details

## Clean Up

To remove compiled examples:
```bash
cd examples
make clean
```

---

**Ready to start?** Pick a topic that interests you and dive in!

- Want to create processes? → `processes/README.md`
- Need file I/O? → `files/README.md`
- Curious about memory? → `memory/README.md`
- Want to communicate between processes? → `ipc/README.md`
- Need to manage resources? → `resources/README.md`

