"""
Shared fixtures and helpers for weed_out.cli tests.
"""

import subprocess
import sys

import pytest


@pytest.fixture
def run_cli():
    """Return a callable that invokes `python -m weed_out.cli` via subprocess."""

    def _run_cli(args, input_text=None, cwd=None):
        return subprocess.run(
            [sys.executable, "-m", "weed_out.cli", *args],
            input=input_text,
            capture_output=True,
            text=True,
            cwd=cwd,
            check=False,
        )

    return _run_cli


@pytest.fixture
def sample_tree(tmp_path):
    """Build a small nested throwaway tree and return its root.

    Layout:
        keep.md                    -- exact-kept file
        drop.txt                   -- not kept, at root
        src/main.py                -- kept via directory (src/)
        notes/design.md            -- kept only via the *.md glob pattern,
                                       so notes/ must be protected without
                                       being named in --keep itself
        notes/scratch.txt          -- not kept, sibling inside a protected dir
        build/                     -- entirely unkept, non-empty directory
        build/artifact.bin
        .env                       -- dotfile, not kept unless --dot-files
        empty_dir/                 -- already empty, not kept
    """
    (tmp_path / "keep.md").write_text("keep\n")
    (tmp_path / "drop.txt").write_text("drop\n")

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n")

    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "design.md").write_text("design notes\n")
    (tmp_path / "notes" / "scratch.txt").write_text("scratch\n")

    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "artifact.bin").write_text("binary\n")

    (tmp_path / ".env").write_text("SECRET=1\n")

    (tmp_path / "empty_dir").mkdir()

    return tmp_path
