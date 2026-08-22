# weed-out DESIGN

## Architecture

`weed-out` requires Python 3.9 or newer and is built on the standard
library (`argparse`, `fnmatch`, `shutil`, `pathlib`) plus one runtime
dependency, `send2trash` (BSD-3-Clause), used exclusively by the `trash`
command. It cannot be an *optional* extra: the distribution target is
`pipx`/a formal package install, so `pip install weed-out[trash]` would
leave `trash` silently no-oping or erroring for anyone who installed the
plain package. `send2trash` is small, stable, and widely used, which is
why this one exception was judged acceptable. It is not an invitation
to add more. The GitHub CI matrix tests Python 3.9 through 3.14.

The implementation is split by responsibility: `src/weed_out/args.py`
(argument parsing), `keep.py` (keep-list resolution and the
protected-directory pass), `tree.py` (`tree` display), `delete.py` (the
delete/trash/dry-run walk, and `run_removal`, the shared pipeline both
removal commands run), and `cli.py` (the banner and the dispatch). Each
command also has a thin surface module, `cli_delete.py`, `cli_trash.py`,
`cli_tree.py`, holding that command's documentation and a `run()` that
delegates to the engines. This is the house layout (`prg` is the
multi-command reference); the surface modules exist so each command has
a document of its own to print, not to hold logic. Data is plain
`Path`/`set`/`str`; the only state is the filesystem being read and, on
`delete`/`trash` with `--commit`, written.

### Dependencies live in `pyproject.toml` only

There is no `requirements.txt` and no `requirements-dev.txt`. The
runtime package sits in `[project] dependencies`, dev tooling in
`[dependency-groups]`. One file, two tables, nothing to keep in sync by
hand. Install both halves with one command:

```bash
pip install -e . --group dev
```

The runtime file held `Send2Trash>=1.8`, and so does `pyproject.toml`.
Two files answering one question, with nothing able to check one against
the other. The dev file goes for a different reason. `weed-out` is
installed with `pipx` and run, not cloned and contributed to, so a
requirements file is onboarding scaffolding for a contributor who does
not exist here.

Dev tooling belongs in `[dependency-groups]` rather than
`[project.optional-dependencies]`. An extra is published metadata: it
lands in the wheel, appears on PyPI, and turns `pip install
weed-out[dev]` into a supported offer. Dev tooling is a fact about the
working copy, not about the installed artifact. A dependency group stays
local and never ships.

The dev pins stay exact while the runtime floor does not, and that
asymmetry is deliberate. A pinned `ruff` freezes a rule set, so local
and CI agree on what counts as a lint failure. `pytest` has no rule set
to freeze and stays unpinned.

`--group` needs pip 25.1 or newer, so CI upgrades pip before installing
anything. The 3.9 leg of the matrix tops out at pip 26.0.1, which still
clears that floor.

## CLI Grammar

`weed-out <delete | trash | tree> PATH [--keep LIST] [--dry-run | --commit]
[--dot-files] [--dot-dirs]`. The action is a command, not a flag, and it
comes first. `PATH` follows it. Flags come last and are freely ordered
among themselves.

### Why the action is a command

Two unrelated questions, held on separate axes rather than conflated
onto one:

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
on a subparser. A fourth command would need the keyword too.

Abbreviating the read-only flags while holding `--commit` to its full
spelling was considered and dropped. One flag surface behaving two ways
costs more to explain than the keystrokes it saves.

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

`--keep` is not strictly required: a `.weed-out-ignore` file at `PATH`
can supply the keep list on its own (see "The `.weed-out-ignore` file"
below). Neither is required under the read-only surfaces (see "An absent
keep list keeps everything" below).

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

### A bare word is a question

Bare `weed-out` prints the usage banner (`cli.py`'s module docstring)
and exits 0. A command word and nothing else at all prints that
command's own docstring, exit 0. The test is `len(sys.argv) == 2`,
never "the argument is missing": once any other token is present the
user asked for something specific, and answering with help would hide
the mistake. A missing `PATH` there is an error, exit 1.

Stdin decides none of this. An earlier version gated the banner on
`isatty()` and treated a non-terminal stdin as piped input, exit 1.
That test is wider than it looks: `/dev/null`, which is what cron,
`nohup`, and CI hand a process, is not a terminal either, so the same
command line answered two ways depending on where it was launched.
What was typed decides the answer. weed-out reads no piped input, and
the banner says so.

### `--version` reads the installed metadata

`weed-out --version` prints the program name and the number on one line
and exits 0. It is documentation, like the banner and the per-command
docs, so it shares their exit code.

The number comes from `importlib.metadata.version("weed-out")`, the
metadata of the installed distribution. The literal stays in
`pyproject.toml` and is copied nowhere. A second copy in the source
would be one more thing to keep in step by hand, and a release would
eventually forget it.

The cost of that falls on whoever is developing the tool. An editable
install records the version once, at install time, and never re-reads
`pyproject.toml`. A checkout whose version has moved on since
`pip install -e .` therefore reports the number it was installed with
while running today's code. Reinstalling refreshes it. Someone who
installed the tool to use it has one copy and no gap.

The flag sits on the top-level parser, never on the subparsers.
Argparse's `action="version"` fires during parsing, ahead of the check
for a required command word, which is what lets it answer without one.
It calls `sys.exit(0)` itself, so 0 arrives as a `SystemExit` unwinding
past `main()` rather than as a return value, the same way exit 2 does.

`weed-out delete --version` is consequently not a version query. No
subparser defines the flag, so it is an unknown flag and argparse owns
it, exit 2. One place asks the tool what it is, and the tool answers,
not a command.

With no distribution metadata to be found, the version reads
`unknown (not installed)`. That is a fresh clone run straight from
source, `PYTHONPATH=src python -m weed_out.cli`, with nothing installed
and nothing built. A tree that has been built keeps
`src/weed_out.egg-info` beside the package, and metadata discovery
reads that instead, number and all. The parser is built on every
invocation that is not a bare word, so an unguarded lookup would fail
every command there, not only this one.

### Exit codes

- `0`: success, and documentation (the banner, a command's own doc, or
  `--version`).
- `1`: every error `weed-out` raises itself (a missing `PATH`, a stray
  token after it, `PATH` not a directory, or neither `--keep` nor
  `.weed-out-ignore` yielded any keep entries *and* `--commit` was
  passed).
- `2`: argparse's own errors (unknown flag, unknown command, a bad
  value, or `--dry-run` and `--commit` together).

The line falls where ownership falls: argparse keeps the vocabulary it
owns, and the slots are ours (see "Positions are decided, not
inferred"). A missing `PATH` was argparse's exit 2 before the slot rule
moved it to ours. The rule for anything added later: when it is
genuinely ambiguous who owns an error, it is ours, and it exits 1.

All self-raised errors go to stderr as `weed-out: <message>`.

## The Keep/Delete Pipeline

`main()` runs: answer the bare words (the banner, or a command's own
doc) → parse args → read the `PATH` slot and check it is a directory →
dispatch to the command's `run()`, which resolves the keep list and
either prints the tree (the `tree` command, read-only) or walks and
removes (`run_removal` in `delete.py`, read-only unless `--commit` was
passed).

### Two-phase keep resolution: exact paths vs. glob patterns

`--keep` entries are split at parse time into two buckets:

- **Exact paths** (`src/`, `README.md`) resolve immediately to absolute
  paths, and their full parent chain up to `PATH` is added to
  `exact_keep` (`build_exact_keep`), so a kept file always drags its
  containing directories along with it. A dragged-in ancestor survives as
  a *shell* only: it is kept because a named descendant sits under it,
  which protects the directory entry itself and nothing else inside it.
  `--keep "src/main.py"` leaves `src/` holding just `main.py`.
  Resolution is **lexical**, never `Path.resolve()`: `os.path.normpath`
  against the already-resolved `PATH`, so `.` and `..` collapse without
  the filesystem being consulted and a symlink is never dereferenced. An
  exact keep therefore names the entry exactly as written, which is the
  only form the walk can ever match, since the walk builds paths by
  descending from `PATH` with `iterdir()` and never steps through a link.
  See "Identity resolution never dereferences" below.
- **Glob patterns** (`*.md`) are matched by filename against every
  entry during a full tree walk, since a pattern doesn't correspond to
  one fixed path; it has to be evaluated per-file.

### Path-scoped glob patterns

Each pattern is routed individually, decided once by whether it
contains `/`:

- No `/`: matched against the bare filename, tree-wide. `*.md`
  protects every `.md` file at any depth.
- Contains `/`: matched against the path relative to `PATH`,
  **gitignore-style**: `*` stays within one path segment (it does not
  cross `/`), and `**` matches zero or more segments, giving explicit
  opt-in recursion (`src/weed_out/*.py` protects direct children only;
  `src/weed_out/**/*.py` protects any depth below it). A leading and/or
  trailing `/` on the pattern is stripped before matching, so
  `/src/*.py` and `src/*.py` are equivalent; without that, a leading
  slash would match nothing at all, since a root-relative path never
  itself starts with `/`.

Anchored matching was chosen over the simpler option of `fnmatch`
against the full path as a single string. `weed-out` is explicitly a
git-orphan-branch release-packaging helper, so consistency with git's
own ignore-pattern semantics is a first-class goal here rather than a
nice-to-have; and anchoring `*` at `/` while requiring `**` for
recursion is the near-universal convention (`.gitignore`,
`.dockerignore`, `rsync` filter rules, npm's `minimatch`, bash
`globstar`, Python's own `glob`/`pathlib.Path.glob`). Raw
`fnmatch.fnmatch()` on a whole path string is the outlier: it has no
concept of path components at all.

Known, accepted tradeoff: unlike full-string matching, which can only
ever over-protect, anchored matching means a user who forgets `**` and
assumes recursion could under-protect a nested file and lose it on
`--commit`. Mitigated by the README introducing `**` plainly and early
rather than as a footnote, by the narrowing warning below, and by the
tool's primary safety mechanism: always run `tree` before `--commit`.

`pathlib.PurePath.match()` was considered as the matching engine and
rejected: its `**` support only landed in Python 3.13, and `weed-out`
supports 3.9+, so it would behave inconsistently across the supported
matrix. `path_pattern_match`/`_segments_match` in `keep.py` is a small
hand-rolled recursive matcher instead: stdlib only, reusing
`fnmatch.fnmatch` per path segment, so anchoring falls out for free,
since a single segment never contains `/`.

One implementation subtlety. `print_tree` recurses by passing the
current subdirectory as the next call's traversal cursor, but
path-scoped matching needs the *original* `PATH` to compute a stable
relative path. So `print_tree` takes two separate parameters,
`directory` (shifts every recursive call) and `keep_root` (passed
through unchanged). Collapsing them back into one would make the `tree`
preview silently diverge from what `--commit` deletes below the top
level; don't reintroduce that by "simplifying" it later.

### Warning when a path pattern narrows

The asymmetry a user is most likely to trip over is not `*` versus `**`,
it is slash versus no slash. `*.md` protects every `.md` file at any
depth; `/*.md` is path-matched, and once the leading slash is stripped
it is a single-segment pattern: top-level `.md` files only. Adding a
leading `/` to be *more* explicit silently narrows the pattern, and by
the tradeoff above the cost of that is a deleted file.

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

### `PATH` validation

`main()` checks `root.is_dir()` before any walk starts and fails loudly
(`weed-out: {root} is not a directory`, exit 1) rather than silently
walking nothing, using the same error-message convention `docmap` does.
No usage line accompanies it: this is a readiness failure, not a
grammar error. The command line was read fine, and printing usage
beside it would answer a question nobody asked. `docmap` and `prg`
draw the same line.

### The `.weed-out-ignore` file

A checked-in, per-repo file holding the same kind of entries as `--keep`
(exact paths and glob patterns), one per line, so a project's keep list
doesn't have to be retyped on every invocation.

- **Discovery: automatic, root-only.** `weed-out` looks for it directly
  at `PATH`, with no flag to opt in and no `.gitignore`-style walk into
  subdirectories. Automatic reading is safe by construction: the file
  can only ever *add* to the keep set, never cause a deletion, so there
  is none of the silent-behaviour-change risk a flag that changed what
  gets deleted would carry. Root-only because the tool's model is
  "state the keep list once," not per-directory rules.
- **`--keep` is therefore optional.** `read_ignore_file` (`keep.py`)
  supplies entries the same way `--keep` does, so `weed-out tree .`
  works on its own when the file exists. If **neither** source yields an
  entry, the run keeps everything rather than nothing, and only
  `--commit` treats that as an error (see "An absent keep list keeps
  everything"). Silence must never be able to mean "delete everything in
  `PATH`."
- **Comments and blank lines are skipped** (`#`-prefixed, or empty
  after stripping), following `.gitignore` convention. It matters here
  because the file is meant to be a reviewable, git-blame-able record,
  and comments let it explain *why* an entry survives, not just *that*
  it does.
- **Newline-separated, not comma-separated.** `--keep` is one comma-
  joined string because it is a CLI flag; that's a constraint of the
  flag, not a design choice worth repeating in a file. One entry per
  line diffs cleanly in git, which is the whole point of checking it in.
- **Merges with `--keep`, doesn't override it.** No real conflict here,
  since neither source can say "delete this." Anything named in either
  source survives and is fed to the same two-phase resolution
  (`build_exact_keep`/`build_protected_dirs`). The merge dedupes and
  preserves order (`dict.fromkeys`, `--keep` first), so warnings come
  out in a consistent order across runs.
- **No negation syntax: by design, not "not yet."** A `.gitignore`-style
  `!pattern` ("keep all `.md` except `DRAFT.md`") was considered and
  rejected. Keeping the grammar keep-only is what makes the union-merge
  unambiguous: with only "explicitly protected" and "not mentioned" as
  states, no config can accidentally delete something you meant to keep.
  If negation is ever added, "keep wins" is the conflict rule.
- **Naming.** Follows the `.dockerignore`/`.eslintignore` reading of
  "ignore" (scoped to what the tool *does*) rather than `.gitignore`'s
  "excluded from tracking". `weed-out`'s action is delete, so entries
  here are ignored *by the delete pass*, i.e. protected. `--keep` is not
  renamed to match: different jobs (per-invocation flag vs. persistent
  checked-in file), and ESLint doesn't call its flag `--eslintignore`
  either.

## Invariants

Four rules the walks depend on. Each is cheap to violate by accident.

### Survival propagates both ways

Protection travels **up** from a kept entry and **down** from a kept
directory. Neither direction is derivable from the other.

- **Up.** `build_protected_dirs` walks the tree once, finds every
  directly-kept entry (`is_directly_kept`: exact match, pattern match,
  or the dot-file/dot-dir default), and unions each one's parent chain
  into `protected_dirs`. Not derivable from `exact_keep` alone: a file
  kept only by a glob still has to protect its ancestors, even though
  none of their names match anything in `--keep`.
- **Down.** A directly-kept *directory* also lands in `kept_roots`
  (the entries as named, before the ancestor-chain expansion), and
  `is_under_kept_dir(p, kept_roots)` protects everything beneath it.
  `Path.parents` yields the full ancestor chain, so one check covers any
  depth, not just immediate children.

The down direction has to be blind to *why* the directory is kept.
`build_exact_keep` supplies only the exact-path entries; one kept by a
glob on its own name (`--keep "*.config"` matching `.config/`) or by
`--dot-dirs` reaches `kept_roots` only because `build_protected_dirs`
collects every directory where `is_directly_kept` returns true, whatever
the route, riding the walk that already exists with no second `rglob`.
Miss this and the shell survives while its contents are deleted, the
opposite of what `--keep "src/"` and `--dot-dirs` both promise.

Blind to the route, but not to the *reason*: that classification is
tested against `kept_roots`, never against `exact_keep`. `exact_keep` is
ancestor-inflated by design, so testing against it files every ancestor
of a named file as a directly-kept directory too, and
`--keep "src/main.py"` ends up protecting the whole of `src/`: the down
direction firing on a directory nobody named. The narrower set is safe
for the up direction as well: an ancestor's parent chain is a subset of
its named descendant's, and the descendant already contributes the
ancestor itself, so `protected_dirs` comes out identical either way.

Together: **an unkept directory cannot contain anything kept, at any
depth.** The collapse below rests entirely on that.

### `should_keep` is the only authority on survival

Anything deciding what survives must call `should_keep`. A second
opinion expressed as a membership test against one of the sets that
*feeds* it (`exact_keep`, `protected_dirs`, `kept_roots`) drifts out
of agreement with the walk the moment another way to keep something is
added.

`remove_empty_dirs` is the proof. It removed any empty directory not in
`exact_keep`, one survival route among several, so a directory that was
*already* empty on disk and kept via `--dot-dirs`, via a glob on its own
name, or by sitting under an exact-kept parent was deleted after the
main walk had correctly decided to keep it. It was removed rather than
guarded, because once a kept directory protects its own contents the
pass had no legitimate work left: a `kept_roots` directory has
everything beneath it protected, a `protected_dirs` directory is there
*because* a kept descendant survives, a directory that is neither is
doomed and gets recorded whole (it never empties out, it disappears),
and `PATH` was excluded from the pass's own `rglob("*")`. An unkept
empty directory is already an ordinary target. The pass's entire
reachable effect was the defect, which is why a skip-list would have
been the wrong fix. Re-adding it looks harmless.

### Identity resolution never dereferences

`build_exact_keep` turns a `--keep` entry into a path lexically, with
`os.path.normpath` against the already-resolved `PATH`, never
`Path.resolve()`. `resolve()` dereferences the whole path *including its
final component*, so `--keep "link_to_outside"` became the link's target
path: something the walk never produces, so the named symlink was
evaluated as unkept and removed, while the target's own ancestor chain
got protected in its place. Naming a thing has to keep that thing.

This is the identity half of the atomic-leaf rule below. `is_real_dir`
stops the walk from stepping through a link; lexical resolution stops
`--keep` from naming anything on the far side of one. Between them, no
path outside `PATH` can enter `exact_keep` at all.

Two consequences, stated rather than engineered away. A keep entry whose
path runs *through* a symlinked directory (`--keep "link/file.txt"`)
never matches, because the walk doesn't generate that path; the ancestor
rule still protects the part of the chain that does exist, so the link
itself survives as a shell and the entry ends up behaving exactly like
`--keep "link"`. And `..` inside an entry collapses lexically, which is
not what the kernel would do across a link; the entry it yields still
names something under `PATH`, or nothing at all.

Glob patterns never had this problem. `matches_any` compares against the
name and relative path of the entry the walk produced, so no resolution
is involved, and `--keep "link_to_*"` protected the link all along.

### `is_real_dir` is the only authority on traversal

`is_real_dir(entry)` is `entry.is_dir() and not entry.is_symlink()`:
true only for a real directory node, never a symlink, whatever it points
at and whether or not it is kept. It governs every "recurse into this /
remove this whole" decision: `collect_targets` and `print_tree`'s
recursion branches, `delete_rest`'s commit-mode removal action, and
`report_dry_run`'s directory count.

A bare `entry.is_dir()` in a walk is the bug: it follows symlinks, so a
walk steps through a symlink-to-directory as if it were an ordinary
subdirectory, and everything below the link's target becomes fair game
for `should_keep` even when that target lives entirely outside `PATH`.
Being kept by any route at all (exact path, a pattern on its own name,
`--dot-dirs`, or just sitting under a kept ancestor) triggered it.

So a symlink is an atomic leaf, file or directory alike: kept whole,
removed whole, never descended into. Four facts make that rule specific
rather than stylistic.

- **`shutil.rmtree()` refuses a path that is itself a symlink**
  (`OSError`, "Cannot call rmtree on a symbolic link"; `shutil.py`'s own
  comment cites bug #1669) and `ignore_errors=True` swallowed it, so a
  doomed symlink-to-directory reported by `tree`/`--dry-run` survived
  `--commit` untouched and silently. `Path.unlink()` removes the link
  node without touching its target.
- **`entry.exists()` follows symlinks**, so a dangling one reports
  `False` and the old `if not entry.exists(): continue` guard skipped a
  target it had just promised to remove. Now
  `if not (entry.exists() or entry.is_symlink()): continue`.
- **`rglob` does not descend through symlinks** on 3.9, 3.12 or 3.14
  (verified on all three), so `build_protected_dirs` needs no guard of
  its own. Not a hypothesis worth re-opening.
- **`readlink()` does not require the target to exist**, so `print_tree`
  marks every symlink with its literal, unresolved target
  (`name -> target`, `ls -l`-style), dangling ones included. An entry
  that looks like a directory but isn't expanded has to say why, or "not
  descended into" reads as "empty".

### Collapsing doomed directories, and what the walks report

Both walks stop at a directory that isn't kept. `tree` prints it as one
tagged line; `delete_rest` records it as one target and hands the whole
directory to `shutil.rmtree` or `send2trash` in a single call. The first
invariant is what licenses this: no walk ever has to descend into a
doomed directory to find a survivor.

Because the descent stops at every doomed entry, the collected targets
are pairwise non-nested by construction and can be removed once each, in
any order. An earlier version flattened the tree with `rglob("*")` and
sorted deepest-first so files went before their parents; that ordering
guarantee is needed only by a flat walk. Don't reintroduce it.

Collapse must not stop *early*, though: a **kept** directory holding
doomed children still has to be descended into. Recurse when kept,
record-and-stop when not. Keeping those two conditions distinct is the
whole of the correctness argument, and what the cases in
`tests/test_delete_walk.py` exist to pin down.

The payoff is largest for `trash`, where a 3,000-file `venv/` moves to
the OS trash as one recoverable folder rather than 3,000 loose items;
for `tree` it is legibility. Both read-only surfaces close with a tally
whose load-bearing number is how many removal targets are collapsed
directories: without it a collapsed `venv/` reads as a single doomed
file and the preview understates what `--commit` is about to do, which
this tool's primary safety mechanism cannot afford. The dry-run count
line carries the same correction, its `N` counting removal roots rather
than files. Symlinks count in neither tally, since `is_real_dir` gates
both: `collapsed` means "a real subtree was elided for brevity," and a
symlink is atomic on principle, not for brevity.

## Open Questions

- **`trash` and symlinks.** `delete`'s commit loop routes symlinks
  through `Path.unlink()` (see "`is_real_dir` is the only authority on
  traversal"). `trash`'s path is `send2trash(entry)`, since `send2trash`
  receives the entry's own unresolved path either way. Each platform
  backend (`mac`, `win`, freedesktop-via-`gio`/`plat_other`) has not
  been exercised against a live symlink-to-directory to confirm it moves
  the link node rather than erroring or dereferencing it. The `trash`
  tests assert the call shape against a stubbed `send2trash`, never real
  OS behaviour.
- **Case sensitivity.** `fnmatch` inherits OS-level case sensitivity.
  Fine on Linux, could surprise someone on macOS's default
  case-insensitive filesystem. Might want an explicit `--case-sensitive`
  flag rather than relying on the OS default silently.
- **Logging removed paths to a file.** Right now dry-run output prints
  to stdout only. A `--log-file` option to record exactly what was
  removed during a `delete --commit` run would help with the "no undo"
  tradeoff, at least giving a record of what happened. Less pressing
  now that `trash` exists as a recoverable alternative, but still
  relevant for `delete`.

## Known Bugs

Confirmed defects, recorded here until fixed (this file is the bug
tracker; a solo project doesn't need GitHub Issues).

None open. The two that were tracked here are fixed, and each one's rule
now lives with the invariant it belongs to: "Survival propagates both
ways" for the exact-keep ancestor over-protection, "Identity resolution
never dereferences" for the exact-path symlink keep.

## Use of AI

Both the use of AI and its disclosure are deliberate. Code and
documentation in this project are written in collaboration with
Artificial Intelligence (AI). The division of labour: the AI explores,
challenges assumptions and edge cases, and drafts; the human
initiates, drafts the designs, explores alongside the AI, reviews
every change, and decides what gets committed.

---

**East Van AI** · AI for the rest of us! · Vancouver, BC, Canada

[github.com/east-van-ai](https://github.com/east-van-ai) · <east-van-ai@proton.me>

Copyright (c) 2026 Go Nakamaru
