"""Keep-list resolution: exact paths, glob patterns, and protected directories."""

import fnmatch
import os.path
import sys
from pathlib import Path


def is_glob(entry: str) -> bool:
    """Whether a keep entry is a glob pattern rather than an exact path.

    The one definition of that split: `build_exact_keep` skips the entries
    this accepts, and `main()` collects exactly those as `patterns`.
    """
    return any(c in entry for c in "*?[")


def matches_any(name: str, rel_path: str, patterns: list[str]) -> bool:
    """Whether an entry matches any keep pattern.

    A pattern with no `/` is matched against the bare filename at any
    depth (`*.md`); one with a `/` is path-matched against `rel_path`
    gitignore-style (`src/**/*.py`), so `/*.md` is top-level only.
    """
    for pat in patterns:
        if "/" in pat:
            if path_pattern_match(rel_path, pat):
                return True
        elif fnmatch.fnmatch(name, pat):
            return True
    return False


def path_pattern_match(rel_path: str, pattern: str) -> bool:
    """gitignore-style path match: '*' stays within one path segment,
    '**' matches zero or more segments. A leading/trailing '/' on the
    pattern is stripped first, since rel_path never starts with '/'."""
    return _segments_match(rel_path.split("/"), pattern.strip("/").split("/"))


def _segments_match(path_parts: list[str], pat_parts: list[str]) -> bool:
    if not pat_parts:
        return not path_parts
    head, rest_pat = pat_parts[0], pat_parts[1:]
    if head == "**":
        return _segments_match(path_parts, rest_pat) or (
            bool(path_parts) and _segments_match(path_parts[1:], pat_parts)
        )
    if not path_parts:
        return False
    return fnmatch.fnmatch(path_parts[0], head) and _segments_match(
        path_parts[1:], rest_pat
    )


def deepen_pattern(pattern: str) -> str:
    """The `**` form of a path pattern: `src/*.py` -> `src/**/*.py`."""
    parts = pattern.strip("/").split("/")
    return "/".join(parts[:-1] + ["**"] + parts[-1:])


def narrowing_pattern_hints(root: Path, patterns: list[str]) -> list[str]:
    """Warn about path patterns that quietly match less than they look like.

    Each candidate is compared against its own `**` form rather than
    against the bare filename, so a deliberately scoped `src/*.py` is
    measured against `src/**/*.py` and never against every `.py` under
    `PATH`.

    Returns one message per provably narrowing pattern. The candidate
    test runs before the walk, so a run with no such pattern never pays
    for this.
    """
    candidates = [p for p in patterns if "/" in p and "*" in p and "**" not in p]
    if not candidates:
        return []

    rel_paths = [p.relative_to(root).as_posix() for p in root.rglob("*")]
    hints = []
    for pattern in candidates:
        deep = deepen_pattern(pattern)
        narrow_hits = sum(1 for rel in rel_paths if path_pattern_match(rel, pattern))
        deep_hits = sum(1 for rel in rel_paths if path_pattern_match(rel, deep))
        if deep_hits > narrow_hits:
            noun = "path" if narrow_hits == 1 else "paths"
            hints.append(
                f"weed-out: '{pattern}' matches {narrow_hits} {noun}, but "
                f"'{deep}' would match {deep_hits}. A '*' never crosses a "
                "'/' -- use '**' if you meant any depth."
            )
    return hints


def read_ignore_file(root: Path) -> list[str]:
    """Read keep entries from a `.weed-out-ignore` file at `root`, if present.

    One entry per line, same exact-path/glob-pattern rules as --keep.
    Blank lines and lines starting with `#` are skipped. Returns an empty
    list if the file doesn't exist.
    """
    path = root / ".weed-out-ignore"
    if not path.is_file():
        return []
    entries = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        entries.append(line)
    return entries


def resolve_keep_list(root: Path, keep_arg):
    """Merge --keep with the ignore file into the inputs both walks take.

    Returns `(exact_keep, kept_roots, patterns, keep_everything)`.
    `keep_arg` is the raw --keep value, or None. When neither source
    yields an entry, the list resolves to `--keep "."` and
    `keep_everything` says so, so the caller can announce or refuse it
    (see DESIGN.md, "An absent keep list keeps everything").
    """
    keep_entries = [x.strip() for x in (keep_arg or "").split(",") if x.strip()]
    ignore_entries = read_ignore_file(root)
    # dict.fromkeys, not set(): dedupes without shuffling, so a pattern's
    # warnings surface in the order it was given (see DESIGN.md).
    raw_list = list(dict.fromkeys(keep_entries + ignore_entries))
    keep_everything = not raw_list
    if keep_everything:
        # "." normalizes to root, and a directly-kept directory protects
        # its whole subtree, so no walk needs a special case.
        raw_list = ["."]
    patterns = [x for x in raw_list if is_glob(x)]
    exact_keep, kept_roots = build_exact_keep(root, raw_list)
    return exact_keep, kept_roots, patterns, keep_everything


def warn_keep_everything() -> None:
    """Note on stderr that an absent keep list was read as "keep everything".

    Read-only surfaces only, like `warn_narrowing_patterns`. Under
    `--commit` an absent keep list is an error rather than a note, so
    this never follows a destructive run.
    """
    print(
        "weed-out: no keep entries specified, so everything is kept "
        '(as if --keep "."). Nothing would be removed.',
        file=sys.stderr,
    )


def warn_narrowing_patterns(root: Path, patterns: list[str]) -> None:
    """Warn on stderr about `--keep` patterns that match less than they look like.

    Only the read-only surfaces call this. Under `--commit` the advice
    comes too late to act on, and a stderr line surfacing after a
    destructive run reads as an error report on the run itself.
    """
    for hint in narrowing_pattern_hints(root, patterns):
        print(hint, file=sys.stderr)


def build_exact_keep(root: Path, keep_list: list[str]) -> tuple[set[Path], set[Path]]:
    """Resolve exact (non-glob) keep entries into `(exact_keep, kept_roots)`.

    `exact_keep` is ancestor-inflated: each entry plus every directory up
    to `root`, so a kept file drags its parents along. `kept_roots` holds
    only the entries as *named*, which is what protects a kept
    directory's contents rather than just its shell.

    Entries are made absolute lexically (`os.path.normpath`), never with
    `Path.resolve()` (see DESIGN.md, "Identity resolution never
    dereferences"). `root` is expected to arrive already resolved, as
    `main()` resolves `PATH`.
    """
    keep = set()
    kept_roots = set()
    root_normalized = Path(os.path.normpath(root))
    for item in keep_list:
        if is_glob(item):
            continue  # handled as a glob pattern, not an exact path
        item = item.strip().rstrip("/")
        if not item:
            continue
        p = Path(os.path.normpath(root / item))
        keep.add(p)
        kept_roots.add(p)
        for parent in p.parents:
            if parent == root_normalized or root_normalized in parent.parents:
                keep.add(parent)
    return keep, kept_roots


def is_under_kept_dir(p: Path, kept_roots: set[Path]) -> bool:
    """True if p is nested inside a directory named directly in --keep."""
    return any(root in p.parents for root in kept_roots)


def is_directly_kept(
    p: Path,
    root: Path,
    exact_paths: set[Path],
    patterns: list[str],
    dot_files: bool,
    dot_dirs: bool,
) -> bool:
    """Whether p itself matches a keep rule, ignoring anything below it.

    `exact_paths` is either of the two exact-path sets, and which one the
    caller passes is the question it is really asking: `exact_keep` asks
    about *survival*, where an ancestor shell counts; `kept_roots` asks
    whether the entry was *named*, which is what deciding a directory's
    whole subtree requires (see DESIGN.md, "Survival propagates both
    ways").
    """
    if p in exact_paths:
        return True
    rel_path = p.relative_to(root).as_posix()
    if matches_any(p.name, rel_path, patterns):
        return True
    if p.is_dir() and dot_dirs and p.name.startswith("."):
        return True
    return p.is_file() and dot_files and p.name.startswith(".")


def build_protected_dirs(
    root: Path, kept_roots, patterns, dot_files, dot_dirs
) -> tuple[set[Path], set[Path]]:
    """One walk finding what must survive because of what sits inside it.

    Returns `(protected_dirs, directly_kept_dirs)`: every ancestor of a
    directly-kept entry, and every directory that is itself directly kept
    by any route (named, pattern match, or the --dot-dirs default).
    `resolve_walk_sets` folds the second into `kept_roots`, which is what
    `build_exact_keep` alone cannot supply for the non-exact routes.

    Takes `kept_roots`, the exact paths as *named*, never the
    ancestor-inflated `exact_keep`, which would file every ancestor of a
    named file as directly kept (see DESIGN.md, "Survival propagates both
    ways").
    """
    protected = set()
    directly_kept_dirs = set()
    for entry in root.rglob("*"):
        if is_directly_kept(entry, root, kept_roots, patterns, dot_files, dot_dirs):
            if entry.is_dir():
                directly_kept_dirs.add(entry)
            for parent in entry.parents:
                if root in parent.parents or parent == root:
                    protected.add(parent)
    return protected, directly_kept_dirs


def resolve_walk_sets(
    root: Path, kept_roots: set[Path], patterns, dot_files, dot_dirs
) -> tuple[set[Path], set[Path]]:
    """The `(protected_dirs, kept_roots)` pair every walk runs on.

    Folds `build_protected_dirs`'s directly-kept directories into
    `kept_roots`, which is the only thing either caller ever does with
    them: a directly-kept directory has to protect its whole subtree, not
    just its own shell. Both the `tree` walk and the delete walk resolve
    their inputs through here, so the two cannot disagree about what is
    kept (see DESIGN.md, "Survival propagates both ways").
    """
    protected_dirs, directly_kept_dirs = build_protected_dirs(
        root, kept_roots, patterns, dot_files, dot_dirs
    )
    return protected_dirs, kept_roots | directly_kept_dirs


def is_real_dir(entry: Path) -> bool:
    """True for an actual directory node, False for a symlink, even one
    that points at a directory.

    The single discriminator for every "recurse into this / bulk-remove
    this whole" decision in the walks, because a symlink is an atomic
    leaf (see DESIGN.md, "`is_real_dir` is the only authority on
    traversal").
    """
    return entry.is_dir() and not entry.is_symlink()


def should_keep(
    p: Path,
    root: Path,
    exact_keep: set[Path],
    patterns: list[str],
    dot_files: bool,
    dot_dirs: bool,
    protected_dirs: set[Path],
    kept_roots: set[Path],
) -> bool:
    """Whether p survives, and the only authority on that question.

    Three routes: p is directly kept, p is an ancestor of something
    directly kept (`protected_dirs`), or p is nested inside a
    directly-kept directory (`kept_roots`). Nothing else may re-answer
    this with a membership test against one of those sets (see DESIGN.md,
    "`should_keep` is the only authority on survival").
    """
    if is_directly_kept(p, root, exact_keep, patterns, dot_files, dot_dirs):
        return True
    if p in protected_dirs:
        return True
    return is_under_kept_dir(p, kept_roots)
