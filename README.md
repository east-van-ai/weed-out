# weed-out - delete everything except what you keep

`weed-out` deletes everything in a directory tree except what you
explicitly tell it to keep, the inverse of `rm`/`find -delete`-style
cleanup.

## Table of Contents

- [weed-out - delete everything except what you keep](#weed-out---delete-everything-except-what-you-keep)
  - [Table of Contents](#table-of-contents)
  - [Why](#why)
  - [Example output](#example-output)
  - [Install](#install)
  - [Usage](#usage)
    - [How `--keep` works](#how---keep-works)
    - [The `.weed-out-ignore` file](#the-weed-out-ignore-file)
    - [Exit codes](#exit-codes)
  - [Notes](#notes)
  - [Use of AI](#use-of-ai)

## Why

Most cleanup tools are exclude-list shaped: `rm`, `find -delete`, most
CLI cleaners on npm all ask what to remove. That's backwards for
prepping a repo for release, clearing build output, or pruning a
folder back to a known-good set of files, cases where the keep list is
short and the accumulated cruft (cache dirs, scratch files, whatever
some other tool left behind) isn't worth enumerating by hand.

`weed-out` flips it: you state the keep list, everything else is fair
game. Because getting this wrong deletes real files, the command names
the disposal: `delete` (permanent) or `trash` (recoverable, sends items
to the OS trash instead). Neither actually removes anything until you
add `--commit`. On its own, `weed-out delete .` only reports.

There's a second, quieter benefit to naming what survives. A release
checklist that says `rm secret.txt` discloses that a file called
`secret.txt` was there. The removal instruction names the thing being
removed, so the cleanup step leaks exactly what the cleanup was meant to
get rid of, to anyone who reads the manual or the shell history. A
`weed-out` invocation names only the keep list, so it says nothing at all
about what was discarded. Whatever was in the directory stays the
directory's business. This is the same property as the deliberate absence
of `!pattern` negation (see [Notes](#notes)): `weed-out` only ever talks
about what survives.

## Example output

- Plain dry run (`delete` or `trash` without `--commit`): prints the
  bare path of each entry that isn't on the keep list, one per line,
  then a final count.
- `tree`: prints the directory with `[REMOVE]` tags and a closing
  tally. Read-only, and takes no `--commit` at all.
- `--commit` is the only thing that touches the filesystem; every
  other invocation just reports.

```text
Tree under . ([REMOVE] marks what would be removed):

├── build/  [REMOVE]
├── src/
│   └── main.py
├── README.md
└── notes.txt  [REMOVE]

3 kept, 2 to remove (1 directory collapsed -- contents not listed).
```

A directory that isn't kept is printed as a single tagged line and not
expanded, because nothing inside it can be kept either: if anything
were, the directory itself would survive. So a doomed `venv/` is one
line rather than several thousand, and it goes to the trash as one
recoverable folder rather than as thousands of loose items. The tally's
last number is there so a collapsed directory is never mistaken for a
single doomed file.

## Install

`weed-out` requires Python 3.9 or newer. It depends on the standard
library plus one small runtime dependency, [`send2trash`](https://pypi.org/project/Send2Trash/)
(BSD-3-Clause), used by `trash` to move items to the OS trash instead
of deleting them outright. `pipx`/`pip` install it automatically, with
no separate step. Tested in CI on Python 3.9 through 3.14.

```bash
pipx install "git+https://github.com/east-van-ai/weed-out.git@stable"
```

`pipx` installs Python CLI tools into isolated environments, no
dependency conflicts to worry about. Worth having around if you use
more than one Python CLI tool.

## Usage

Bare `weed-out` prints this usage summary. It doesn't read piped
input, its unit of work is a directory, not a stream.

The grammar is always `weed-out COMMAND PATH [flags]`.

`PATH` is required (use `.` for the current directory), and flags
come after it, in any order among themselves.

```bash
# Preview as a tree with [REMOVE] tags, nothing touched
weed-out tree . --keep "src/**/*.py,tests/*.py,README.md"

# Relying entirely on a checked-in .weed-out-ignore at PATH, no --keep needed
weed-out tree .

# List what would be permanently deleted (dry run, nothing removed)
weed-out delete . --keep "src/**/*.py,tests/*.py,README.md"

# Same dry run, made explicit
weed-out delete . --keep "src/**/*.py,tests/*.py,README.md" --dry-run

# Actually send everything not kept to the OS trash -- recoverable
weed-out trash . --keep "src/**/*.py,tests/*.py,README.md" --commit

# Actually delete permanently -- no undo
weed-out delete . --keep "src/**/*.py,tests/*.py,README.md" --commit
```

| Command | Description |
| --- | --- |
| `delete PATH` | Permanently remove everything not kept. No undo. |
| `trash PATH` | Send everything not kept to the OS trash -- recoverable. |
| `tree PATH` | Print a tree of the whole directory, tagging what would be removed. Read-only; takes no `--dry-run`/`--commit`. |

| Flag | Description |
| --- | --- |
| `--keep` | Comma-separated list of files, directories, and glob patterns to keep. Optional if a `.weed-out-ignore` file at `PATH` supplies the keep list instead. With neither, everything is kept and `--commit` is refused. |
| `--dry-run` | Explicitly report what would be removed without touching anything. This is what `delete`/`trash` do anyway when `--commit` is absent. |
| `--commit` | Actually carry the removal out. Permanent for `delete`. Mutually exclusive with `--dry-run`, and not accepted by `tree`. |
| `--dot-files` | Keep dotfiles, even if not in keep list. |
| `--dot-dirs` | Keep dot-directories, even if not in keep list. |

### How `--keep` works

With no keep list at all (no `--keep`, no `.weed-out-ignore`), a run
keeps everything, exactly as if you had passed `--keep "."`. Nothing is
tagged and nothing would be removed, so `weed-out tree PATH` is a safe
way to look at a directory before deciding what to protect. `--commit`
is the exception: it refuses to run without a keep list and exits 1,
because there an empty list is far likelier to be a forgotten argument
than a deliberate choice.

Entries can be:

- **Exact paths**: `src/`, `README.md`, `.gitignore`
- **Glob patterns**: `*.md`, `test_*.py`, `src/**/*.py`

Glob patterns come in two flavors, decided by whether the pattern
contains a `/`.

**Bare patterns** (no `/`) match by filename at any depth. `*.md`
keeps `README.md` at the root and `src/notes/design.md` three folders
down, same rule everywhere in the tree.

**Path-scoped patterns** (contain a `/`) match against the path
relative to `PATH` instead of just the filename, so the pattern only
protects files in that location. `src/weed_out/*.py` protects `.py`
files directly under `src/weed_out/` without also protecting every
`.py` file anywhere else under `PATH`, say inside a `venv/`.

A plain `*` in a path-scoped pattern stops at the next `/`, so
`src/weed_out/*.py` only protects files directly inside
`src/weed_out/`, not anything nested deeper. Use `**` to reach deeper
too, it matches zero or more whole path segments:

```text
src/weed_out/*.py       matches: src/weed_out/cli.py
                        misses:  src/weed_out/sub/deep.py

src/weed_out/**/*.py    matches: src/weed_out/cli.py
                        matches: src/weed_out/sub/deep.py
```

A leading or trailing `/` on a pattern is optional and stripped before
matching, so `/src/*.py` and `src/*.py` behave the same. Gitignore-style
matching, deliberately.

Watch the slash, though: it's what decides which flavor you get. `*.md`
has no `/`, so it's a bare pattern and keeps every `.md` file at any
depth. `/*.md` has one, so it's path-scoped, and after the leading slash
is stripped it's a single segment: top-level `.md` files only. Adding
the slash to be *more* explicit quietly protects less. `weed-out` warns
about this when it costs you something:

```text
weed-out: '/*.md' matches 2 paths, but '**/*.md' would match 47. A '*'
never crosses a '/' -- use '**' if you meant any depth.
```

The warning goes to stderr, and compares your pattern only against its
own `**` form; `src/*.py` is measured against `src/**/*.py`, never
against every `.py` under `PATH`. So scoping a pattern on purpose stays
silent; the only thing it speaks up about is depth, and the number it
shows is what the suggested fix would actually protect. `tree` and
`--dry-run` show it; `--commit` doesn't, since by then it's no longer
advice.

A directory is never deleted if anything inside it, at any depth, is
being kept. So keeping `src/notes/design.md` via a pattern
automatically protects `src/notes/` and `src/`, even though neither
directory name matches anything in `--keep` itself. See "Survival
propagates both ways" in [DESIGN.md](DESIGN.md) for why this needs
its own pass.

Those parent directories survive as *shells*, though: naming a file
keeps that file, not its neighbours. `--keep "src/main.py"` leaves
`src/` in place holding only `main.py`; a `src/junk.txt` beside it is
still removed. To keep a directory's whole contents, name the directory
itself (`--keep "src/"`).

### The `.weed-out-ignore` file

Drop a `.weed-out-ignore` file at `PATH` to check a keep list into
the repo instead of retyping it as a `--keep` string every time:

```text
# example .weed-out-ignore contents

.git/
.gitignore
.weed-out-ignore
src/**/*.py
tests/*.py
LICENSE
README.md
requirements.txt
```

- One entry per line, same exact-path/glob-pattern rules as `--keep`,
  just newline-separated instead of comma-separated. That also makes it
  the way to keep a file whose own name contains a comma, which `--keep`
  can't express.
- Blank lines and lines starting with `#` are ignored, so you can
  annotate entries.
- `weed-out` reads it automatically from `PATH`, no flag required,
  and merges its entries with anything passed via `--keep`. Neither
  source overrides the other.
- Read-only from the file's point of view too: like everything else in
  `weed-out` except `--commit`, having the file present never deletes
  anything on its own, it only ever adds to what survives.
- Only the file at `PATH` counts. A `.weed-out-ignore` in a
  subdirectory, such as `data/.weed-out-ignore`, isn't part of the
  keep rules.

### Exit codes

- `0`: success
- `1`: any error `weed-out` raises itself (usage errors, `PATH` not a
    directory, or `--commit` with neither `--keep` nor
    `.weed-out-ignore` supplying any keep entries)
- `2`: argparse's own errors (unknown flag, a missing or unknown
    command, a missing `PATH`, or `--dry-run` and `--commit` together)

Note that the two "bad path" cases differ: a *missing* `PATH` is
argparse's error and exits 2, while a `PATH` that isn't a directory is
`weed-out`'s own and exits 1.

## Notes

- Run `tree` first, always, on anything you'd be upset to lose. Take a
  moment to actually read it before moving on.
- `--commit` is the only thing that touches anything. Every other
  invocation is safe to run and just reports back -- including a bare
  `weed-out delete PATH`, which previews rather than deletes.
- There's no undo for `delete --commit` -- it works directly against
  your files and folders, so back things up or commit to git before
  running for real. `trash` is recoverable through your OS trash, but
  don't treat that as a substitute for backups either.
- A symlink -- whether it points at a file or a directory -- is never
  followed while walking the tree. It's treated as an atomic leaf, kept
  or removed as the link itself, never its target, and `tree` shows
  what it points at (`name -> target`) so you can see when a
  seemingly-ordinary file or folder is actually a link to somewhere
  else entirely. Naming one in `--keep` keeps the link, not whatever
  it points at, and nothing rides along with it the way a kept folder's
  contents would. The flip side: you can't reach *through* a link to
  keep something on the far side, so `--keep "notes/file.md"` where
  `notes` is a link keeps only the link, exactly as `--keep "notes"`
  would.
- Whether names are matched case-sensitively depends on your operating
  system, macOS is case-insensitive by default, Linux usually isn't.
- There's no way to say "delete this one thing" inside a pattern (no
  `!pattern` negation like `.gitignore` has). That's on purpose,
  `weed-out` only ever talks about what survives, never what to
  remove, which is also why a `weed-out` command discloses nothing
  about the files it removes (see [Why](#why)).

See [DESIGN.md](DESIGN.md) for the reasoning behind these decisions
and open questions for where this could go next.

## Use of AI

This project is built with Artificial Intelligence (AI), deliberately
and in the open. Code and documentation are written in collaboration
with remote and local AI; design decisions, code review, and final
judgment stay human.

---

**East Van AI** · AI for the rest of us! · Vancouver, BC, Canada

[github.com/east-van-ai](https://github.com/east-van-ai) · <east-van-ai@proton.me>

Copyright (c) 2026 Go Nakamaru
