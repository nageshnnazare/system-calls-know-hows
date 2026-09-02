# 3.2 — brk() & the Heap

The **heap** is the upward-growing region between the BSS and the mmap arena. Its
upper bound — the **program break** — is moved by `brk()`/`sbrk()`. You almost
never call these directly; **glibc `malloc()`** uses them for small allocations and
switches to `mmap()` for large ones (Part 3.3). Understanding the break is still
essential for debugging memory growth, fragmentation, and OOM behaviour.

---

## 3.2.1 The program break

```
   low addr
   ┌──────────┐
   │  text    │
   │  data    │
   │  BSS     │
   ├──────────┤  ◀── end of BSS (fixed at load)
   │  heap    │      malloc's small blocks live here
   │    ▲     │
   │    │ brk grows upward
   ├──────────┤  ◀── program break (current brk)
   │  (gap)   │
   │  mmap    │      libraries, large mmap allocs
   │  stack   │
   └──────────┘
```

After `execve()`, the kernel sets an initial break just past BSS. Each successful
`brk(new_end)` extends the `[heap]` VMA in `/proc/self/maps` (Part 3.1).

> **The call ▸**
> ```c
> #include <unistd.h>
>
> int brk(void *addr);
> void *sbrk(intptr_t increment);
> ```
> **`brk(addr)`** — set break to `addr` (must be page-aligned internally; kernel
> rounds). Returns **0** on success, **-1** on error.
> **`sbrk(incr)`** — move break by `incr` bytes; returns **previous** break
> address, or `(void *)-1` with `errno` set.
>
> **Note:** `sbrk()` is deprecated in POSIX.1-2001 but still widely used inside
> libc. Prefer `malloc()` in application code.

**Errors ▸**

| `errno` | When |
|---------|------|
| `ENOMEM` | Insufficient virtual memory; would collide with mmap region |
| `EINVAL` | Requested address invalid (below current break or misaligned policy) |

---

## 3.2.2 What brk() actually does in the kernel

```
   brk(new_end)
        │
        ├─ new_end <= current break  → shrink heap VMA (uncommon; may not release RAM)
        │
        └─ new_end > current break   → extend [heap] VMA, zero-fill new pages
              │
              └─ if heap would hit mmap region → fail ENOMEM
```

> **Under the hood ▸** `sys_brk()` adjusts the `start_brk`/`brk` fields in
> `mm_struct` and merges/extents the heap VMA. Physical pages are allocated on
> **first write** (demand paging, Part 3.1) — extending brk does not immediately
> consume RAM equal to the virtual extension.

**Pitfall ▸** `free()` does **not** shrink the break. Freed small blocks return to
libc's free lists; the `[heap]` VMA size in maps stays at the high-water mark until
the process exits.

---

## 3.2.3 How malloc() uses brk vs mmap

glibc's allocator (ptmalloc) follows a rough policy:

```
   malloc(size)
        │
        ├─ size <= mmap threshold (default ~128 KiB on glibc)
        │       → carve from heap arena(s) via brk/sbrk internally
        │
        └─ size > threshold
                → anonymous mmap(..., MAP_PRIVATE|MAP_ANONYMOUS)
                   separate mapping, munmap on free
```

Check your system's threshold:

```bash
mallinfo   # legacy; or inspect glibc tunables
# M_MMAP_THRESHOLD via mallopt(3)
```

| Path | Pros | Cons |
|------|------|------|
| **brk/heap** | Fast for small, frequent allocs; good locality | Fragmentation; rarely returns memory to OS |
| **mmap** | Large blocks returned on free; isolated | Syscall per mapping; page-rounded overhead |

**Trade-offs ▸** A long-running server that allocates many varied small sizes can
**fragment** the heap — RSS stays high even if `malloc` statistics show plenty of
free space. Tools: `malloc_info()`, `jemalloc`/`tcmalloc`, or periodic restart.

---

## 3.2.4 Fragmentation mechanics

```
   heap after many alloc/free cycles:

   [used][free 200B][used][free 8K][used][free 400B]...
                              │
                              └─ brk cannot shrink past last used page
```

External fragmentation: free chunks exist but none satisfy a new request → libc
extends brk again. Internal fragmentation: allocator rounds sizes to alignment
(16 bytes on 64-bit).

**Systems ▸** `strace -e brk,mmap,munmap ./your_server` shows whether growth is
brk steps or anonymous mmaps — the first step in "why is VSZ climbing?"

---

## 3.2.5 glibc arenas (overview)

In multi-threaded programs, a single heap lock would serialize every `malloc`.
glibc creates **arenas** — each arena owns a heap extent (via brk or mmap):

```
   thread 1 ──▶ arena 0 ──▶ brk heap
   thread 2 ──▶ arena 1 ──▶ mmap'd heap chunk
   thread 3 ──▶ arena 0 (if free)
        ...
   up to M_ARENA_MAX (default: 8 × CPU cores on 64-bit)
```

> **Under the hood ▸** Arenas reduce lock contention but **increase** virtual memory
> — each arena may hold unused free lists. Part 5.1 covers threads; Part 5.5
> covers futex-based locking inside libc.

Tune with:

```c
#include <malloc.h>
mallopt(M_ARENA_MAX, 4);   /* call before much allocation, e.g. early main */
```

---

## 3.2.6 Why you rarely call brk directly

- **Portability:** `mmap()` is the POSIX-endorsed way to obtain memory mappings.
- **Alignment & metadata:** `malloc` manages chunk headers, alignment, and
  `free()` coalescing — raw brk gives you a byte range and nothing else.
- **Thread safety:** Direct brk bypasses arena locking → corruption with pthreads.
- **ASLR & security:** libc and the loader expect to own break management.

Legitimate uses: libc itself, some embedded allocators, historical code, debugging
(`sbrk(0)` to read current break).

---

## 3.2.7 Observing the break (debugging only)

```c
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int main(void) {
    void *break_before = sbrk(0);
    if (break_before == (void *)-1) {
        perror("sbrk(0)");
        return 1;
    }
    printf("break before alloc: %p\n", break_before);

    void *p = malloc(64 * 1024);
    if (!p) {
        perror("malloc");
        return 1;
    }

    void *break_after = sbrk(0);
    if (break_after == (void *)-1) {
        perror("sbrk(0)");
        free(p);
        return 1;
    }
    printf("break after 64KiB malloc: %p (delta %td bytes)\n",
           break_after, (char *)break_after - (char *)break_before);

    free(p);
    return 0;
}
```

Compare with `malloc(512 * 1024)` — above the mmap threshold you may see **no**
brk movement; instead a new `[anon]` mapping appears in maps.

---

## Summary

- The **program break** bounds the heap; `brk()`/`sbrk()` extend or shrink it,
  backed by a `[heap]` VMA and demand-paged physical memory.
- **glibc malloc** serves small requests from brk-backed **arenas** and large ones
  via anonymous `mmap()` — see Part 3.3.
- **Fragmentation** and arena proliferation can inflate RSS/VSZ even after `free()`.
- Application code should use `malloc()`/`free()` (or modern allocators), not raw
  `brk()`.
- Inspect growth with `/proc/self/maps`, `sbrk(0)`, and `strace -e brk,mmap`.

Next: [3.3 — mmap(): mapping files & anonymous memory](03-mmap.md)
