# 8.6 — seccomp & Syscall Security

Namespaces hide resources; **seccomp** (secure computing) **filters which syscalls**
a process may invoke. Combined with **capabilities** (splitting traditional root
privilege) and LSMs (AppArmor, SELinux), seccomp is the syscall firewall inside
Chrome sandboxes, systemd services, and default Docker profiles. Part 8.5 placed
containers; this chapter dissects filter mechanics and production patterns.

---

## 8.6.1 seccomp modes

![seccomp BPF filter: syscall number and args inspected, ALLOW/ERRNO/KILL actions](figures/seccomp.svg)

```
   thread invokes SYSCALL
        │
        ▼
   seccomp filter (optional BPF program)
        │
        ├─ ALLOW  ──▶ continue to sys_call_table
        ├─ ERRNO   ──▶ return -EPERM (no kill)
        ├─ KILL    ──▶ SIGSYS, process dies
        ├─ TRAP    ──▶ SIGSYS to tracer (ptrace)
        └─ TRACE   ──▶ notify supervisor (advanced)
```

| mode | set via | behavior |
|------|---------|----------|
| disabled | default | all allowed (subject to DAC/capabilities) |
| strict | `seccomp(SECCOMP_SET_MODE_STRICT)` | only read, write, exit, sigreturn |
| filter | `seccomp(SECCOMP_SET_MODE_FILTER)` | BPF program decides |

Strict mode is legacy — filter mode is what sandboxes use.

> **The call ▸**
> ```c
> #include <linux/seccomp.h>
> #include <sys/prctl.h>
> #include <sys/syscall.h>
>
> int seccomp(unsigned int operation, unsigned int flags, void *args);
> int prctl(int option, unsigned long arg2, ...);
> ```

---

## 8.6.2 seccomp-BPF filters

Filter mode loads a **Berkeley Packet Filter** program evaluated on each syscall:

```
   BPF program inputs:
     seccomp_data {
         int   nr;        /* syscall number */
         __u32 arch;      /* AUDIT_ARCH_X86_64 */
         __u64 args[6];   /* register arguments */
     }
```

Classic pattern:

```
   if nr == read  → ALLOW
   if nr == write → ALLOW
   if nr == exit  → ALLOW
   if nr == openat && args[2] & O_CREAT → ERRNO(EACCES)
   default        → KILL
```

> **Under the hood ▸** The BPF verifier ensures the program terminates and doesn't
> access arbitrary kernel memory. On match, return action code; kernel never reaches
> the real syscall handler for KILL/ERRNO/TRAP.

Install filter:

```c
#include <linux/filter.h>
#include <linux/seccomp.h>
#include <stddef.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <unistd.h>

/* illustrative — production uses libseccomp */
static int install_basic_filter(void) {
    struct sock_filter filter[] = {
        /* load syscall number */
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, nr)),
        /* allow read */
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, SYS_read, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        /* allow write */
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, SYS_write, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        /* allow exit_group */
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, SYS_exit_group, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        /* kill rest */
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_KILL),
    };

    struct sock_fprog prog = {
        .len = (unsigned short)(sizeof filter / sizeof filter[0]),
        .filter = filter,
    };

    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) == -1)
        return -1;

    if (prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &prog) == -1)
        return -1;

    return 0;
}
```

**Pitfall ▸** Forgetting `PR_SET_NO_NEW_PRIVS` before filter — required so a
restricted process can't `exec` a setuid binary and regain full syscalls.

---

## 8.6.3 Filter actions in detail

| action | effect |
|--------|--------|
| `SECCOMP_RET_ALLOW` | syscall proceeds normally |
| `SECCOMP_RET_ERRNO(code)` | fail with specified errno (e.g. `EPERM`) |
| `SECCOMP_RET_KILL` | deliver `SIGSYS`, kill thread/process |
| `SECCOMP_RET_TRAP` | `SIGSYS` to ptrace tracer |
| `SECCOMP_RET_TRACE` | notify seccomp user notifier (supervisor decides) |
| `SECCOMP_RET_LOG` | allow + kernel log (audit) |

`ERRNO` is preferred over `KILL` for compatibility — libc may probe syscalls and
handle failure gracefully.

Argument inspection example (conceptual): deny `openat` unless path is under `/tmp` —
requires **pointer argument inspection** with `SECCOMP_RET_TRAP` + supervisor or
careful `libseccomp` rules (advanced; easy to get wrong).

---

## 8.6.4 libseccomp

Hand-written BPF does not scale. **libseccomp** provides a rule API:

```c
#include <seccomp.h>

scmp_filter_ctx ctx = seccomp_init(SCMP_ACT_KILL);
seccomp_rule_add(ctx, SCMP_ACT_ALLOW, SCMP_SYS(read), 0);
seccomp_rule_add(ctx, SCMP_ACT_ALLOW, SCMP_SYS(write), 0);
seccomp_rule_add(ctx, SCMP_ACT_ALLOW, SCMP_SYS(exit_group), 0);
seccomp_load(ctx);
seccomp_release(ctx);
```

Export human-readable profiles:

```bash
scmp_arch_native | scmp_dump seccomp_profile
```

Docker's default profile allows ~300 syscalls, denies `mount`, `reboot`, `kexec_load`,
etc. — tuned per workload over years of production pain.

---

## 8.6.5 Capabilities overview

Traditional root = all privileges. Linux **capabilities** split them:

```
   CAP_NET_BIND_SERVICE   bind port < 1024
   CAP_SYS_ADMIN          many admin ops (mount, sysctl, ...)
   CAP_SYS_PTRACE         ptrace other processes
   CAP_DAC_OVERRIDE       bypass file permission checks
   ...
```

> **The call ▸**
> ```c
> #include <sys/capability.h>
> int capget(cap_user_header_t hdr, cap_user_data_t data);
> int capset(cap_user_header_t hdr, const cap_user_data_t data);
> ```

Containers drop all caps except a whitelist (`--cap-add`). **seccomp** and
**capabilities** overlap but differ — seccomp blocks syscall *entry*; capabilities
check inside specific syscalls.

`man 7 capabilities` is the authoritative list. Part 8.5: user namespaces map
container "root" without granting host `CAP_SYS_ADMIN`.

---

## 8.6.6 Who uses seccomp

```
   Chrome renderer     strict profile — no filesystem, limited ioctl
   systemd services    SystemCallFilter= in unit files
   Docker / runc       default + custom profiles per image
   Kubernetes          seccompProfile: RuntimeDefault / Localhost
   sshd                minimal filtering on some distros
```

**Systems ▸** strace a sandboxed process (Part 8.4) — `SIGSYS` or `EPERM` on
denied syscalls reveals profile gaps.

Testing filter before deploy:

```bash
systemd-run --scope -p SystemCallFilter=@system-service true
```

---

## 8.6.7 Security layering

```
   effective containment ≈
       namespaces (view isolation)
     + cgroups (resource bounds, Part 8.5)
     + seccomp (syscall surface reduction)
     + capabilities (privilege minimization)
     + LSM (MAC policies on files/sockets)
     + read-only rootfs + no setuid
```

No single layer suffices. seccomp stops `mount`; it does not stop a allowed `write`
to a writable volume — DAC and LSM still matter.

**Errors ▸** (from blocked syscalls)

| errno / signal | when |
|----------------|------|
| `EPERM` / custom | `SECCOMP_RET_ERRNO` action |
| `SIGSYS` | `SECCOMP_RET_KILL` or `TRAP` |
| `EACCES` | capability missing inside allowed syscall |

**Pitfall ▸** Overly tight profiles break glibc initialization (e.g. denying
`openat`, `futex`, `arch_prctl`). Start from `SCMP_ACT_ERRNO`, log, widen — don't
start with KILL.

---

## Summary

- seccomp strict mode allows only read/write/exit; filter mode runs BPF on each
  syscall (`nr` + args) returning ALLOW, ERRNO, KILL, TRAP, or TRACE.
- `PR_SET_NO_NEW_PRIVS` must precede filter install to block privilege escalation
  via setuid exec.
- libseccomp is the practical way to build and deploy profiles; Docker and browsers
  ship curated allow-lists.
- Capabilities split root into fine-grained privileges; seccomp complements caps by
  blocking entire syscall classes at the trap boundary.

Next: [99-reference — System-call cheat sheet](../99-reference/syscall-cheatsheet.md)
