"""
CLI-level tests for weed_out.cli.

These invoke `python -m weed_out.cli` via subprocess to cover the CLI
grammar, `--root` validation, --tree/dry-run/--commit behavior, and exit
codes end to end.

The `run_cli` and `sample_tree` fixtures live in conftest.py.
"""

# ---------- grammar ----------


def test_cli_bare_with_piped_stdin_is_usage_error(run_cli):
    result = run_cli([], input_text="")
    assert result.returncode == 1
    assert "takes no piped input" in result.stderr
    assert "Usage: weed-out" in result.stderr
    assert result.stdout == ""


def test_cli_missing_keep_and_no_ignore_file_is_usage_error(run_cli, sample_tree):
    result = run_cli(["--root", str(sample_tree)], input_text="")
    assert result.returncode == 1
    assert "no keep entries specified" in result.stderr
    assert result.stderr.startswith("weed-out: ")


def test_cli_flag_order_is_free(run_cli, sample_tree):
    result = run_cli(
        ["--root", str(sample_tree), "--keep", "keep.md", "--tree"], input_text=""
    )
    assert result.returncode == 0
    assert "keep.md" in result.stdout


def test_cli_unknown_flag_is_argparse_error(run_cli, sample_tree):
    result = run_cli(
        ["--keep", "keep.md", "--root", str(sample_tree), "--nope"], input_text=""
    )
    assert result.returncode == 2


def test_cli_nonexistent_root_is_error(run_cli, tmp_path):
    result = run_cli(
        ["--keep", "keep.md", "--root", str(tmp_path / "nope")], input_text=""
    )
    assert result.returncode == 1
    assert "is not a directory" in result.stderr
    assert result.stderr.startswith("weed-out: ")


# ---------- --tree ----------


def test_cli_tree_tags_unkept_entries_and_leaves_files_alone(run_cli, sample_tree):
    result = run_cli(
        ["--keep", "keep.md", "--root", str(sample_tree), "--tree"], input_text=""
    )
    assert result.returncode == 0
    assert "drop.txt  [DELETE]" in result.stdout
    assert "keep.md" in result.stdout
    assert "keep.md  [DELETE]" not in result.stdout
    assert (sample_tree / "drop.txt").exists()


def test_cli_tree_protects_contents_of_a_kept_directory(run_cli, sample_tree):
    """Regression coverage for the kept-directory-contents bug at the
    CLI layer, not just the unit level."""
    result = run_cli(
        ["--keep", "src/", "--root", str(sample_tree), "--tree"], input_text=""
    )
    assert result.returncode == 0
    assert "main.py  [DELETE]" not in result.stdout


# ---------- dry run ----------


def test_cli_dry_run_reports_without_deleting(run_cli, sample_tree):
    result = run_cli(["--keep", "keep.md", "--root", str(sample_tree)], input_text="")
    assert result.returncode == 0
    assert "would delete:" in result.stdout
    assert "Dry run only" in result.stdout
    assert (sample_tree / "drop.txt").exists()


# ---------- --commit ----------


def test_cli_commit_deletes_and_preserves_kept(run_cli, sample_tree):
    result = run_cli(
        ["--keep", "keep.md,src/", "--root", str(sample_tree), "--commit"],
        input_text="",
    )
    assert result.returncode == 0
    assert not (sample_tree / "drop.txt").exists()
    assert not (sample_tree / "build").exists()
    assert (sample_tree / "keep.md").exists()
    assert (sample_tree / "src" / "main.py").exists()


# ---------- path-scoped glob patterns ----------


def test_cli_commit_path_scoped_pattern_keeps_only_within_scoped_directory(
    run_cli, sample_tree
):
    (sample_tree / "build" / "main.py").write_text("print('other')\n")
    result = run_cli(
        ["--keep", "src/*.py", "--root", str(sample_tree), "--commit"],
        input_text="",
    )
    assert result.returncode == 0
    assert (sample_tree / "src" / "main.py").exists()
    assert not (sample_tree / "build").exists()


def test_cli_commit_path_scoped_pattern_does_not_cross_subdirectory(
    run_cli, sample_tree
):
    (sample_tree / "src" / "pkg").mkdir()
    (sample_tree / "src" / "pkg" / "deep.py").write_text("x = 1\n")
    result = run_cli(
        ["--keep", "src/*.py", "--root", str(sample_tree), "--commit"],
        input_text="",
    )
    assert result.returncode == 0
    assert (sample_tree / "src" / "main.py").exists()
    assert not (sample_tree / "src" / "pkg" / "deep.py").exists()


def test_cli_commit_path_scoped_pattern_with_double_star_crosses_subdirectory(
    run_cli, sample_tree
):
    (sample_tree / "src" / "pkg").mkdir()
    (sample_tree / "src" / "pkg" / "deep.py").write_text("x = 1\n")
    result = run_cli(
        ["--keep", "src/**/*.py", "--root", str(sample_tree), "--commit"],
        input_text="",
    )
    assert result.returncode == 0
    assert (sample_tree / "src" / "main.py").exists()
    assert (sample_tree / "src" / "pkg" / "deep.py").exists()


def test_cli_commit_bare_pattern_still_matches_everywhere_regression_guard(
    run_cli, sample_tree
):
    """Contrast test: adding path-scoped patterns must not change bare
    (no "/") pattern behavior -- still filename match, tree-wide."""
    (sample_tree / "build" / "main.py").write_text("print('other')\n")
    result = run_cli(
        ["--keep", "*.py", "--root", str(sample_tree), "--commit"],
        input_text="",
    )
    assert result.returncode == 0
    assert (sample_tree / "src" / "main.py").exists()
    assert (sample_tree / "build" / "main.py").exists()


def test_cli_tree_path_scoped_pattern_protects_parent_directory(run_cli, sample_tree):
    result = run_cli(
        ["--keep", "notes/*.md", "--root", str(sample_tree), "--tree"],
        input_text="",
    )
    assert result.returncode == 0
    assert "design.md  [DELETE]" not in result.stdout
    assert "notes  [DELETE]" not in result.stdout
    assert "scratch.txt  [DELETE]" in result.stdout


# ---------- .weed-out-ignore ----------


def test_cli_ignore_file_alone_drives_tree_with_no_keep_flag(run_cli, sample_tree):
    (sample_tree / ".weed-out-ignore").write_text("keep.md\n")
    result = run_cli(["--root", str(sample_tree), "--tree"], input_text="")
    assert result.returncode == 0
    assert "drop.txt  [DELETE]" in result.stdout
    assert "keep.md  [DELETE]" not in result.stdout


def test_cli_keep_flag_and_ignore_file_entries_both_survive(run_cli, sample_tree):
    (sample_tree / ".weed-out-ignore").write_text("src/\n")
    result = run_cli(
        ["--keep", "keep.md", "--root", str(sample_tree), "--tree"], input_text=""
    )
    assert result.returncode == 0
    assert "keep.md  [DELETE]" not in result.stdout
    assert "main.py  [DELETE]" not in result.stdout
    assert "drop.txt  [DELETE]" in result.stdout


def test_cli_ignore_file_comments_and_blank_lines_are_skipped(run_cli, sample_tree):
    (sample_tree / ".weed-out-ignore").write_text(
        "# keep the readme-ish file\nkeep.md\n\n# trailing comment\n"
    )
    result = run_cli(["--root", str(sample_tree), "--tree"], input_text="")
    assert result.returncode == 0
    assert "keep.md  [DELETE]" not in result.stdout
    assert "drop.txt  [DELETE]" in result.stdout
