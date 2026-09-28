# weed-out CLI

The command surface: the grammar, what a bare command word answers, what
each command prints, what each flag decides, and the exit codes. The
model underneath, and the reasoning that produced it, is in DESIGN.

## Grammar

`weed-out <delete | trash | tree> PATH [--keep LIST] [--dry-run | --commit]
[--dot-files] [--dot-dirs]`. The command comes first and `PATH` follows it.
Flags come last, in any order among themselves.

### Flags

| Flag | What it decides |
| --- | --- |
| `--keep LIST` | Comma-separated paths and globs. Adds to `.weed-out-ignore`. |
| `--dry-run` | Report only. The same as giving no mode flag, spelled out. |
| `--commit` | Carry the removal out. Excludes `--dry-run`. `tree` refuses it. |
| `--dot-files` | Keep every dotfile, listed or not. |
| `--dot-dirs` | Keep every dot-directory and its contents, listed or not. |

### Why the action is a command

Two separate questions sit on two separate axes:

- **Disposal**: permanent removal, or the OS trash? The command.
- **How far to go**: preview it, or actually do it? The mode flag.

`tree` is a command rather than a mode because it can only ever look. It
takes no mode flag, so `tree PATH --commit` is a parse error. And since
`tree` stands on its own, a preview never makes you pick a disposal you
haven't decided on yet.

### The bare verb is a dry run

`weed-out delete .` reads as an imperative, so it must not act like one.
It reports what would be removed and touches nothing. `--commit` is the
separate keystroke that makes it real.

No confirmation prompt follows `--commit`. The flag already is the second
step a prompt would supply, and it is typed on purpose rather than
answered on autopilot, which is how a prompt fails once it becomes
routine. Worth revisiting only if a real accident happens.

### `PATH` is required

The destructive form always states what it is aimed at. A defaulted
target would let a short, muscle-memory `--commit` line do real damage
from the wrong directory. Typing `.` costs nothing.

`--keep` stays a flag rather than a second positional. With two
positionals, `weed-out delete foo` would be ambiguous: path, or keep
entry? It is not required either, since a `.weed-out-ignore` at `PATH`
supplies the same entries.

### Positions are fixed

The command word is the first argument and `PATH` is the second, and
nothing else fills those slots. From Python 3.12, argparse will happily
take a positional from after the flags, so `weed-out delete --keep "*.md"
.` would parse. Accepting it would let the grammar drift from the
documented one, and drift by interpreter version at that.

Argparse still owns the vocabulary: unknown commands, unknown flags, bad
values, and the mode-flag pair. The slots are ours. A missing `PATH`, or
a stray token after it, exits 1 with the command's usage line.

### Flags are spelled in full

Left to its default, argparse accepts any unambiguous prefix, so `--com`
would mean `--commit`. `--commit` is only a deliberate keystroke if it has
to be typed whole. Abbreviating only the read-only flags was considered
and dropped: one flag surface behaving two ways costs more to explain
than it saves.

## What the commands answer

### A bare word is a question

Bare `weed-out` prints the banner and exits 0. A command word and
nothing else prints that command's own page, exit 0. Once any other token
is present, the user asked for something specific, and answering with
help would hide the mistake. A missing `PATH` there is an error, exit 1.

That page is the only manual most users open, since installing the tool
leaves the documents behind. So it carries how: every flag, every default,
and what happens. Why stays in these documents.

A page is the command's own prose, then argparse's help for the command.
The usage line, `PATH`, and the flags are written once, where they are
parsed, so the page cannot document one the parser rejects. The banner
works the same way and ends in `weed-out --help`. Both spellings of the
version are listed there. argparse names `version` among the commands in
its own errors anyway, so hiding it was never complete.

Stdin decides none of this. Treating a non-terminal stdin as piped input
catches cron, `nohup`, and CI, which all hand a process `/dev/null`. The
same command line would then answer two ways depending on where it ran.
`weed-out` reads no piped input, and the banner says so.

### What each command prints

`tree` draws the whole tree on stdout, tags every removal target
`[REMOVE]`, and closes with a tally:

```text
Tree under /home/go/proj ([REMOVE] marks what would be removed):

├── notes/  [REMOVE]
├── src/
│   └── pkg/
│       ├── a.py
│       └── b.py
├── venv/  [REMOVE]
└── README.md

5 kept, 2 to remove (2 directories collapsed -- contents not listed).
```

The tag names no disposal, because `tree` is neither `delete` nor
`trash`. The parenthetical is the part that matters. `venv/` is one line
here and thousands of files on disk, so without a count of collapsed
directories the preview would understate what `--commit` does.

`delete` and `trash` without `--commit` print bare paths on stdout, one
per line, then the same correction as a count and a trailer naming the
disposal:

```text
/home/go/proj/notes
/home/go/proj/venv

2 items would be removed, including 2 directories and everything inside them.

Dry run only. Re-run with --commit to permanently delete.
```

Bare paths, because that list is the one output a user may reasonably
pipe. Everything advisory goes to stderr for the same reason. The count
is of removal roots, not files.

Under `--commit` there is no listing and no trailer. The run is over, so
a list would be a report rather than a preview.

### An absent keep list keeps everything

An empty keep list can mean "keep nothing", which deletes everything
under `PATH`, or "keep everything", which removes nothing. `weed-out`
takes the safe reading and treats it as `--keep "."`. Both read-only
surfaces say so on stderr, so a user who forgot `--keep` learns why
nothing is tagged.

`--commit` with nothing to keep still exits 1. There, an empty list is
far likelier a mistake than a choice, say an unset variable in
`weed-out delete "$DIR" --keep "$PATTERNS" --commit`. Exiting 0 would
leave the caller unable to tell a cleanup from a keep list that
evaporated.

Leniency and advice belong to the surfaces that only look. `--commit` is
held to the stricter contract.

### Warning when a path pattern narrows

The trap is slash versus no slash. `*.md` keeps every `.md` file at any
depth. `/*.md` is path-matched, and once the leading slash is stripped it
means top-level `.md` files only. Adding a slash to be *more* explicit
quietly narrows the pattern, and under a keep-only grammar a narrower
pattern means files deleted.

So the read-only surfaces print one line on stderr when a pattern is
provably narrowing:

```text
weed-out: '/*.md' matches 2 paths, but '**/*.md' would match 47. A '*'
never crosses a '/' -- use '**' if you meant any depth.
```

It fires only for a pattern with `/` and `*` but no `**`, and only when
the pattern's own `**` form would match more. `src/*.py` is compared with
`src/**/*.py`, never with every `.py` under `PATH`, which would count the
ones inside `venv/`. So a pattern scoped on purpose stays quiet, and the
number shown is what the suggested fix would actually protect.

Stderr, so a piped `--dry-run` list stays clean. Never under `--commit`,
where the advice arrives too late and would read as an error in the run.

## Errors and exit codes

Two failures are about readiness, not grammar: `PATH` is not a directory
(`weed-out: {root} is not a directory`), or `--commit` has no keep entries
from either source. Both are caught before any walk starts, and both exit
1 without a usage line. The command line was read fine, so printing usage
would answer a question nobody asked.

- `0`: success, and documentation (the banner, a command's own page, or the
  version).
- `1`: every error `weed-out` raises itself: a missing `PATH`, a stray
  token after it, `PATH` not a directory, or `--commit` with no keep
  entries.
- `2`: argparse's own errors: an unknown flag, an unknown command, a bad
  value, or `--dry-run` and `--commit` together.

The line falls where ownership falls. Argparse keeps its vocabulary, and
the slots are ours. When it's unclear who owns a new error, it's ours, and
it exits 1.

All of these go to stderr as `weed-out: <message>`.

## Use of AI

Both the use of AI and its disclosure are deliberate. Code and documentation in
this project are written in collaboration with Artificial Intelligence (AI). The
division of labour: the AI explores, challenges assumptions and edge cases, and
drafts; the human initiates, drafts the designs, explores alongside the AI,
reviews every change, and decides what gets committed.

---

**East Van AI** · AI for the rest of us! · Vancouver, BC, Canada

[github.com/east-van-ai](https://github.com/east-van-ai) · <east-van-ai@proton.me>

Copyright (c) 2026 Go Nakamaru
