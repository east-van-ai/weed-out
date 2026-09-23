"""
# ==============================================
# East Van AI -- AI for the rest of us!
# https://github.com/east-van-ai/weed-out
# contact: east-van-ai@proton.me
# ==============================================
#
# ~~~ ~~~ ~~~ ~~~ ~~~ ~~~ ~~~ weed-out ~~~ ~~~ ~~~ ~~~ ~~~ ~~~ ~~~
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
from collections import namedtuple

from weed_out import cli_delete, cli_trash, cli_tree, errors
from weed_out.args import build_parser, version_line

# main() returns EXIT_OK or EXIT_ERROR. On usage errors, argparse's
# ArgumentParser.error() calls sys.exit(2) before main() can return, so
# EXIT_ARGPARSE is never returned by main(). It's defined for test assertions.
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_ARGPARSE = 2

__all__ = ["EXIT_ARGPARSE", "EXIT_ERROR", "EXIT_OK", "main"]

Command = namedtuple("Command", "bare usage slots action")
"""A command word's answer to being typed alone, its usage line, the path slots it
reads, and the action a full invocation runs.

`bare` returns the text for the bare word; `action` runs the command. For `version`,
both read from `version_line`, since running the command answers the bare word.
"""

COMMANDS = {
    "delete": Command(
        lambda: cli_delete.__doc__.strip(),
        cli_delete.USAGE,
        cli_delete.SLOTS,
        lambda paths, args: cli_delete.run(*paths, args),
    ),
    "trash": Command(
        lambda: cli_trash.__doc__.strip(),
        cli_trash.USAGE,
        cli_trash.SLOTS,
        lambda paths, args: cli_trash.run(*paths, args),
    ),
    "tree": Command(
        lambda: cli_tree.__doc__.strip(),
        cli_tree.USAGE,
        cli_tree.SLOTS,
        lambda paths, args: cli_tree.run(*paths, args),
    ),
    "version": Command(
        version_line,
        "weed-out version",
        (),
        lambda paths, args: print(version_line()),
    ),
}


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


def usage_error(usage, message):
    """Report a command line weed-out could not read, with that command's usage."""
    sys.stdout.flush()
    print(f"weed-out: {message}", file=sys.stderr)
    print(f"Usage: {usage}", file=sys.stderr)
    return EXIT_ERROR


def readiness_error(message):
    """Report what the run needed and did not find, with no usage line."""
    sys.stdout.flush()
    print(f"weed-out: {message}", file=sys.stderr)
    return EXIT_ERROR


def runtime_error(message):
    """Report a run that stopped partway, naming what was written."""
    sys.stdout.flush()
    print(f"weed-out: {message}", file=sys.stderr)
    return EXIT_ERROR


def main(argv=None):
    """Parse arguments, run the matching command, return an exit code."""
    tokens = list(sys.argv[1:] if argv is None else argv)

    if not tokens:
        print(__doc__.strip())
        return EXIT_OK

    if len(tokens) == 1 and tokens[0] in COMMANDS:
        print(COMMANDS[tokens[0]].bare())
        return EXIT_OK

    parser = build_parser()
    args, extras = parser.parse_known_args(tokens)

    if any(extra.startswith("-") for extra in extras):
        parser.parse_args(tokens)  # argparse names the flag better, exit 2

    paths = leading_paths(tokens[1:])

    command = COMMANDS[args.command]

    if len(paths) < len(command.slots):
        needed = " and ".join(command.slots)
        if len(command.slots) > 1:
            needed = f"both {needed}"
        return usage_error(command.usage, f"{args.command} needs {needed}")

    if len(paths) > len(command.slots):
        stray = paths[len(command.slots)]
        last = command.slots[-1] if command.slots else "it"
        return usage_error(
            command.usage,
            f"{args.command} takes nothing after {last}: {stray!r}",
        )

    try:
        command.action(paths, args)
    except errors.ReadinessError as failure:
        return readiness_error(str(failure))
    except errors.RuntimeFailure as failure:
        return runtime_error(str(failure))

    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
