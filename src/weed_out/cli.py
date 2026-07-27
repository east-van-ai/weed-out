"""
# ==============================================
# East Van AI -- AI for the rest of us!
# https://github.com/east-van-ai
# contact: east-van-ai@proton.me
# ==============================================
#
# ~~~ ~~~ ~~~ ~~~ weed-out ~~~ ~~~ ~~~ ~~~
#
# cli.py -- entry point for weed-out.
#
# Delete everything in a directory tree except what's explicitly listed
# in --keep (exact paths and/or glob patterns). Most cleanup tools are
# exclude-list shaped ("delete these"); weed-out inverts that. Dry run
# is the default -- nothing is deleted unless --commit is passed.
#
# Usage:
#    weed-out [--keep LIST] [--root PATH] [--dot-files] [--dot-dirs] [--tree] [--commit]
#
#    --keep LIST        comma-separated files/dirs/glob patterns to keep.
#                        Optional if a .weed-out-ignore file at --root supplies
#                        entries instead -- at least one of the two is required.
#                        Flag order is free. Bare `weed-out` prints this help.
#    --root PATH         root directory to operate on. Defaults to `.`
#                        A .weed-out-ignore file here (newline-separated,
#                        # comments and blank lines allowed) is read
#                        automatically and merged with --keep.
#    --dot-files         keep dotfiles by default, even if not listed in --keep
#    --dot-dirs          keep dot-directories by default, even if not listed in --keep
#    --tree              print a tree tagging what would be deleted. No changes made.
#    --commit            actually delete. Without this flag, weed-out only reports
#                        what it would do.
#
# Exit codes: 0 success; 1 any weed-out-raised error (usage, bad root,
# no keep entries from --keep or .weed-out-ignore); 2 argparse's own errors.
#
# License: MIT
# ==============================================
"""

import argparse
import fnmatch
import shutil
import sys
from pathlib import Path

USAGE = (
    "Usage: weed-out [--keep LIST] [--root PATH] [--dot-files] [--dot-dirs] "
    "[--tree] [--commit]"
)


def parse_args():
    p = argparse.ArgumentParser(
        prog="weed-out",
        description="Delete everything except specified paths/patterns.",
    )
    p.add_argument(
        "--keep",
        help="Comma-separated list of files/dirs/glob patterns to keep. "
        "Optional if a .weed-out-ignore file at --root supplies entries instead.",
    )
    p.add_argument("--root", default=".", help="Root path to operate on")
    p.add_argument("--dot-files", action="store_true", help="Keep dotfiles by default")
    p.add_argument(
        "--dot-dirs", action="store_true", help="Keep dot-directories by default"
    )
    p.add_argument(
        "--tree",
        action="store_true",
        help="Print a tree showing what survives and what's marked for deletion. No changes made.",
    )
    p.add_argument(
        "--commit",
        action="store_true",
        help="Actually delete. Without this flag, it's a dry run.",
    )
    return p.parse_args()


def matches_any(name: str, rel_path: str, patterns: list[str]) -> bool:
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


def build_exact_keep(root: Path, keep_list: list[str]) -> tuple[set[Path], set[Path]]:
    """Resolve exact (non-glob) keep entries and their parent chain.

    Returns (exact_keep, kept_roots). `exact_keep` also includes every
    ancestor directory up to `root`, so a kept file drags its containing
    directories along with it. `kept_roots` holds just the entries as
    named in --keep (not their ancestors) -- used to recursively protect
    everything *under* a kept directory, since `exact_keep` alone only
    protects the directory shell, not its contents.
    """
    keep = set()
    kept_roots = set()
    root_resolved = root.resolve()
    for item in keep_list:
        if any(c in item for c in "*?["):
            continue  # handled as a glob pattern, not an exact path
        item = item.strip().rstrip("/")
        if not item:
            continue
        p = (root / item).resolve()
        keep.add(p)
        kept_roots.add(p)
        for parent in p.parents:
            if parent == root_resolved or root_resolved in parent.parents:
                keep.add(parent)
    return keep, kept_roots


def is_under_kept_dir(p: Path, kept_roots: set[Path]) -> bool:
    """True if p is nested inside a directory named directly in --keep."""
    return any(root in p.parents for root in kept_roots)


def is_directly_kept(
    p: Path,
    root: Path,
    exact_keep: set[Path],
    patterns: list[str],
    dot_files: bool,
    dot_dirs: bool,
) -> bool:
    """Whether p itself matches a keep rule, ignoring anything below it."""
    if p in exact_keep:
        return True
    rel_path = p.relative_to(root).as_posix()
    if matches_any(p.name, rel_path, patterns):
        return True
    if p.is_dir() and dot_dirs and p.name.startswith("."):
        return True
    return p.is_file() and dot_files and p.name.startswith(".")


def build_protected_dirs(
    root: Path, exact_keep, patterns, dot_files, dot_dirs
) -> set[Path]:
    """Any directory that contains (at any depth) something directly kept
    must itself survive, even if the directory's own name matches nothing."""
    protected = set()
    for entry in root.rglob("*"):
        if is_directly_kept(entry, root, exact_keep, patterns, dot_files, dot_dirs):
            for parent in entry.parents:
                if root in parent.parents or parent == root:
                    protected.add(parent)
    return protected


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
    if is_directly_kept(p, root, exact_keep, patterns, dot_files, dot_dirs):
        return True
    # keep if this is an ancestor directory of anything kept, directly or via pattern
    if p in protected_dirs:
        return True
    # keep if this is nested inside a directory named directly in --keep
    return is_under_kept_dir(p, kept_roots)


def print_tree(
    directory: Path,
    keep_root: Path,
    exact_keep,
    patterns,
    dot_files,
    dot_dirs,
    protected_dirs,
    kept_roots,
    prefix="",
):
    try:
        entries = sorted(directory.iterdir(), key=lambda x: (x.is_file(), x.name))
    except PermissionError:
        return
    for i, entry in enumerate(entries):
        keep = should_keep(
            entry,
            keep_root,
            exact_keep,
            patterns,
            dot_files,
            dot_dirs,
            protected_dirs,
            kept_roots,
        )
        connector = "└── " if i == len(entries) - 1 else "├── "
        tag = "" if keep else "  [DELETE]"
        print(f"{prefix}{connector}{entry.name}{tag}")
        if entry.is_dir():
            extension = "    " if i == len(entries) - 1 else "│   "
            print_tree(
                entry,
                keep_root,
                exact_keep,
                patterns,
                dot_files,
                dot_dirs,
                protected_dirs,
                kept_roots,
                prefix + extension,
            )


def delete_rest(
    root: Path, exact_keep, patterns, dot_files, dot_dirs, commit: bool, kept_roots
):
    protected_dirs = build_protected_dirs(
        root, exact_keep, patterns, dot_files, dot_dirs
    )
    # deepest paths first so files go before their parent directories
    all_entries = sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True)
    dry_run_lines = []
    for entry in all_entries:
        if not entry.exists():
            continue
        if should_keep(
            entry,
            root,
            exact_keep,
            patterns,
            dot_files,
            dot_dirs,
            protected_dirs,
            kept_roots,
        ):
            continue
        if commit:
            if entry.is_dir():
                shutil.rmtree(entry, ignore_errors=True)
            else:
                entry.unlink()
        else:
            dry_run_lines.append(f"would delete: {entry}")

    # sorted separately from the deepest-first deletion walk above, purely
    # for readability -- a path string sort naturally puts a directory
    # before its own contents, e.g. ".../src" sorts before ".../src/cli.py"
    for line in sorted(dry_run_lines):
        print(line)

    if commit:
        remove_empty_dirs(root, exact_keep)


def remove_empty_dirs(root: Path, exact_keep: set[Path]) -> None:
    # bottom-up so nested empty dirs collapse before their parents are checked
    all_dirs = sorted(
        (p for p in root.rglob("*") if p.is_dir()),
        key=lambda p: len(p.parts),
        reverse=True,
    )
    for d in all_dirs:
        if not d.exists() or d in exact_keep:
            continue
        try:
            if not any(d.iterdir()):
                d.rmdir()
        except OSError:
            pass  # not empty, or a permissions thing, just leave it


def main():
    """Parse arguments, enforce the CLI grammar, and run the keep/delete pipeline."""
    if len(sys.argv) == 1:

        # a human typed bare `weed-out`
        if sys.stdin.isatty():
            print(__doc__, file=sys.stdout)
            sys.exit(0)

        # piped input, real usage error -- weed-out operates on directories, not streams
        print(
            "weed-out: weed-out takes no piped input.",
            file=sys.stderr,
        )
        print(USAGE, file=sys.stderr)
        sys.exit(1)

    args = parse_args()
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"weed-out: {root} is not a directory", file=sys.stderr)
        sys.exit(1)

    keep_entries = [x.strip() for x in (args.keep or "").split(",") if x.strip()]
    ignore_entries = read_ignore_file(root)
    raw_list = keep_entries + ignore_entries
    if not raw_list:
        print(
            "weed-out: no keep entries specified "
            "(pass --keep or add a .weed-out-ignore file)",
            file=sys.stderr,
        )
        print(USAGE, file=sys.stderr)
        sys.exit(1)
    patterns = [x for x in raw_list if any(c in x for c in "*?[")]
    exact_keep, kept_roots = build_exact_keep(root, raw_list)

    if args.tree:
        protected_dirs = build_protected_dirs(
            root, exact_keep, patterns, args.dot_files, args.dot_dirs
        )
        print(f"Tree under {root} ([DELETE] marks what would be removed):\n")
        print_tree(
            root,
            root,
            exact_keep,
            patterns,
            args.dot_files,
            args.dot_dirs,
            protected_dirs,
            kept_roots,
        )
        return

    delete_rest(
        root,
        exact_keep,
        patterns,
        args.dot_files,
        args.dot_dirs,
        args.commit,
        kept_roots,
    )

    if not args.commit:
        print("\nDry run only. Re-run with --commit to actually delete.")


if __name__ == "__main__":
    main()
