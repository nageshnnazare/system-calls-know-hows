# File System Calls Tutorial

## Overview

File operations are among the most common system calls in Unix/Linux. This tutorial covers all major file-related system calls.

## File I/O Architecture

```
┌────────────────────────────────────────────────────────────┐
│                    USER SPACE                              │
│                                                            │
│  Application Program                                       │
│  ┌────────────────────────────────────────────────────┐    │
│  │  int fd = open("file.txt", O_RDONLY);              │    │
│  │  read(fd, buffer, size);                           │    │
│  │  close(fd);                                        │    │
│  └─────────────────────┬──────────────────────────────┘    │
└────────────────────────┼───────────────────────────────────┘
                         │ System Call Interface
┌────────────────────────┼───────────────────────────────────┐
│                        ▼          KERNEL SPACE             │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │     System Call Handler                              │  │
│  │  sys_open(), sys_read(), sys_write(), sys_close()    │  │
│  └────────────────────┬─────────────────────────────────┘  │
│                       ▼                                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │     Virtual File System (VFS) Layer                  │  │
│  │  - Abstraction layer for different filesystems       │  │
│  │  - File descriptor management                        │  │
│  │  - Inode cache, dentry cache                         │  │
│  └────────────────────┬─────────────────────────────────┘  │
│                       ▼                                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │     Filesystem Implementations                       │  │
│  │  ext4  │  xfs  │  btrfs  │  nfs  │  tmpfs  │ ...     │  │
│  └────────────────────┬─────────────────────────────────┘  │
│                       ▼                                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │     Block Layer / Page Cache                         │  │
│  └────────────────────┬─────────────────────────────────┘  │
│                       ▼                                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │     Device Drivers (disk, SSD, etc.)                 │  │
│  └────────────────────┬─────────────────────────────────┘  │
└───────────────────────┼────────────────────────────────────┘
                        ▼
                   Physical Storage
```

## 1. open() - Open a File

### Synopsis
```c
#include <fcntl.h>

int open(const char *pathname, int flags);
int open(const char *pathname, int flags, mode_t mode);
int creat(const char *pathname, mode_t mode);
```

### Flags

```
O_RDONLY    ┐
O_WRONLY    ├─ Access modes (mutually exclusive)
O_RDWR      ┘

O_CREAT     - Create file if it doesn't exist
O_EXCL      - Ensure file creation (fail if exists, with O_CREAT)
O_TRUNC     - Truncate existing file to 0 length
O_APPEND    - Append to end of file
O_NONBLOCK  - Non-blocking I/O
O_SYNC      - Synchronous writes (wait for physical write)
O_DIRECT    - Direct I/O (bypass cache)
O_DIRECTORY - Fail if not a directory
O_CLOEXEC   - Close on exec()
```

### File Descriptor Table

```
Process File Descriptor Table:
┌─────┬──────────────────────────────────┐
│ FD  │  Description                     │
├─────┼──────────────────────────────────┤
│  0  │  stdin  (Standard Input)         │◄─── Always open
│  1  │  stdout (Standard Output)        │◄─── Always open
│  2  │  stderr (Standard Error)         │◄─── Always open
├─────┼──────────────────────────────────┤
│  3  │  open("file1.txt", O_RDONLY)     │◄─── First open() returns 3
│  4  │  open("file2.txt", O_WRONLY)     │◄─── Second open() returns 4
│  5  │  open("file3.txt", O_RDWR)       │◄─── Third open() returns 5
│ ... │  ...                             │
└─────┴──────────────────────────────────┘

Each FD points to:
    ▼
┌────────────────────────────┐
│  Open File Description     │
│  - File offset             │
│  - Access mode             │
│  - File status flags       │
│  - Reference to inode      │
└────────────────────────────┘
```

### Example
```c
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <errno.h>
#include <string.h>

int main() {
    int fd;
    
    // Open existing file for reading
    fd = open("example.txt", O_RDONLY);
    if (fd == -1) {
        perror("open");
        return 1;
    }
    printf("Opened file, fd = %d\n", fd);
    close(fd);
    
    // Create new file with permissions rw-r--r--
    fd = open("newfile.txt", O_CREAT | O_WRONLY | O_TRUNC, 0644);
    if (fd == -1) {
        perror("open");
        return 1;
    }
    printf("Created file, fd = %d\n", fd);
    close(fd);
    
    return 0;
}
```

## 2. read() and write() - I/O Operations

### Synopsis
```c
#include <unistd.h>

ssize_t read(int fd, void *buf, size_t count);
ssize_t write(int fd, const void *buf, size_t count);
ssize_t pread(int fd, void *buf, size_t count, off_t offset);
ssize_t pwrite(int fd, const void *buf, size_t count, off_t offset);
```

### Read/Write Flow

```
read() Operation:
                           ┌─────────────────┐
User Buffer (buf)          │  Kernel Buffer  │        Disk
┌──────────────┐           │   (Page Cache)  │     ┌─────────┐
│              │           │                 │     │ File    │
│  [empty]     │  ◄────────┤  [file data]    │ ◄───┤ Data    │
│              │  copy     │                 │ read│         │
└──────────────┘           └─────────────────┘     └─────────┘
      ▲                            │
      └────────────────────────────┘
         returns bytes read

write() Operation:
                           ┌─────────────────┐
User Buffer (buf)          │  Kernel Buffer  │        Disk
┌──────────────┐           │   (Page Cache)  │     ┌─────────┐
│ "Hello"      │  ────────►│  "Hello"        │ ───►│ File    │
│              │  copy     │                 │write│ Data    │
└──────────────┘           └─────────────────┘     └─────────┘
                                   │                     ▲
                                   └─────────────────────┘
                           (written back later or with fsync)
```

### File Offset

```
File: "Hello, World!\n"
      0123456789...

Initial state:
┌──────────────────────────────┐
│ H e l l o ,   W o r l d ! \n │
│ ▲                            │
│ offset = 0                   │
└──────────────────────────────┘

After read(fd, buf, 5):
┌──────────────────────────────┐
│ H e l l o ,   W o r l d ! \n │
│           ▲                  │
│           offset = 5         │
└──────────────────────────────┘
buf now contains: "Hello"

After read(fd, buf, 7):
┌──────────────────────────────┐
│ H e l l o ,   W o r l d ! \n │
│                       ▲      │
│                       offset = 12
└──────────────────────────────┘
buf now contains: ", World"
```

### Example
```c
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>

int main() {
    int fd;
    char write_buf[] = "Hello, System Calls!";
    char read_buf[100];
    ssize_t bytes;
    
    // Write to file
    fd = open("test.txt", O_CREAT | O_WRONLY | O_TRUNC, 0644);
    if (fd == -1) {
        perror("open for write");
        return 1;
    }
    
    bytes = write(fd, write_buf, strlen(write_buf));
    printf("Wrote %zd bytes\n", bytes);
    close(fd);
    
    // Read from file
    fd = open("test.txt", O_RDONLY);
    if (fd == -1) {
        perror("open for read");
        return 1;
    }
    
    bytes = read(fd, read_buf, sizeof(read_buf) - 1);
    if (bytes > 0) {
        read_buf[bytes] = '\0';  // Null terminate
        printf("Read %zd bytes: %s\n", bytes, read_buf);
    }
    close(fd);
    
    return 0;
}
```

## 3. lseek() - Change File Offset

### Synopsis
```c
#include <unistd.h>

off_t lseek(int fd, off_t offset, int whence);
```

### Whence Values

```
SEEK_SET: offset from beginning of file
┌────────────────────────────────┐
│ [file content]                 │
│ ▲                              │
│ └─ lseek(fd, 10, SEEK_SET)     │
│    offset = 10                 │
└────────────────────────────────┘

SEEK_CUR: offset from current position
┌────────────────────────────────┐
│ [file content]                 │
│           ▲                    │
│ current   └─ lseek(fd, 5, SEEK_CUR)
│ pos       offset = current + 5 │
└────────────────────────────────┘

SEEK_END: offset from end of file
┌────────────────────────────────┐
│ [file content]                 │
│                              ▲ │
│     lseek(fd, -10, SEEK_END)─┘ │
│     offset = file_size - 10    │
└────────────────────────────────┘
```

### Creating Sparse Files

```
Normal File (1MB):
┌────────────────────────────────────────┐
│████████████████████████████████████████│ 1 MB on disk
└────────────────────────────────────────┘

Sparse File (1MB logical, data at ends):
┌────┬───────────────────────────┬─────┐
│████│░░░░░░░░░░░░░░░░░░░░░░░░░░░│█████│ ~8 KB on disk
└────┴───────────────────────────┴─────┘
 data        (hole)              data
```

### Example
```c
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>

int main() {
    int fd;
    off_t offset;
    char buf[20];
    
    fd = open("test.txt", O_RDWR | O_CREAT | O_TRUNC, 0644);
    if (fd == -1) {
        perror("open");
        return 1;
    }
    
    // Write at beginning
    write(fd, "START", 5);
    
    // Seek to position 100 (creates sparse file)
    offset = lseek(fd, 100, SEEK_SET);
    printf("Current offset: %ld\n", offset);
    
    // Write at offset 100
    write(fd, "END", 3);
    
    // Get file size
    offset = lseek(fd, 0, SEEK_END);
    printf("File size: %ld bytes\n", offset);
    
    // Read from beginning
    lseek(fd, 0, SEEK_SET);
    read(fd, buf, 5);
    buf[5] = '\0';
    printf("First 5 bytes: %s\n", buf);
    
    close(fd);
    return 0;
}
```

## 4. File Descriptors: dup() and dup2()

### Synopsis
```c
#include <unistd.h>

int dup(int oldfd);
int dup2(int oldfd, int newfd);
int dup3(int oldfd, int newfd, int flags);
```

### dup() Mechanism

```
Before dup(4):
File Descriptor Table          Open File Table
┌─────┬─────────────┐         ┌────────────────┐
│  3  │  ─────────┐ │         │ File: a.txt    │
├─────┼───────────┼─┤         │ offset: 0      │
│  4  │  ─────────┼─┼────────►│ flags: O_RDWR  │
├─────┼───────────┼─┤         └────────────────┘
│  5  │  ─────────┼─┼────┐    ┌────────────────┐
└─────┴───────────┘ │    └───►│ File: b.txt    │
                    │         │ offset: 100    │
                    │         └────────────────┘
                    │         ┌────────────────┐
                    └────────►│ File: c.txt    │
                              └────────────────┘

After int newfd = dup(4):
File Descriptor Table          Open File Table
┌─────┬─────────────┐         ┌────────────────┐
│  3  │  ─────────┐ │         │ File: a.txt    │
├─────┼───────────┼─┤         └────────────────┘
│  4  │  ─────────┼─┼────┐    ┌────────────────┐
├─────┼───────────┼─┤    │    │ File: b.txt    │
│  5  │  ─────────┼─┼───┐│    │ offset: 100    │◄── Shared!
├─────┼───────────┼─┤   ││    │ flags: O_RDWR  │
│  6  │  ─────────┼─┼───┼┼───►│ refs: 2        │
└─────┴───────────┘ │   │└────┤                │
                    │   │     └────────────────┘
                    └───┘     ┌────────────────┐
                              │ File: c.txt    │
                              └────────────────┘
Both fd 4 and 6 point to same file description!
Changes to offset affect both.
```

### Redirecting Standard Output

```
Initial state:
┌─────┬──────────┐
│  0  │  stdin   │
│  1  │  stdout  │───► Terminal
│  2  │  stderr  │
└─────┴──────────┘

After: 
  fd = open("output.txt", O_WRONLY | O_CREAT, 0644);
  dup2(fd, 1);
  close(fd);

┌─────┬──────────┐
│  0  │  stdin   │
│  1  │  ────────┼───► output.txt (all output redirected)
│  2  │  stderr  │
└─────┴──────────┘
```

### Example
```c
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>

int main() {
    int fd, newfd;
    
    // Create a file
    fd = open("redirect.txt", O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd == -1) {
        perror("open");
        return 1;
    }
    
    printf("This goes to terminal\n");
    
    // Redirect stdout to file
    newfd = dup2(fd, STDOUT_FILENO);
    if (newfd == -1) {
        perror("dup2");
        return 1;
    }
    
    close(fd);  // Can close original fd
    
    printf("This goes to file\n");
    fprintf(stdout, "This also goes to file\n");
    
    return 0;
}
```

## 5. fcntl() - File Control

### Synopsis
```c
#include <fcntl.h>

int fcntl(int fd, int cmd, ... /* arg */ );
```

### Common Operations

```
┌────────────────────────────────────────────────────────┐
│  fcntl() Commands                                      │
├────────────────────────────────────────────────────────┤
│  F_DUPFD      - Duplicate file descriptor              │
│  F_GETFD      - Get file descriptor flags              │
│  F_SETFD      - Set file descriptor flags (FD_CLOEXEC) │
│  F_GETFL      - Get file status flags                  │
│  F_SETFL      - Set file status flags                  │
│  F_GETLK      - Get file lock information              │
│  F_SETLK      - Set file lock (non-blocking)           │
│  F_SETLKW     - Set file lock (blocking)               │
│  F_GETOWN     - Get process receiving SIGIO            │
│  F_SETOWN     - Set process receiving SIGIO            │
└────────────────────────────────────────────────────────┘
```

### File Locking

```
File Locking Types:

Read Lock (Shared):
┌──────────────────────────────────┐
│ Process A: Read Lock (bytes 0-99)│◄─┐
│ Process B: Read Lock (bytes 0-99)│◄─┼─ Multiple readers OK
│ Process C: Read Lock (bytes 0-99)│◄─┘
└──────────────────────────────────┘

Write Lock (Exclusive):
┌──────────────────────────────────┐
│ Process A: Write Lock(bytes 0-99)│◄── Only one writer
│ Process B: BLOCKED               │◄── Must wait
│ Process C: BLOCKED               │◄── Must wait
└──────────────────────────────────┘

Advisory vs Mandatory:
┌────────────────────────────────────────┐
│ Advisory Locking (Linux default)       │
│ - Cooperative                          │
│ - Processes must check locks           │
│ - Can be bypassed                      │
└────────────────────────────────────────┘
```

### Example
```c
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>
#include <errno.h>

int main() {
    int fd;
    struct flock lock;
    
    fd = open("lockfile.txt", O_RDWR | O_CREAT, 0644);
    if (fd == -1) {
        perror("open");
        return 1;
    }
    
    // Set up write lock structure
    lock.l_type = F_WRLCK;      // Write lock
    lock.l_whence = SEEK_SET;   // From start of file
    lock.l_start = 0;           // Offset
    lock.l_len = 0;             // Lock entire file (0 = EOF)
    
    printf("Trying to acquire lock...\n");
    
    // Try to acquire lock (non-blocking)
    if (fcntl(fd, F_SETLK, &lock) == -1) {
        if (errno == EACCES || errno == EAGAIN) {
            printf("File is already locked\n");
        } else {
            perror("fcntl");
        }
        close(fd);
        return 1;
    }
    
    printf("Lock acquired! Press Enter to release...\n");
    getchar();
    
    // Release lock
    lock.l_type = F_UNLCK;
    fcntl(fd, F_SETLK, &lock);
    
    close(fd);
    return 0;
}
```

## 6. stat() Family - File Metadata

### Synopsis
```c
#include <sys/stat.h>

int stat(const char *pathname, struct stat *statbuf);
int fstat(int fd, struct stat *statbuf);
int lstat(const char *pathname, struct stat *statbuf);
```

### struct stat

```
struct stat {
    dev_t     st_dev;      // Device ID
    ino_t     st_ino;      // Inode number
    mode_t    st_mode;     // Protection mode
    nlink_t   st_nlink;    // Number of hard links
    uid_t     st_uid;      // User ID
    gid_t     st_gid;      // Group ID
    dev_t     st_rdev;     // Device ID (if special file)
    off_t     st_size;     // Total size (bytes)
    blksize_t st_blksize;  // Block size for I/O
    blkcnt_t  st_blocks;   // Number of 512B blocks
    time_t    st_atime;    // Last access time
    time_t    st_mtime;    // Last modification time
    time_t    st_ctime;    // Last status change time
};
```

### File Type Macros

```
┌──────────────────────────────────────────┐
│  File Type Checking Macros               │
├──────────────────────────────────────────┤
│  S_ISREG(m)   Regular file               │
│  S_ISDIR(m)   Directory                  │
│  S_ISCHR(m)   Character device           │
│  S_ISBLK(m)   Block device               │
│  S_ISFIFO(m)  FIFO/pipe                  │
│  S_ISLNK(m)   Symbolic link              │
│  S_ISSOCK(m)  Socket                     │
└──────────────────────────────────────────┘

Permission Bits:
┌─────────────────────────────────────────┐
│  Owner  │  Group  │  Others             │
│  r w x  │  r w x  │  r w x              │
│  4 2 1  │  4 2 1  │  4 2 1              │
└─────────────────────────────────────────┘
Example: 0644 = rw-r--r--
         0755 = rwxr-xr-x
```

### Example
```c
#include <sys/stat.h>
#include <stdio.h>
#include <time.h>

void print_file_type(mode_t mode) {
    if (S_ISREG(mode))       printf("Regular file\n");
    else if (S_ISDIR(mode))  printf("Directory\n");
    else if (S_ISCHR(mode))  printf("Character device\n");
    else if (S_ISBLK(mode))  printf("Block device\n");
    else if (S_ISFIFO(mode)) printf("FIFO/pipe\n");
    else if (S_ISLNK(mode))  printf("Symbolic link\n");
    else if (S_ISSOCK(mode)) printf("Socket\n");
    else                     printf("Unknown\n");
}

int main(int argc, char *argv[]) {
    struct stat sb;
    
    if (argc != 2) {
        fprintf(stderr, "Usage: %s <pathname>\n", argv[0]);
        return 1;
    }
    
    if (stat(argv[1], &sb) == -1) {
        perror("stat");
        return 1;
    }
    
    printf("File: %s\n", argv[1]);
    printf("  Inode: %lu\n", sb.st_ino);
    printf("  Type: ");
    print_file_type(sb.st_mode);
    printf("  Size: %ld bytes\n", sb.st_size);
    printf("  Links: %lu\n", sb.st_nlink);
    printf("  Permissions: %o\n", sb.st_mode & 0777);
    printf("  Last modified: %s", ctime(&sb.st_mtime));
    
    return 0;
}
```

## 7. Directory Operations

### Synopsis
```c
#include <sys/stat.h>
int mkdir(const char *pathname, mode_t mode);
int rmdir(const char *pathname);

#include <dirent.h>
DIR *opendir(const char *name);
struct dirent *readdir(DIR *dirp);
int closedir(DIR *dirp);

#include <unistd.h>
int chdir(const char *path);
char *getcwd(char *buf, size_t size);
```

### Directory Structure

```
Directory Entry (dirent):
┌────────────────────────────────────┐
│ struct dirent {                    │
│   ino_t d_ino;      // Inode       │
│   char  d_name[256]; // Filename   │
│   ...                              │
│ }                                  │
└────────────────────────────────────┘

Directory Tree:
/home/user/
    │
    ├── documents/
    │   ├── file1.txt
    │   └── file2.pdf
    │
    ├── pictures/
    │   └── photo.jpg
    │
    └── code/
        ├── main.c
        └── utils.h
```

### Example
```c
#include <dirent.h>
#include <stdio.h>
#include <sys/stat.h>

int main(int argc, char *argv[]) {
    DIR *dir;
    struct dirent *entry;
    struct stat sb;
    const char *dirname = argc > 1 ? argv[1] : ".";
    
    dir = opendir(dirname);
    if (dir == NULL) {
        perror("opendir");
        return 1;
    }
    
    printf("Contents of %s:\n", dirname);
    printf("%-30s %10s %s\n", "Name", "Size", "Type");
    printf("----------------------------------------\n");
    
    while ((entry = readdir(dir)) != NULL) {
        char path[1024];
        snprintf(path, sizeof(path), "%s/%s", dirname, entry->d_name);
        
        if (stat(path, &sb) == 0) {
            char type = '?';
            if (S_ISREG(sb.st_mode))  type = 'f';
            else if (S_ISDIR(sb.st_mode)) type = 'd';
            else if (S_ISLNK(sb.st_mode)) type = 'l';
            
            printf("%-30s %10ld %c\n", 
                   entry->d_name, sb.st_size, type);
        }
    }
    
    closedir(dir);
    return 0;
}
```

## 8. Links: Hard and Symbolic

### Synopsis
```c
#include <unistd.h>

int link(const char *oldpath, const char *newpath);
int unlink(const char *pathname);
int symlink(const char *target, const char *linkpath);
ssize_t readlink(const char *pathname, char *buf, size_t bufsiz);
```

### Hard Link vs Symbolic Link

```
Hard Links:
Original File:  inode 12345
┌─────────────────────────────┐
│ Inode 12345                 │
│ - Data blocks: [10, 11, 12] │
│ - Link count: 3             │
│ - Permissions: rw-r--r--    │
└─────────────────────────────┘
         ▲        ▲         ▲
         │        │         │
    ┌────┴───┬────┴───┬─────┴────┐
    │ /a.txt │ /b.txt │ /c.txt   │ ← All point to same inode
    └────────┴────────┴──────────┘
    
Deleting /a.txt: link count becomes 2
Data is deleted only when link count reaches 0

Symbolic (Soft) Links:
Original File:
┌─────────────────────────────┐
│ Inode 12345                 │
│ File: /path/original.txt    │
│ Data: "Hello World"         │
└─────────────────────────────┘
         ▲
         │
┌────────┴──────────────────────┐
│ Inode 67890                   │
│ Symbolic Link: /link.txt      │
│ Data: "/path/original.txt"    │
└───────────────────────────────┘
         │
         └─► Points to pathname, not inode
         
If original is deleted, symlink becomes "dangling"
```

### Example
```c
#include <unistd.h>
#include <stdio.h>
#include <sys/stat.h>

int main() {
    struct stat sb;
    char link_target[256];
    ssize_t len;
    
    // Create original file
    FILE *fp = fopen("original.txt", "w");
    fprintf(fp, "Hello, Links!\n");
    fclose(fp);
    
    // Create hard link
    if (link("original.txt", "hardlink.txt") == -1) {
        perror("link");
    } else {
        printf("Created hard link\n");
    }
    
    // Create symbolic link
    if (symlink("original.txt", "symlink.txt") == -1) {
        perror("symlink");
    } else {
        printf("Created symbolic link\n");
    }
    
    // Check link count
    if (stat("original.txt", &sb) == 0) {
        printf("Link count: %lu\n", sb.st_nlink);
    }
    
    // Read symbolic link target
    len = readlink("symlink.txt", link_target, sizeof(link_target) - 1);
    if (len != -1) {
        link_target[len] = '\0';
        printf("Symlink points to: %s\n", link_target);
    }
    
    return 0;
}
```

## Complete Examples

See the [examples/](../examples/) directory for:
- `file_copy.c` - Efficient file copying
- `file_lock.c` - File locking demonstration
- `dir_tree.c` - Recursive directory traversal
- `sparse_file.c` - Creating sparse files

## Common Pitfalls

1. **Not checking return values** - Always check for -1
2. **Buffer overflows** - Ensure read buffers are large enough
3. **File descriptor leaks** - Always close files
4. **Race conditions** - Use O_EXCL with O_CREAT for atomicity
5. **Partial reads/writes** - Handle short counts in loops
6. **Permission errors** - Check errno == EACCES or EPERM

## Practice Exercises

1. Implement `cat` command using system calls
2. Write a program to copy directory trees
3. Create a file monitoring program
4. Implement a simple file-based database
5. Build a log rotation system

## See Also
- `man 2 open`
- `man 2 read`
- `man 2 stat`
- `man 3 readdir`

