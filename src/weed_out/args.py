"""Argument parsing for weed-out's CLI grammar."""

import argparse

USAGE = (
    "Usage: weed-out <delete | trash | tree> PATH [--keep LIST] "
    "[--dry-run | --commit] [--dot-files] [--dot-dirs]"
)


def add_common_options(parser):
    """Add the PATH positional and the options every command shares."""
    parser.add_argument(
        "path",
        metavar="PATH",
        help="Directory to operate on. Use `.` for the current directory.",
    )
    parser.add_argument(
        "--keep",
        help="Comma-separated list of files/dirs/glob patterns to keep. "
        "Optional if a .weed-out-ignore file at PATH supplies entries instead. "
        "With neither, everything is kept and --commit is refused.",
    )
    parser.add_argument("--dot-files", action="store_true", help="Keep dotfiles")
    parser.add_argument("--dot-dirs", action="store_true", help="Keep dot-directories")


def add_mode_flags(parser):
    """Add the mutually exclusive --dry-run/--commit pair to a removal command.

    Only `delete` and `trash` get these. `tree` can do nothing but look, so
    leaving them undefined there makes `tree PATH --commit` a parse error by
    construction rather than a case the code has to handle.
    """
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be removed without touching anything. "
        "This is the default when --commit is not passed.",
    )
    group.add_argument(
        "--commit",
        action="store_true",
        help="Actually carry the removal out. Permanent for `delete` -- no undo.",
    )


def parse_args():
    """Parse the command line into a command plus its options."""
    p = argparse.ArgumentParser(
        prog="weed-out",
        description="Delete everything except specified paths/patterns.",
    )
    subparsers = p.add_subparsers(dest="command", required=True, metavar="COMMAND")

    delete_help = "Permanently remove everything not kept. No undo."
    delete_p = subparsers.add_parser(
        "delete", help=delete_help, description=delete_help
    )
    add_common_options(delete_p)
    add_mode_flags(delete_p)

    trash_help = "Send everything not kept to the OS trash. Recoverable."
    trash_p = subparsers.add_parser("trash", help=trash_help, description=trash_help)
    add_common_options(trash_p)
    add_mode_flags(trash_p)

    tree_help = (
        "Print a tree tagging what would be removed. Never touches the filesystem."
    )
    tree_p = subparsers.add_parser("tree", help=tree_help, description=tree_help)
    add_common_options(tree_p)

    return p.parse_args()
