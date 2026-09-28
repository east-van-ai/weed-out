"""
# ==============================================
# East Van AI -- AI for the rest of us!
# https://github.com/east-van-ai/weed-out
# contact: east-van-ai@proton.me
# license: MIT
# ==============================================

        weed-out

weed-out deletes everything in a directory tree except what --keep lists,
as exact paths or glob patterns. Most cleanup tools are exclude-list shaped
("delete these"); weed-out inverts that. Nothing is ever removed unless
--commit is passed. See what would go with `weed-out tree`, remove it with
`weed-out delete` or `weed-out trash`.

Run a command with nothing after it for its own page.

piped input:
    weed-out reads none.

exit codes:
    0:     success, and documentation
    1:     weed-out's own error: a PATH missing, stray, or not a directory,
           or --commit with no keep entries
    2:     an unknown command, an unknown option, or a bad value
"""

import sys
from collections import namedtuple

from weed_out import args, cli_delete, cli_trash, cli_tree, errors

# main() returns EXIT_OK or EXIT_ERROR. On usage errors, argparse's
# ArgumentParser.error() calls sys.exit(2) before main() can return, so
# EXIT_ARGPARSE is never returned by main(). It's defined for test assertions.
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_ARGPARSE = 2

Command = namedtuple("Command", "bare usage slots action")
"""A command word's answer to being typed alone, its usage line, the path slots it
reads, and the action a full invocation runs.

`bare` returns the text for the bare word; `action` runs the command. For `version`,
both read from `version_line`, since running the command answers the bare word.
"""


def command_page(module, add_command):
    """Return a command's answer to its bare word: its docstring, then its --help.

    argparse documents the usage, PATH, and the flags, so each has one copy.
    """
    doc = module.__doc__.strip("\n")  # not strip(): the title's indent is layout
    return f"{doc}\n\n{args.command_help(add_command).rstrip()}"


COMMANDS = {
    "delete": Command(
        lambda: command_page(cli_delete, args.add_delete),
        cli_delete.USAGE,
        cli_delete.SLOTS,
        lambda paths, parsed: cli_delete.run(*paths, parsed),
    ),
    "trash": Command(
        lambda: command_page(cli_trash, args.add_trash),
        cli_trash.USAGE,
        cli_trash.SLOTS,
        lambda paths, parsed: cli_trash.run(*paths, parsed),
    ),
    "tree": Command(
        lambda: command_page(cli_tree, args.add_tree),
        cli_tree.USAGE,
        cli_tree.SLOTS,
        lambda paths, parsed: cli_tree.run(*paths, parsed),
    ),
    "version": Command(
        args.version_line,
        "weed-out version",
        (),
        lambda paths, parsed: print(args.version_line()),
    ),
}


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
        print(f"{__doc__.strip()}\n\n{args.build_parser().format_help().rstrip()}")
        return EXIT_OK

    if len(tokens) == 1 and tokens[0] in COMMANDS:
        print(COMMANDS[tokens[0]].bare())
        return EXIT_OK

    parser = args.build_parser()
    parsed, extras = parser.parse_known_args(tokens)

    if any(extra.startswith("-") for extra in extras):
        parser.parse_args(tokens)  # argparse names the flag better, exit 2

    paths = args.leading_paths(tokens[1:])

    command = COMMANDS[parsed.command]

    if len(paths) < len(command.slots):
        needed = " and ".join(command.slots)
        if len(command.slots) > 1:
            needed = f"both {needed}"
        return usage_error(command.usage, f"{parsed.command} needs {needed}")

    if len(paths) > len(command.slots):
        stray = paths[len(command.slots)]
        last = command.slots[-1] if command.slots else "it"
        return usage_error(
            command.usage,
            f"{parsed.command} takes nothing after {last}: {stray!r}",
        )

    if extras:
        return usage_error(
            command.usage,
            f"{parsed.command} got a stray argument: {extras[0]!r} "
            "(separate --keep entries with commas)",
        )

    try:
        command.action(paths, parsed)
    except errors.ReadinessError as failure:
        return readiness_error(str(failure))
    except errors.RuntimeFailure as failure:
        return runtime_error(str(failure))

    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
