"""
CLI-level tests for weed_out.cli.

These invoke `python -m weed_out.cli` via subprocess to cover the CLI
grammar, PATH validation, tree/dry-run/delete/trash behavior, and exit
codes end to end.

The `run_cli`, `sample_tree`, `named_file_tree` and `linked_tree`
fixtures live in conftest.py.
"""

# ---------- grammar ----------


def test_cli_bare_with_piped_stdin_is_usage_error(run_cli):
    result = run_cli([], input_text="")
    assert result.returncode == 1
    assert "takes no piped input" in result.stderr
    assert "Usage: weed-out" in result.stderr
    assert result.stdout == ""


def test_cli_flag_order_after_command_is_free(run_cli, sample_tree):
    """Flags are order-free among themselves, but only after COMMAND and PATH."""
    result = run_cli(
        ["tree", str(sample_tree), "--dot-files", "--keep", "keep.md"], input_text=""
    )
    assert result.returncode == 0
    assert "keep.md" in result.stdout


def test_cli_missing_command_is_argparse_error(run_cli):
    result = run_cli(["--keep", "keep.md"], input_text="")
    assert result.returncode == 2


def test_cli_unknown_command_is_argparse_error(run_cli, sample_tree):
    result = run_cli(["obliterate", str(sample_tree)], input_text="")
    assert result.returncode == 2


def test_cli_missing_path_is_argparse_error(run_cli):
    result = run_cli(["delete", "--keep", "keep.md"], input_text="")
    assert result.returncode == 2


def test_cli_flags_before_command_is_argparse_error(run_cli, sample_tree):
    result = run_cli(["--keep", "keep.md", "tree", str(sample_tree)], input_text="")
    assert result.returncode == 2


def test_cli_old_action_flag_is_argparse_error(run_cli, sample_tree):
    """The pre-command grammar's --delete/--trash/--tree flags are gone outright."""
    result = run_cli(
        ["--delete", "--keep", "keep.md", "--root", str(sample_tree)], input_text=""
    )
    assert result.returncode == 2


def test_cli_unknown_flag_is_argparse_error(run_cli, sample_tree):
    result = run_cli(
        ["tree", str(sample_tree), "--keep", "keep.md", "--nope"], input_text=""
    )
    assert result.returncode == 2


def test_cli_nonexistent_path_is_error(run_cli, tmp_path):
    """A PATH that parses but isn't a directory is weed-out's own error, exit 1 --
    unlike a missing PATH, which argparse rejects with exit 2."""
    result = run_cli(
        ["delete", str(tmp_path / "nope"), "--keep", "keep.md"], input_text=""
    )
    assert result.returncode == 1
    assert "is not a directory" in result.stderr
    assert result.stderr.startswith("weed-out: ")


# ---------- an absent keep list keeps everything ----------
#
# See DESIGN.md, "An absent keep list keeps everything". With neither
# --keep nor .weed-out-ignore, the run resolves as `--keep "."`, so every
# entry survives. Only --commit still refuses to run.


def test_cli_tree_with_no_keep_list_keeps_every_entry(run_cli, sample_tree):
    """Everything is kept, so nothing is tagged and nothing collapses."""
    result = run_cli(["tree", str(sample_tree)], input_text="")
    assert result.returncode == 0
    # not a bare "[REMOVE]" check: the header line mentions the tag too
    assert not any(ln.endswith("[REMOVE]") for ln in result.stdout.splitlines())

    total = sum(1 for _ in sample_tree.rglob("*"))
    assert f"{total} kept, 0 to remove." in result.stdout
    assert "collapsed" not in result.stdout


def test_cli_no_keep_list_is_announced_on_stderr(run_cli, sample_tree):
    """The read-only surfaces explain why nothing is tagged."""
    for args in (["tree"], ["delete"], ["trash"]):
        result = run_cli([*args, str(sample_tree)], input_text="")
        assert result.returncode == 0
        assert 'as if --keep "."' in result.stderr
        assert result.stderr.startswith("weed-out: ")


def test_cli_dry_run_with_no_keep_list_removes_nothing(run_cli, sample_tree):
    result = run_cli(["delete", str(sample_tree)], input_text="")
    assert result.returncode == 0
    assert "0 items would be removed." in result.stdout
    assert (sample_tree / "drop.txt").exists()
    assert (sample_tree / "build" / "artifact.bin").exists()


def test_cli_dry_run_with_no_keep_list_omits_the_commit_trailer(run_cli, sample_tree):
    """The usual trailer would point at a --commit that exits 1."""
    result = run_cli(["delete", str(sample_tree)], input_text="")
    assert "Re-run with --commit" not in result.stdout


def test_cli_commit_with_no_keep_list_is_a_usage_error(run_cli, sample_tree):
    """--commit is the one mode that still refuses an absent keep list."""
    for command in ("delete", "trash"):
        result = run_cli([command, str(sample_tree), "--commit"], input_text="")
        assert result.returncode == 1
        assert "no keep entries specified" in result.stderr
        assert result.stderr.startswith("weed-out: ")
        assert (sample_tree / "drop.txt").exists()
        assert (sample_tree / "build" / "artifact.bin").exists()


def test_cli_ignore_file_with_only_comments_is_an_absent_keep_list(
    run_cli, sample_tree
):
    """read_ignore_file yields nothing, so the file may as well not exist."""
    (sample_tree / ".weed-out-ignore").write_text("# nothing to see\n\n")
    result = run_cli(["tree", str(sample_tree)], input_text="")
    assert result.returncode == 0
    assert not any(ln.endswith("[REMOVE]") for ln in result.stdout.splitlines())
    assert 'as if --keep "."' in result.stderr


# ---------- tree ----------


def test_cli_tree_tags_unkept_entries_and_leaves_files_alone(run_cli, sample_tree):
    result = run_cli(["tree", str(sample_tree), "--keep", "keep.md"], input_text="")
    assert result.returncode == 0
    assert "drop.txt  [REMOVE]" in result.stdout
    assert "keep.md" in result.stdout
    assert "keep.md  [REMOVE]" not in result.stdout
    assert (sample_tree / "drop.txt").exists()


def test_cli_tree_protects_contents_of_a_kept_directory(run_cli, sample_tree):
    """Regression coverage for the kept-directory-contents bug at the
    CLI layer, not just the unit level."""
    result = run_cli(["tree", str(sample_tree), "--keep", "src/"], input_text="")
    assert result.returncode == 0
    assert "main.py  [REMOVE]" not in result.stdout


def test_cli_tree_rejects_commit(run_cli, sample_tree):
    """`tree` defines no mode flags, so --commit is unrecognized rather than
    silently accepted and ignored."""
    result = run_cli(
        ["tree", str(sample_tree), "--keep", "keep.md", "--commit"], input_text=""
    )
    assert result.returncode == 2


# ---------- dry run ----------


def test_cli_dry_run_reports_without_deleting(run_cli, sample_tree):
    result = run_cli(["delete", str(sample_tree), "--keep", "keep.md"], input_text="")
    assert result.returncode == 0
    assert "would delete:" not in result.stdout
    assert str(sample_tree / "drop.txt") in result.stdout
    assert "items would be removed" in result.stdout
    assert "Dry run only" in result.stdout
    assert (sample_tree / "drop.txt").exists()


def test_cli_dry_run_explicit_flag_matches_default(run_cli, sample_tree):
    default_result = run_cli(
        ["delete", str(sample_tree), "--keep", "keep.md"], input_text=""
    )
    explicit_result = run_cli(
        ["delete", str(sample_tree), "--keep", "keep.md", "--dry-run"], input_text=""
    )
    assert explicit_result.returncode == 0
    assert explicit_result.stdout == default_result.stdout


def test_cli_dry_run_footer_names_the_disposal(run_cli, sample_tree):
    """delete and trash select the identical set, so the footer is the only
    thing that distinguishes their previews."""
    delete_result = run_cli(
        ["delete", str(sample_tree), "--keep", "keep.md"], input_text=""
    )
    trash_result = run_cli(
        ["trash", str(sample_tree), "--keep", "keep.md"], input_text=""
    )
    assert delete_result.returncode == 0
    assert trash_result.returncode == 0
    assert "permanently delete" in delete_result.stdout
    assert "OS trash" in trash_result.stdout
    assert (sample_tree / "drop.txt").exists()


def test_cli_commit_and_dry_run_together_is_argparse_error(run_cli, sample_tree):
    result = run_cli(
        ["delete", str(sample_tree), "--keep", "keep.md", "--commit", "--dry-run"],
        input_text="",
    )
    assert result.returncode == 2


# ---------- delete ----------


def test_cli_delete_deletes_and_preserves_kept(run_cli, sample_tree):
    result = run_cli(
        ["delete", str(sample_tree), "--keep", "keep.md,src/", "--commit"],
        input_text="",
    )
    assert result.returncode == 0
    assert not (sample_tree / "drop.txt").exists()
    assert not (sample_tree / "build").exists()
    assert (sample_tree / "keep.md").exists()
    assert (sample_tree / "src" / "main.py").exists()


# ---------- trash ----------


def test_cli_trash_removes_from_source_and_preserves_kept(run_cli, sample_tree):
    result = run_cli(
        ["trash", str(sample_tree), "--keep", "keep.md,src/", "--commit"],
        input_text="",
    )
    assert result.returncode == 0
    assert not (sample_tree / "drop.txt").exists()
    assert not (sample_tree / "build").exists()
    assert (sample_tree / "keep.md").exists()
    assert (sample_tree / "src" / "main.py").exists()


# ---------- an exact-kept file keeps only itself ----------


def test_cli_dry_run_lists_the_sibling_of_a_named_file(run_cli, named_file_tree):
    """--keep "src/main.py" used to protect all of src/. junk.txt beside
    it is a removal target now."""
    result = run_cli(
        ["delete", str(named_file_tree), "--keep", "src/main.py"], input_text=""
    )
    assert result.returncode == 0
    assert str(named_file_tree / "src" / "junk.txt") in result.stdout
    assert str(named_file_tree / "src" / "main.py") not in result.stdout


def test_cli_tree_and_dry_run_agree_about_a_named_file_sibling(
    run_cli, named_file_tree
):
    """The two read-only walks must reach the same verdict -- disagreeing
    about the same entry is this tool's worst failure mode."""
    tree = run_cli(
        ["tree", str(named_file_tree), "--keep", "src/main.py"], input_text=""
    )
    dry_run = run_cli(
        ["delete", str(named_file_tree), "--keep", "src/main.py"], input_text=""
    )
    assert tree.returncode == 0
    assert dry_run.returncode == 0

    # junk.txt is doomed on both surfaces, main.py and its src/ shell on neither
    assert "junk.txt  [REMOVE]" in tree.stdout
    assert str(named_file_tree / "src" / "junk.txt") in dry_run.stdout
    assert "main.py  [REMOVE]" not in tree.stdout
    assert "src/  [REMOVE]" not in tree.stdout
    assert str(named_file_tree / "src" / "main.py") not in dry_run.stdout
    assert f"{named_file_tree / 'src'}\n" not in dry_run.stdout


# ---------- path-scoped glob patterns ----------


def test_cli_delete_path_scoped_pattern_keeps_only_within_scoped_directory(
    run_cli, sample_tree
):
    (sample_tree / "build" / "main.py").write_text("print('other')\n")
    result = run_cli(
        ["delete", str(sample_tree), "--keep", "src/*.py", "--commit"],
        input_text="",
    )
    assert result.returncode == 0
    assert (sample_tree / "src" / "main.py").exists()
    assert not (sample_tree / "build").exists()


def test_cli_delete_path_scoped_pattern_does_not_cross_subdirectory(
    run_cli, sample_tree
):
    (sample_tree / "src" / "pkg").mkdir()
    (sample_tree / "src" / "pkg" / "deep.py").write_text("x = 1\n")
    result = run_cli(
        ["delete", str(sample_tree), "--keep", "src/*.py", "--commit"],
        input_text="",
    )
    assert result.returncode == 0
    assert (sample_tree / "src" / "main.py").exists()
    assert not (sample_tree / "src" / "pkg" / "deep.py").exists()


def test_cli_delete_path_scoped_pattern_with_double_star_crosses_subdirectory(
    run_cli, sample_tree
):
    (sample_tree / "src" / "pkg").mkdir()
    (sample_tree / "src" / "pkg" / "deep.py").write_text("x = 1\n")
    result = run_cli(
        ["delete", str(sample_tree), "--keep", "src/**/*.py", "--commit"],
        input_text="",
    )
    assert result.returncode == 0
    assert (sample_tree / "src" / "main.py").exists()
    assert (sample_tree / "src" / "pkg" / "deep.py").exists()


def test_cli_delete_bare_pattern_still_matches_everywhere_regression_guard(
    run_cli, sample_tree
):
    """Contrast test: adding path-scoped patterns must not change bare
    (no "/") pattern behavior -- still filename match, tree-wide."""
    (sample_tree / "build" / "main.py").write_text("print('other')\n")
    result = run_cli(
        ["delete", str(sample_tree), "--keep", "*.py", "--commit"],
        input_text="",
    )
    assert result.returncode == 0
    assert (sample_tree / "src" / "main.py").exists()
    assert (sample_tree / "build" / "main.py").exists()


def test_cli_tree_path_scoped_pattern_protects_parent_directory(run_cli, sample_tree):
    result = run_cli(
        ["tree", str(sample_tree), "--keep", "notes/*.md"],
        input_text="",
    )
    assert result.returncode == 0
    assert "design.md  [REMOVE]" not in result.stdout
    assert "notes/  [REMOVE]" not in result.stdout
    # notes/ survives, so the tree descends into it and shows the sibling
    # that doesn't -- this is the "kept directory, doomed child" case
    assert "scratch.txt  [REMOVE]" in result.stdout


# ---------- collapse, summary, and the narrowing-pattern warning ----------


def test_cli_tree_collapses_a_doomed_directory(run_cli, sample_tree):
    result = run_cli(["tree", str(sample_tree), "--keep", "keep.md"], input_text="")
    assert result.returncode == 0
    assert "build/  [REMOVE]" in result.stdout
    assert "artifact.bin" not in result.stdout


def test_cli_tree_summary_counts_collapsed_directories(run_cli, sample_tree):
    result = run_cli(["tree", str(sample_tree), "--keep", "keep.md"], input_text="")
    assert (
        "1 kept, 6 to remove (4 directories collapsed -- contents not listed)."
        in result.stdout
    )


def test_cli_tree_summary_omits_the_clause_when_nothing_collapsed(run_cli, tmp_path):
    (tmp_path / "keep.md").write_text("keep\n")
    (tmp_path / "drop.txt").write_text("drop\n")
    result = run_cli(["tree", str(tmp_path), "--keep", "keep.md"], input_text="")
    assert "1 kept, 1 to remove." in result.stdout


def test_cli_tree_warns_when_a_path_pattern_narrows(run_cli, sample_tree):
    """sample_tree has keep.md at the root and notes/design.md below it, so
    '/*.md' silently protects one of the two."""
    result = run_cli(["tree", str(sample_tree), "--keep", "/*.md"], input_text="")
    assert result.returncode == 0
    assert "'/*.md' matches 1 path, but '**/*.md' would match 2." in result.stderr
    assert "never crosses" in result.stderr


def test_cli_dry_run_warns_when_a_path_pattern_narrows(run_cli, sample_tree):
    result = run_cli(["delete", str(sample_tree), "--keep", "/*.md"], input_text="")
    assert result.returncode == 0
    assert "'/*.md' matches 1 path" in result.stderr


def test_cli_does_not_warn_when_the_pattern_already_reaches_deep(run_cli, sample_tree):
    result = run_cli(["tree", str(sample_tree), "--keep", "**/*.md"], input_text="")
    assert result.returncode == 0
    assert result.stderr == ""


def test_cli_does_not_warn_when_scoping_costs_nothing(run_cli, sample_tree):
    """'notes/*.md' and 'notes/**/*.md' protect the same file here, so the
    pattern isn't costing anything and the warning stays quiet."""
    result = run_cli(["tree", str(sample_tree), "--keep", "notes/*.md"], input_text="")
    assert result.returncode == 0
    assert result.stderr == ""


def test_cli_a_pattern_named_in_both_sources_warns_once(run_cli, sample_tree):
    """The merged keep list is deduplicated, so a pattern named in both
    --keep and .weed-out-ignore is one entry and warns once, not twice."""
    (sample_tree / ".weed-out-ignore").write_text("/*.md\n")
    result = run_cli(["tree", str(sample_tree), "--keep", "/*.md"], input_text="")
    assert result.returncode == 0
    assert result.stderr.count("'/*.md' matches") == 1


def test_cli_warnings_follow_the_order_the_patterns_were_given(run_cli, sample_tree):
    """Deduplication preserves order, so narrowing patterns warn in the order
    given. Three patterns in both orders, because a keep list shuffled by
    hash order can still land on the given order by chance."""
    for keep in ("/*.md,/*.txt,/*.py", "/*.py,/*.txt,/*.md"):
        result = run_cli(["tree", str(sample_tree), "--keep", keep], input_text="")
        assert result.returncode == 0
        warned = [line.split("'")[1] for line in result.stderr.splitlines()]
        assert warned == keep.split(",")


# ---------- symlinks are never descended into ----------
#
# See DESIGN.md, "Symlinks are never descended into". `outside` is built
# as a sibling of `root`, not under it, to stand in for "outside PATH".


def _tree_with_outside_link(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("outside content\n")
    (root / "link_to_outside").symlink_to(outside)
    (root / "junk.txt").write_text("junk\n")
    return root


def test_cli_tree_marks_symlinks_with_their_target(run_cli, tmp_path):
    root = _tree_with_outside_link(tmp_path)
    result = run_cli(["tree", str(root), "--keep", "junk.txt"], input_text="")
    assert result.returncode == 0
    assert "link_to_outside -> " in result.stdout


def test_cli_tree_kept_symlink_never_lists_outside_contents(run_cli, tmp_path):
    """Flagship regression: a symlink kept via a pattern matching its own
    name used to be walked straight through, evaluating files that were
    never under PATH at all."""
    root = _tree_with_outside_link(tmp_path)
    result = run_cli(["tree", str(root), "--keep", "link_to_*"], input_text="")
    assert result.returncode == 0
    assert "secret.txt" not in result.stdout


def test_cli_tree_doomed_symlink_is_a_leaf_not_a_collapsed_directory(run_cli, tmp_path):
    root = _tree_with_outside_link(tmp_path)
    result = run_cli(["tree", str(root), "--keep", "junk.txt"], input_text="")
    assert result.returncode == 0
    assert "link_to_outside -> " in result.stdout
    assert "collapsed" not in result.stdout


def test_cli_tree_marks_a_dangling_symlink(run_cli, tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "broken").symlink_to(root / "does_not_exist")
    (root / "keep.txt").write_text("keep\n")
    result = run_cli(["tree", str(root), "--keep", "keep.txt"], input_text="")
    assert result.returncode == 0
    assert "broken -> " in result.stdout


def test_cli_tree_does_not_recurse_through_a_self_referential_symlink(
    run_cli, tmp_path
):
    root = tmp_path / "root"
    dotdir = root / ".dotdir"
    dotdir.mkdir(parents=True)
    (dotdir / "real.txt").write_text("x\n")
    (dotdir / "loop").symlink_to(dotdir)
    result = run_cli(["tree", str(root), "--keep", "*.md", "--dot-dirs"], input_text="")
    assert result.returncode == 0
    assert result.stdout.count("loop") == 1  # printed once, never recursed into


def test_cli_delete_commit_removes_a_doomed_symlink_and_leaves_target_untouched(
    run_cli, tmp_path
):
    """End-to-end regression for the silent-no-op bug: shutil.rmtree()
    refuses to run on a path that is itself a symlink, and
    ignore_errors=True used to swallow that error without a trace."""
    root = _tree_with_outside_link(tmp_path)
    outside = tmp_path / "outside"
    result = run_cli(
        ["delete", str(root), "--keep", "junk.txt", "--commit"], input_text=""
    )
    assert result.returncode == 0
    assert not (root / "link_to_outside").is_symlink()
    assert outside.is_dir()
    assert (outside / "secret.txt").read_text() == "outside content\n"


def test_cli_commit_does_not_warn_about_narrowing_patterns(run_cli, sample_tree):
    """By --commit the advice is too late to act on, and a stderr line after
    a destructive run reads as an error report on the run itself."""
    result = run_cli(
        ["delete", str(sample_tree), "--keep", "/*.md", "--commit"], input_text=""
    )
    assert result.returncode == 0
    assert result.stderr == ""


# ---------- .weed-out-ignore ----------


def test_cli_ignore_file_alone_drives_tree_with_no_keep_flag(run_cli, sample_tree):
    (sample_tree / ".weed-out-ignore").write_text("keep.md\n")
    result = run_cli(["tree", str(sample_tree)], input_text="")
    assert result.returncode == 0
    assert "drop.txt  [REMOVE]" in result.stdout
    assert "keep.md  [REMOVE]" not in result.stdout


def test_cli_keep_flag_and_ignore_file_entries_both_survive(run_cli, sample_tree):
    (sample_tree / ".weed-out-ignore").write_text("src/\n")
    result = run_cli(["tree", str(sample_tree), "--keep", "keep.md"], input_text="")
    assert result.returncode == 0
    assert "keep.md  [REMOVE]" not in result.stdout
    assert "main.py  [REMOVE]" not in result.stdout
    assert "drop.txt  [REMOVE]" in result.stdout


def test_cli_same_keep_entry_in_ignore_file_and_keep_flag(run_cli, sample_tree):
    (sample_tree / ".weed-out-ignore").write_text("keep.md\n")
    result = run_cli(["tree", str(sample_tree), "--keep", "keep.md"], input_text="")
    assert result.returncode == 0
    assert "keep.md" in result.stdout
    assert "keep.md  [REMOVE]" not in result.stdout
    assert "drop.txt  [REMOVE]" in result.stdout


def test_cli_ignore_file_comments_and_blank_lines_are_skipped(run_cli, sample_tree):
    (sample_tree / ".weed-out-ignore").write_text(
        "# keep the readme-ish file\nkeep.md\n\n# trailing comment\n"
    )
    result = run_cli(["tree", str(sample_tree)], input_text="")
    assert result.returncode == 0
    assert "keep.md  [REMOVE]" not in result.stdout
    assert "drop.txt  [REMOVE]" in result.stdout


# ---------- identity resolution never dereferences ----------


def test_cli_tree_keeps_a_symlink_named_by_its_exact_path(run_cli, linked_tree):
    """End to end: the named links are untagged, and the real directory
    nobody named is tagged."""
    result = run_cli(
        ["tree", str(linked_tree), "--keep", "to_dir,to_file"], input_text=""
    )
    assert result.returncode == 0
    link_lines = [
        line
        for line in result.stdout.splitlines()
        if "to_dir -> " in line or "to_file -> " in line
    ]
    assert len(link_lines) == 2
    assert not any("[REMOVE]" in line for line in link_lines)
    assert "archive/  [REMOVE]" in result.stdout


def test_cli_commit_keeps_a_named_symlink_and_its_target_outside_path(
    run_cli, linked_tree
):
    """The disposal surface, not just the preview: the link survives as a
    link, and nothing outside PATH is touched."""
    outside = linked_tree.parent / "outside"
    result = run_cli(
        ["delete", str(linked_tree), "--keep", "to_dir", "--commit"], input_text=""
    )
    assert result.returncode == 0
    assert (linked_tree / "to_dir").is_symlink()
    assert (outside / "real" / "far.md").exists()
    assert not (linked_tree / "archive").exists()
    assert not (linked_tree / "top.txt").exists()


def test_cli_tree_and_dry_run_agree_about_a_named_symlink(run_cli, linked_tree):
    """The two read-only walks must reach the same verdict about the link
    and about the target it points at inside PATH."""
    tree = run_cli(["tree", str(linked_tree), "--keep", "inside"], input_text="")
    dry_run = run_cli(["delete", str(linked_tree), "--keep", "inside"], input_text="")
    assert tree.returncode == 0
    assert dry_run.returncode == 0

    assert "archive/  [REMOVE]" in tree.stdout
    assert str(linked_tree / "archive") in dry_run.stdout
    assert str(linked_tree / "inside") not in dry_run.stdout
