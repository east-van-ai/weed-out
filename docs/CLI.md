# weed-out CLI

The command surface: the grammar, what a bare command word answers, what
each command prints, what each flag decides, and the exit codes. The
model underneath, and the reasoning that produced it, is in DESIGN.

## Grammar

`weed-out <delete | trash | tree> PATH [--keep LIST] [--dry-run | --commit]
[--dot-files] [--dot-dirs]`. The action is a command, not a flag, and it
comes first. `PATH` follows it. Flags come last and are freely ordered
among themselves.

### Why the action is a command

Two unrelated questions, held on separate axes rather than treated as
one:

- **Disposal**: permanent removal, or the OS trash? The command.
- **How far to go**: preview it, or actually do it? The mode flag.

`tree` is a command rather than a mode because it can only ever look. It
defines no mode flag at all, so `tree PATH --commit` is a parse error by
construction rather than a case the code has to handle. And because
`tree` stands on its own, previewing never requires naming a disposal
method you may not have decided on yet.

### The bare verb is a dry run, deliberately

`weed-out delete .` reads as an imperative. It must therefore not be
one: it reports what would be removed and touches nothing. `--commit` is
the separate, explicit keystroke that makes it real. The bare verb is
the safe end of a two-valued axis whose other end has to be spelled out,
not a silent default concealing an invisible action.

No interactive confirmation follows `--commit`. The flag is already the
second step a prompt would supply, and it is typed on purpose rather
than answered under momentum, which is the failure a prompt invites once
it becomes routine. Worth revisiting only if a real accident happens.

### `PATH` is required

A required positional means the destructive form always states what it
is aimed at. The risk a defaulted target carries is not the default
itself (a bare verb is only a dry run) but that a `--commit` run would
inherit one: a short, muscle-memory line that does real damage from the
wrong directory. Typing `.` is not a meaningful cost for a tool whose
purpose is deleting things.

`--keep` deliberately stays a flag rather than becoming a second
positional. With exactly one positional there is nothing to
disambiguate; a second would make `weed-out delete foo` ambiguous
(path, or keep entry?) with no default able to resolve it.

`--keep` is not strictly required. A `.weed-out-ignore` file at `PATH`
supplies the same kind of entries and merges with the flag, so a project
that checks one in never retypes its keep list; DESIGN carries that
file's rules. Neither source is required under the read-only surfaces
(see "An absent keep list keeps everything" below).

### Positions are decided, not inferred

The command word is `sys.argv[1]` and `PATH` is `sys.argv[2]`, checked
against those slots directly. `main()` reads the tokens ahead of the
first flag (`leading_paths`) and discards whatever argparse resolved
for the positional. Since Python 3.12 argparse back-fills a trailing
optional positional from a token appearing after any number of flags,
so `weed-out delete --keep "*.md" .` would parse happily and the
accepted grammar would silently drift from the documented one, and
drift by interpreter version at that.

To make that possible, `PATH` is `nargs="?"` in the parser: optional to
argparse so a bare command word reaches `main` and gets an answer, its
parsed value unused. Argparse still owns the vocabulary (unknown
command, unknown flag, bad value, the mode-flag pair), reported through
`parse_known_args` plus a re-parse when an unknown flag is present,
because argparse names the flag better. Shortfalls in the slots are
ours: no `PATH`, or a stray token after it, exits 1 with the command's
usage line.

### Flags are spelled in full

`argparse` matches any unambiguous prefix of a long flag unless
`allow_abbrev=False` says otherwise. Left at the default, `--com` and
even `--c` mean `--commit`. `--commit` is only a separate, explicit
keystroke if it has to be typed whole, and a four-character prefix is
short enough to arrive by a slip of the hand.

The keyword has to be repeated on every subparser. `add_parser()` builds
a fresh `ArgumentParser` from the keywords it is handed and inherits
nothing else, so setting it on the top-level parser alone leaves
`delete PATH --com` parsing happily. Every flag `weed-out` defines lives
on a subparser, so every command added later has to carry the keyword
too.

Abbreviating the read-only flags while holding `--commit` to its full
spelling was considered and dropped. One flag surface behaving two ways
costs more to explain than the keystrokes it saves.

## What the commands answer

### A bare word is a question

Bare `weed-out` prints the usage banner (`cli.py`'s module docstring)
and exits 0. A command word and nothing else at all prints that
command's own docstring, exit 0. The test is `len(sys.argv) == 2`,
never "the argument is missing": once any other token is present the
user asked for something specific, and answering with help would hide
the mistake. A missing `PATH` there is an error, exit 1.

Stdin decides none of this. Gating the banner on `isatty()`, and
treating a non-terminal stdin as piped input, is a wider test than it
looks: `/dev/null`, which is what cron, `nohup`, and CI hand a process,
is not a terminal either. The same command line would answer two ways
depending on where it was launched. What was typed decides the answer.
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

The tag is disposal-neutral, because `tree` is neither `delete` nor
`trash`. The parenthetical is the load-bearing half of the tally:
`venv/` is one line here and thousands of files on disk, so without a
count of collapsed directories the preview understates what `--commit`
would do. DESIGN carries why the walk stops at a doomed directory at
all.

`delete` and `trash` without a mode flag, and with `--dry-run`, print
bare paths on stdout, one per line, then the same correction as a count
line and a trailer naming the disposal:

```text
/home/go/proj/notes
/home/go/proj/venv

2 items would be removed, including 2 directories and everything inside them.

Dry run only. Re-run with --commit to permanently delete.
```

Bare paths, because that list is the one output a user may reasonably
pipe. Everything advisory goes to stderr for the same reason. `N` counts
removal roots, not files.

Under `--commit` there is no listing and no trailer. The run has already
happened, so a list of what it did would be a report rather than a
preview, and the trailer would point at a run that is over.

### An absent keep list keeps everything

An empty keep list has two readings, and only one of them is safe:
"keep nothing", which deletes everything under `PATH`, or "keep
everything", which removes nothing. `weed-out` takes the second. The
absent list resolves to `--keep "."`, which normalizes to `PATH` itself,
and a directly-kept directory protects its whole subtree, so nothing in
the walks needs a special case for it. Both read-only surfaces announce
the substitution on stderr, so a user who forgot `--keep` is told why
nothing is tagged.

The error survives in exactly one place: `--commit` with nothing to keep
still exits 1. There, an empty keep list is far likelier to be a
misconfiguration than a deliberate choice (an unset variable in
`weed-out delete "$DIR" --keep "$PATTERNS" --commit`), and exiting 0
would leave the caller unable to tell a successful cleanup from a keep
list that evaporated. Nothing would be deleted either way; the cost of a
silent exit 0 is the signal, and the signal is worth keeping.

This is the line `warn_narrowing_patterns` already sits on: leniency and
advice belong to the surfaces that only look, while `--commit` is held
to the stricter contract.

### Warning when a path pattern narrows

The asymmetry a user is most likely to trip over is not `*` versus `**`,
it is slash versus no slash. `*.md` protects every `.md` file at any
depth; `/*.md` is path-matched, and once the leading slash is stripped
it is a single-segment pattern: top-level `.md` files only. Adding a
leading `/` to be *more* explicit silently narrows the pattern, and
under a keep-only grammar a pattern that narrows is a file that gets
deleted. DESIGN carries the matching rules the asymmetry falls out of.

The read-only surfaces therefore emit one advisory line on stderr when a
pattern is provably narrowing:

```text
weed-out: '/*.md' matches 2 paths, but '**/*.md' would match 47. A '*'
never crosses a '/' -- use '**' if you meant any depth.
```

It fires only when a pattern contains `/` and `*` but no `**`, *and* the
pattern's own `**` form would have matched strictly more entries. The
comparison is against `deepen_pattern(p)`, not against the bare
filename: measuring `src/*.py` against every `.py` under `PATH` would
count the ones inside `venv/`, so a deliberately scoped pattern would
nag on every run for doing exactly what it was asked. Compared against
`src/**/*.py` it speaks up only about depth, and the number it prints is
what the suggested fix would actually protect.

The candidate test is cheap and runs *before* any walk, so an invocation
with no such pattern pays nothing. This must not add a second full
`rglob` to a venv-sized tree just to stay silent. Stderr rather than
stdout, because `--dry-run` prints a list of paths a user may reasonably
pipe. Suppressed under `--commit`: the hint's value is entirely upstream
of committing, and a stderr line after a destructive run reads as an
error report on the run itself.

## Errors and exit codes

### Readiness failures

Each command's `run()` resolves `PATH` and checks `root.is_dir()` itself, before
any walk starts, and fails loudly (`weed-out: {root} is not a directory`, exit 1)
rather than silently walking nothing. The empty-keep-list case (`--commit` passed
with neither `--keep` nor `.weed-out-ignore` supplying an entry) fails the same way,
from `run_removal`, before any walk runs. No usage line accompanies either: both are
readiness failures, not grammar errors. The command line was read fine, and printing
usage beside it would answer a question nobody asked.

### Exit codes

- `0`: success, and documentation (the banner, or a command's own
  doc).
- `1`: every error `weed-out` raises itself (a missing `PATH`, a stray
  token after it, `PATH` not a directory, or neither `--keep` nor
  `.weed-out-ignore` yielded any keep entries *and* `--commit` was
  passed).
- `2`: argparse's own errors (unknown flag, unknown command, a bad
  value, or `--dry-run` and `--commit` together).

The line falls where ownership falls: argparse keeps the vocabulary it
owns, and the slots are ours (see "Positions are decided, not
inferred"). The rule for anything added later: when it is genuinely
ambiguous who owns an error, it is ours, and it exits 1.

All self-raised errors go to stderr as `weed-out: <message>`.

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
