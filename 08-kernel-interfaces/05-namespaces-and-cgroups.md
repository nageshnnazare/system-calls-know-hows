# 8.5 — Namespaces & cgroups: How Containers Work

A "container" is not magic — it is an ordinary process with **extra isolation**
(namespaces) and **resource accounting/limits** (cgroups), optionally wrapped by
`seccomp` (Part 8.6) and capabilities. Docker, containerd, and runc orchestrate the
same syscalls you can invoke from C: `clone()` with `CLONE_NEW*`, `unshare()`,
`setns()`, and cgroup filesystem writes. Part 1.2 introduced `fork`/`clone`; this
chapter completes the picture.

---

## 8.5.1 Namespaces: what each one hides

![Linux namespaces: PID, NET, MNT, UTS, IPC, USER, cgroup, time](figures/namespaces.svg)

```
   global Linux host                    container view
   ─────────────────                    ───────────────
   PID 1 systemd                        PID 1 = container init (thinks it's alone)
   eth0, docker0, lo                    eth0 only (NET ns)
   / on host                            / on container rootfs (MNT ns)
   hostname host.example                hostname myapp (UTS ns)
   SysV IPC keys                        separate IPC objects (IPC ns)
   UID 0 root on host                   UID 0 mapped to 100000 (USER ns)
```

| namespace | flag | isolates |
|-----------|------|----------|
| Mount (MNT) | `CLONE_NEWNS` | mount points, `/` tree |
| UTS | `CLONE_NEWUTS` | hostname, domainname |
| IPC | `CLONE_NEWIPC` | SysV IPC, POSIX mq names |
| PID | `CLONE_NEWPID` | process ID numbers |
| Network (NET) | `CLONE_NEWNET` | interfaces, routes, iptables |
| User (USER) | `CLONE_NEWUSER` | UID/GID mappings |
| cgroup | `CLONE_NEWCGROUP` | cgroup root view |
| Time | `CLONE_NEWTIME` | boottime/monotonic offsets (5.6+) |

> **Under the hood ▸** Each namespace type is a refcounted kernel object; tasks point
> at namespace structs. `clone`/`unshare` create or join views; `/proc/PID/ns/*`
> symlinks identify namespace inodes.

---

## 8.5.2 clone, unshare, setns

> **The call ▸**
> ```c
> #define _GNU_SOURCE
> #include <sched.h>
>
> int clone(int (*fn)(void *), void *stack, int flags, void *arg, ...);
> int unshare(int flags);
> int setns(int fd, int nstype);
> ```

`unshare(CLONE_NEWUTS)` moves **calling thread** into fresh namespace(s). `setns`
joins an existing ns via fd from `/proc/PID/ns/uts`. `clone` with flags creates
child already in new ns(s).

Docker/runc roughly:

```
   runc create
     ├─ unshare/clone NEWNS, NEWUTS, NEWIPC, NEWNET, NEWPID, NEWUSER
     ├─ pivot_root / bind mount rootfs
     ├─ write UID/GID maps (USER ns)
     ├─ join cgroup (Part 8.5.4)
     ├─ seccomp filter (Part 8.6)
     └─ exec container entrypoint
```

Part 1.2: `fork()` ≡ `clone` without sharing flags; containers use `clone` with
many `CLONE_NEW*`.

---

## 8.5.3 Minimal unshare example

```c
#define _GNU_SOURCE
#include <errno.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/utsname.h>
#include <sys/wait.h>
#include <unistd.h>

#define STACK (1024 * 1024)

static int child(void *arg) {
    (void)arg;
    if (sethostname("container", 10) == -1) {
        perror("sethostname");
        return 1;
    }

    struct utsname uts;
    if (uname(&uts) == -1) {
        perror("uname");
        return 1;
    }
    printf("child hostname: %s (pid %d)\n", uts.nodename, getpid());
    return 0;
}

int main(void) {
    struct utsname before;
    if (uname(&before) == -1) { perror("uname"); return 1; }
    printf("before: %s (pid %d)\n", before.nodename, getpid());

    char *stack = malloc(STACK);
    if (!stack) { perror("malloc"); return 1; }

    int flags = CLONE_NEWUTS | SIGCHLD;
    pid_t pid = clone(child, stack + STACK, flags, NULL);
    if (pid == -1) {
        perror("clone");
        free(stack);
        return 1;
    }

    if (waitpid(pid, NULL, 0) == -1)
        perror("waitpid");

    if (uname(&before) == -1) { perror("uname"); return 1; }
    printf("after:  %s (host unchanged)\n", before.nodename);

    free(stack);
    return 0;
}
```

Build: `gcc -Wall -o unshare_demo unshare_demo.c`. Needs `CAP_SYS_ADMIN` for some
namespace combos; `CLONE_NEWUTS` alone often works unprivileged.

**Pitfall ▸** `CLONE_NEWPID` only takes effect in **children** of the unshare/clone
caller — the first process in a new PID ns still sees host PIDs until it forks.

---

## 8.5.4 cgroups v2 — unified hierarchy

cgroups **account and limit** resources: CPU, memory, I/O, pids.

```
   /sys/fs/cgroup/                    (cgroup v2 unified tree)
   ├── cgroup.controllers             cpu memory io pids ...
   ├── system.slice/
   │   └── docker-abc.scope/
   │       ├── cgroup.procs           PIDs in this group
   │       ├── memory.max             hard memory cap
   │       ├── cpu.max                bandwidth quota
   │       └── pids.max               max processes
   └── user.slice/...
```

Controllers (v2):

| controller | limits |
|------------|--------|
| `cpu` | weight, max bandwidth (`cpu.max`) |
| `memory` | `memory.max`, swap, OOM policy |
| `io` | wbps/rbps throttling |
| `pids` | process count cap |

Join a cgroup by writing PID to `cgroup.procs`:

```c
#include <fcntl.h>
#include <stdio.h>
#include <unistd.h>

static int join_cgroup(const char *path, pid_t pid) {
    char procs[256], line[32];
    snprintf(procs, sizeof procs, "%s/cgroup.procs", path);
    snprintf(line, sizeof line, "%d\n", pid);

    int fd = open(procs, O_WRONLY);
    if (fd == -1) return -1;
    ssize_t n = write(fd, line, strlen(line));
    close(fd);
    return (n > 0) ? 0 : -1;
}
```

> **Under the hood ▸** Each cgroup is a `css_set` linking tasks to controller
> state. OOM killer uses cgroup memory pressure; CPU scheduler uses cgroup weights.

Part 8.1 `/proc/[pid]/cgroup` shows a process's cgroup path.

---

## 8.5.5 How Docker/runc combine them

```
   docker run nginx
        │
        ▼
   containerd ──▶ runc
        │
        ├─ namespaces: pid, net, mnt, uts, ipc, (user)
        ├─ cgroups v2: memory.max, cpu.max, pids.max
        ├─ capabilities: drop most, keep NET_BIND_SERVICE etc.
        ├─ seccomp: default Docker profile (~300 allowed syscalls)
        └─ rootfs: overlayfs mount (Part 2.7 VFS)
```

The running container is **one or more processes** on the host kernel — not a VM.
`docker exec` calls `setns` into existing namespaces.

**Trade-offs ▸** Namespaces isolate view, not cost — a containerized fork bomb still
consumes host CPU until the **pids** controller stops it. Memory limits trigger OOM
kill inside the cgroup, not necessarily protecting host if misconfigured.

---

## 8.5.6 USER namespace and ID maps

Unprivileged containers map container root (UID 0) to unprivileged host UID:

```
   /proc/PID/uid_map:
   0  100000  1        # container 0 → host 100000
   1  100001  65535
```

Write maps once per USER ns. Enables root-in-container without host root for many
operations — but `/proc`, device nodes, and mounts still gate real privilege.

---

## Summary

- Namespaces (PID, NET, MNT, UTS, IPC, USER, cgroup, time) give processes isolated
  views of IDs, filesystem, network, and hostname.
- `clone(CLONE_NEW*)`, `unshare`, and `setns` create or join namespaces; containers
  are processes plus these syscalls, not separate kernels.
- cgroups v2 unify resource control under `/sys/fs/cgroup` — CPU, memory, I/O, pids.
- Docker/runc stack namespaces, cgroups, seccomp, and capabilities into the familiar
  `docker run` workflow.

Next: [8.6 — seccomp & Syscall Security](06-seccomp-and-security.md)
