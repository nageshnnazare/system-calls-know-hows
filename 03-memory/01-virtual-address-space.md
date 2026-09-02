# 3.1 — The Virtual Address Space

Every process on Linux sees its own **virtual address space** — a contiguous range
of addresses from `0` up to the architecture limit (typically `0x00007fffffffffff`
on x86-64 user space). Those addresses are **not** physical RAM locations. They are
**translations** the Memory Management Unit (MMU) resolves through page tables into
physical frames, swap, or "not present yet." Part 1.2's `fork()` duplicates these
mappings with copy-on-write; Part 3.2–3.3 show how the heap and `mmap()` grow the
space.

---

## 3.1.1 The layout of a typical process

![Per-process virtual address space layout](figures/address-space.svg)

On Linux x86-64, the kernel maps each process roughly like this (exact addresses
vary with ASLR and linker flags):

```
   high addresses
   ┌─────────────────────────────────────────┐
   │  kernel (not visible in user space)      │  ← ring 0 only
   ├─────────────────────────────────────────┤
   │  stack          grows ▼                  │  argv, envp, local vars
   │     ... gap (guard pages) ...            │
   │  mmap region    grows ▼ (or fixed)       │  libs, shared mem, large allocs
   │     ...                                    │
   │  heap           grows ▲                  │  brk/sbrk, malloc small blocks
   │  BSS            (zero-init globals)      │
   │  data           (initialized globals)    │
   │  text (code)    read-only + execute      │
   └─────────────────────────────────────────┘
   low addresses (often 0x400000 or PIE base)
```

| Segment | Contents | Typical growth |
|---------|----------|----------------|
| **text** | Machine code, read-only string literals | Fixed at load |
| **data** | Initialized global/static variables | Fixed at load |
| **BSS** | Zero-initialized globals (`int x;`) | Fixed at load |
| **heap** | Dynamic allocations via `brk`/`malloc` | Upward via `brk()` (Part 3.2) |
| **mmap** | Shared libraries, file mappings, large allocs | `mmap()`/`munmap()` (Part 3.3) |
| **stack** | Function frames, local arrays | Downward on each call |

> **Under the hood ▸** The kernel tracks each contiguous region as a **VMA**
> (virtual memory area) in the process's `mm_struct`. `mmap()`, `brk()`, and
> `munmap()` add, extend, or remove VMAs. The MMU only sees the resulting page
> table entries.

**Systems ▸** Inspect a live layout:

```bash
cat /proc/self/maps          # your shell's own layout
cat /proc/1234/maps          # process 1234
pmap -x 1234                 # human-readable summary
```

Each line is one VMA: start–end permissions offset device inode pathname.

---

## 3.1.2 Pages, the MMU, and page tables

Physical memory is managed in **pages** — typically **4096 bytes** on x86-64
(4 KiB). Huge pages (2 MiB, 1 GiB) exist for performance (Part 3.4).

```
   virtual address (64-bit, mostly unused high bits)
        │
        ▼
   ┌─────────────┐     page walk (hardware)
   │ page tables │ ──────────────────────────▶ physical frame (or fault)
   │  (per proc) │
   └─────────────┘
        │
        ├─ present bit set  → frame number + perms (R/W/X/U)
        └─ present bit clear → page fault → kernel handler
```

The **MMU** is CPU hardware that walks multi-level page tables on every memory
access. The kernel builds and updates those tables when you `mmap()`, `fork()`,
or fault in a page.

**Trade-offs ▸** Page tables cost memory (roughly 8 bytes per 4 KiB mapped on
x86-64 with 4 levels) and TLB misses add latency. That is why `mmap()` of huge
files and transparent huge pages matter for big working sets.

---

## 3.1.3 Demand paging

Linux rarely loads an entire executable into RAM at `execve()` (Part 1.3). Instead:

```
   execve("/bin/ls")
        │
        ├─ map text/data/BSS VMAs in page tables as "not present"
        │
        └─ first instruction fetch or first data touch
              │
              ▼
           page fault (minor) → kernel reads that ONE page from disk → resume
```

Only pages actually touched consume physical memory. Unused code paths and cold
data never fault in.

**Pitfall ▸** "My process RSS is tiny but VSZ is huge" is normal — VSZ counts
*mapped* virtual bytes including not-yet-faulted pages and `mmap()` reservations.

---

## 3.1.4 Page faults: minor vs major

![Page fault handling flow](figures/page-fault.svg)

A **page fault** is not always a crash. It is the CPU trapping to the kernel when
the MMU cannot resolve an access:

```
   CPU access to virtual addr
        │
        ├─ TLB hit + present page     → no fault, nanoseconds
        │
        └─ not present / protection     → #PF exception → do_page_fault()
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    ▼                         ▼                         ▼
              minor fault               major fault              segfault
              (COW, first touch)        (read from disk/swap)    (invalid access)
              ~µs                       ~ms                      SIGSEGV
```

| Type | Cause | Cost | Example |
|------|-------|------|---------|
| **Minor** | Page not in RAM but recoverable | Microseconds | First touch of BSS; COW after `fork()` |
| **Major** | Must read from disk or swap | Milliseconds | Cold start; swapped-out page |
| **Invalid** | No valid mapping or bad perms | Signal | NULL deref; write to read-only text |

> **Under the hood ▸** `do_page_fault()` checks the faulting address against VMAs.
> Valid faults allocate a frame, read from the page cache or swap, or duplicate a
> COW page. Invalid faults deliver **SIGSEGV** (`SIGSEGV`, signal 11).

Monitor faults:

```bash
ps -o min_flt,maj_flt,cmd -p 1234
# min_flt = minor, maj_flt = major since process start
```

---

## 3.1.5 SIGSEGV — when the kernel refuses

**SIGSEGV** means the faulting address has no legitimate mapping or the access
violates permissions (write to read-only, execute non-executable, user access to
kernel-only mapping).

Common causes:

- Dereferencing `NULL` or a wild pointer.
- Stack overflow past the guard region.
- Use-after-free (mapping gone or reused).
- Buffer overrun into an unmapped guard page.

```c
/* guaranteed SIGSEGV on typical Linux */
int *p = NULL;
*p = 42;
```

The default action for SIGSEGV is **terminate + core dump** (if `ulimit -c` allows).
Debug with `gdb ./prog core` or run under Valgrind/ASan.

**Pitfall ▸** A segfault in a **signal handler** (Part 4.2) often means you called
a non-async-signal-safe function like `printf()`. The handler itself faulted.

---

## 3.1.6 Reading /proc/[pid]/maps

`/proc/<pid>/maps` (Part 8.1) lists every VMA. Example line:

```
00400000-00401000 r-xp 00000000 08:01 12345  /bin/cat
│          │       │    │        │    │       └─ pathname (or [heap], [stack], [anon])
│          │       │    │        │    └─ inode
│          │       │    │        └─ device (major:minor)
│          │       │    └─ file offset of this mapping
│          │       └─ r=read w=write x=execute p=private s=shared
└──────────┴─ start-end virtual addresses
```

Special names:

- `[heap]` — brk-managed region (Part 3.2).
- `[stack]` — main thread stack.
- `[vdso]` — kernel-provided user-space helpers (time, syscall fast paths).
- `[anon]` — anonymous `mmap()` with no file backing.

```bash
grep heap /proc/self/maps
grep '\.so' /proc/self/maps | head    # loaded shared libraries
```

**Trade-offs ▸** `/proc/pid/maps` is read-only introspection — no syscall needed
beyond `open`/`read` on the procfs file. It is the first tool when debugging
mysterious crashes or unexpected mappings from JITs and allocators.

---

## 3.1.7 A minimal maps dumper

```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(void) {
    char path[64];
    snprintf(path, sizeof path, "/proc/%d/maps", getpid());

    FILE *f = fopen(path, "r");
    if (!f) {
        perror("fopen /proc/self/maps");
        return 1;
    }

    char line[512];
    while (fgets(line, sizeof line, f)) {
        /* print only anonymous or heap regions as a demo filter */
        if (strstr(line, "[heap]") || strstr(line, "[anon") || strstr(line, "[stack]"))
            fputs(line, stdout);
    }

    if (ferror(f)) {
        perror("fgets");
        fclose(f);
        return 1;
    }
    fclose(f);
    return 0;
}
```

Compile and compare before/after `malloc(1 << 20)` to see heap or mmap growth.

---

## Summary

- Each process has its own virtual address space; segments (text, data, BSS, heap,
  mmap, stack) are **VMAs** the kernel maintains separately from physical RAM.
- The MMU translates virtual addresses via **page tables** in fixed-size pages
  (usually 4 KiB); accesses to unmapped or protected pages trap to the kernel.
- **Demand paging** faults in pages on first use — minor faults are cheap, major
  faults hit disk or swap.
- Invalid faults become **SIGSEGV**; `/proc/<pid>/maps` shows every mapping with
  permissions and backing file.
- `fork()` duplicates the page table metadata with COW (Part 1.2); `brk()` and
  `mmap()` grow the space (Parts 3.2–3.3).

Next: [3.2 — brk() & the heap](02-brk-and-heap.md)
