# 2.6 — Links & Directories

Unix filesystems separate **names** (directory entries) from **inodes** (the
actual file object). `link()` adds another name for the same inode; `symlink()`
creates a name that points to another path. Directories are files whose data is a
list of `(name → inode)` pairs — read with `opendir`/`readdir`, implemented over
`getdents64` in the kernel.

---

## 2.6.1 Names vs inodes

```
   directory "docs"              inode 481516
   ┌─────────────────┐          ┌──────────────────┐
   │ report.txt ─────┼─────────▶│ data blocks      │
   │ draft.txt ──────┼──┐       │ mode, size, ...  │
   └─────────────────┘  │       │ link count = 2   │
                        └──────▶│ (same inode)     │
                                └──────────────────┘

   symlink "latest" ──▶ "report.txt"   (separate inode; content is a path string)
```

The **inode** holds metadata and block pointers. The **filename** is just a hard
link — a directory entry with a reference count on the inode.

> **Under the hood ▸** `unlink("draft.txt")` removes one directory entry and
> decrements `st_nlink`. When `st_nlink` hits 0 and no process holds the file
> open, the inode and blocks are reclaimed.

---

## 2.6.2 Hard links: link() and unlink()

> **The call ▸**
> ```c
> #include <unistd.h>
> int link(const char *oldpath, const char *newpath);
> int unlink(const char *pathname);
> int rename(const char *oldpath, const char *newpath);
> ```

Hard links:

- Same filesystem only (`EXDEV` across mount points).
- Cannot link directories (except `.` / `..` created by the kernel) — prevents
  directory cycles.
- All hard links equal — no "original" vs "alias."

**Trade-offs ▸** Hard links give cheap snapshots of the same bytes (no duplicate
storage). Editors that save via "write temp + rename" rely on `rename()` atomicity
(see below).

---

## 2.6.3 Symbolic links: symlink() and readlink()

> **The call ▸**
> ```c
> #include <unistd.h>
> ssize_t readlink(const char *path, char *buf, size_t bufsiz);
> ssize_t readlinkat(int dirfd, const char *path, char *buf, size_t bufsiz);
> int symlink(const char *target, const char *linkpath);
> ```

Symlinks store a **path string** in the inode. Resolution happens at open time
(walk path components; when you hit a symlink, substitute and continue — with
limits on depth → `ELOOP`).

```
   open("/tmp/latest")  →  read symlink target "report.txt"
                         →  resolve relative to /tmp/
                         →  open resulting path
```

Use `lstat()` (Part 2.5) to inspect symlinks without following them.
`readlink()` does not NUL-terminate if buffer too small — size carefully.

---

## 2.6.4 rename() atomicity

On the same filesystem, `rename(old, new)` is **atomic** with respect to crash
and concurrent observers:

```
   replace existing "config":   rename("config.new", "config")
   readers see old OR new       never a torn/partial file
```

If `new` exists, it is replaced (subject to directory semantics). Cross-device
rename fails with `EXDEV` — use copy + unlink instead.

---

## 2.6.5 Directories: mkdir, rmdir, reading entries

> **The call ▸**
> ```c
> #include <sys/stat.h>
> int mkdir(const char *path, mode_t mode);
> int rmdir(const char *path);   /* directory must be empty */

> #include <dirent.h>
> DIR *opendir(const char *name);
> struct dirent *readdir(DIR *dirp);
> int closedir(DIR *dirp);
> ```

`struct dirent` provides `d_name` (and on Linux `d_type` hint — not always
reliable; `stat` if you need certainty).

> **Under the hood ▸** glibc `readdir()` loops on the **`getdents64`** syscall,
> filling a buffer with multiple `(ino, type, name)` records per trap — far
> cheaper than one syscall per name.

Every directory contains at least:

```
   .       inode of this directory
   ..      inode of parent directory
```

**Pitfall ▸** `readdir` order is **unsorted** and may skip or repeat names if the
directory mutates during iteration — snapshot with `openat` + repeated `getdents`
or sort names after a full pass if you need consistency.

---

## 2.6.6 Unlinking an open file

Classic Unix behaviour:

```
   fd = open("temp", O_RDWR);
   unlink("temp");          /* name gone from directory; st_nlink → 0 */
   write(fd, ...);          /* still works — inode alive via open fd ref */
   close(fd);               /* now inode reclaimed, blocks freed
```

Used for secure temp files (no pathname for other users to open) and lazy delete
("delete on close"). Disk space is not freed until the last fd closes — a common
"disk full but I deleted the log" ops issue.

```
   process holds fd open ──▶ deleted file still consumes st_size on disk
   lsof +L1                 shows such files
```

---

## 2.6.7 Example: walk a directory tree (non-recursive)

```c
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static int list_dir(const char *dirpath) {
    DIR *d = opendir(dirpath);
    if (!d) {
        perror("opendir");
        return -1;
    }

    struct dirent *ent;
    while ((ent = readdir(d)) != NULL) {
        if (strcmp(ent->d_name, ".") == 0 || strcmp(ent->d_name, "..") == 0)
            continue;

        char path[4096];
        int n = snprintf(path, sizeof path, "%s/%s", dirpath, ent->d_name);
        if (n < 0 || (size_t)n >= sizeof path) {
            fprintf(stderr, "path too long\n");
            closedir(d);
            return -1;
        }

        struct stat sb;
        if (lstat(path, &sb) == -1) {
            perror(path);
            continue;
        }

        if (S_ISDIR(sb.st_mode))
            printf("[dir]  %s/\n", path);
        else if (S_ISLNK(sb.st_mode))
            printf("[lnk]  %s\n", path);
        else if (S_ISREG(sb.st_mode))
            printf("[file] %s (%lld bytes)\n", path, (long long)sb.st_size);
        else
            printf("[?]    %s\n", path);
    }

    if (errno) {
        perror("readdir");
        closedir(d);
        return -1;
    }
    if (closedir(d) == -1) {
        perror("closedir");
        return -1;
    }
    return 0;
}

int main(int argc, char *argv[]) {
    if (argc != 2) {
        fprintf(stderr, "usage: %s directory\n", argv[0]);
        return 1;
    }
    return list_dir(argv[1]) == 0 ? 0 : 1;
}
```

**Errors ▸**

| errno | when it happens |
|-------|-----------------|
| `EEXIST` | `mkdir` on existing path |
| `ENOTEMPTY` | `rmdir` on non-empty directory |
| `EISDIR` | `unlink` on directory |
| `EPERM` | Hard link to directory, or immutable flag |
| `EXDEV` | `link` or `rename` across devices |
| `EMLINK` | Too many hard links to file |
| `ENOENT` | Component does not exist |
| `ELOOP` | Symlink loop during resolution |

---

## Summary

- Filenames are directory entries pointing at **inodes**; hard links share an
  inode, symlinks are separate inodes holding a path string.
- `link`/`unlink`/`rename` manipulate names; `rename` is atomic on one filesystem.
- `mkdir`/`rmdir` manage directories; `opendir`/`readdir`/`closedir` read entries
  (kernel: `getdents64`). Every dir has `.` and `..`.
- Unlinking an open file removes the name but data survives until the last
  `close()` — space not freed until then.

Next: [2.7 — The VFS, inodes & "everything is a file"](07-vfs-and-inodes.md)
