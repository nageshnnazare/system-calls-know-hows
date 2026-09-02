# 8.1 — The /proc Filesystem

`/proc` looks like a directory tree on disk. It is not. Every path is **synthesized
on read** (and sometimes on write) by kernel handlers — a text API to live kernel
state. `ps`, `top`, `free`, and `lsof` are thin parsers over `/proc`. Part 0.5
established that "everything is a file"; procfs is the clearest proof for process and
system introspection without custom kernel modules.

---

## 8.1.1 procfs is not on disk

![The /proc filesystem: virtual tree synthesized by kernel handlers](figures/proc-fs.svg)

```
   ls /proc/1234/status
        │
        ▼
   openat("/proc/1234/status", O_RDONLY)   ← normal syscall
        │
        ▼
   VFS → procfs inode → kernel formats struct task_struct fields → copy to user
        │
        ▼
   read() returns text like "Name:\tbash\nState:\tS (sleeping)\n..."
```

No persistent storage. Reboot clears nothing because nothing was stored. inode
numbers and content can change between reads as the kernel state changes.

> **Under the hood ▸** procfs registers with the VFS (Part 2.7). Each file type has
> `seq_show` or `read` handlers that walk kernel data structures and `sprintf` into
> your buffer. Writes hit different handlers — often permission-checked tunables.

**Trade-offs ▸** Human-readable, script-friendly, stable enough for decades of
tooling. Not a high-performance binary API — parsing text costs CPU. Race-prone for
atomic snapshots (read `stat` twice, PID may have exited).

---

## 8.1.2 /proc/[pid]/ — per-process entries

For each live process `PID`:

| path | content |
|------|---------|
| `status` | human summary: name, state, uid/gid, vm peak, threads |
| `stat` | one-line machine parse: state, utime, stime, vsize, rss, ... |
| `statm` | memory page counts |
| `maps` | memory mappings (Part 3.1) — VMA list with permissions |
| `smaps` | maps + per-mapping RSS/PSS detail |
| `fd/` | symlinks `0`→`/dev/pts/0`, `3`→`socket:[...]` |
| `fdinfo/N` | offset, flags, mount id per fd |
| `cmdline` | NUL-separated argv (may be empty for kernel threads) |
| `environ` | `KEY=value\0...` (root or same uid to read) |
| `limits` | soft/hard rlimits (Part 1.6) |
| `cwd`, `exe`, `root` | symlinks to working dir, binary, chroot root |
| `task/` | thread subdirs (`/proc/PID/task/TID/...`) |

Reading `status`:

```c
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int read_proc_status(pid_t pid) {
    char path[64];
    snprintf(path, sizeof path, "/proc/%d/status", pid);

    int fd = open(path, O_RDONLY);
    if (fd == -1) { perror("open"); return -1; }

    char buf[4096];
    ssize_t n = read(fd, buf, sizeof buf - 1);
    if (n == -1) { perror("read"); close(fd); return -1; }
    buf[n] = '\0';

    char *line = strstr(buf, "VmRSS:");
    if (line) fputs(line, stdout);

    close(fd);
    return 0;
}
```

**Pitfall ▸** `stat` is one line — fields after `(comm)` contain spaces inside
parentheses. Parsers must skip `(...)` before tokenizing. Use `man proc_pid_stat`.

---

## 8.1.3 /proc/[pid]/maps and debugging memory

```
   00400000-00401000 r-xp ... /bin/cat          ← executable text
   00600000-00601000 rw-p ... [heap]             ← brk heap
   7f....-7f.... rw-p ... [stack]
   7f....-7f.... r--p ... /lib/libc.so.6
```

Part 3.1 virtual layout, visible live. `pmap` and `gdb` read this. `smaps` adds
`Rss`, `Pss`, `Shared_Clean` per line — essential for memory leak hunts.

---

## 8.1.4 /proc/[pid]/fd/ and lsof

Each numeric name is a **duplicate** of the process's fd table entry (Part 0.5):

```
   /proc/1234/fd/3 → socket:[12345]
   /proc/1234/fd/4 → /var/log/app.log
```

`lsof` walks `/proc/*/fd` and decodes socket inodes via `/proc/net/tcp`. You can
do the same in C with `readlink`.

**Errors ▸**

| errno | when |
|-------|------|
| `EACCES` | inspect another user's process without privilege |
| `ENOENT` | PID exited between listing and open |
| `EINVAL` | read on `/proc/self/fd/N` incorrectly |

---

## 8.1.5 Global /proc files

| path | exposes |
|------|---------|
| `meminfo` | system memory: MemTotal, MemFree, Cached, Swap... |
| `cpuinfo` | per-CPU model, flags, bogomips |
| `loadavg` | 1/5/15 min load + runnable/total entities |
| `stat` | aggregate CPU ticks, context switches, boot time |
| `uptime` | seconds since boot, idle sum |
| `sys/` | sysctl tunables (Part 8.2) |
| `self` | symlink to calling process's `/proc/PID` |

`free` reads `meminfo`. `uptime` reads `uptime` + `loadavg`. `top` combines
`/proc/stat`, `/proc/[pid]/stat`, and `meminfo`.

Parse `meminfo` pattern:

```c
static long parse_meminfo_kb(const char *key) {
    FILE *f = fopen("/proc/meminfo", "r");
    if (!f) return -1;
    char line[256], unit[16];
    long val = -1;
    while (fgets(line, sizeof line, f)) {
        if (sscanf(line, "%*s %ld %15s", &val, unit) >= 1 &&
            strstr(line, key)) {
            fclose(f);
            return val;
        }
    }
    fclose(f);
    return -1;
}
```

---

## 8.1.6 Writing to /proc for tunables

Many `/proc/sys/*` and some `/proc` files accept writes (Part 8.2). Example —
trigger sysrq (if enabled):

```bash
echo 1 > /proc/sys/kernel/sysrq   # needs CAP_SYS_ADMIN
```

Process-specific writes are rarer; most tuning is global. **Pitfall ▸** Writing
wrong values to tunables (`vm.overcommit_memory`, `net.ipv4.*`) causes production
incidents — always validate via documentation and staging.

`/proc/sys/fs/file-max` read/write controls system-wide fd ceiling — relates to
Part 0.5 descriptor limits.

---

## 8.1.7 How tools map to procfs

```
   ps aux     →  /proc/*/stat, status, cmdline
   top        →  /proc/stat + /proc/*/stat (repeat)
   free -m    →  /proc/meminfo
   pgrep      →  /proc/*/cmdline
   cat /proc/cpuinfo  →  driver enumeration, affinity tools
```

All of these are **`open`/`read`/`close`** — no special syscall beyond normal
file I/O (Part 2.1–2.2). That is why procfs integration is universal in C.

---

## Summary

- `/proc` is a virtual filesystem: kernel generates content on read from live
  structures — nothing persists on disk.
- `/proc/[pid]/{status,stat,maps,fd,cmdline,limits}` expose per-process state;
  `/proc/{meminfo,cpuinfo,loadavg,stat}` expose machine-wide metrics.
- Standard tools (`ps`, `top`, `lsof`, `free`) are procfs parsers built on normal
  file I/O syscalls.
- Writable `/proc/sys/*` entries tune kernel behavior — powerful, permission-gated,
  and easy to misuse.

Next: [8.2 — /sys & sysctl](02-sys-and-sysctl.md)
