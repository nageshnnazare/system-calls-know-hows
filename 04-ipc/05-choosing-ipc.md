# 4.5 — Choosing an IPC Mechanism

Linux offers a buffet of IPC: **pipes**, **FIFOs**, **signals**, **message queues**,
**shared memory**, and **Unix domain sockets** (Part 6.4). None is universally best —
the right choice depends on **relationship** (related processes vs strangers),
**data shape** (byte stream vs messages vs random access), **throughput/latency**, and
**operational complexity**. This chapter is a decision guide, not a popularity contest.

---

## 4.5.1 The landscape at a glance

![IPC mechanisms compared on latency throughput and complexity axes](figures/ipc-comparison.svg)

```
   latency (lower better)          throughput (higher better)
   ─────────────────────          ───────────────────────────
   shared memory  ★★★★★            shared memory  ★★★★★
   Unix sockets   ★★★★             Unix sockets   ★★★★
   pipes/FIFOs    ★★★              pipes/FIFOs    ★★★
   POSIX mq       ★★★              POSIX mq       ★★★
   SysV mq        ★★               SysV mq        ★★
   signals        ★ (control only) signals        ★ (no bulk data)
```

**Systems ▸** Shared memory wins raw bandwidth because, after setup, accesses are
ordinary loads/stores — no kernel copy per message. Everything else moves bytes
through kernel buffers at least once.

---

## 4.5.2 Decision flow

```
   Need to pass bulk data?
        │
        no ──▶ signals / signalfd for events only (Part 4.2)
        │
        yes
        │
        ├─ related processes (fork/exec, same tree)?
        │       │
        │       yes ──▶ pipe() enough for byte streams (Part 4.1)
        │               need fd passing or credentials? → Unix SOCK_STREAM (Part 6.4)
        │
        └─ unrelated / named / persistent?
                │
                ├─ random access / huge blob → mmap + shm_open (Parts 3.3, 3.5)
                ├─ discrete messages + priorities → POSIX mq (Part 4.4)
                ├─ legacy / existing SysV → msgget/semget (Part 4.3)
                └─ request/reply RPC style → Unix domain sockets
```

---

## 4.5.3 Mechanism profiles

### Pipes & FIFOs (Part 4.1)

| | |
|---|---|
| **Best for** | Parent/child streams, shell pipelines, simple producer/consumer |
| **Latency** | Good — one kernel copy per direction |
| **Relationship** | Inherited fds or agreed FIFO path |
| **Complexity** | Low |
| **Limits** | Byte stream only; no message boundaries; ~64 KiB buffer |

### Signals (Part 4.2)

| | |
|---|---|
| **Best for** | Events (SIGCHLD, SIGTERM, timer, fault notification) |
| **Latency** | Excellent for notification — **not for data** |
| **Relationship** | Same user or privileged sender |
| **Complexity** | Handler safety rules are hard |
| **Limits** | No payload; coalesce/lost signals possible for same signum |

### Message queues — SysV & POSIX (Parts 4.3–4.4)

| | |
|---|---|
| **Best for** | Typed/prioritized messages, job dispatch |
| **Latency** | Moderate — kernel copies each message |
| **Relationship** | Named (POSIX/SysV key) or private |
| **Complexity** | Medium — attr tuning, unlink/ipcrm hygiene |
| **Limits** | Max message size and queue depth (`mq_attr`, sysctl) |

### Shared memory (Part 3.5)

| | |
|---|---|
| **Best for** | High-frequency shared state, ring buffers, large datasets |
| **Latency** | Best after mapping |
| **Relationship** | Named shm or inherited anonymous |
| **Complexity** | **High** — requires separate sync (sem/mutex/futex) |
| **Limits** | No implicit boundaries; false sharing, cache effects |

### Unix domain sockets (Part 6.4)

| | |
|---|---|
| **Best for** | RPC, stream + message modes, **SCM_RIGHTS fd passing** |
| **Latency** | Very good; comparable to pipes for stream mode |
| **Relationship** | Filesystem or abstract `@` path |
| **Complexity** | Medium — socket API, but well understood |
| **Limits** | Copy overhead unless combined with shm for bulk |

---

## 4.5.4 Latency vs throughput trade-offs

```
   copies per message
   ┌────────────────┬───────────────────────────────────────┐
   │ shared memory  │ 0 (after map) — user-space only       │
   │ pipe/socket    │ 2 (user→kernel→user) typical          │
   │ message queue  │ 2 + queue management                  │
   └────────────────┴───────────────────────────────────────┘
```

**Trade-offs ▸** Shared memory + a lock is fastest but easiest to get wrong.
Pipes/sockets give **kernel-enforced isolation** and **automatic backpressure**
(block when buffer full). Message queues add **record boundaries** and **priorities**
at the cost of syscalls per message.

For **multi-GB** transfers, **`mmap` file** or **shm** beats repeated `write()`.
For **many small control messages**, sockets or mq beat setting up shared regions.

---

## 4.5.5 Relationship matrix

| Mechanism | fork parent/child | unrelated processes | threads (same process) |
|-----------|-------------------|---------------------|------------------------|
| pipe | ✓ natural | ✗ use FIFO | ✓ but odd (use queue) |
| FIFO | ✓ | ✓ path-based | rare |
| signal | ✓ | ✓ with permissions | ✓ thread-directed signals |
| POSIX shm/mq | ✓ + name | ✓ | ✓ (mq less common) |
| SysV IPC | ✓ pass id | ✓ if key agreed | possible |
| Unix socket | ✓ inherit fd | ✓ | ✓ |

After **`execve()`**, inherited pipe/socket fds survive if **`O_CLOEXEC`** not set
(Part 2.1).

---

## 4.5.6 Complexity and operations

```
   operational burden (high → low)
   SysV IPC (ipcrm nightmares)
        ↓
   POSIX mq/shm (unlink discipline)
        ↓
   Unix sockets (familiar tooling, ss/lsof)
        ↓
   pipes (automatic cleanup on process death)
```

**Pitfall ▸** Choosing shared memory for a **low-frequency config update** saves
microseconds once but adds mutex bugs for years. Choosing **pipes for a 10 GB
transfer** works but copies unnecessarily.

---

## 4.5.7 Summary comparison table

| Mechanism | Data model | Copies/msg | Sync built-in | Poll/epoll | Typical use |
|-----------|------------|------------|---------------|------------|-------------|
| **pipe/FIFO** | byte stream | 2 | backpressure | ✓ (fd) | shell pipes, simple IPC |
| **signal** | none (event) | 0 | no | signalfd | lifecycle, timers, faults |
| **SysV mq** | typed msgs | 2+ | no | ✗ | legacy job queues |
| **POSIX mq** | typed + prio | 2+ | no | ✓ (fd Linux) | structured messages |
| **shared mem** | random access | 0 | **no** | ✗ (use sem/eventfd) | hot path data |
| **Unix socket** | stream/seqpacket | 2 | backpressure | ✓ | RPC, fd passing |

---

## 4.5.8 Practical recommendations

1. **Default stream IPC between related processes:** `pipe()` or Unix **`SOCK_STREAM`**
   if you need bidirectional or fd passing.
2. **Unrelated processes on same host:** Unix domain socket or **POSIX mq** with
   documented names in `/dev/mqueue` or `/dev/shm`.
3. **Hot shared state at memory speed:** **`shm_open` + mmap + POSIX sem/mutex**
   (Parts 3.5, 4.4, 5.3).
4. **Control plane only:** **signals** + **`signalfd`** in an event loop (Part 4.2,
   Part 6.6) — never bulk data on signals.
5. **Greenfield avoiding SysV:** unless integrating legacy — use POSIX or sockets.
6. **Cross-machine:** none of the above apply — use network sockets (Part 6).

---

## Summary

- **Shared memory** leads latency/throughput but demands explicit synchronization.
- **Pipes/FIFOs** are the simplest byte streams for related or shell-style workflows.
- **Message queues** (especially POSIX) fit discrete, prioritized messages.
- **Unix domain sockets** balance performance, **`poll`** integration, and **fd
  passing** — the general-purpose local RPC transport.
- **Signals** notify; they do not transport application payload — use with care and
  async-signal-safe handlers.

Next: [5.1 — Threads vs processes](../05-threads/01-threads-vs-processes.md)
