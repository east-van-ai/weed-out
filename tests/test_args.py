"""
Unit tests for weed_out.args.

These cover the version helpers and the --version action they feed, all
of which sit above the CLI walk and answer before any command runs. The
`version` command word is a CLI-level concern and lives in
test_cli_integration.py, alongside the check that the two spellings
agree. The rest of args.py is exercised through the CLI, there too.
"""

from importlib import metadata

import pytest

from weed_out.args import PROG, build_parser, installed_version, version_line


def test_installed_version_reads_the_distribution_metadata():
    """The number comes from the installed distribution, never from a literal."""
    assert installed_version() == metadata.version("weed-out")


def test_installed_version_answers_when_nothing_is_installed(monkeypatch):
    """A tree with no install has no metadata to read: answer, don't raise.

    Every command that is not a bare word builds the parser, so an
    unguarded lookup would fail the whole CLI there, not just --version.
    """

    def missing(name):
        raise metadata.PackageNotFoundError(name)

    monkeypatch.setattr(metadata, "version", missing)
    assert installed_version() == "unknown (not installed)"


def test_version_line_joins_the_program_name_and_the_number():
    """One builder, so the flag and the command word cannot drift apart."""
    assert version_line() == f"{PROG} {installed_version()}"


def test_parser_prog_is_the_shared_constant():
    """The parser and the helper take the same name, so %(prog)s cannot differ."""
    assert build_parser().prog == PROG


def test_version_action_exits_zero_through_systemexit(capsys):
    """--version calls sys.exit(0) itself, so 0 never returns through main().

    The other documentation paths (the banner, a command's own doc) do
    return their code, which is why this one is asserted differently.
    """
    with pytest.raises(SystemExit) as exit_info:
        build_parser().parse_args(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == version_line()


def test_version_action_prints_whatever_the_helper_answered(monkeypatch, capsys):
    """The parser is built from the helper, so the fallback reaches the output.

    Asserting the helper's return alone would pass even if build_parser
    stopped calling it.
    """
    monkeypatch.setattr(
        "weed_out.args.installed_version", lambda: "unknown (not installed)"
    )
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--version"])
    assert capsys.readouterr().out.strip() == "weed-out unknown (not installed)"
