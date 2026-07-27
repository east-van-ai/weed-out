# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

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
  (`test_delete_walk.py`), and CLI end-to-end behavior via a subprocess
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
