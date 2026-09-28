"""Argument parsing for weed-out's CLI grammar."""

import argparse
import sys
from importlib import metadata

from weed_out import cli_delete, cli_trash, cli_tree

PROG = "weed-out"
"""The word typed on the command line, which the parser and `version_line` share."""

PATHS = """\
paths:
  PATH      the directory to operate on. Use `.` for the current directory.
            A .weed-out-ignore file there is read and merged with --keep.
  PATH comes right after COMMAND, then options in any order."""
"""The section `weed-out --help` closes with, since PATH belongs to no one command."""

MONOCHROME = {"color": False} if sys.version_info >= (3, 14) else {}
"""argparse's `color=` switch, from 3.14. Older versions print no colour."""


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


def leading_paths(tokens):
    """Return the tokens ahead of the first flag.

    The documented grammar puts PATH before every flag, so the slot is
    read off the front of the command line. What argparse resolved from
    anywhere else is discarded, since how much it tolerates depends on
    the interpreter.
    """
    paths = []
    for token in tokens:
        if token.startswith("-"):
            break
        paths.append(token)
    return paths


def add_common_options(parser):
    """Add the PATH positional and the options every command shares.

    PATH is optional to argparse so that a bare command word reaches
    `main()` and gets documentation instead of a usage error. Its parsed
    value goes unused: `main()` reads the slot itself.
    """
    paths = parser.add_argument_group("paths")
    paths.add_argument(
        "path",
        metavar="PATH",
        nargs="?",
        help="the directory to operate on",
    )
    parser.add_argument(
        "--keep",
        metavar="LIST",
        help="comma-separated files, directories, and glob patterns to keep; "
        "optional if .weed-out-ignore supplies entries",
    )
    parser.add_argument(
        "--dot-files", action="store_true", help="keep dotfiles, even if not listed"
    )
    parser.add_argument(
        "--dot-dirs",
        action="store_true",
        help="keep dot-directories, even if not listed",
    )


def add_mode_flags(parser, commit_help):
    """Add the mutually exclusive --dry-run/--commit pair to a removal command.

    Only `delete` and `trash` get these. `tree` can do nothing but look, so
    leaving them undefined there makes `tree PATH --commit` a parse error by
    construction rather than a case the code has to handle.
    """
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be removed, touching nothing (default)",
    )
    group.add_argument("--commit", action="store_true", help=commit_help)


def add_delete(subparsers):
    """Add the `delete` subparser and return it."""
    delete = subparsers.add_parser(
        "delete", help=cli_delete.HELP, usage=cli_delete.USAGE, allow_abbrev=False
    )
    add_common_options(delete)
    add_mode_flags(delete, "actually remove; permanent, no undo")
    return delete


def add_trash(subparsers):
    """Add the `trash` subparser and return it."""
    trash = subparsers.add_parser(
        "trash", help=cli_trash.HELP, usage=cli_trash.USAGE, allow_abbrev=False
    )
    add_common_options(trash)
    add_mode_flags(trash, "actually send to the OS trash")
    return trash


def add_tree(subparsers):
    """Add the `tree` subparser and return it."""
    tree = subparsers.add_parser(
        "tree", help=cli_tree.HELP, usage=cli_tree.USAGE, allow_abbrev=False
    )
    add_common_options(tree)
    return tree


def build_parser():
    """Construct the argument parser for the whole CLI.

    `add_parser()` inherits nothing from this parser, so each subparser
    repeats `allow_abbrev=False`.
    """
    parser = argparse.ArgumentParser(
        prog=PROG,
        **MONOCHROME,
        usage=f"{cli_delete.USAGE}\n       {cli_trash.USAGE}\n       {cli_tree.USAGE}",
        epilog=PATHS,
        # Keeps the epilog's lines as written rather than joined into one paragraph.
        formatter_class=argparse.RawDescriptionHelpFormatter,
        allow_abbrev=False,
    )

    subparsers = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    version_help = "print the installed version and exit"
    parser.add_argument(
        "--version", action="version", version=version_line(), help=version_help
    )

    add_delete(subparsers)
    add_trash(subparsers)
    add_tree(subparsers)
    subparsers.add_parser("version", help=version_help, allow_abbrev=False)

    return parser


def command_help(add_command):
    """Return one command's own `--help` text, as argparse prints it.

    `add_command` is `add_delete`, `add_trash`, or `add_tree`.
    """
    subparsers = argparse.ArgumentParser(prog=PROG, **MONOCHROME).add_subparsers()
    return add_command(subparsers).format_help()
