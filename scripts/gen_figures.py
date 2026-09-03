#!/usr/bin/env python3
"""Generate the Linux system-calls guide's SVG figures, tuned to the htmler blue theme.

Same house style as the computer-architecture guide: because the figures are
inlined as static images (no page CSS reaches them), every colour is chosen to
work on BOTH the dark (#0b0d12) and light (#ffffff) themes at once. A mid-slate
around luminance ~0.2 gives roughly 4.3:1 contrast three ways -- white text on
the fill, and the same colour as ink on either background.

  * slate blue  #6B7B94  (neutral boxes, connectors, axes, labels)
  * blue        #3E7CC0  (highlighted / user-space boxes)          + dark #2F5F98
  * teal        #1F918C  (positive "result" accent / kernel)
  * amber       #D9922B  (warning / trap; dark text on fill)
  * red         #D65A5F  (problem callouts / errors)
  * muted       #9AA0B4  (captions)
  * white       #FFFFFF  (text inside dark fills)
  * 1.5pt wide rules, hand-drawn Virgil font stack

Run:  python3 scripts/gen_figures.py
Output: figures/*.svg  (referenced from the chapter markdown)
"""
import base64
import io
import math
import os

# House-style constants (htmler blue theme, dual light/dark legible)
GREY = "#6B7B94"
GREY_D = "#55637A"
BLUE = "#3E7CC0"
BLUE_D = "#2F5F98"
TEAL = "#1F918C"
AMBER = "#D9922B"
RED = "#D65A5F"
WHITE = "#FFFFFF"
LIGHT = "#9AA0B4"
INK_DARK = "#1F2433"
FONT = ("'Virgil','Segoe Print','Bradley Hand','Comic Sans MS',"
        "'Segoe UI',system-ui,-apple-system,sans-serif")
MONO = ("'Virgil','SFMono-Regular',ui-monospace,'JetBrains Mono',Consolas,"
        "monospace")
RULE = 1.5

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "JetBrainsMonoNerdFont-Regular.woff2")

USED_CHARS = set()
FONT_STYLE = ""


def esc(s):
    USED_CHARS.update(str(s))
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def defs():
    marks = []
    for name, col in (("g", GREY), ("p", BLUE), ("t", TEAL),
                      ("r", RED), ("a", AMBER), ("l", LIGHT)):
        marks.append(
            f'<marker id="ah-{name}" viewBox="0 0 10 10" refX="8" refY="5" '
            f'markerWidth="4.5" markerHeight="4.5" '
            f'orient="auto-start-reverse">'
            f'<path d="M0 1L9 5L0 9z" fill="{col}"/></marker>')
    return "<defs>" + "".join(marks) + "</defs>"


def rrect(x, y, w, h, fill, rx=9, stroke=None, sw=RULE, dash=None, opacity=None):
    s = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" ry="{rx}" '
         f'fill="{fill}"')
    if stroke:
        s += f' stroke="{stroke}" stroke-width="{sw}"'
    if dash:
        s += f' stroke-dasharray="{dash}"'
    if opacity is not None:
        s += f' opacity="{opacity}"'
    return s + "/>"


def tspan_lines(x, cy, lines, fill, size, weight, lh, mono=False):
    fam = MONO if mono else FONT
    n = len(lines)
    y0 = cy - (n - 1) * lh / 2.0
    out = [f'<text x="{x}" y="{y0}" fill="{fill}" font-family="{fam}" '
           f'font-size="{size}" font-weight="{weight}" text-anchor="middle" '
           f'dominant-baseline="central">']
    for i, ln in enumerate(lines):
        dy = 0 if i == 0 else lh
        out.append(f'<tspan x="{x}" dy="{dy}">{esc(ln)}</tspan>')
    out.append("</text>")
    return "".join(out)


def box(x, y, w, h, lines, fill=GREY, tcol=WHITE, size=13, weight=600,
        rx=9, lh=16, stroke=None, sw=RULE, dash=None, mono=False):
    if isinstance(lines, str):
        lines = lines.split("\n")
    r = rrect(x, y, w, h, fill, rx=rx, stroke=stroke, sw=sw, dash=dash)
    t = tspan_lines(x + w / 2.0, y + h / 2.0, lines, tcol, size, weight, lh, mono)
    return r + t


def obox(x, y, w, h, lines, stroke=GREY, tcol=GREY, size=13, weight=600,
         rx=9, lh=16, sw=RULE, dash=None, fill="none", mono=False):
    r = rrect(x, y, w, h, fill, rx=rx, stroke=stroke, sw=sw, dash=dash)
    t = tspan_lines(x + w / 2.0, y + h / 2.0, lines if isinstance(lines, list)
                    else [lines], tcol, size, weight, lh, mono)
    return r + t


def text(x, y, s, fill=GREY, size=13, weight=600, anchor="middle",
         italic=False, mono=False):
    fam = MONO if mono else FONT
    return (f'<text x="{x}" y="{y}" fill="{fill}" font-family="{fam}" '
            f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}"'
            f' dominant-baseline="central">{esc(s)}</text>')


def line(x1, y1, x2, y2, col=GREY, sw=RULE, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col}" '
            f'stroke-width="{sw}"{d}/>')


def _mk(col):
    return {GREY: "g", BLUE: "p", TEAL: "t", RED: "r", AMBER: "a",
            LIGHT: "l"}.get(col, "g")


def arrow(x1, y1, x2, y2, col=GREY, sw=RULE, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col}" '
            f'stroke-width="{sw}" marker-end="url(#ah-{_mk(col)})"{d}/>')


def path(d, col=GREY, sw=RULE, dash=None, arrow_end=False, fill="none"):
    dd = f' stroke-dasharray="{dash}"' if dash else ""
    m = f' marker-end="url(#ah-{_mk(col)})"' if arrow_end else ""
    return (f'<path d="{d}" fill="{fill}" stroke="{col}" stroke-width="{sw}"'
            f'{dd}{m}/>')


def circle(cx, cy, r, fill, stroke=None, sw=RULE):
    st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"{st}/>'


def cylinder(x, y, w, h, fill=GREY, tcol=WHITE, lines=None, size=12,
             stroke=None, sw=RULE):
    ry = min(h * 0.16, 14)
    st = (f' stroke="{stroke}" stroke-width="{sw}"') if stroke else ""
    body = (f'<path d="M{x} {y+ry} A{w/2} {ry} 0 0 0 {x+w} {y+ry} '
            f'L{x+w} {y+h-ry} A{w/2} {ry} 0 0 1 {x} {y+h-ry} Z" '
            f'fill="{fill}"{st}/>')
    top = (f'<ellipse cx="{x+w/2}" cy="{y+ry}" rx="{w/2}" ry="{ry}" '
           f'fill="{fill}"{st}/>')
    t = ""
    if lines:
        t = tspan_lines(x + w / 2.0, y + h / 2.0 + ry / 2, lines, tcol, size,
                        600, 15)
    return body + top + t


def dash_boundary(x1, y, x2, label=None):
    """The user/kernel privilege boundary: a double dashed rule."""
    out = [line(x1, y, x2, y, AMBER, 1.4, dash="7 5"),
           line(x1, y + 4, x2, y + 4, AMBER, 1.4, dash="7 5")]
    if label:
        out.append(text((x1 + x2) / 2, y - 10, label, AMBER, 11, 700))
    return "".join(out)


def svg(w, h, body, title=""):
    t = f"<title>{esc(title)}</title>" if title else ""
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'width="{w}" height="{h}" font-family="{FONT}">{t}{FONT_STYLE}'
            f'{defs()}{body}</svg>\n')


def write(rel_path, content):
    full = os.path.join(REPO_ROOT, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        f.write(content)
    print("wrote", rel_path, f"({len(content)} bytes)")


# FIGURES

ALL = []


def fig(fn):
    ALL.append(fn)
    return fn


# -- 00 foundations ----------------------------------------------------------
@fig
def fig_syscall_boundary():
    W, H = 780, 430
    b = [text(W / 2, 26, "The system-call boundary", GREY, 16, 700)]
    b.append(text(150, 58, "USER SPACE", BLUE, 12, 700))
    b.append(box(60, 74, 660, 96, "", "none", rx=12, stroke=BLUE, sw=1.4))
    b.append(text(388, 92, "your C program (ring 3, unprivileged)", GREY, 11,
                  500))
    for i, (name, sub) in enumerate([("printf()", "libc"), ("fopen()", "libc"),
                                     ("malloc()", "libc"), ("write()", "wrapper")]):
        x = 90 + i * 160
        b.append(box(x, 110, 130, 44, [name, sub], BLUE, size=12, lh=15, rx=8))
    b.append(arrow(155, 154, 155, 214, GREY))
    b.append(arrow(535, 154, 535, 214, GREY))
    b.append(dash_boundary(60, 232, 720, "syscall / SYSCALL instruction  (mode switch, ring 3 -> ring 0)"))
    b.append(text(150, 262, "KERNEL SPACE", TEAL, 12, 700))
    b.append(box(60, 278, 660, 116, "", "none", rx=12, stroke=TEAL, sw=1.4))
    b.append(box(90, 300, 160, 40, "syscall dispatch", TEAL, size=11, rx=8))
    b.append(box(280, 300, 150, 40, "sys_write()", TEAL, size=11, rx=8))
    b.append(box(300, 352, 220, 32, ["VFS -> driver -> hardware"], GREY_D,
                 size=11, rx=8))
    b.append(arrow(170, 340, 300, 352, GREY))
    b.append(arrow(355, 340, 400, 352, GREY))
    b.append(text(W / 2, H - 16, "the ONLY controlled door from your process "
                  "into the kernel's privileged code", LIGHT, 11, 500))
    write("figures/syscall-boundary.svg", svg(W, H, "".join(b),
          "System-call boundary"))


@fig
def fig_syscall_mechanism():
    W, H = 820, 400
    b = [text(W / 2, 26, "How a syscall is dispatched (x86-64 Linux ABI)", GREY,
              15, 700)]
    regs = [("rax", "syscall number (1 = write)"),
            ("rdi", "arg1  (fd)"),
            ("rsi", "arg2  (buf)"),
            ("rdx", "arg3  (count)")]
    for i, (r, d) in enumerate(regs):
        y = 66 + i * 40
        b.append(box(60, y, 90, 30, r, BLUE, size=12, rx=6, mono=True))
        b.append(text(165, y + 15, d, GREY, 11, 500, anchor="start"))
    b.append(box(60, 236, 320, 40, ["SYSCALL instruction"], AMBER,
                 tcol=INK_DARK, size=13, rx=8))
    b.append(arrow(380, 256, 470, 256, AMBER))
    b.append(box(470, 66, 300, 100, ["kernel entry_SYSCALL_64", "save regs, "
                 "swap to kernel stack"], TEAL, size=11, lh=17, rx=10))
    b.append(box(470, 186, 300, 56, ["sys_call_table[rax]", "-> sys_write()"],
                 TEAL, size=12, lh=17, rx=10, mono=False))
    b.append(box(470, 262, 300, 40, ["result -> rax  (>=0 or -errno)"], BLUE,
                 size=11, rx=8))
    b.append(arrow(620, 166, 620, 186, GREY))
    b.append(arrow(620, 242, 620, 262, GREY))
    b.append(arrow(620, 302, 300, 256, GREY, dash="5 4"))
    b.append(text(300, 300, "SYSRET -> back to user, rax holds return value",
                  LIGHT, 11, 500))
    b.append(text(W / 2, H - 14, "libc reads rax: if in [-4095, -1] it sets "
                  "errno = -rax and returns -1", LIGHT, 11, 500))
    write("figures/syscall-mechanism.svg", svg(W, H, "".join(b),
          "Syscall mechanism"))


@fig
def fig_fd_table():
    W, H = 820, 400
    b = [text(W / 2, 26, "Three levels behind a file descriptor", GREY, 16,
              700)]
    b.append(text(150, 60, "per-process", BLUE, 11, 700))
    b.append(text(150, 76, "fd table", BLUE, 11, 700))
    fds = [("0", "stdin"), ("1", "stdout"), ("2", "stderr"), ("3", "open()")]
    for i, (n, d) in enumerate(fds):
        y = 96 + i * 46
        b.append(box(70, y, 60, 36, n, BLUE, size=13, rx=6, mono=True))
        b.append(text(140, y + 18, d, GREY, 10, 500, anchor="start"))
    b.append(text(420, 60, "system-wide", TEAL, 11, 700))
    b.append(text(420, 76, "open file table", TEAL, 11, 700))
    b.append(box(360, 96, 190, 50, ["offset, flags", "(O_APPEND, ...)"], TEAL,
                 size=11, lh=15, rx=8))
    b.append(box(360, 188, 190, 50, ["offset, flags"], TEAL, size=11, rx=8))
    b.append(text(700, 60, "in-kernel", GREY, 11, 700))
    b.append(text(700, 76, "inode / vnode", GREY, 11, 700))
    b.append(box(640, 116, 140, 70, ["inode", "(size, perms,", "disk blocks)"],
                 GREY_D, size=11, lh=15, rx=8))
    b.append(arrow(130, 226, 360, 130, GREY))
    b.append(arrow(130, 114, 360, 120, BLUE))
    b.append(arrow(130, 160, 360, 205, GREY, dash="4 4"))
    b.append(arrow(550, 120, 640, 145, GREY))
    b.append(arrow(550, 210, 700, 170, GREY))
    b.append(text(W / 2, H - 16, "dup() copies an fd -> same open-file entry "
                  "(shared offset); open() twice -> two entries", LIGHT, 11,
                  500))
    write("figures/fd-table.svg", svg(W, H, "".join(b), "File descriptors"))


# -- 01 processes ------------------------------------------------------------
@fig
def fig_process_states():
    W, H = 760, 380
    b = [text(W / 2, 26, "Process state machine (Linux task states)", GREY, 16,
              700)]
    b.append(box(300, 70, 160, 50, ["TASK_RUNNING", "(on CPU)"], TEAL,
                 size=12, lh=15, rx=10))
    b.append(box(300, 180, 160, 50, ["TASK_RUNNING", "(runnable, in queue)"],
                 BLUE, size=11, lh=15, rx=10))
    b.append(box(60, 180, 170, 50, ["INTERRUPTIBLE /", "UNINTERRUPTIBLE sleep"],
                 GREY, size=11, lh=15, rx=10))
    b.append(box(540, 180, 160, 50, ["EXIT_ZOMBIE", "(dead, unreaped)"], AMBER,
                 tcol=INK_DARK, size=11, lh=15, rx=10))
    b.append(box(300, 296, 160, 44, ["EXIT_DEAD (reaped)"], GREY_D, size=11,
                 rx=10))
    b.append(arrow(380, 180, 380, 120, TEAL))
    b.append(text(430, 150, "scheduled", LIGHT, 10, 500, anchor="start"))
    b.append(arrow(340, 120, 340, 180, GREY))
    b.append(text(250, 150, "preempted", LIGHT, 10, 500, anchor="end"))
    b.append(arrow(300, 100, 150, 180, GREY))
    b.append(text(190, 132, "block (I/O, wait)", LIGHT, 10, 500))
    b.append(arrow(160, 230, 300, 205, BLUE))
    b.append(text(210, 250, "wake up", LIGHT, 10, 500))
    b.append(arrow(460, 100, 600, 180, AMBER))
    b.append(text(560, 130, "exit()", LIGHT, 10, 500))
    b.append(arrow(590, 230, 440, 300, GREY))
    b.append(text(540, 275, "parent wait()s", LIGHT, 10, 500))
    b.append(text(W / 2, H - 12, "an unreaped zombie holds only its exit "
                  "status + PID until the parent calls wait()", LIGHT, 11, 500))
    write("figures/process-states.svg", svg(W, H, "".join(b),
          "Process states"))


@fig
def fig_fork_cow():
    W, H = 780, 380
    b = [text(W / 2, 26, "fork(): copy-on-write address space", GREY, 16, 700)]
    for (x, name, col) in ((90, "parent", BLUE), (430, "child", TEAL)):
        b.append(box(x, 70, 200, 210, "", "none", rx=12, stroke=col, sw=1.4))
        b.append(text(x + 100, 88, f"{name}  (own page tables)", col, 11, 700))
        for i, seg in enumerate(["stack", "heap", "data", "text (code)"]):
            b.append(box(x + 20, 104 + i * 42, 160, 34, seg, GREY_D, size=11,
                         rx=6))
    b.append(box(300, 150, 180, 90, ["SHARED physical", "pages (read-only)",
                 "until first write"], AMBER, tcol=INK_DARK, size=11, lh=17,
                 rx=10))
    b.append(arrow(250, 180, 300, 180, GREY))
    b.append(arrow(480, 180, 430, 180, GREY))
    b.append(text(W / 2, 320, "fork() returns twice: child PID in parent, 0 in "
                  "child; a write traps -> kernel copies just that page", LIGHT,
                  11, 500))
    b.append(text(W / 2, H - 14, "no eager copy of the whole address space -- "
                  "that is why fork() is cheap even for huge processes", LIGHT,
                  11, 500))
    write("figures/fork-cow.svg", svg(W, H, "".join(b), "fork copy-on-write"))


@fig
def fig_exec_overlay():
    W, H = 760, 360
    b = [text(W / 2, 26, "exec(): replace the program, keep the process", GREY,
              15, 700)]
    b.append(box(70, 70, 200, 230, "", "none", rx=12, stroke=GREY, sw=1.4))
    b.append(text(170, 88, "before execve()", GREY, 11, 700))
    for i, seg in enumerate(["old stack", "old heap", "old data", "old code"]):
        b.append(box(90, 108 + i * 44, 160, 36, seg, GREY_D, size=11, rx=6))
    b.append(arrow(290, 190, 470, 190, TEAL))
    b.append(text(380, 170, "execve()", TEAL, 12, 700))
    b.append(box(490, 70, 200, 230, "", "none", rx=12, stroke=TEAL, sw=1.4))
    b.append(text(590, 88, "after execve()", TEAL, 11, 700))
    for i, seg in enumerate(["new stack", "new heap", "new data", "new code"]):
        b.append(box(510, 108 + i * 44, 160, 36, seg, TEAL, size=11, rx=6))
    b.append(text(W / 2, H - 30, "same PID, open fds (unless O_CLOEXEC), and "
                  "signal dispositions survive; the memory image is thrown away",
                  LIGHT, 11, 500))
    b.append(text(W / 2, H - 12, "fork()+exec() is the canonical 'spawn a "
                  "program' idiom on Unix", LIGHT, 11, 500))
    write("figures/exec-overlay.svg", svg(W, H, "".join(b), "exec overlay"))


@fig
def fig_process_lifecycle():
    W, H = 820, 320
    b = [text(W / 2, 26, "fork / exec / wait lifecycle", GREY, 16, 700)]
    b.append(box(60, 120, 130, 60, ["parent", "running"], BLUE, size=12,
                 lh=16, rx=10))
    b.append(arrow(190, 150, 280, 150, GREY))
    b.append(text(235, 132, "fork()", LIGHT, 10, 600))
    b.append(box(280, 70, 130, 54, ["parent", "wait()s"], BLUE, size=11,
                 lh=15, rx=10))
    b.append(box(280, 176, 130, 54, ["child", "(copy)"], TEAL, size=11, lh=15,
                 rx=10))
    b.append(arrow(410, 203, 500, 203, TEAL))
    b.append(text(455, 185, "execve()", LIGHT, 10, 600))
    b.append(box(500, 176, 140, 54, ["new program", "runs"], TEAL, size=11,
                 lh=15, rx=10))
    b.append(arrow(640, 203, 720, 150, AMBER))
    b.append(text(700, 190, "exit()", LIGHT, 10, 600))
    b.append(box(720, 120, 90, 60, ["zombie"], AMBER, tcol=INK_DARK, size=11,
                 rx=10))
    b.append(arrow(720, 130, 410, 100, GREY, dash="5 4"))
    b.append(text(560, 96, "SIGCHLD + exit status reaped by wait()", LIGHT, 10,
                  500))
    b.append(text(W / 2, H - 14, "orphan (parent died first) is re-parented to "
                  "init/systemd, which reaps it", LIGHT, 11, 500))
    write("figures/process-lifecycle.svg", svg(W, H, "".join(b),
          "Process lifecycle"))


# -- 02 file I/O -------------------------------------------------------------
@fig
def fig_open_file_table():
    W, H = 800, 380
    b = [text(W / 2, 26, "read()/write() move bytes at the open-file offset",
              GREY, 15, 700)]
    b.append(box(70, 80, 180, 60, ["user buffer", "char buf[4096]"], BLUE,
                 size=11, lh=16, rx=10))
    b.append(arrow(250, 110, 360, 110, BLUE))
    b.append(text(305, 92, "write(fd,buf,n)", LIGHT, 10, 600, mono=True))
    b.append(dash_boundary(360, 60, 380, None))
    b.append(box(380, 70, 210, 90, ["page cache", "(kernel copy of blocks)"],
                 TEAL, size=11, lh=16, rx=10))
    b.append(arrow(590, 115, 690, 115, GREY))
    b.append(cylinder(690, 70, 90, 120, GREY_D, WHITE, ["disk"], size=11))
    b.append(box(380, 210, 210, 46, ["offset += n  (per open-file entry)"],
                 GREY, size=11, rx=8))
    b.append(arrow(485, 160, 485, 210, GREY))
    b.append(text(W / 2, 300, "read() short-count is normal (pipe/socket): "
                  "always loop until you have all the bytes", LIGHT, 11, 500))
    b.append(text(W / 2, H - 16, "buffered fwrite() batches many writes into "
                  "one write() syscall -- fewer mode switches", LIGHT, 11, 500))
    write("figures/open-file-table.svg", svg(W, H, "".join(b), "read/write"))


@fig
def fig_vfs_inode():
    W, H = 800, 360
    b = [text(W / 2, 26, "The VFS: one interface, many filesystems", GREY, 16,
              700)]
    b.append(box(300, 60, 200, 46, ["open/read/write/stat"], BLUE, size=12,
                 rx=10))
    b.append(box(300, 130, 200, 46, ["VFS (virtual filesystem)"], TEAL,
                 size=12, rx=10))
    b.append(arrow(400, 106, 400, 130, GREY))
    fss = [("ext4", 70), ("xfs", 250), ("tmpfs", 430), ("procfs", 610)]
    for name, x in fss:
        b.append(box(x, 220, 120, 44, name, GREY_D, size=12, rx=8))
        b.append(arrow(360 + (x - 360) * 0.55, 176, x + 60, 220, GREY))
    b.append(text(W / 2, 300, "every open file is an inode behind a struct "
                  "file; even sockets and pipes look like fds", LIGHT, 11, 500))
    b.append(text(W / 2, H - 14, "\"everything is a file\" = the VFS gives one "
                  "fd-based API to disks, devices, networks and kernel state",
                  LIGHT, 11, 500))
    write("figures/vfs-inode.svg", svg(W, H, "".join(b), "VFS and inodes"))


@fig
def fig_fd_redirection():
    W, H = 780, 320
    b = [text(W / 2, 26, "Redirection: dup2() rewires a descriptor", GREY, 16,
              700)]
    b.append(text(190, 66, "before", GREY, 12, 700))
    b.append(box(90, 84, 60, 34, "1", BLUE, size=12, rx=6, mono=True))
    b.append(box(90, 130, 60, 34, "3", TEAL, size=12, rx=6, mono=True))
    b.append(box(220, 84, 150, 34, "terminal", GREY_D, size=11, rx=6))
    b.append(box(220, 130, 150, 34, "log.txt", GREY_D, size=11, rx=6))
    b.append(arrow(150, 101, 220, 101, GREY))
    b.append(arrow(150, 147, 220, 147, GREY))
    b.append(text(560, 66, "after dup2(3, 1)", TEAL, 12, 700))
    b.append(box(470, 84, 60, 34, "1", BLUE, size=12, rx=6, mono=True))
    b.append(box(470, 130, 60, 34, "3", TEAL, size=12, rx=6, mono=True))
    b.append(box(600, 130, 150, 34, "log.txt", GREY_D, size=11, rx=6))
    b.append(arrow(530, 101, 600, 140, TEAL))
    b.append(arrow(530, 147, 600, 147, TEAL))
    b.append(text(W / 2, 240, "fd 1 now points at the same open-file entry as "
                  "fd 3 -> stdout goes to the file", LIGHT, 11, 500))
    b.append(text(W / 2, 266, "this is exactly how a shell implements  "
                  "command > log.txt", LIGHT, 11, 500, mono=False))
    write("figures/fd-redirection.svg", svg(W, H, "".join(b), "dup2 redirect"))


# -- 03 memory ---------------------------------------------------------------
@fig
def fig_address_space():
    W, H = 520, 470
    b = [text(W / 2, 26, "Process virtual address space (64-bit Linux)", GREY,
              14, 700)]
    segs = [("stack", "grows down, local vars", RED, 60),
            ("(gap)", "mmap region: libs, mmap()", GREY, 110),
            ("shared libs", "libc.so, mmapped files", BLUE, 170),
            ("heap", "malloc/brk, grows up", TEAL, 235),
            ("BSS / data", "globals", GREY_D, 300),
            ("text (code)", "read-only, shared", BLUE_D, 355)]
    for name, desc, col, y in segs:
        b.append(box(120, y, 280, 44, name, col, size=12, rx=8))
        b.append(text(410, y + 22, desc, LIGHT, 9, 500, anchor="start"))
    b.append(text(70, 70, "high", LIGHT, 10, 600))
    b.append(text(70, 388, "0", LIGHT, 10, 600))
    b.append(arrow(90, 262, 90, 300, TEAL))
    b.append(arrow(90, 108, 90, 70, RED))
    b.append(text(W / 2, 430, "each process sees its own flat address space; "
                  "the MMU maps pages to physical RAM", LIGHT, 11, 500))
    b.append(text(W / 2, 450, "unmapped access -> page fault -> SIGSEGV",
                  LIGHT, 11, 500))
    write("figures/address-space.svg", svg(W, H, "".join(b), "Address space"))


@fig
def fig_mmap():
    W, H = 780, 360
    b = [text(W / 2, 26, "mmap(): map a file (or anonymous pages) into memory",
              GREY, 15, 700)]
    b.append(box(70, 80, 200, 160, "", "none", rx=12, stroke=BLUE, sw=1.4))
    b.append(text(170, 98, "virtual address space", BLUE, 11, 700))
    for i in range(3):
        b.append(box(90, 118 + i * 40, 160, 32, f"page {i}", BLUE, size=11,
                     rx=6))
    b.append(cylinder(560, 80, 150, 150, GREY_D, WHITE,
                      ["file on disk"], size=11))
    for i in range(3):
        b.append(arrow(250, 134 + i * 40, 560, 120 + i * 40, TEAL, dash="4 4"))
    b.append(text(410, 120, "page fault -> demand-page the block in", LIGHT,
                  10, 500))
    b.append(text(W / 2, 290, "no read()/write() calls: loads and stores hit "
                  "memory, the kernel pages data in lazily", LIGHT, 11, 500))
    b.append(text(W / 2, H - 16, "MAP_SHARED writes flush back to the file; "
                  "MAP_PRIVATE is copy-on-write; MAP_ANONYMOUS = raw RAM",
                  LIGHT, 11, 500))
    write("figures/mmap.svg", svg(W, H, "".join(b), "mmap"))


@fig
def fig_page_fault():
    W, H = 800, 340
    b = [text(W / 2, 26, "A page fault is a syscall you did not write", GREY,
              15, 700)]
    b.append(box(60, 80, 150, 50, ["load/store to", "virtual address"], BLUE,
                 size=11, lh=15, rx=10))
    b.append(arrow(210, 105, 290, 105, GREY))
    b.append(box(290, 80, 150, 50, ["MMU: no valid", "page table entry"],
                 AMBER, tcol=INK_DARK, size=11, lh=15, rx=10))
    b.append(arrow(440, 105, 520, 105, AMBER))
    b.append(box(520, 80, 220, 50, ["#PF trap -> kernel", "page-fault handler"],
                 TEAL, size=11, lh=15, rx=10))
    b.append(arrow(630, 130, 630, 180, GREY))
    b.append(box(500, 180, 260, 44, ["allocate/COW/swap-in the page,", "fix "
                 "PTE, retry the instruction"], TEAL, size=10, lh=14, rx=10))
    b.append(box(300, 180, 150, 44, ["invalid -> SIGSEGV"], RED, size=11,
                 rx=10))
    b.append(arrow(400, 130, 380, 180, RED))
    b.append(text(W / 2, H - 16, "minor fault = map an existing page (fast); "
                  "major fault = read from disk/swap (slow)", LIGHT, 11, 500))
    write("figures/page-fault.svg", svg(W, H, "".join(b), "Page fault"))


# -- 04 IPC ------------------------------------------------------------------
@fig
def fig_pipe():
    W, H = 780, 300
    b = [text(W / 2, 26, "A pipe is a one-way in-kernel byte buffer", GREY, 16,
              700)]
    b.append(box(70, 110, 150, 60, ["writer", "write(fd[1])"], BLUE, size=11,
                 lh=15, rx=10))
    b.append(box(560, 110, 150, 60, ["reader", "read(fd[0])"], TEAL, size=11,
                 lh=15, rx=10))
    b.append(box(280, 100, 220, 80, ["pipe buffer", "(~64 KiB ring in kernel)"],
                 GREY_D, size=11, lh=16, rx=10))
    b.append(arrow(220, 140, 280, 140, BLUE))
    b.append(arrow(500, 140, 560, 140, TEAL))
    b.append(text(W / 2, 220, "full buffer blocks the writer; empty buffer "
                  "blocks the reader -> automatic flow control", LIGHT, 11,
                  500))
    b.append(text(W / 2, 246, "writer closes -> reader sees EOF (read returns "
                  "0); all readers gone -> writer gets SIGPIPE", LIGHT, 11,
                  500))
    b.append(text(W / 2, H - 16, "shells build  a | b  by dup2()-ing pipe ends "
                  "onto stdout/stdin", LIGHT, 11, 500))
    write("figures/pipe.svg", svg(W, H, "".join(b), "Pipe"))


@fig
def fig_signal():
    W, H = 800, 340
    b = [text(W / 2, 26, "Signal delivery: asynchronous notification", GREY, 16,
              700)]
    b.append(box(60, 90, 150, 50, ["kill(pid, SIG)", "or kernel event"], BLUE,
                 size=11, lh=15, rx=10))
    b.append(arrow(210, 115, 300, 115, GREY))
    b.append(box(300, 90, 180, 50, ["pending signal set", "on target task"],
                 GREY_D, size=11, lh=15, rx=10))
    b.append(arrow(480, 115, 570, 115, GREY))
    b.append(box(570, 90, 180, 50, ["delivered at next", "kernel->user return"],
                 TEAL, size=11, lh=15, rx=10))
    b.append(arrow(660, 140, 660, 190, GREY))
    b.append(box(560, 190, 200, 44, ["handler runs, or default", "(term / core "
                 "/ stop / ignore)"], AMBER, tcol=INK_DARK, size=10, lh=14,
                 rx=10))
    b.append(text(W / 2, 275, "async-signal-safe functions only inside a "
                  "handler; classic pattern: set a volatile sig_atomic_t flag",
                  LIGHT, 11, 500))
    b.append(text(W / 2, H - 14, "SIGKILL (9) and SIGSTOP cannot be caught, "
                  "blocked, or ignored", LIGHT, 11, 500))
    write("figures/signal-delivery.svg", svg(W, H, "".join(b), "Signals"))


@fig
def fig_ipc_comparison():
    W, H = 820, 360
    b = [text(W / 2, 26, "Choosing an IPC mechanism", GREY, 16, 700)]
    rows = [("Pipe / FIFO", "byte stream", "related / named", "simple, 1-way"),
            ("Signal", "1 bit + number", "any process", "async events only"),
            ("Message queue", "discrete msgs", "unrelated", "typed, priorities"),
            ("Shared memory", "raw bytes", "unrelated", "fastest, needs a lock"),
            ("Socket (AF_UNIX)", "stream/datagram", "unrelated / net", "most "
             "flexible")]
    cols = [("Mechanism", 40, 190, GREY_D), ("Carries", 235, 150, BLUE),
            ("Between", 390, 170, TEAL), ("Notes", 565, 215, GREY)]
    for name, x, w, col in cols:
        b.append(box(x, 60, w, 32, name, col, size=11, rx=6))
    for i, row in enumerate(rows):
        y = 100 + i * 46
        for (name, x, w, col), cell in zip(cols, row):
            b.append(box(x, y, w, 38, cell, "none", tcol=col, size=10, rx=6,
                         stroke=col, sw=1))
    b.append(text(W / 2, H - 14, "shared memory wins on throughput but you own "
                  "the synchronization; sockets win on flexibility", LIGHT, 11,
                  500))
    write("figures/ipc-comparison.svg", svg(W, H, "".join(b), "IPC comparison"))


# -- 05 threads --------------------------------------------------------------
@fig
def fig_thread_vs_process():
    W, H = 800, 380
    b = [text(W / 2, 26, "Threads share an address space; processes do not",
              GREY, 15, 700)]
    b.append(box(60, 70, 300, 250, "", "none", rx=12, stroke=BLUE, sw=1.4))
    b.append(text(210, 88, "one process, two threads", BLUE, 11, 700))
    b.append(box(90, 108, 240, 40, ["shared: heap, globals, fds, code"], TEAL,
                 size=10, rx=8))
    for i in range(2):
        x = 90 + i * 130
        b.append(box(x, 168, 110, 120, "", "none", rx=8, stroke=GREY, sw=1))
        b.append(text(x + 55, 186, f"thread {i}", GREY, 10, 700))
        b.append(box(x + 12, 200, 86, 34, "own stack", GREY_D, size=9, rx=5))
        b.append(box(x + 12, 244, 86, 34, "own regs", GREY_D, size=9, rx=5))
    b.append(box(440, 70, 300, 250, "", "none", rx=12, stroke=GREY, sw=1.4))
    b.append(text(590, 88, "two processes", GREY, 11, 700))
    for i in range(2):
        x = 470 + i * 130
        b.append(box(x, 118, 110, 180, "", "none", rx=8, stroke=GREY, sw=1))
        b.append(text(x + 55, 136, f"process {i}", GREY, 10, 700))
        for j, seg in enumerate(["stack", "heap", "data", "code"]):
            b.append(box(x + 12, 150 + j * 36, 86, 30, seg, GREY_D, size=9,
                         rx=5))
    b.append(text(W / 2, H - 30, "threads: fast to create/switch, cheap "
                  "sharing -- but a bug in one corrupts all", LIGHT, 11, 500))
    b.append(text(W / 2, H - 12, "processes: isolated & robust -- but IPC and "
                  "context switches cost more", LIGHT, 11, 500))
    write("figures/thread-vs-process.svg", svg(W, H, "".join(b),
          "Threads vs processes"))


@fig
def fig_mutex():
    W, H = 780, 340
    b = [text(W / 2, 26, "A mutex serializes the critical section", GREY, 16,
              700)]
    b.append(box(60, 90, 150, 50, ["thread A", "lock()"], BLUE, size=11,
                 lh=15, rx=10))
    b.append(box(60, 200, 150, 50, ["thread B", "lock() ... blocks"], TEAL,
                 size=10, lh=15, rx=10))
    b.append(box(300, 130, 200, 80, ["CRITICAL SECTION", "(one thread at a "
                 "time)"], AMBER, tcol=INK_DARK, size=11, lh=17, rx=12))
    b.append(arrow(210, 115, 300, 150, BLUE))
    b.append(arrow(210, 225, 300, 195, TEAL, dash="5 4"))
    b.append(arrow(500, 170, 600, 170, GREY))
    b.append(box(600, 145, 130, 50, ["unlock() ->", "B proceeds"], TEAL,
                 size=10, lh=15, rx=10))
    b.append(text(W / 2, 275, "uncontended lock is a fast userspace atomic "
                  "(CAS); only contention falls into the futex() syscall",
                  LIGHT, 11, 500))
    b.append(text(W / 2, H - 14, "always lock in a fixed global order to avoid "
                  "deadlock", LIGHT, 11, 500))
    write("figures/mutex.svg", svg(W, H, "".join(b), "Mutex"))


@fig
def fig_futex():
    W, H = 800, 320
    b = [text(W / 2, 26, "futex: fast path in user space, slow path in kernel",
              GREY, 15, 700)]
    b.append(box(60, 70, 320, 100, "", "none", rx=12, stroke=BLUE, sw=1.4))
    b.append(text(220, 88, "uncontended (common)", BLUE, 11, 700))
    b.append(box(90, 108, 260, 44, ["atomic CAS on the lock word", "-> no "
                 "syscall at all"], TEAL, size=10, lh=15, rx=8))
    b.append(box(420, 70, 320, 190, "", "none", rx=12, stroke=AMBER, sw=1.4))
    b.append(text(580, 88, "contended (rare)", AMBER, size=11, weight=700))
    b.append(box(450, 108, 260, 40, ["FUTEX_WAIT: kernel sleeps thread"],
                 GREY_D, size=10, rx=8))
    b.append(box(450, 158, 260, 40, ["FUTEX_WAKE: unlocker wakes a waiter"],
                 GREY_D, size=10, rx=8))
    b.append(box(450, 208, 260, 36, ["only pay syscall cost on contention"],
                 AMBER, tcol=INK_DARK, size=10, rx=8))
    b.append(text(W / 2, H - 14, "pthread mutexes, semaphores and condvars are "
                  "all built on futex()", LIGHT, 11, 500))
    write("figures/futex.svg", svg(W, H, "".join(b), "futex"))


# -- 06 sockets --------------------------------------------------------------
@fig
def fig_socket_sequence():
    W, H = 780, 420
    b = [text(W / 2, 26, "TCP socket syscall sequence", GREY, 16, 700)]
    server = ["socket()", "bind()", "listen()", "accept()  <- blocks",
              "read()/write()", "close()"]
    client = ["socket()", "", "", "connect()", "write()/read()", "close()"]
    b.append(box(80, 60, 260, 30, "SERVER", TEAL, size=12, rx=8))
    b.append(box(440, 60, 260, 30, "CLIENT", BLUE, size=12, rx=8))
    for i, s in enumerate(server):
        if s:
            b.append(box(80, 104 + i * 48, 260, 36, s, TEAL, size=11, rx=8,
                         mono=True))
    for i, c in enumerate(client):
        if c:
            b.append(box(440, 104 + i * 48, 260, 36, c, BLUE, size=11, rx=8,
                         mono=True))
    b.append(arrow(440, 106 + 3 * 48, 340, 106 + 3 * 48, GREY, dash="5 4"))
    b.append(text(390, 90 + 3 * 48, "SYN", LIGHT, 9, 600))
    b.append(arrow(340, 122 + 3 * 48, 440, 122 + 3 * 48, GREY, dash="5 4"))
    b.append(text(390, 140 + 3 * 48, "SYN-ACK / ACK", LIGHT, 9, 600))
    b.append(text(W / 2, H - 14, "accept() returns a NEW connected fd; the "
                  "listening fd keeps accepting more clients", LIGHT, 11, 500))
    write("figures/socket-sequence.svg", svg(W, H, "".join(b),
          "Socket sequence"))


@fig
def fig_tcp_handshake():
    W, H = 720, 320
    b = [text(W / 2, 26, "TCP three-way handshake", GREY, 16, 700)]
    b.append(box(80, 70, 130, 40, "client", BLUE, size=12, rx=8))
    b.append(box(510, 70, 130, 40, "server", TEAL, size=12, rx=8))
    b.append(line(145, 110, 145, 280, GREY, 1.2, dash="3 4"))
    b.append(line(575, 110, 575, 280, GREY, 1.2, dash="3 4"))
    steps = [(140, "SYN  seq=x", 145, 575, BLUE),
             (185, "SYN-ACK  seq=y ack=x+1", 575, 145, TEAL),
             (230, "ACK  ack=y+1", 145, 575, BLUE)]
    for y, lab, x1, x2, col in steps:
        b.append(arrow(x1, y, x2, y, col))
        b.append(text((x1 + x2) / 2, y - 12, lab, col, 10, 600, mono=True))
    b.append(text(W / 2, 275, "after the ACK both sides are ESTABLISHED; "
                  "connect()/accept() now return", LIGHT, 11, 500))
    write("figures/tcp-handshake.svg", svg(W, H, "".join(b), "TCP handshake"))


@fig
def fig_epoll():
    W, H = 800, 360
    b = [text(W / 2, 26, "epoll: O(1) readiness for thousands of fds", GREY, 15,
              700)]
    b.append(box(60, 90, 150, 200, "", "none", rx=12, stroke=BLUE, sw=1.4))
    b.append(text(135, 108, "10k sockets", BLUE, 11, 700))
    for i in range(5):
        b.append(box(85, 128 + i * 30, 100, 24, f"fd {i}", BLUE, size=10, rx=5))
    b.append(text(135, 278, "...", BLUE, 12, 700))
    b.append(arrow(210, 190, 300, 190, GREY))
    b.append(box(300, 150, 200, 80, ["epoll instance", "(kernel red-black "
                 "tree + ready list)"], TEAL, size=10, lh=15, rx=12))
    b.append(arrow(500, 190, 600, 190, TEAL))
    b.append(box(600, 150, 150, 80, ["epoll_wait()", "returns only", "READY "
                 "fds"], AMBER, tcol=INK_DARK, size=10, lh=15, rx=12))
    b.append(text(W / 2, 320, "select()/poll() rescan every fd each call = "
                  "O(n); epoll registers once and wakes on events", LIGHT, 11,
                  500))
    b.append(text(W / 2, H - 12, "level-triggered (default) vs edge-triggered "
                  "(EPOLLET, must drain to EAGAIN)", LIGHT, 11, 500))
    write("figures/epoll.svg", svg(W, H, "".join(b), "epoll"))


# -- 07 I/O and performance --------------------------------------------------
@fig
def fig_io_models():
    W, H = 820, 360
    b = [text(W / 2, 26, "Four I/O models", GREY, 16, 700)]
    models = [
        ("Blocking", "thread waits in the syscall until data is ready", BLUE),
        ("Non-blocking", "returns EAGAIN if not ready; you poll / retry", TEAL),
        ("I/O multiplexing", "one thread waits on many fds (select/poll/epoll)",
         GREY_D),
        ("Async (io_uring/AIO)", "kernel completes the op, notifies you later",
         AMBER),
    ]
    for i, (name, desc, col) in enumerate(models):
        y = 70 + i * 66
        tc = INK_DARK if col == AMBER else WHITE
        b.append(box(60, y, 220, 50, name, col, tcol=tc, size=12, rx=10))
        b.append(text(300, y + 25, desc, GREY, 11, 500, anchor="start"))
    b.append(text(W / 2, H - 14, "more concurrency per thread as you go down; "
                  "async decouples 'start' from 'complete'", LIGHT, 11, 500))
    write("figures/io-models.svg", svg(W, H, "".join(b), "I/O models"))


@fig
def fig_io_uring():
    W, H = 800, 340
    b = [text(W / 2, 26, "io_uring: two shared ring buffers, few syscalls",
              GREY, 15, 700)]
    b.append(box(80, 90, 260, 60, ["Submission Queue (SQ)", "app writes "
                 "requests"], BLUE, size=11, lh=16, rx=10))
    b.append(box(80, 200, 260, 60, ["Completion Queue (CQ)", "app reads "
                 "results"], TEAL, size=11, lh=16, rx=10))
    b.append(dash_boundary(360, 70, 380, None))
    b.append(box(420, 130, 300, 90, ["kernel", "consumes SQ, performs I/O,",
                 "posts to CQ"], GREY_D, size=11, lh=16, rx=12))
    b.append(arrow(340, 120, 420, 150, BLUE))
    b.append(arrow(420, 200, 340, 230, TEAL))
    b.append(text(W / 2, 300, "batch many ops per io_uring_enter() -- amortize "
                  "the syscall; rings are mmap'd and shared with the kernel",
                  LIGHT, 11, 500))
    b.append(text(W / 2, H - 12, "with SQPOLL the kernel polls the SQ and you "
                  "can do zero syscalls on the hot path", LIGHT, 11, 500))
    write("figures/io-uring.svg", svg(W, H, "".join(b), "io_uring"))


@fig
def fig_zero_copy():
    W, H = 800, 360
    b = [text(W / 2, 26, "Zero-copy: sendfile() skips the user buffer", GREY,
              15, 700)]
    b.append(text(200, 66, "read() + write()", GREY, 12, 700))
    b.append(cylinder(80, 84, 70, 70, GREY_D, WHITE, ["disk"], size=10))
    b.append(box(200, 90, 110, 40, "kernel buf", TEAL, size=10, rx=8))
    b.append(box(200, 150, 110, 40, "user buf", BLUE, size=10, rx=8))
    b.append(box(200, 210, 110, 40, "socket buf", TEAL, size=10, rx=8))
    b.append(arrow(150, 110, 200, 110, GREY))
    b.append(arrow(255, 130, 255, 150, GREY))
    b.append(arrow(255, 190, 255, 210, GREY))
    b.append(text(255, 285, "4 copies + 4 mode switches", RED, 10, 600))
    b.append(text(600, 66, "sendfile()", TEAL, 12, 700))
    b.append(cylinder(480, 84, 70, 70, GREY_D, WHITE, ["disk"], size=10))
    b.append(box(600, 110, 120, 40, "kernel buf", TEAL, size=10, rx=8))
    b.append(box(600, 200, 120, 40, "socket buf", TEAL, size=10, rx=8))
    b.append(arrow(550, 120, 600, 130, GREY))
    b.append(arrow(660, 150, 660, 200, TEAL))
    b.append(text(660, 285, "stays in kernel: 0 user copies", TEAL, 10, 600))
    b.append(text(W / 2, H - 12, "splice(), sendfile() and MSG_ZEROCOPY cut "
                  "copies for big file->socket transfers", LIGHT, 11, 500))
    write("figures/zero-copy.svg", svg(W, H, "".join(b), "Zero copy"))


# -- 08 kernel interfaces ----------------------------------------------------
@fig
def fig_proc_fs():
    W, H = 780, 340
    b = [text(W / 2, 26, "/proc and /sys: the kernel as a filesystem", GREY, 15,
              700)]
    b.append(box(60, 90, 150, 50, ["cat, open(),", "read()"], BLUE, size=11,
                 lh=15, rx=10))
    b.append(arrow(210, 115, 300, 115, GREY))
    b.append(box(300, 74, 200, 40, "/proc/[pid]/status", TEAL, size=11, rx=8,
                 mono=True))
    b.append(box(300, 122, 200, 40, "/proc/meminfo", TEAL, size=11, rx=8,
                 mono=True))
    b.append(box(300, 170, 200, 40, "/sys/class/net/...", TEAL, size=11, rx=8,
                 mono=True))
    b.append(arrow(500, 140, 590, 140, GREY))
    b.append(box(590, 116, 150, 50, ["kernel data,", "rendered on read"],
                 GREY_D, size=10, lh=15, rx=10))
    b.append(text(W / 2, 260, "these files are not on disk -- the kernel "
                  "synthesizes their contents when you read them", LIGHT, 11,
                  500))
    b.append(text(W / 2, H - 14, "ps, top, free and lsof are mostly just "
                  "/proc parsers", LIGHT, 11, 500))
    write("figures/proc-fs.svg", svg(W, H, "".join(b), "procfs"))


@fig
def fig_namespaces():
    W, H = 800, 360
    b = [text(W / 2, 26, "Namespaces + cgroups = containers", GREY, 16, 700)]
    b.append(box(60, 70, 340, 250, "", "none", rx=12, stroke=BLUE, sw=1.4))
    b.append(text(230, 88, "namespaces: WHAT a process sees", BLUE, 11, 700))
    ns = ["PID  (own process tree)", "NET  (own interfaces, ports)",
          "MNT  (own filesystem view)", "UTS  (own hostname)",
          "IPC / USER / cgroup / time"]
    for i, n in enumerate(ns):
        b.append(box(85, 110 + i * 40, 290, 32, n, TEAL, size=10, rx=6))
    b.append(box(440, 70, 300, 250, "", "none", rx=12, stroke=AMBER, sw=1.4))
    b.append(text(590, 88, "cgroups: HOW MUCH it can use", AMBER, size=11,
                  weight=700))
    cg = ["cpu  (shares, quota)", "memory  (hard/soft limits)",
          "io  (bandwidth)", "pids  (max tasks)"]
    for i, c in enumerate(cg):
        b.append(box(465, 120 + i * 46, 250, 36, c, GREY_D, size=10, rx=6))
    b.append(text(W / 2, H - 12, "clone(CLONE_NEW*) + cgroup writes are how "
                  "Docker/Kubernetes isolate workloads -- no VM needed", LIGHT,
                  11, 500))
    write("figures/namespaces.svg", svg(W, H, "".join(b), "Namespaces"))


@fig
def fig_seccomp():
    W, H = 780, 320
    b = [text(W / 2, 26, "seccomp: filter which syscalls are allowed", GREY, 15,
              700)]
    b.append(box(60, 110, 150, 60, ["sandboxed", "process"], BLUE, size=11,
                 lh=15, rx=10))
    b.append(arrow(210, 140, 300, 140, GREY))
    b.append(box(300, 100, 180, 80, ["seccomp-BPF filter", "inspects nr + args"],
                 AMBER, tcol=INK_DARK, size=11, lh=16, rx=12))
    b.append(arrow(480, 120, 590, 100, TEAL))
    b.append(box(590, 78, 150, 42, ["ALLOW -> kernel"], TEAL, size=10, rx=8))
    b.append(arrow(480, 160, 590, 190, RED))
    b.append(box(590, 168, 150, 42, ["KILL / errno / trap"], RED, size=10,
                 rx=8))
    b.append(text(W / 2, 250, "shrinks the kernel attack surface: a compromised "
                  "process can only call the syscalls you whitelisted", LIGHT,
                  11, 500))
    b.append(text(W / 2, H - 14, "used by container runtimes, browsers and "
                  "systemd's SystemCallFilter=", LIGHT, 11, 500))
    write("figures/seccomp.svg", svg(W, H, "".join(b), "seccomp"))


def build_font_style(chars):
    if not os.path.exists(FONT_PATH):
        print("WARNING: Virgil.woff2 not found; figures fall back to a system "
              "handwriting font.")
        return ""
    from fontTools.subset import Options, Subsetter
    from fontTools.ttLib import TTFont
    text_ = "".join(sorted(chars))
    opts = Options()
    opts.flavor = "woff2"
    opts.desubroutinize = True
    opts.notdef_outline = True
    opts.recalc_bounds = True
    font = TTFont(FONT_PATH)
    ss = Subsetter(options=opts)
    ss.populate(text=text_)
    ss.subset(font)
    buf = io.BytesIO()
    font.save(buf)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    print(f"embedded font: {len(chars)} glyphs, {len(buf.getvalue())} bytes")
    return ('<style>@font-face{font-family:"Virgil";font-style:normal;'
            'font-weight:400 700;src:url("data:font/woff2;base64,'
            f'{b64}") format("woff2");}}</style>')


if __name__ == "__main__":
    for fn in ALL:
        fn()
    FONT_STYLE = build_font_style(USED_CHARS)
    for fn in ALL:
        fn()
    print(f"\nDone: {len(ALL)} figures generated.")
