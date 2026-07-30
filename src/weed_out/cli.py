"""
# ==============================================
# East Van AI -- AI for the rest of us!
# https://github.com/east-van-ai
# contact: east-van-ai@proton.me
# ==============================================
#
# ~~~ ~~~ ~~~ ~~~ ~~~ weed-out ~~~ ~~~ ~~~ ~~~ ~~~
#
# Delete everything in a directory tree except what's explicitly listed
# in --keep (exact paths and/or glob patterns). Most cleanup tools are
# exclude-list shaped ("delete these"); weed-out inverts that. Nothing is
# ever removed unless --commit is passed.
#
# Usage:
#
#    weed-out <delete | trash | tree> PATH [--keep LIST]
#             [--dry-run | --commit] [--dot-files] [--dot-dirs]
#
# Commands:
#
#    delete PATH         permanently remove everything not kept. No undo.
#    trash PATH          send everything not kept to the OS trash.
#                        Recoverable.
#    tree PATH           print a tree tagging what would be removed.
#                        Read-only -- takes no --dry-run/--commit.
#
# PATH is required -- the directory to operate on. Use `.` for the current
# directory. A .weed-out-ignore file there (newline-separated, # comments
# and blank lines allowed) is read automatically and merged with --keep.
#
# Options:
#
#    --keep LIST         comma-separated files/dirs/glob patterns to keep.
#                        Optional if .weed-out-ignore supplies entries
#                        instead -- at least one of the two is required.
#    --dry-run           report what would be removed, touching nothing.
#                        The default for `delete` and `trash`.
#    --commit            actually carry it out. Permanent for `delete`.
#    --dot-files         keep dotfiles, even if not listed in --keep
#    --dot-dirs          keep dot-directories, even if not listed in --keep
#
# Flags come after the command and PATH; their order among themselves is
# free. Bare `weed-out` prints this help.
#
# License: MIT
# ==============================================
"""

import sys
from pathlib import Path

from weed_out.args import USAGE, parse_args
from weed_out.delete import delete_rest
from weed_out.keep import (
    build_exact_keep,
    is_glob,
    narrowing_pattern_hints,
    read_ignore_file,
    resolve_walk_sets,
)
from weed_out.tree import format_summary, print_tree


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
    root = Path(args.path).resolve()
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
    patterns = [x for x in raw_list if is_glob(x)]
    exact_keep, kept_roots = build_exact_keep(root, raw_list)

    if args.command == "tree":
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
        warn_narrowing_patterns(root, patterns)
        return

    # `tree` has already returned, so args.command is "delete" or "trash" here --
    # the same strings delete_rest() expects for its mode.
    mode = args.command if args.commit else "dry-run"

    delete_rest(
        root,
        exact_keep,
        patterns,
        args.dot_files,
        args.dot_dirs,
        mode,
        kept_roots,
    )

    if mode == "dry-run":
        disposal = (
            "permanently delete"
            if args.command == "delete"
            else "send everything to the OS trash"
        )
        print(f"\nDry run only. Re-run with --commit to {disposal}.")
        warn_narrowing_patterns(root, patterns)


def warn_narrowing_patterns(root: Path, patterns: list[str]) -> None:
    """Warn on stderr about `--keep` patterns that match less than they look like.

    Only the read-only surfaces call this. Under `--commit` the advice
    comes too late to act on, and a stderr line surfacing after a
    destructive run reads as an error report on the run itself.
    """
    for hint in narrowing_pattern_hints(root, patterns):
        print(hint, file=sys.stderr)


if __name__ == "__main__":
    main()
