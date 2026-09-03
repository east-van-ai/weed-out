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
#    weed-out delete PATH [--keep LIST] [--dry-run | --commit] [options]
#    weed-out trash  PATH [--keep LIST] [--dry-run | --commit] [options]
#    weed-out tree   PATH [--keep LIST] [options]
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
# Run a command with nothing else after it for its own documentation,
# including the options it takes:
#
#    weed-out delete
#    weed-out trash
#    weed-out tree
#
# PATH comes first, then flags, whose order among themselves is free.
# Spell flags in full: an abbreviation like `--com` is rejected, so it
# can never stand in for `--commit`. Bare `weed-out` prints this text
# and exits 0. Asking is not a usage error.
#
# weed-out reads no piped input.
#
# Exit codes:
#
#    0:     success, and documentation
#    1:     weed-out's own error, a PATH missing, stray, or not a
#           directory, or --commit with no keep entries
#    2:     an unknown command, an unknown flag, or a bad value
#
# License: MIT
# ==============================================
"""

import sys
from pathlib import Path

from weed_out import cli_delete, cli_trash, cli_tree
from weed_out.args import (
    EXIT_ARGPARSE,
    EXIT_ERROR,
    EXIT_OK,
    build_parser,
    version_line,
)

__all__ = ["EXIT_ARGPARSE", "EXIT_ERROR", "EXIT_OK", "main"]

# Each command's surface module carries its own documentation, usage
# line, and run(). The table adds nothing else: every command reads the
# same single PATH slot.
COMMANDS = {
    "delete": cli_delete,
    "trash": cli_trash,
    "tree": cli_tree,
}

# `version` is missing from that table on purpose, and the gap is not an
# oversight to fill: the bare-word guard in main() answers any command
# word it holds with a docstring, and `weed-out version` is one word.
# It has no surface module either, for the same reason.
VERSION_USAGE = "weed-out version"


def leading_paths(tokens):
    """Return the tokens ahead of the first flag.

    The documented grammar puts PATH before every flag, so the slot is
    read off the front of the command line. What argparse resolved from
    anywhere else is discarded, since how much it tolerates depends on
    the interpreter. See DESIGN.md, "Positions are decided, not
    inferred".
    """
    paths = []
    for token in tokens:
        if token.startswith("-"):
            break
        paths.append(token)
    return paths


def usage_error(usage, message):
    """Report a command line weed-out could not read, with the matching usage.

    Takes the usage line rather than the command's module, because
    `version` has no surface module to read one off.

    Grammar errors only. A readiness failure (PATH not a directory)
    prints no usage line: the command line was read fine, and usage
    beside it would answer a question nobody asked (see DESIGN.md,
    "PATH validation").
    """
    print(f"weed-out: {message}", file=sys.stderr)
    print(f"Usage: {usage}", file=sys.stderr)
    return EXIT_ERROR


def main():
    """Parse arguments, enforce the CLI grammar, and dispatch to a command.

    A bare word is a question and gets documentation, exit 0. Any other
    shortfall in the PATH slot is a slip and gets an error, exit 1.
    Argparse keeps the vocabulary it owns: an unknown command, an
    unknown flag, or a bad value, exiting 2.
    """
    tokens = sys.argv[1:]

    if not tokens:
        print(__doc__.strip())
        return EXIT_OK

    if len(tokens) == 1 and tokens[0] in COMMANDS:
        print(COMMANDS[tokens[0]].__doc__.strip())
        return EXIT_OK

    parser = build_parser()
    args, extras = parser.parse_known_args(tokens)

    if any(extra.startswith("-") for extra in extras):
        parser.parse_args(tokens)  # argparse names the flag better, exit 2

    if args.command == "version":
        # The subparser defines no positional, so parse_known_args takes
        # a stray bare word without complaint. The slot rule catches it.
        strays = leading_paths(tokens[1:])
        if strays:
            return usage_error(
                VERSION_USAGE, f"version takes nothing after it: {strays[0]!r}"
            )
        print(version_line())
        return EXIT_OK

    module = COMMANDS[args.command]

    # Not args.path: what argparse resolves from a token after a flag
    # varies by interpreter, and the grammar should not.
    paths = leading_paths(tokens[1:])
    if not paths:
        return usage_error(module.USAGE, f"{args.command} needs PATH")
    if len(paths) > 1:
        return usage_error(
            module.USAGE, f"{args.command} takes nothing after PATH: {paths[1]!r}"
        )

    root = Path(paths[0]).resolve()
    if not root.is_dir():
        print(f"weed-out: {root} is not a directory", file=sys.stderr)
        return EXIT_ERROR

    return module.run(root, args)


if __name__ == "__main__":
    sys.exit(main())
