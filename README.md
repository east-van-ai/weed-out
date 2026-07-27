# weed-out - delete everything except what you keep

Delete everything except what you say to keep. Most cleanup tools are
exclude-list shaped: "delete these." `weed-out` inverts that — you
state the keep list, everything else in the tree goes.

## Table of Contents

- [weed-out - delete everything except what you keep](#weed-out---delete-everything-except-what-you-keep)
  - [Table of Contents](#table-of-contents)
  - [Why](#why)
  - [Example output](#example-output)
  - [Install](#install)
  - [Usage](#usage)
    - [How `--keep` works](#how---keep-works)
    - [The `.weed-out-ignore` file](#the-weed-out-ignore-file)
    - [After a `--commit` run](#after-a---commit-run)
  - [Notes](#notes)
  - [Use of AI](#use-of-ai)

## Why

Standard cleanup tools (`rm`, `find -delete`, most CLI cleaners on npm)
are exclude-list shaped: you tell them what to remove. That's backwards
for the case this was built for — prepping a repo for release, where
you know the small set of things that should survive and don't want to
enumerate every build artifact, cache folder, and scratch file that
shouldn't.

`weed-out` flips the model. You state the keep list. Everything else is
fair game. Useful for stripping a repo down to release-ready shape,
clearing build artifacts, or pruning a directory back to a known-good
set of files before a commit.

Dry run is the default. Nothing is deleted unless you pass `--commit`.

## Example output

```text
Tree under . ([DELETE] marks what would be removed):

├── src/
├── README.md
├── build/  [DELETE]
└── notes.txt  [DELETE]
```

- `--tree` prints the whole directory with `[DELETE]` tags — read-only,
  no changes made.
- Plain dry run (no `--tree`, no `--commit`) prints `would delete: PATH`
  for each entry that isn't being kept.
- `--commit` is the only flag that deletes anything.

## Install

`weed-out` requires Python 3.9 or newer and has no runtime
dependencies — standard library only. Tested in CI on Python 3.9
through 3.14.

```bash
pipx install "git+https://github.com/gonakamaru/weed-out.git@stable"
```

No dependencies to worry about, this is a small, self-contained tool.

## Usage

```bash
# Preview only, shows a tree with [DELETE] tags, nothing touched
weed-out --keep "src/,tests/,*.md,.gitignore,.python-version,LICENSE,pyproject.toml" --root . --tree

# List what would be deleted (dry run, no --tree, no --commit)
weed-out --keep "src/,tests/,*.md,.gitignore,.python-version,LICENSE,pyproject.toml" --root .

# Actually delete
weed-out --keep "src/,tests/,*.md,.gitignore,.python-version,LICENSE,pyproject.toml" --root . --commit

# Relying entirely on a checked-in .weed-out-ignore at --root, no --keep needed
weed-out --root . --tree
```

| Flag | Description |
| --- | --- |
| `--keep` | Comma-separated list of files, directories, and glob patterns to keep. Optional if a `.weed-out-ignore` file at `--root` supplies the keep list instead — but at least one of the two is required. |
| `--root` | Root directory to operate on. Defaults to `.` |
| `--dot-files` | Keep dotfiles by default, even if not listed in `--keep` |
| `--dot-dirs` | Keep dot-directories by default, even if not listed in `--keep` |
| `--tree` | Print a tree of the whole directory, tagging what would be deleted. No changes made. |
| `--commit` | Actually delete. Without this flag, `weed-out` only reports what it would do. |

Bare `weed-out` prints this usage information; `weed-out` does not read
piped input — its unit of work is a directory, not a stream. Exit
codes: `0` success, `1` for any error `weed-out` raises itself (usage
errors, `--root` not a directory, or neither `--keep` nor
`.weed-out-ignore` supplying any keep entries), `2` for argparse's own
errors. (Curious about the grammar? See the "CLI Grammar" section of
[DESIGN.md](DESIGN.md).)

### How `--keep` works

Entries can be:

- **Exact paths** — `src/`, `README.md`, `.gitignore`
- **Glob patterns** — `*.md`, `test_*.py`, `src/weed_out/*.py`

Glob patterns come in two flavors, decided by whether the pattern
contains a `/`:

**Bare patterns** (no `/`) match by filename at any depth. `*.md`
keeps `README.md` at the root and `src/notes/design.md` three folders
down — same rule, everywhere in the tree.

**Path-scoped patterns** (contain a `/`) match against the path
relative to `--root` instead of just the filename, so the pattern only
protects files in that location. `src/weed_out/*.py` protects `.py`
files directly under `src/weed_out/` without also protecting every
`.py` file anywhere else under `--root` — say, inside a `venv/`.

That last point is where `**` comes in, and it's worth knowing even if
you've never seen it before: **`**` matches zero or more whole path
segments** — shorthand for "at any depth from here down." A plain `*`
in a path-scoped pattern stops at the next `/`, so `src/weed_out/*.py`
only protects files directly inside `src/weed_out/`, not anything
nested deeper. Swap in `**` to reach deeper too:

```text
src/weed_out/*.py       matches: src/weed_out/cli.py
                         misses:  src/weed_out/sub/deep.py

src/weed_out/**/*.py    matches: src/weed_out/cli.py
                         matches: src/weed_out/sub/deep.py
```

A leading or trailing `/` on a pattern is optional and stripped before
matching, so `/src/*.py` and `src/*.py` behave the same. This is
gitignore-style matching, deliberately — see "Path-scoped glob
patterns" in [DESIGN.md](DESIGN.md) for why.

A directory is never deleted if anything inside it, at any depth, is
being kept. So keeping `src/notes/design.md` via a pattern
automatically protects `src/notes/` and `src/`, even though neither
directory name matches anything in your `--keep` list itself. See
"The protected-directory bug" in [DESIGN.md](DESIGN.md) for why this
needs its own pass.

### The `.weed-out-ignore` file

Drop a `.weed-out-ignore` file at `--root` to check a keep list into
the repo instead of retyping it as a `--keep` string every time:

```text
src/
tests/
*.md
.gitignore
.python-version
LICENSE
pyproject.toml
```

- One entry per line — same exact-path/glob-pattern rules as `--keep`,
  just newline-separated instead of comma-separated.
- Blank lines and lines starting with `#` are ignored, so you can
  annotate entries.
- `weed-out` reads it automatically from `--root` — no flag required —
  and merges its entries with anything passed via `--keep`; neither
  source overrides the other.
- It's read-only from the file's point of view too: like everything
  else in `weed-out` except `--commit`, having the file present never
  deletes anything on its own — it only ever adds to what survives.

### After a `--commit` run

Once files are removed, `weed-out` does a second pass and removes any
directory left empty as a result, bottom-up, so nested empty folders
clear out before their parents are checked. Directories you listed
explicitly in `--keep` are never removed by this pass, even if they end
up empty.

## Notes

- Always run with `--tree` first on anything that matters. Read it.
- `--commit` is the only flag that deletes anything. Everything else is
  read-only.
- No undo. This calls `shutil.rmtree` and `Path.unlink` directly. Back
  up or commit to git before running for real.
- Symlinks are followed by `rglob` in the underlying walk; behavior on
  symlinked directories hasn't been stress tested.
- Case sensitivity follows the OS default via `fnmatch`; this may
  differ between macOS (case-insensitive by default) and Linux.
- No `.gitignore`-style negation syntax (`!pattern`) — by design, not a
  gap. `weed-out` never expresses "delete this," only what survives.
- A `.weed-out-ignore` file at `--root` is read automatically and
  merged with `--keep` — see "The `.weed-out-ignore` file" above, and
  the same-named section in [DESIGN.md](DESIGN.md) for the full design
  rationale.

See [DESIGN.md](DESIGN.md) for the reasoning behind these decisions and
open questions for where this could go next.

## Use of AI

This project is built with Artificial Intelligence (AI), deliberately
and in the open. Code and documentation are written in collaboration
with remote and local AI; design decisions, code review, and final
judgment stay human.

---

**East Van AI** · AI for the rest of us! · Vancouver, BC, Canada

[github.com/east-van-ai](https://github.com/east-van-ai) · <east-van-ai@proton.me>

Copyright (c) 2026 Go Nakamaru
