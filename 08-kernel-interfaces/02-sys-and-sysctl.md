# 8.2 — /sys & sysctl

Where `/proc` mixes process introspection with tunables, **`/sys`** (sysfs) exposes
a **structured object tree** of devices, drivers, and kernel subsystems — one file
per attribute, typed and documented in-tree. **`sysctl`** is the programmatic and
`/proc/sys` filesystem interface for **kernel parameters** at runtime. Together they
are how you inspect hardware and tune behavior without recompiling the kernel.

---

## 8.2.1 sysfs: the kernel object tree

```
   /sys/
   ├── block/sda/          size, queue, stat, ...
   ├── class/net/eth0/     address, operstate, statistics/
   ├── bus/pci/devices/    PCI topology
   ├── fs/ext4/            filesystem knobs
   ├── kernel/             debugging, notes
   └── devices/            physical device hierarchy
```

Each file typically maps to one **`struct kobject` attribute** — `show` on read,
`store` on write:

```
   cat /sys/class/net/lo/operstate  →  "unknown"
   echo 1 > /sys/block/sda/queue/nomerges  →  write path (root)
```

> **Under the hood ▸** sysfs is built on kobject/kset infrastructure. udev (systemd-
> udevd) listens to netlink and creates `/dev` nodes based on sysfs paths — the
> userspace half of hotplug.

**Trade-offs ▸** sysfs paths are stable enough for scripts but can shift with driver
renames. Prefer udev properties or `/dev/disk/by-*` for disk identity in production.

---

## 8.2.2 Key sysfs locations

| path | use |
|------|-----|
| `/sys/class/net/` | network interfaces |
| `/sys/block/` | block devices + queue tunables |
| `/sys/devices/system/cpu/` | CPU online, cpufreq |
| `/sys/fs/cgroup/` | cgroup v2 hierarchy (Part 8.5) |
| `/sys/kernel/tracing/` | ftrace (Part 8.4) |
| `/sys/module/` | loaded modules, parameters |

Example — read link speed (if driver exposes it):

```bash
cat /sys/class/net/eth0/speed
```

Same mechanics as procfs: `open`, `read`, `write`, `close` (Part 2.2).

---

## 8.2.3 The sysctl() interface

> **The call ▸**
> ```c
> #include <sys/sysctl.h>
>
> int sysctl(int *name, int nlen, void *oldval, size_t *oldlenp,
>            void *newval, size_t newlen);
> ```

`name` is an OID array — e.g. `{ CTL_KERN, KERN_VERSION }`. Reads and writes kernel
variables in one syscall. **Deprecated in glibc** for new code — prefer `/proc/sys`
file I/O, which is clearer and auditable.

Legacy example (may fail on modern glibc without `_GNU_SOURCE` / linkage):

```c
/* prefer /proc/sys file I/O instead */
int mib[] = { CTL_KERN, KERN_VERSION };
char buf[256];
size_t len = sizeof buf;
if (sysctl(mib, 2, buf, &len, NULL, 0) == -1)
    perror("sysctl");
else
    printf("%.*s\n", (int)len, buf);
```

---

## 8.2.4 /proc/sys — the filesystem face of sysctl

Every tunable appears as a file:

```
   /proc/sys/vm/swappiness          →  0–200, swap aggressiveness
   /proc/sys/net/core/somaxconn     →  listen backlog cap (Part 6.2)
   /proc/sys/fs/file-max            →  system-wide open file limit
   /proc/sys/kernel/pid_max         →  max PID value
```

Read/write via normal I/O:

```c
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int read_proc_sys(const char *rel, char *out, size_t outsz) {
    char path[256];
    snprintf(path, sizeof path, "/proc/sys/%s", rel);

    int fd = open(path, O_RDONLY);
    if (fd == -1) return -1;

    ssize_t n = read(fd, out, outsz - 1);
    close(fd);
    if (n <= 0) return -1;
    out[n] = '\0';
    /* trim trailing newline */
    if (n > 0 && out[n - 1] == '\n') out[n - 1] = '\0';
    return 0;
}

static int write_proc_sys(const char *rel, const char *val) {
    char path[256];
    snprintf(path, sizeof path, "/proc/sys/%s", rel);

    int fd = open(path, O_WRONLY);
    if (fd == -1) return -1;

    size_t len = strlen(val);
    ssize_t n = write(fd, val, len);
    close(fd);
    return (n == (ssize_t)len) ? 0 : -1;
}

int main(void) {
    char buf[64];
    if (read_proc_sys("vm/swappiness", buf, sizeof buf) == 0)
        printf("swappiness=%s\n", buf);

    /* writing requires CAP_SYS_ADMIN in most namespaces */
    if (write_proc_sys("net/core/somaxconn", "4096") == -1)
        perror("write somaxconn");

    return 0;
}
```

**Errors ▸**

| errno | when |
|-------|------|
| `EACCES` | insufficient privilege to write |
| `EPERM` | namespaced restriction (container) |
| `EINVAL` | value out of range |
| `ENOENT` | unknown sysctl path |

---

## 8.2.5 sysctl.conf and persistence

`/etc/sysctl.conf` and `/etc/sysctl.d/*.conf` apply at boot via `systemd-sysctl`
or `sysctl -p`:

```
# /etc/sysctl.d/99-custom.conf
vm.swappiness = 10
net.core.somaxconn = 4096
fs.file-max = 2097152
```

```bash
sysctl -w vm.swappiness=10          # runtime
sysctl -a | grep somaxconn            # list all
```

Runtime writes to `/proc/sys` are **not** persistent across reboot unless saved to
conf files.

---

## 8.2.6 Worked examples

**vm.swappiness** (0–200): how eagerly the kernel swaps anonymous pages vs dropping
file cache. Low values favor keeping app memory resident — common on database servers.

**net.core.somaxconn**: upper bound for `listen(backlog)` (Part 6.2). Your app's
backlog and this sysctl interact — kernel accepts min(request, somaxconn).

**fs.file-max**: system-wide open file ceiling. Per-process limits still apply via
`getrlimit(RLIMIT_NOFILE)` (Part 1.6) — both must allow your workload.

```
   effective fd capacity = min(
       RLIMIT_NOFILE soft limit per process,
       fs.file-max system-wide,
       practical memory for struct file
   )
```

**Pitfall ▸** Tuning `net.ipv4.tcp_*` without measuring — defaults evolved over
decades. Change one knob, benchmark, document.

---

## 8.2.7 sysfs vs procfs vs sysctl

```
   ┌─────────────┬──────────────────────┬─────────────────────┐
   │             │ procfs               │ sysfs               │
   ├─────────────┼──────────────────────┼─────────────────────┤
   │ Focus       │ processes + tunables │ devices + drivers   │
   │ Layout      │ /proc/PID/*          │ /sys/class, block   │
   │ Tunables    │ /proc/sys/*          │ per-driver attrs    │
   └─────────────┴──────────────────────┴─────────────────────┘

   sysctl / /proc/sys  →  kernel parameters (vm, net, fs, kernel)
   sysfs               →  hardware + driver object model
```

Part 8.1 for process introspection; this chapter for machine tuning and device state.

---

## Summary

- sysfs (`/sys`) exposes a hierarchical view of kernel objects — devices, block
  queues, network interfaces — as small attribute files.
- sysctl tunables appear under `/proc/sys`; read/write via normal file I/O is
  preferred over the legacy `sysctl()` syscall wrapper.
- `/etc/sysctl.d/` persists runtime tunables (`vm.swappiness`, `net.core.somaxconn`,
  `fs.file-max`) across reboot.
- Effective limits combine per-process rlimits and system-wide sysctl ceilings.

Next: [8.3 — ioctl()](03-ioctl.md)
