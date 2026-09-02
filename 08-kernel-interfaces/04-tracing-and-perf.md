# 8.4 — Tracing: strace, ftrace, perf & eBPF

When a program misbehaves — wrong syscall order, mystery latency, silent `EACCES` —
you need to **observe** boundary crossings without recompiling. Linux stacks four
complementary tools: **strace/ltrace** (syscall/library trace via ptrace),
**ftrace** (kernel static tracepoints), **perf** (hardware counters + sampling),
and **eBPF** (programmable in-kernel probes). Part 7.5 introduced `strace -c` and
`perf stat`; this chapter maps when each tool wins and what happens under the hood.

---

## 8.4.1 The observability stack

```
   question                          tool
   ────────────────────────────────  ─────────────────────
   "which syscalls, in what order?"  strace
   "which libc calls?"               ltrace
   "kernel function flow?"           ftrace
   "CPU cycles, cache misses?"       perf
   "custom kernel/user probes?"      eBPF (bpftrace, bcc)
```

```
   user program
        │
        │  strace: ptrace stops child at syscall entry/exit
        │  ltrace:  PLT hooks + ptrace
        ▼
   kernel ── ftrace: mcount/tracepoints on syscalls, sched, block
        │
        │  perf: PMU counters + ring buffer samples
        │  eBPF: verified programs on kprobes/tracepoints/maps
        ▼
   analysis (text log, perf report, bpftrace output)
```

---

## 8.4.2 strace and ltrace — ptrace under the hood

> **The call ▸** (ptrace basics)
> ```c
> #include <sys/ptrace.h>
>
> long ptrace(enum __ptrace_request request, pid_t pid,
>             void *addr, void *data);
> ```

`strace` **forks** the target (or attaches to a running PID), calls
`PTRACE_SYSCALL`, and on each stop reads registers to decode the syscall number and
arguments (using kernel ABI from Part 0.3), then continues.

```
   tracee:  ... SYSCALL entry ──▶ STOP ──▶ strace reads rax, rdi, rsi ...
            kernel runs syscall ──▶ STOP ──▶ strace reads rax result
            SYSRET ──▶ continue
```

Usage:

```bash
strace -o trace.log ./app arg1
strace -p 1234                 # attach (needs permission)
strace -c -f ./app             # summary per syscall (Part 7.5)
strace -e trace=open,read,write  # filter
strace -yy ./app               # decode fd paths
```

**ltrace** intercepts **dynamic linker PLT** entries — `malloc`, `printf` — and can
show libc before syscalls fire.

**Trade-offs ▸** strace is the fastest debug path for syscall bugs. Cost: **massive
slowdown** (stop/start each syscall) — not for production load tests.

**Pitfall ▸** Attaching to production processes pauses them during each stop — use
`perf` or eBPF for low-overhead production tracing.

**Errors ▸** (strace attach)

| errno | when |
|-------|------|
| `EPERM` | ptrace scope restricts non-child attach (`/proc/sys/kernel/yama/ptrace_scope`) |
| `ESRCH` | target exited |
| `EBUSY` | already being traced |

---

## 8.4.3 ftrace and /sys/kernel/tracing

Built into the kernel, exposed via tracefs:

```bash
mount -t tracefs none /sys/kernel/tracing   # often pre-mounted
cd /sys/kernel/tracing
echo function_graph > current_tracer
echo sys_read > set_graph_function
echo 1 > tracing_on
# run workload
cat trace
echo 0 > tracing_on
```

Components:

| interface | purpose |
|-----------|---------|
| `available_tracers` | function, function_graph, nop |
| `trace_events/` | static tracepoints (syscalls, sched, ext4, tcp) |
| `kprobe_events` | dynamic kernel probes |
| `uprobe_events` | user-space probes (precursor to eBPF uprobe) |

> **Under the hood ▸** `-pg` / mcount instrumentation or static `TRACE_EVENT` macros
> emit ring-buffer events with low overhead when disabled.

Good for **kernel developer** questions: "did TCP retransmit?" not "what errno did
my app get?" — though `trace_events/syscalls/` bridges that gap.

---

## 8.4.4 perf_event_open and the perf tool

> **The call ▸**
> ```c
> #include <linux/perf_event.h>
> #include <sys/syscall.h>
>
> long perf_event_open(struct perf_event_attr *attr,
>                      pid_t pid, int cpu, int group_fd,
>                      unsigned long flags);
> ```

`perf` CLI wraps this:

```bash
perf stat ./app                    # counters: cycles, instructions, cache-misses
perf record -g ./app               # sample call stacks at 997 Hz
perf report                        # interactive hotspot view
perf trace -e syscalls:sys_enter_openat   # syscall trace, lower overhead than strace
perf list                          # available events
```

Sampling flow:

```
   PMU overflow interrupt every N cycles
        │
        ▼
   kernel records IP + stack + pid into perf ring buffer
        │
        ▼
   perf report aggregates by symbol
```

**Systems ▸** Use `perf stat` for Part 7.5 syscall amortization work — compare
`syscalls:sys_enter_read` counts before/after batching.

---

## 8.4.5 ptrace() syscall basics

Beyond strace, debuggers (`gdb`) use ptrace:

| request | effect |
|---------|--------|
| `PTRACE_TRACEME` | child asks parent to trace |
| `PTRACE_ATTACH` | tracer attaches to PID |
| `PTRACE_SYSCALL` | stop at syscall entry/exit |
| `PTRACE_SINGLESTEP` | one instruction |
| `PTRACE_PEEKDATA` | read tracee memory |

Security: `kernel.yama.ptrace_scope` limits cross-user attach. Containers may block
ptrace via seccomp (Part 8.6).

---

## 8.4.6 eBPF, bcc, and bpftrace

**eBPF** runs verified bytecode in the kernel on events:

```
   kprobe/sys_read  ──▶  bpf program  ──▶  map (counts, histogram)
   tracepoint/sched/sched_switch
   uprobe on libc:malloc
```

**bpftrace** (one-liners):

```bash
sudo bpftrace -e 'tracepoint:syscalls:sys_enter_openat { @ = count(); }'
sudo bpftrace -e 'kprobe:vfs_read { @bytes = sum(arg2); }'
```

**bcc** (Python/Lua frontends) ships tools like `execsnoop`, `biolatency`, `tcpconnect`.

> **Under the hood ▸** Programs pass verifier checks (bounded loops, no arbitrary
> kernel writes), attach to hooks, communicate via maps (`BPF_MAP_TYPE_HASH`,
> ring buffers). `bpf()` syscall loads programs (Part 0.1 system category).

**Trade-offs ▸** Steeper learning curve than strace; production-safe at high frequency.
Requires kernel ≥ 4.x (5.x+ for many features) and often `CAP_BPF` / root.

---

## 8.4.7 When to use which

```
   ┌────────────────────┬─────────────────────────────────────────┐
   │ Scenario           │ Start here                              │
   ├────────────────────┼─────────────────────────────────────────┤
   │ Wrong errno/order  │ strace -e trace=...                   │
   │ Hot syscall count  │ strace -c or perf stat syscalls:*       │
   │ CPU hotspot        │ perf record -g                          │
   │ Kernel path detail │ ftrace function_graph / trace_events    │
   │ Production, low OH │ bpftrace / bcc / perf probe             │
   │ libc not syscalls  │ ltrace                                  │
   └────────────────────┴─────────────────────────────────────────┘
```

Layer tools: `strace` finds *what*; `perf` finds *where CPU goes*; eBPF finds
*distribution at scale*.

---

## Summary

- strace/ltrace use ptrace to stop processes at syscalls/library calls — invaluable
  for debugging, too slow for production.
- ftrace via `/sys/kernel/tracing` traces kernel functions and static tracepoints.
- `perf_event_open` + `perf` provide counters and sampling with moderate overhead.
- eBPF/bpftrace/bcc enable custom, efficient kernel and user probes.
- Match the tool to the question: syscall correctness (strace), CPU (perf), kernel
  internals (ftrace/eBPF).

Next: [8.5 — Namespaces & cgroups: How Containers Work](05-namespaces-and-cgroups.md)
