# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

## [0.3.1] - 2026-08-22

### Added

- `weed-out --version` prints the installed version and exits 0. The
  number comes from the installed distribution's metadata.

## [0.3.0] - 2026-08-19

### Added

- Per-command documentation: a command word alone (`weed-out delete`)
  prints that command's own doc and exits 0.

### Changed

- **Breaking:** `PATH` must come before the flags. A `PATH` placed
  after them is no longer accepted, whatever the interpreter tolerates.
- **Breaking:** a missing `PATH` is now weed-out's own error (exit 1,
  with the command's usage line), no longer argparse's (exit 2).
- **Breaking:** a run with no keep entries (no `--keep`, no
  `.weed-out-ignore`) now keeps everything (like `--keep "."`)
  instead of exiting 1, allowing `tree` and dry runs to display
  results. Both notify stderr. `--commit` still exits 1, as an
  empty keep list is more likely a forgotten argument.
- Bare `weed-out` prints the banner and exits 0 whatever stdin is; the
  piped-stdin error is gone. The banner now lists the exit codes.
- Duplicate entries are removed from the merged `--keep` and
  `.weed-out-ignore` list, in the order they were given, so a repeated
  pattern warns once and the warnings read the same on every run.
- `pyproject.toml` is the only place dependencies are declared. Dev
  tooling moved to `[dependency-groups]`, which never ships in the
  wheel. Install with `pip install -e . --group dev` (needs pip 25.1
  or newer).

### Fixed

- Flags must be spelled in full. `argparse` matched any unambiguous
  prefix, so `--com` silently meant `--commit` and removed files. An
  abbreviation now exits 2.

### Removed

- `requirements.txt` and `requirements-dev.txt`.

## [0.2.0] - 2026-07-30

### Added

- `trash` command: sends everything not on the keep list to the OS
  trash via the new `send2trash` runtime dependency, instead of
  deleting it outright -- recoverable, unlike `delete`
- `--dry-run` flag: makes the existing silent default (report only,
  touch nothing) explicit, for scripts that want it spelled out
- `tree` now ends with a summary line -- how many entries are kept, how
  many would be removed, and how many of those are collapsed
  directories whose contents aren't listed
- Warning when a `--keep` pattern narrows without meaning to. `tree` and
  `--dry-run` now note on stderr when a `/`-bearing pattern would
  protect strictly more paths in its `**` form -- `/*.md` is top-level
  only, `*.md` is any depth. Silent for deliberately scoped patterns

### Changed

- **Breaking:** directories that aren't kept are now collapsed. Both
  `tree` and the removal walk stop at an unkept directory instead of
  descending into it. A doomed `venv/` is one line of output rather than
  several thousand, and under `trash` it moves to the OS trash as a
  single recoverable folder instead of thousands of loose items. What
  survives a run is unchanged; what gets *listed* is
- **Breaking:** the `tree` tag is now `[REMOVE]`, not `[DELETE]`. `tree`
  doesn't know the disposal -- it is neither `delete` nor `trash` -- so
  the old tag was wrong half the time. Directories also print with a
  trailing `/`, which matters now that a collapsed directory appears as
  a leaf
- **Breaking:** the dry-run count line names how many targets are
  directories (`4 items would be removed, including 2 directories and
  everything inside them.`), since after the collapse one line can stand
  for a whole subtree. The clause is omitted entirely when no target is
  a directory

- **Breaking:** the action is now a **command**, not a flag. The
  grammar is
  `weed-out <delete | trash | tree> PATH [--keep LIST] [--dry-run | --commit] [--dot-files] [--dot-dirs]`.
  The command names the disposal (permanent vs. trash), the mode flag
  says how far to go, and `--tree` becomes the `tree` command. `--tree`
  and a destructive action are no longer combinable; the old
  `--tree --commit` was expressible and silently did nothing.
  `--commit` keeps its name and meaning

  | 0.1.1 | 0.2.0 |
  | --- | --- |
  | `weed-out --keep "*.md" --root .` | `weed-out delete . --keep "*.md"` |
  | `weed-out --keep "*.md" --root . --tree` | `weed-out tree . --keep "*.md"` |
  | `weed-out --keep "*.md" --root . --commit` | `weed-out delete . --keep "*.md" --commit` |
  | *(not available)* | `weed-out trash . --keep "*.md" --commit` |

- **Breaking:** `--root` is gone, replaced by a required `PATH`
  positional -- no more defaulting to the current directory, so a
  `--commit` run can never inherit an implicit target. Use `.` for the
  current directory
- **Breaking:** `tree` takes no `--dry-run`/`--commit`; passing either
  is an argparse error (exit 2) rather than a silently-ignored flag.
  A missing or unknown command, and a missing `PATH`, are likewise
  argparse errors (exit 2). A `PATH` that isn't a directory remains
  `weed-out`'s own error (exit 1)
- **Breaking:** dry-run output no longer prefixes each line with
  `would delete:` -- entries print as bare paths, followed by a final
  `N item(s) would be removed.` count line, since "delete" and "trash"
  are now distinct actions. The closing hint names the disposal it is
  previewing
- `weed-out` now depends on `send2trash` (BSD-3-Clause) at runtime,
  needed for `trash`. This ends the project's previous
  zero-runtime-dependency policy -- see "Architecture" in `DESIGN.md`
- `DESIGN.md`/`README.md`/`CLAUDE.md`/`RELEASING.md` updated throughout
  for the new grammar and dependency
- Internal: `cli.py` split into `args.py`, `keep.py`, `tree.py`, and
  `delete.py` by responsibility; `cli.py` now only hosts `main()`. Both
  walks resolve their keep sets through one wrapper, and the
  exact-vs-glob split is defined once in `is_glob`. No behaviour change

### Fixed

- **Breaking:** keeping a file by its exact path no longer protects its
  siblings. `--keep "src/main.py"` kept the whole of `src/`, because the
  ancestor directories a named file drags along were classified as
  directly kept in their own right, and a directly-kept directory
  protects its entire subtree. `src/` now survives as a shell holding
  only `main.py`; a `src/junk.txt` beside it is removed. Note the
  direction of the change -- entries that survived before are deleted
  now, so re-check any saved `--keep` string or `.weed-out-ignore` with
  `tree` before the next `--commit`. Name the directory itself
  (`--keep "src/"`) to keep its contents. See "Survival propagates both
  ways" in `DESIGN.md`
- **Breaking:** `--keep` naming a symlink by its exact path now keeps the
  link, not what it points at. Keep entries were made absolute with
  `Path.resolve()`, which follows a link all the way to its target, so
  `--keep "notes"` filed the target's path: a path the walk never
  produces, since it doesn't follow links either. The named link matched
  nothing and was deleted, while the target was protected in its place,
  and when that target sat under `PATH` and was a directory, its whole
  subtree came along with it. Entries are now made absolute lexically
  (`os.path.normpath`), so `--keep` names what it says. `.` and `..`
  still collapse. Two knock-on effects worth knowing: the target of a
  kept link is now judged on its own (name it too if you want it), and a
  keep entry reaching *through* a link (`--keep "notes/file.md"`, `notes`
  being a link) keeps only the link, exactly as `--keep "notes"` would.
  See "Identity resolution never dereferences" in `DESIGN.md`
- **Breaking:** symlinks are never descended into. Both walks used bare
  `entry.is_dir()`, which follows symlinks, so a link to a directory
  outside `PATH` was walked straight through and files that were never
  under `PATH` entered the keep/remove decision. A symlink is now an
  atomic leaf -- kept whole, or removed whole as the link node rather
  than its target -- and `tree` marks it `name -> target` so it reads
  apart from a collapsed real directory. See "`is_real_dir` is the only
  authority on traversal" in `DESIGN.md`
- **Breaking (bug fix):** `delete --commit` silently did nothing to a
  doomed symlink-to-directory, which `tree`/`--dry-run` had reported as
  a target. It is now removed
- A dangling symlink recorded as a removal target was skipped by
  `--commit` even though `tree`/`--dry-run` had reported it. It is now
  removed
- `--dot-dirs` (and any directory kept only because its own name matches
  a `--keep` glob) protected the directory shell but deleted everything
  inside it. A directory's full contents now survive however the
  directory came to be kept. Same shell-only bug as the 0.1.0
  exact-path case, one keep-route later. See "Survival propagates both
  ways" in `DESIGN.md`
- A directory that was *already* empty on disk and kept by any route
  other than an exact `--keep` path was deleted anyway on a `--commit`
  run. Empty kept directories now survive. The cleanup pass responsible
  (`remove_empty_dirs`) is gone rather than guarded -- it had no
  legitimate work left. See "`should_keep` is the only authority on
  survival" in `DESIGN.md`

## [0.1.1] - 2026-07-27

### Fixed

- Pinned `ruff` and `black` in `requirements-dev.txt` (previously installed unpinned in CI), so lint tooling no longer breaks silently when upstream ships new defaults
- Pinned `black==25.11.0` specifically to keep Python 3.9 support in the CI matrix (26.5.1 requires 3.10+)
- Adopted ruff 0.16.0's expanded lint rules and fixed the resulting 10 findings (dropped an unused shebang, collapsed two bool-return blocks, made a subprocess call's `check` behaviour explicit, cleaned up unused tuple-unpacking vars in tests)

## [0.1.0] - 2026-07-26

### Added

- `.weed-out-ignore` file: `weed-out` automatically reads a
  newline-separated keep list from this file at `--root` (blank lines
  and `#` comments allowed) and merges it with `--keep`, so a project's
  keep list can be checked into the repo instead of retyped as a
  comma-separated string on every invocation. `--keep` is now optional
  as a result -- but if neither `--keep` nor `.weed-out-ignore` yields
  any entries, `weed-out` exits 1 with a usage error rather than
  running with an empty keep list
- Packaged as an installable CLI: `src/weed_out/` layout, `pyproject.toml`
  with a `weed-out` console script entry point, `requirements.txt` /
  `requirements-dev.txt`
- pytest suite covering keep-list/protected-directory resolution
  (`test_keep_resolution.py`), the delete/empty-dir passes
  (`test_delete_walk.py`), and CLI end-to-end behaviour via a subprocess
  `run_cli` fixture (`test_cli_integration.py`)
- GitHub Actions CI (`.github/workflows/ci.yaml`) running pytest, `ruff
  check`, and `black --check` on a Python 3.9-3.14 matrix
- `RELEASING.md` (stable-branch release model, src-layout packaging
  pitfalls) and `LICENSE` (MIT)
- `.gitignore`, `.claude/settings.json`, `.markdownlint.json` /
  `.markdownlintignore`

### Changed

- CLI grammar aligned with `mdmap`/`docmap`: bare `weed-out` on a TTY
  prints the module docstring as a usage banner and exits 0; bare
  `weed-out` with piped stdin is a usage error (`weed-out` takes no
  piped input); errors go to stderr as `weed-out: ...`
- Exit codes normalized to `0` success, `1` for every `weed-out`-raised
  error (usage errors, `--root` not a directory -- previously
  unvalidated and would silently walk nothing), `2` reserved for
  argparse's own errors
- Moved from a flat root-level `poc.py` to `src/weed_out/cli.py`
- `README.md`/`DESIGN.md`/`CLAUDE.md` restructured to the mdmap/docmap
  shape (Why / Example output / Install / Usage / Notes / Use of AI in
  README; Architecture / File Tree / CLI Grammar / Pipeline / Open
  Questions / Known Bugs / Use of AI in DESIGN)

### Fixed

- **Breaking (bug fix):** `--keep` glob patterns containing `/` (e.g.
  `src/weed_out/*.py`) were silently inert -- matching only ever ran
  `fnmatch.fnmatch` against an entry's bare filename, which by
  definition never contains a slash, so any path segment in a pattern
  was dead weight and could never match anything. Patterns containing
  `/` are now matched gitignore-style against the path relative to
  `--root`: `*` stays within one path segment (`fnmatch.fnmatch` per
  segment, so it can't cross `/`), and `**` matches zero or more
  segments for explicit recursive scoping. A leading and/or trailing
  `/` on the pattern is stripped first, so it can't silently
  reintroduce the same dead-pattern problem. Bare patterns (no `/`)
  are unaffected -- still matched by filename, tree-wide. See
  "Path-scoped glob patterns" in `DESIGN.md`
- **Breaking (bug fix):** `--keep`-ing a directory by exact path (e.g.
  `--keep "src/"`) only protected the directory shell, not its
  contents -- every file inside it was still evaluated independently
  and deleted if it didn't separately match a keep rule. Found while
  writing `tests/test_keep_resolution.py`; contradicted the tool's own
  purpose and the README's usage examples. `build_exact_keep` now also
  returns `kept_roots` (the entries as named in `--keep`), and
  `is_under_kept_dir` protects anything nested under one at any depth.
  See "Kept directories protect their contents, not just the shell" in
  `DESIGN.md`
- Plain dry-run output (`--keep ...` with no `--tree`) was printed in
  the same deepest-first order the deletion walk needs for safety, so
  a file's line appeared before its own parent directory's -- backwards
  to read top to bottom. The listing is now buffered and sorted
  separately for display, so a directory's line comes before its own
  contents; the deletion walk itself is unchanged
