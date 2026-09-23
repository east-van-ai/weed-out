"""Argument parsing for weed-out's CLI grammar."""

import argparse
from importlib import metadata

from weed_out import cli_delete, cli_trash, cli_tree

PROG = "weed-out"
"""The word typed on the command line, which the parser and `version_line` share."""


def installed_version():
    """Return the version of the installed weed-out distribution.

    The literal lives in `pyproject.toml` and reaches the CLI through
    the installed metadata, never through a second copy in the source.
    A source tree run with no install has no metadata to read, and
    every command builds the parser, so the miss is answered rather
    than raised.
    """
    try:
        return metadata.version("weed-out")
    except metadata.PackageNotFoundError:
        return "unknown (not installed)"


def version_line():
    """Return the program name and the installed version on one line.

    Both spellings print this. `weed-out version` calls it directly and
    `--version` is built from it, so the two cannot drift apart.
    """
    return f"{PROG} {installed_version()}"


def add_common_options(parser):
    """Add the PATH positional and the options every command shares.

    PATH is optional to argparse so that a bare command word reaches
    `main()` and gets documentation instead of a usage error. Its parsed
    value goes unused: `main()` reads the slot itself.
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
        prog=PROG,
        description="Delete everything except specified paths/patterns.",
        allow_abbrev=False,
    )

    subparsers = p.add_subparsers(dest="command", required=True, metavar="COMMAND")

    version_help = "Print the installed version and exit."
    # Fires during parsing, ahead of the required-command check, so this
    # answers with no command word and calls sys.exit(0) itself.
    p.add_argument(
        "--version", action="version", version=version_line(), help=version_help
    )
    # No PATH, no flags: cli.py's Command entry reads version_line
    # directly, not a module docstring, so table membership is safe.
    subparsers.add_parser(
        "version", help=version_help, description=version_help, allow_abbrev=False
    )

    delete_p = subparsers.add_parser(
        "delete", help=cli_delete.HELP, description=cli_delete.HELP, allow_abbrev=False
    )
    add_common_options(delete_p)
    add_mode_flags(delete_p)

    trash_p = subparsers.add_parser(
        "trash", help=cli_trash.HELP, description=cli_trash.HELP, allow_abbrev=False
    )
    add_common_options(trash_p)
    add_mode_flags(trash_p)

    tree_p = subparsers.add_parser(
        "tree", help=cli_tree.HELP, description=cli_tree.HELP, allow_abbrev=False
    )
    add_common_options(tree_p)

    return p
