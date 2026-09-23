"""
# ~~~ ~~~ ~~~ ~~~ ~~~ ~~~ ~~~ weed-out tree ~~~ ~~~ ~~~ ~~~ ~~~ ~~~ ~~~
#
# https://github.com/east-van-ai/weed-out
#
# Print a tree of PATH, tagging everything a removal would take with [REMOVE].
# It never touches the filesystem, and it takes no --dry-run or --commit at
# all. This is the tool's primary safety mechanism.
#
# Usage:
#
#    weed-out tree PATH [--keep LIST] [--dot-files] [--dot-dirs]
#
# PATH is the directory to operate on. Use `.` for the current
# directory. A .weed-out-ignore file there (newline-separated,
# # comments and blank lines allowed) is read automatically and merged
# with --keep.
#
# Options:
#
#    --keep LIST         comma-separated files/dirs/glob patterns to keep.
#                        Optional if .weed-out-ignore supplies entries
#                        instead. With neither, everything is kept.
#    --dot-files         keep dotfiles, even if not listed in --keep
#    --dot-dirs          keep dot-directories, even if not listed in --keep
"""

from pathlib import Path

from weed_out import errors
from weed_out.keep import (
    resolve_keep_list,
    resolve_walk_sets,
    warn_keep_everything,
    warn_narrowing_patterns,
)
from weed_out.tree import format_summary, print_tree

HELP = "Print a tree tagging what would be removed. Never touches the filesystem."
USAGE = "weed-out tree PATH [--keep LIST] [--dot-files] [--dot-dirs]"
SLOTS = ("PATH",)


def run(path: str, args) -> None:
    """Print the keep/remove tree for PATH. Read-only."""
    root = Path(path).resolve()

    if not root.is_dir():
        raise errors.ReadinessError(f"{root} is not a directory")

    exact_keep, kept_roots, patterns, keep_everything = resolve_keep_list(
        root, args.keep
    )
    protected_dirs, walk_kept_roots = resolve_walk_sets(
        root, kept_roots, patterns, args.dot_files, args.dot_dirs
    )
    print(f"Tree under {root} ([REMOVE] marks what would be removed):\n")
    tally = print_tree(
        root,
        root,
        exact_keep,
        patterns,
        args.dot_files,
        args.dot_dirs,
        protected_dirs,
        walk_kept_roots,
    )
    print(f"\n{format_summary(*tally)}")
    if keep_everything:
        warn_keep_everything()
    warn_narrowing_patterns(root, patterns)
