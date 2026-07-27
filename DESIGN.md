# weed-out DESIGN

## Table of Contents

- [weed-out DESIGN](#weed-out-design)
  - [Table of Contents](#table-of-contents)
  - [Architecture](#architecture)
  - [File Tree](#file-tree)
  - [CLI Grammar](#cli-grammar)
  - [The Keep/Delete Pipeline](#the-keepdelete-pipeline)
    - [Two-phase keep resolution: exact paths vs. glob patterns](#two-phase-keep-resolution-exact-paths-vs-glob-patterns)
    - [Path-scoped glob patterns](#path-scoped-glob-patterns)
    - [The protected-directory bug, and why `build_protected_dirs` exists](#the-protected-directory-bug-and-why-build_protected_dirs-exists)
    - [Kept directories protect their contents, not just the shell](#kept-directories-protect-their-contents-not-just-the-shell)
    - [Deletion order: deepest first](#deletion-order-deepest-first)
    - [Empty directory cleanup as a separate pass](#empty-directory-cleanup-as-a-separate-pass)
    - [`--root` validation](#--root-validation)
    - [The `.weed-out-ignore` file](#the-weed-out-ignore-file)
  - [Open Questions](#open-questions)
  - [Known Bugs](#known-bugs)
  - [Use of AI](#use-of-ai)

## Architecture

`weed-out` requires Python 3.9 or newer and uses the standard library
only — no runtime dependencies (`argparse`, `fnmatch`, `shutil`,
`pathlib`). Standard library only is a deliberate choice, not an
oversight: it keeps the tool trivial to audit and trivial to drop into
any environment without a `pip install` step, in line with the
"ethically local" principle of minimal dependency surface. Do not add
runtime dependencies. The GitHub CI matrix tests Python 3.9 through
3.14.

The whole implementation is one module, `src/weed_out/cli.py`: pure
functions with one job each, plus a `main()` that wires them into a
pipeline. Data is plain `Path`/`set`/`str`; the only state is the
filesystem being read and, on `--commit`, written.

## File Tree

Trimmed view of the layout

```text
.
├── src/
│   └── weed_out/
│       ├── __init__.py
│       └── cli.py
├── tests/
│   ├── conftest.py
│   ├── test_cli_integration.py
│   ├── test_delete_walk.py
│   └── test_keep_resolution.py
├── .weed-out-ignore
├── CHANGELOG.md
├── CLAUDE.md
├── DESIGN.md
├── LICENSE
├── pyproject.toml
├── README.md
└── RELEASING.md
```

## CLI Grammar

`weed-out [--keep LIST] [--root PATH] [--dot-files] [--dot-dirs] [--tree]
[--commit]`. Flags, not positionals — order is free. `--keep` is no
longer strictly required at the argparse level: a `.weed-out-ignore`
file at `--root` can supply the keep list on its own (see "The
`.weed-out-ignore` file" below). At least one of the two has to yield
an entry, though — everything else defaults to a safe, read-only
invocation (`--root` defaults to `.`, and neither `--tree` nor the
plain dry-run output touches the filesystem).

Bare `weed-out` on a TTY prints the module docstring (the usage banner)
and exits 0. `weed-out` takes no piped input — its unit of work is a
directory, not a stream — so bare `weed-out` with stdin attached to a
pipe is a usage error (exit 1), not a help dump, for the same reason
`docmap` treats it that way: printing help to stdout mid-pipeline would
silently exit 0 into a pipeline expecting real output.

Exit codes:

- `0` — success (files reported/deleted, or bare-on-TTY printed help).
- `1` — every error `weed-out` raises itself: usage errors, `--root` is
  not a directory, or neither `--keep` nor `.weed-out-ignore` yielded
  any keep entries.
- `2` — argparse's own errors (unknown flag, etc.), argparse's
  convention, left untouched.

All self-raised errors go to stderr as `weed-out: <message>`.

## The Keep/Delete Pipeline

`main()` runs: parse args → grammar guards (bare invocation, `--root`
must be a directory) → resolve the keep list → either print the tree
(`--tree`, read-only) or walk and delete (`delete_rest`, read-only
unless `--commit`).

### Two-phase keep resolution: exact paths vs. glob patterns

`--keep` entries are split at parse time into two buckets:

- **Exact paths** (`src/`, `README.md`) resolve immediately to absolute
  paths, and their full parent chain up to `--root` is added to
  `exact_keep` (`build_exact_keep`), so a kept file always drags its
  containing directories along with it.
- **Glob patterns** (`*.md`) are matched by filename against every
  entry during a full tree walk, since a pattern doesn't correspond to
  one fixed path — it has to be evaluated per-file.

### Path-scoped glob patterns

A pattern containing `/` (e.g. `src/weed_out/*.py`) used to be dead on
arrival: glob matching only ever tested an entry's bare filename
(`p.name`), which by definition never contains a slash, so any path
segment in a pattern was inert. This was documented as the complete,
intended rule in this file and in the README — it wasn't a deliberate
limitation, path-scoping just hadn't been designed for yet.

The fix routes each pattern individually, decided once by whether it
contains `/`:

- No `/` — matched against the bare filename, tree-wide, exactly as
  before. Fully backward compatible.
- Contains `/` — matched against the path relative to `--root`,
  **gitignore-style**: `*` stays within one path segment (it does not
  cross `/`), and `**` matches zero or more segments, giving explicit
  opt-in recursion (`src/weed_out/*.py` protects direct children only;
  `src/weed_out/**/*.py` protects any depth below it). A leading and/or
  trailing `/` on the pattern is stripped before matching, so
  `/src/*.py` and `src/*.py` are equivalent — without that, a leading
  slash would silently reintroduce the exact same dead-pattern bug,
  since a root-relative path never itself starts with `/`.

Anchored, gitignore-style matching was chosen over reusing `fnmatch`
against the full path as a single string (which was the simpler option)
for two reasons:

1. weed-out is explicitly a git-orphan-branch release-packaging helper.
   Consistency with git's own ignore-pattern semantics is a first-class
   goal here, not a nice-to-have.
2. It matches the near-universal convention across `.gitignore`,
   `.dockerignore`, `rsync` filter rules, npm's `minimatch`, bash
   `globstar`, and Python's own `glob`/`pathlib.Path.glob` — all of
   which anchor `*` at `/` and require `**` for recursion. Raw
   `fnmatch.fnmatch()` on a full path string is the outlier: it was
   built for matching one filename against one pattern with no concept
   of path components, which is exactly why the original bug existed.

Known, accepted tradeoff: unlike full-string matching (which can only
ever over-protect), anchored matching means a user who forgets `**` and
assumes recursion could under-protect a nested file and lose it on
`--commit`. This is mitigated by documentation (the README introduces
`**` plainly and early, not as a footnote) and by the tool's existing
primary safety mechanism — always run `--tree` before `--commit`.

`pathlib.PurePath.match()` was considered as the matching engine and
rejected: its `**` support only landed in Python 3.13, and weed-out
supports 3.9+, so relying on it would behave inconsistently across the
supported version matrix. Instead, `path_pattern_match`/`_segments_match`
in `cli.py` is a small hand-rolled recursive matcher, stdlib only,
reusing `fnmatch.fnmatch` per path segment — anchoring falls out for
free from comparing one segment at a time, since a single segment never
contains `/`.

One more implementation subtlety worth calling out: `print_tree`
recurses by passing the current subdirectory as the next call's
traversal cursor. Path-scoped matching needs the *original* `--root` to
compute a stable relative path, not whatever subdirectory is currently
being listed — so `print_tree` takes two separate parameters,
`directory` (shifts every recursive call) and `keep_root` (passed
through unchanged). Collapsing these back into one parameter would make
`--tree`'s preview silently diverge from what `--commit` actually
deletes below the top level, which is close to the worst failure mode
this tool has — don't reintroduce that by "simplifying" it later.

### The protected-directory bug, and why `build_protected_dirs` exists

Early version only propagated "this directory contains something kept"
up the tree for exact-path keeps, not pattern matches. That meant a
file kept only via glob (`src/notes/design.md` via `*.md`) didn't
protect its parent directory (`src/notes/`), so `--commit` would
happily `rmtree` the directory and take the file it was supposed to
protect down with it. Caught this in testing before it shipped —
`tests/test_keep_resolution.py` pins this case down so it can't
regress silently.

The fix: `build_protected_dirs` does a full walk first, finds every
entry that's directly kept (exact match, pattern match, or
dot-file/dot-dir default), and unions the parent chain of every one of
those into a `protected_dirs` set. `should_keep` then checks that set
directly instead of re-deriving ancestry from `exact_keep` alone. This
runs once per invocation as its own pass, not inline per-entry, to
avoid recomputing ancestry checks against every pattern for every file
during the delete walk itself.

### Kept directories protect their contents, not just the shell

Found while writing `tests/test_keep_resolution.py` for this packaging
pass: `build_exact_keep` only added a kept directory itself (and its
*ancestors*) to `exact_keep` — never its *descendants*. `--keep "src/"`
therefore kept the `src` entry from being `rmtree`'d, but every file
*inside* `src/` was still evaluated on its own and deleted individually,
since nothing propagated protection *downward* into a kept directory.
This directly contradicted the tool's own stated purpose and the
README's usage examples (`--keep "src/,tests/,..."` implying "keep the
whole tree").

The fix: `build_exact_keep` now returns `kept_roots` alongside
`exact_keep` — the entries as named in `--keep`, before the
ancestor-chain expansion. `is_under_kept_dir(p, kept_roots)` checks
whether any of `p`'s ancestors is a kept root; `should_keep` treats that
as a third way to survive, alongside direct keeps and `protected_dirs`.
Because `Path.parents` yields the full ancestor chain, this protects
contents at any depth under a kept directory in one check, not just
immediate children.

### Deletion order: deepest first

`delete_rest` sorts all entries by path depth, deepest first, before
acting. This guarantees files are removed before the directories that
contain them, so a directory delete never accidentally requires
recursing into something that's already been individually handled.
`shutil.rmtree` is still used for directories that need to go
entirely, since a kept directory never reaches that branch (it would
have matched `should_keep` first).

### Empty directory cleanup as a separate pass

Removing empty directories left behind after file deletion is
deliberately a second, separate pass (`remove_empty_dirs`), run only
after the main delete pass and only when `--commit` is set. Bottom-up
ordering (deepest directories checked first) means a chain of nested
now-empty directories collapses correctly in one pass, instead of
needing multiple runs. Directories in `exact_keep` are always skipped
here, since being named explicitly is a stronger signal than "happens
to be empty right now."

### `--root` validation

`main()` checks `root.is_dir()` before any walk starts and fails loudly
(`weed-out: {root} is not a directory`, exit 1) rather than silently
walking nothing — the same error-message convention `docmap` uses for
its own root check.

### The `.weed-out-ignore` file

A checked-in, per-repo file holding the same kind of entries as
`--keep` (exact paths and glob patterns), so a project's keep list
doesn't have to be retyped as a comma-separated string on every
invocation.

- **Discovery: automatic, root-only.** `weed-out` looks for
  `.weed-out-ignore` directly at `--root` on every invocation — no flag
  needed to opt in, and no nested/`.gitignore`-style walk into
  subdirectories. Automatic reading is safe by construction here: the
  file can only ever add entries to the keep set, never cause a
  deletion, so there's no silent-behavior-change risk the way there
  would be for a flag that changed what gets deleted. Root-only because
  the tool's whole model is "state the keep list once," not
  per-directory rules.
- **`--keep` is now optional.** `read_ignore_file` (`src/weed_out/cli.py`)
  supplies keep entries the same way `--keep` does, so `--keep` is no
  longer required — `weed-out --root . --tree` works on its own if a
  `.weed-out-ignore` exists at that root. If **neither** `--keep` nor
  `.weed-out-ignore` yields any entries, `weed-out` exits 1 with a usage
  error rather than running with an empty keep list. An empty keep list
  means "delete everything in `--root`," which is exactly the kind of
  accidental maximum-blast-radius outcome the safe-by-default posture
  (see `CLAUDE.md`) exists to prevent — silence should never be able to
  mean "delete it all."
- **Comments and blank lines are supported.** A line that's empty after
  stripping whitespace, or starts with `#`, is skipped. This follows
  `.gitignore`/`.dockerignore` convention and matters here specifically
  because the file is meant to be a reviewable, git-blame-able record —
  comments let it explain *why* an entry survives, not just *that* it
  does.
- **Format: newline-separated, not comma-separated.** `--keep` is a
  single comma-separated string because it's a CLI flag; that's a
  constraint of the flag, not a design choice worth repeating in a
  file. `.weed-out-ignore` holds one entry per line instead. One entry
  per line diffs cleanly in git, which matters since the point of
  checking this file in is to have a reviewable, git-blame-able record
  of what a release is supposed to keep.
- **Merges with `--keep`, doesn't override it.** Anything named in
  either source survives; the combined entries feed the same
  two-phase resolution (`build_exact_keep` / `build_protected_dirs`)
  already used for `--keep` alone. This isn't a policy call with real
  tension to resolve — it falls out of `weed-out` having no negation
  syntax (see below): neither `--keep` nor `.weed-out-ignore` can ever
  say "delete this," only "keep this," so there's nothing for one
  source to override in the other. If negation is ever added, "keep
  wins over delete" is the rule to apply on conflict between the two
  sources, consistent with the tool's safe-by-default posture (see
  `CLAUDE.md`).
- **No negation syntax — by design, not "not yet."** A `.gitignore`-style
  `!pattern`, inside `--keep` or `.weed-out-ignore`, to say "keep all
  `.md` files except `DRAFT.md`," was considered and decided against.
  `weed-out` never expresses "delete this," only "this survives."
  Keeping the grammar keep-only, rather than keep-and-exclude, is what
  makes the union-merge above unambiguous: when the only two states
  are "explicitly protected" and "not mentioned," there's no way to
  accidentally construct a config that deletes something you meant to
  keep.
- **Naming.** `.weed-out-ignore` follows the `.dockerignore`/
  `.eslintignore` convention — "ignore" scoped to what the tool *does*
  ("the tool passes over these during its action"), not `.gitignore`'s
  "excluded from tracking" reading. `weed-out`'s action is delete, so
  entries in `.weed-out-ignore` are ignored *by the delete pass*, i.e.
  protected.
- **`--keep` is not being renamed.** It stays as the CLI flag, for
  per-invocation use and one-offs; `.weed-out-ignore` is the separate,
  persistent, checked-in file. Different jobs, so they don't need
  matching names (ESLint doesn't call its flag `--eslintignore`
  either).

## Open Questions

- **Symlinks.** `Path.rglob` follows symlinks by default in some
  Python versions and configurations. Behavior around symlinked
  directories pointing outside `--root` hasn't been tested and could
  be a foot-gun.
- **Case sensitivity.** `fnmatch` inherits OS-level case sensitivity.
  Fine on Linux, could surprise someone on macOS's default
  case-insensitive filesystem. Might want an explicit `--case-sensitive`
  flag rather than relying on the OS default silently.
- **Confirmation prompt on `--commit`.** Currently `--commit` runs
  immediately with no "are you sure" step. Worth considering an
  interactive confirmation, or an `--assume-yes` flag pattern similar
  to package managers, so scripted use isn't blocked but interactive
  use gets one more safety check.
- **Logging deleted paths to a file.** Right now dry-run output prints
  to stdout only. A `--log-file` option to record exactly what was
  removed during a `--commit` run would help with the "no undo"
  tradeoff, at least giving a record of what happened.

## Known Bugs

Confirmed defects, recorded here until fixed (this file is the bug
tracker — a solo project doesn't need GitHub Issues).

None currently open.

## Use of AI

Both the use of AI and its disclosure are deliberate. Code and
documentation in this project are written in collaboration with
Artificial Intelligence (AI). The division of labor: the AI explores,
challenges assumptions and edge cases, and drafts; the human
initiates, drafts the designs, explores alongside the AI, reviews
every change, and decides what gets committed.

---

**East Van AI** · AI for the rest of us! · Vancouver, BC, Canada

[github.com/east-van-ai](https://github.com/east-van-ai) · <east-van-ai@proton.me>

Copyright (c) 2026 Go Nakamaru
