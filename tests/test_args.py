"""
Unit tests for weed_out.args.

These cover the version helper and the --version action it feeds, both
of which sit above the CLI walk and answer before any command runs. The
rest of args.py is exercised through the CLI, in test_cli_integration.py.
"""

from importlib import metadata

import pytest

from weed_out.args import build_parser, installed_version


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


def test_version_action_exits_zero_through_systemexit(capsys):
    """--version calls sys.exit(0) itself, so 0 never returns through main().

    The other documentation paths (the banner, a command's own doc) do
    return their code, which is why this one is asserted differently.
    """
    with pytest.raises(SystemExit) as exit_info:
        build_parser().parse_args(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"weed-out {installed_version()}"


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
