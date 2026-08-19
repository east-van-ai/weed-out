"""
# ~~~ ~~~ ~~~ ~~~ ~~~ weed-out trash ~~~ ~~~ ~~~ ~~~ ~~~
#
# Send everything under PATH except what's kept to the OS trash.
# Recoverable, unlike `delete`. The bare verb is a dry run; --commit is
# what moves anything. A doomed directory lands in the trash as one
# folder. Run `weed-out tree` first to see what would go.
#
# Usage:
#
#    weed-out trash PATH [--keep LIST] [--dry-run | --commit]
#                   [--dot-files] [--dot-dirs]
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
#                        instead. With neither, everything is kept and
#                        --commit is refused.
#    --dry-run           report what would be removed, touching nothing.
#                        The default.
#    --commit            actually send to the OS trash.
#    --dot-files         keep dotfiles, even if not listed in --keep
#    --dot-dirs          keep dot-directories, even if not listed in --keep
"""

from pathlib import Path

from weed_out.delete import run_removal

USAGE = (
    "weed-out trash PATH [--keep LIST] [--dry-run | --commit] "
    "[--dot-files] [--dot-dirs]"
)


def run(root: Path, args) -> int:
    """Run the removal pipeline with the OS trash as the disposal."""
    return run_removal(root, args, "trash", USAGE)
