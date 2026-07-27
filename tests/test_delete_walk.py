"""
Unit tests for weed_out.cli's delete/empty-dir passes, called directly
against tmp_path (no subprocess). See DESIGN.md's "The Keep/Delete
Pipeline" for the intent behind deepest-first ordering and the
separate empty-dir cleanup pass.
"""

from weed_out.cli import build_exact_keep, delete_rest, remove_empty_dirs

# ---------- dry run ----------


def test_dry_run_does_not_touch_disk(sample_tree, capsys):
    exact_keep, kept_roots = build_exact_keep(sample_tree, ["keep.md"])
    delete_rest(
        sample_tree, exact_keep, [], False, False, commit=False, kept_roots=kept_roots
    )
    assert (sample_tree / "drop.txt").exists()
    assert (sample_tree / "build" / "artifact.bin").exists()
    out = capsys.readouterr().out
    assert "would delete:" in out


def test_dry_run_lists_parent_directory_before_its_contents(sample_tree, capsys):
    """The deletion walk itself is deepest-first (files before their
    parent directories, see DESIGN.md), but the printed dry-run listing
    is sorted separately for readability: a directory's line comes
    before its own contents, top-down, not bottom-up."""
    exact_keep, kept_roots = build_exact_keep(sample_tree, [])
    delete_rest(
        sample_tree, exact_keep, [], False, False, commit=False, kept_roots=kept_roots
    )
    lines = capsys.readouterr().out.splitlines()
    artifact_line = next(i for i, line in enumerate(lines) if "artifact.bin" in line)
    build_line = next(
        i
        for i, line in enumerate(lines)
        if line.strip().endswith(str(sample_tree / "build"))
    )
    assert build_line < artifact_line


# ---------- --commit ----------


def test_commit_deletes_unkept_entries(sample_tree):
    exact_keep, kept_roots = build_exact_keep(sample_tree, ["keep.md"])
    delete_rest(
        sample_tree, exact_keep, [], False, False, commit=True, kept_roots=kept_roots
    )
    assert not (sample_tree / "drop.txt").exists()
    assert not (sample_tree / "build").exists()


def test_commit_preserves_exact_kept_file(sample_tree):
    exact_keep, kept_roots = build_exact_keep(sample_tree, ["keep.md"])
    delete_rest(
        sample_tree, exact_keep, [], False, False, commit=True, kept_roots=kept_roots
    )
    assert (sample_tree / "keep.md").exists()


def test_commit_preserves_everything_under_a_kept_directory(sample_tree):
    """Regression test for the kept-directory-contents bug: --keep "src/"
    must preserve src/main.py, not just the empty src/ shell."""
    exact_keep, kept_roots = build_exact_keep(sample_tree, ["src/"])
    delete_rest(
        sample_tree, exact_keep, [], False, False, commit=True, kept_roots=kept_roots
    )
    assert (sample_tree / "src").exists()
    assert (sample_tree / "src" / "main.py").exists()


def test_commit_preserves_glob_only_kept_file_and_its_parent(sample_tree):
    exact_keep, kept_roots = build_exact_keep(sample_tree, ["*.md"])
    delete_rest(
        sample_tree,
        exact_keep,
        ["*.md"],
        False,
        False,
        commit=True,
        kept_roots=kept_roots,
    )
    assert (sample_tree / "notes").exists()
    assert (sample_tree / "notes" / "design.md").exists()
    assert not (sample_tree / "notes" / "scratch.txt").exists()


# ---------- remove_empty_dirs ----------


def test_remove_empty_dirs_removes_already_empty_directory(sample_tree):
    exact_keep, _ = build_exact_keep(sample_tree, [])
    remove_empty_dirs(sample_tree, exact_keep)
    assert not (sample_tree / "empty_dir").exists()


def test_remove_empty_dirs_skips_exact_keep(sample_tree):
    exact_keep, _ = build_exact_keep(sample_tree, ["empty_dir/"])
    remove_empty_dirs(sample_tree, exact_keep)
    assert (sample_tree / "empty_dir").exists()


def test_remove_empty_dirs_collapses_nested_chain_bottom_up(tmp_path):
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)
    exact_keep, _ = build_exact_keep(tmp_path, [])
    remove_empty_dirs(tmp_path, exact_keep)
    assert not (tmp_path / "a").exists()
