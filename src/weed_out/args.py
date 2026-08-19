"""Argument parsing for weed-out's CLI grammar."""

import argparse

# Argparse hardcodes 2 in `ArgumentParser.error()`, which calls `sys.exit`
# itself, so EXIT_ARGPARSE is never returned, only asserted against. See
# DESIGN.md, "Exit codes", for what the three cover.
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_ARGPARSE = 2


def add_common_options(parser):
    """Add the PATH positional and the options every command shares.

    PATH is optional to argparse so that a bare command word reaches
    `main()` and gets documentation instead of a usage error. Its parsed
    value goes unused: `main()` reads the slot itself (see DESIGN.md,
    "Positions are decided, not inferred").
    """
    parser.add_argument(
        "path",
        metavar="PATH",
        nargs="?",
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


def build_parser():
    """Construct the argument parser for the whole CLI."""
    # No abbreviation anywhere: --com must not silently mean --commit.
    # argparse matches any unambiguous prefix unless told otherwise, and
    # add_parser() inherits nothing from this parser, so every subparser
    # below repeats the keyword. Every flag weed-out defines lives on a
    # subparser, so setting it here alone would change nothing.
    p = argparse.ArgumentParser(
        prog="weed-out",
        description="Delete everything except specified paths/patterns.",
        allow_abbrev=False,
    )
    subparsers = p.add_subparsers(dest="command", required=True, metavar="COMMAND")

    delete_help = "Permanently remove everything not kept. No undo."
    delete_p = subparsers.add_parser(
        "delete", help=delete_help, description=delete_help, allow_abbrev=False
    )
    add_common_options(delete_p)
    add_mode_flags(delete_p)

    trash_help = "Send everything not kept to the OS trash. Recoverable."
    trash_p = subparsers.add_parser(
        "trash", help=trash_help, description=trash_help, allow_abbrev=False
    )
    add_common_options(trash_p)
    add_mode_flags(trash_p)

    tree_help = (
        "Print a tree tagging what would be removed. Never touches the filesystem."
    )
    tree_p = subparsers.add_parser(
        "tree", help=tree_help, description=tree_help, allow_abbrev=False
    )
    add_common_options(tree_p)

    return p
