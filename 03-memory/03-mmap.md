# 3.3 — mmap(): Mapping Files & Anonymous Memory

`mmap()` maps a range of your virtual address space to a file, device, or anonymous
memory. It is the kernel primitive behind shared libraries, JIT code pages, large
`malloc()` blocks, memory-mapped I/O, and POSIX shared memory (Part 3.5). Used
well it eliminates copy-heavy `read()`/`write()` loops (Part 2.2); used carelessly
it trades subtle ordering bugs for speed.

---

## 3.3.1 One syscall, two major use cases

![mmap virtual memory areas and page cache](figures/mmap.svg)

```
   FILE-BACKED                         ANONYMOUS (no fd)
   ┌─────────────┐                     ┌─────────────┐
   │ your VMA    │                     │ your VMA    │
   │  (virtual)  │                     │  (virtual)  │
   └──────┬──────┘                     └──────┬──────┘
          │ page faults                         │ page faults
          ▼                                       ▼
   ┌─────────────┐                     ┌─────────────┐
   │ page cache  │ ◀── file on disk    │ zero pages  │
   └─────────────┘                     └─────────────┘
```

| Backing | Typical use |
|---------|-------------|
| **File** | Fast read-mostly access; shared code; databases |
| **Anonymous** | Large allocations, heaps, COW after `fork()`, shm patterns |

---

## 3.3.2 The call

> **The call ▸**
> ```c
> #include <sys/mman.h>
>
> void *mmap(void *addr, size_t length, int prot, int flags,
>            int fd, off_t offset);
> int munmap(void *addr, size_t length);
> int msync(void *addr, size_t length, int flags);
> ```
> **Returns:** pointer to mapped region on success; **`MAP_FAILED`** `((void *)-1)`
> on error — **not** `NULL`. Check with `== MAP_FAILED`, then read `errno`.
>
> **`length`** — rounded up to page size (4096). **`offset`** — must be page-aligned.

### Protection: `prot`

| Flag | Meaning |
|------|---------|
| `PROT_READ` | Read access |
| `PROT_WRITE` | Write access |
| `PROT_EXEC` | Execute (needed for JIT; subject to W^X — Part 3.4) |
| `PROT_NONE` | No access (guard-like regions) |

### Mapping behaviour: `flags`

| Flag | Meaning |
|------|---------|
| `MAP_SHARED` | Writes visible to other mappers and eventually the file |
| `MAP_PRIVATE` | COW — your writes don't change the file or other processes |
| `MAP_ANONYMOUS` / `MAP_ANON` | No file; `fd` ignored (use `-1`) |
| `MAP_FIXED` | Must map at exact `addr` — **dangerous** unless you know the layout |
| `MAP_POPULATE` | Prefault all pages (eager fault) |
| `MAP_NORESERVE` | Don't reserve swap for mapping (risk OOM on write) |

**Errors ▸**

| `errno` | When |
|---------|------|
| `EINVAL` | Invalid flags/prot combo; bad offset/length; `MAP_FIXED` collision |
| `EBADF` | Bad `fd` for file mapping |
| `EACCES` | File not open for requested access |
| `ENOMEM` | Out of virtual memory or kernel resources |
| `EOVERFLOW` | `offset + length` wraps |

---

## 3.3.3 File-backed mapping

```
   open("data.bin") → fd
        │
        mmap(NULL, len, PROT_READ, MAP_PRIVATE, fd, 0)
        │
        ├─ kernel creates VMA pointing at file's inode page cache
        │
        └─ read via *(char *)p  →  minor fault  →  page cache fill
```

**MAP_PRIVATE** (default for read-mostly):

- Reads share the **page cache** with other processes mapping the same file.
- Writes fault into **private COW copies** — the on-disk file is unchanged.

**MAP_SHARED**:

- Writes dirty pages; `msync(MS_SYNC)` pushes to disk; other processes see updates
  (subject to cache coherency and timing).

> **Under the hood ▸** File `mmap()` increments the inode mapping count and ties
> the VMA's `vm_ops` to fault handlers that read from the **address_space** page
> cache — the same cache `read()` uses (Part 2.7).

**Trade-offs ▸** Random access in a huge file favours `mmap` over `lseek`+
`read` loops. Sequential one-pass streaming may be simpler with `read()` and better
for pipes/sockets.

---

## 3.3.4 Anonymous mapping

```c
void *p = mmap(NULL, size, PROT_READ | PROT_WRITE,
               MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
```

- Zero-filled on first touch (demand paging, Part 3.1).
- `fork()` child shares pages COW until either writes (Part 1.2).
- `munmap(p, size)` returns virtual area; physical pages reclaimed when unreferenced.

glibc uses anonymous `mmap()` above its threshold instead of `brk()` (Part 3.2).

---

## 3.3.5 munmap and msync

**`munmap(addr, length)`** — removes mappings; `addr` and `length` must match a
 prior mapping (typically the same page-rounded region). Partial unmap splits VMAs.

**`msync()`** — for `MAP_SHARED` file mappings, flush dirty pages:

| Flag | Behaviour |
|------|-----------|
| `MS_SYNC` | Blocking flush to storage |
| `MS_ASYNC` | Schedule writeback, return |
| `MS_INVALIDATE` | Invalidate other mappings (rare) |

**Pitfall ▸** Forgetting `munmap()` leaks **virtual address space** (and possibly
RSS until process exit). Long-running services mapping many temp files need explicit
unmap or reuse strategies.

---

## 3.3.6 Page alignment rules

```
   offset % page_size == 0     ✓ required
   length  → rounded up       internally
   returned addr              always page-aligned
```

If you map at a fixed address (`MAP_FIXED`), you can clobber existing mappings —
including libc's heap — and crash instantly.

---

## 3.3.7 File-mmap example: read-only search

```c
#define _POSIX_C_SOURCE 200809L
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int count_char(const char *data, size_t len, char needle) {
    size_t n = 0;
    for (size_t i = 0; i < len; i++)
        if (data[i] == needle)
            n++;
    return (int)n;
}

int main(int argc, char *argv[]) {
    if (argc != 3) {
        fprintf(stderr, "usage: %s <file> <char>\n", argv[0]);
        return 1;
    }
    if (strlen(argv[2]) != 1) {
        fprintf(stderr, "char argument must be a single character\n");
        return 1;
    }
    char needle = argv[2][0];

    int fd = open(argv[1], O_RDONLY);
    if (fd == -1) {
        perror("open");
        return 1;
    }

    struct stat st;
    if (fstat(fd, &st) == -1) {
        perror("fstat");
        close(fd);
        return 1;
    }
    if (st.st_size == 0) {
        printf("0 occurrences in empty file\n");
        close(fd);
        return 0;
    }

    size_t len = (size_t)st.st_size;
    void *map = mmap(NULL, len, PROT_READ, MAP_PRIVATE, fd, 0);
    if (map == MAP_FAILED) {
        perror("mmap");
        close(fd);
        return 1;
    }

    int count = count_char((const char *)map, len, needle);

    if (munmap(map, len) == -1) {
        perror("munmap");
        close(fd);
        return 1;
    }
    if (close(fd) == -1) {
        perror("close");
        return 1;
    }

    printf("'%c' occurs %d times in %s (%zu bytes mapped)\n",
           needle, count, argv[1], len);
    return 0;
}
```

No `read()` buffer — the kernel faults in pages as the loop touches them. For
write-back persistence see `MAP_SHARED` + `msync()` or plain `write()` (Part 2.2).

---

## Summary

- `mmap()` creates a VMA backed by a file page cache or anonymous zero pages;
  failure returns **`MAP_FAILED`**, not NULL.
- **`MAP_PRIVATE`** COW for writes; **`MAP_SHARED`** for IPC and shared file updates.
- **`MAP_ANONYMOUS`** powers large allocations, `fork()` sharing, and shm patterns.
- **`munmap()`** releases mappings; **`msync()`** flushes shared file dirtiness.
- Offsets and returned addresses are **page-aligned**; prefer `MAP_FIXED` only with
  extreme care.

Next: [3.4 — mprotect(), mlock() & madvise()](04-mprotect-and-locking.md)
