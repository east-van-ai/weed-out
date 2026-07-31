"""
Unit tests for weed_out.cli's delete pass, called directly against
tmp_path (no subprocess). See DESIGN.md's "The Keep/Delete Pipeline"
for the intent behind collapsing doomed directories and why there is
no empty-directory cleanup pass.
"""

from weed_out.delete import collect_targets, delete_rest
from weed_out.keep import build_exact_keep, resolve_walk_sets

# ---------- dry run ----------


def test_dry_run_does_not_touch_disk(sample_tree, capsys):
    exact_keep, kept_roots = build_exact_keep(sample_tree, ["keep.md"])
    delete_rest(
        sample_tree, exact_keep, [], False, False, mode="dry-run", kept_roots=kept_roots
    )
    assert (sample_tree / "drop.txt").exists()
    assert (sample_tree / "build" / "artifact.bin").exists()
    out = capsys.readouterr().out
    assert "would delete:" not in out
    assert str(sample_tree / "drop.txt") in out
    assert "items would be removed" in out


def test_dry_run_singular_count_wording(tmp_path, capsys):
    (tmp_path / "only.txt").write_text("x\n")
    exact_keep, kept_roots = build_exact_keep(tmp_path, [])
    delete_rest(
        tmp_path, exact_keep, [], False, False, mode="dry-run", kept_roots=kept_roots
    )
    assert "1 item would be removed." in capsys.readouterr().out


def test_dry_run_lists_a_doomed_directory_without_its_contents(sample_tree, capsys):
    """A directory that isn't kept is reported as one line, not as itself
    plus every file under it -- the same collapse the removal performs
    (see DESIGN.md, "Collapsing doomed directories")."""
    exact_keep, kept_roots = build_exact_keep(sample_tree, [])
    delete_rest(
        sample_tree, exact_keep, [], False, False, mode="dry-run", kept_roots=kept_roots
    )
    lines = capsys.readouterr().out.splitlines()
    assert str(sample_tree / "build") in lines
    assert not any("artifact.bin" in line for line in lines)


def test_dry_run_count_line_flags_directories(sample_tree, capsys):
    """The count is of removal targets, so it has to say when a target
    stands for a whole directory rather than a single file."""
    exact_keep, kept_roots = build_exact_keep(sample_tree, [])
    delete_rest(
        sample_tree, exact_keep, [], False, False, mode="dry-run", kept_roots=kept_roots
    )
    out = capsys.readouterr().out
    assert "directories and everything inside them." in out


def test_dry_run_count_line_stays_plain_without_directories(tmp_path, capsys):
    """...and says nothing extra when every target really is one file."""
    (tmp_path / "a.txt").write_text("a\n")
    (tmp_path / "b.txt").write_text("b\n")
    exact_keep, kept_roots = build_exact_keep(tmp_path, [])
    delete_rest(
        tmp_path, exact_keep, [], False, False, mode="dry-run", kept_roots=kept_roots
    )
    assert "2 items would be removed." in capsys.readouterr().out


# ---------- collapsing doomed directories ----------


def _target_lines(capsys, root):
    """The dry-run path listing, without the trailing count line."""
    return [
        line
        for line in capsys.readouterr().out.splitlines()
        if line.startswith(str(root))
    ]


def test_doomed_directory_is_one_target_not_one_per_file(tmp_path, capsys):
    """Nothing inside an unkept directory can be kept, so the walk records
    the directory itself and never enters it (DESIGN.md, "Collapsing
    doomed directories")."""
    deep = tmp_path / "venv" / "lib" / "site-packages"
    deep.mkdir(parents=True)
    (deep / "mod.py").write_text("x\n")
    (tmp_path / "venv" / "pyvenv.cfg").write_text("home =\n")
    (tmp_path / "keep.md").write_text("keep\n")

    exact_keep, kept_roots = build_exact_keep(tmp_path, ["keep.md"])
    delete_rest(
        tmp_path, exact_keep, [], False, False, mode="dry-run", kept_roots=kept_roots
    )
    assert _target_lines(capsys, tmp_path) == [str(tmp_path / "venv")]


def test_collapse_still_descends_into_a_kept_directory(tmp_path, capsys):
    """The mixed case, and the one collapse must not get wrong: a *kept*
    directory holding doomed children is still walked into."""
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    (src / "main.py").write_text("x\n")
    (src / "junk.txt").write_text("x\n")
    (src / "sub" / "junk.log").write_text("x\n")

    # kept via pattern, so src/ is protected without being *directly*
    # kept -- the state in which its own children are still evaluated
    exact_keep, kept_roots = build_exact_keep(tmp_path, ["*.py"])
    delete_rest(
        tmp_path,
        exact_keep,
        ["*.py"],
        False,
        False,
        mode="dry-run",
        kept_roots=kept_roots,
    )
    lines = _target_lines(capsys, tmp_path)
    assert str(src / "junk.txt") in lines
    assert str(src / "sub") in lines  # doomed subdirectory, collapsed in turn
    assert str(src / "sub" / "junk.log") not in lines
    assert str(src / "main.py") not in lines


def test_delete_removes_a_collapsed_directory_whole(tmp_path):
    """Collapsing changes what gets enumerated, not what survives."""
    deep = tmp_path / "build" / "nested"
    deep.mkdir(parents=True)
    (deep / "artifact.bin").write_text("x\n")
    (tmp_path / "keep.md").write_text("keep\n")

    exact_keep, kept_roots = build_exact_keep(tmp_path, ["keep.md"])
    delete_rest(
        tmp_path, exact_keep, [], False, False, mode="delete", kept_roots=kept_roots
    )
    assert not (tmp_path / "build").exists()
    assert (tmp_path / "keep.md").exists()


def test_trash_sends_a_doomed_directory_in_a_single_call(tmp_path, monkeypatch):
    """The payoff for `trash`: one recoverable folder in the OS trash, not
    one loose item per file. send2trash is stubbed so the test asserts the
    call shape without actually trashing anything."""
    lib = tmp_path / "venv" / "lib"
    lib.mkdir(parents=True)
    for i in range(3):
        (lib / f"mod{i}.py").write_text("x\n")
    (tmp_path / "keep.md").write_text("keep\n")

    trashed = []
    monkeypatch.setattr("weed_out.delete.send2trash", trashed.append)

    exact_keep, kept_roots = build_exact_keep(tmp_path, ["keep.md"])
    delete_rest(
        tmp_path, exact_keep, [], False, False, mode="trash", kept_roots=kept_roots
    )
    assert trashed == [tmp_path / "venv"]


# ---------- "delete" mode ----------


def test_delete_deletes_unkept_entries(sample_tree):
    exact_keep, kept_roots = build_exact_keep(sample_tree, ["keep.md"])
    delete_rest(
        sample_tree, exact_keep, [], False, False, mode="delete", kept_roots=kept_roots
    )
    assert not (sample_tree / "drop.txt").exists()
    assert not (sample_tree / "build").exists()


def test_delete_preserves_exact_kept_file(sample_tree):
    exact_keep, kept_roots = build_exact_keep(sample_tree, ["keep.md"])
    delete_rest(
        sample_tree, exact_keep, [], False, False, mode="delete", kept_roots=kept_roots
    )
    assert (sample_tree / "keep.md").exists()


def test_delete_preserves_everything_under_a_kept_directory(sample_tree):
    """Regression test for the kept-directory-contents bug: --keep "src/"
    must preserve src/main.py, not just the empty src/ shell."""
    exact_keep, kept_roots = build_exact_keep(sample_tree, ["src/"])
    delete_rest(
        sample_tree, exact_keep, [], False, False, mode="delete", kept_roots=kept_roots
    )
    assert (sample_tree / "src").exists()
    assert (sample_tree / "src" / "main.py").exists()


def test_delete_removes_a_sibling_of_a_named_file(named_file_tree):
    """Regression test for the ancestor over-protection bug: --keep
    "src/main.py" used to protect all of src/, because src/ reached
    kept_roots as a mere ancestor. A named file keeps only itself."""
    exact_keep, kept_roots = build_exact_keep(named_file_tree, ["src/main.py"])
    delete_rest(
        named_file_tree,
        exact_keep,
        [],
        False,
        False,
        mode="delete",
        kept_roots=kept_roots,
    )
    src = named_file_tree / "src"
    assert src.exists()
    assert (src / "main.py").exists()
    assert not (src / "junk.txt").exists()


def test_delete_preserves_glob_only_kept_file_and_its_parent(sample_tree):
    exact_keep, kept_roots = build_exact_keep(sample_tree, ["*.md"])
    delete_rest(
        sample_tree,
        exact_keep,
        ["*.md"],
        False,
        False,
        mode="delete",
        kept_roots=kept_roots,
    )
    assert (sample_tree / "notes").exists()
    assert (sample_tree / "notes" / "design.md").exists()
    assert not (sample_tree / "notes" / "scratch.txt").exists()


def test_delete_preserves_everything_under_a_dot_dir(tmp_path):
    """Regression test for the shell-only bug (DESIGN.md): --dot-dirs
    used to keep the dot-directory itself while deleting everything
    inside it. A file and a subdirectory nested inside a dot-dir must
    both survive a "delete" run."""
    dotdir = tmp_path / ".config"
    sub = dotdir / "sub"
    sub.mkdir(parents=True)
    (dotdir / "settings.json").write_text("{}\n")
    (sub / "nested.txt").write_text("nested\n")
    (tmp_path / "drop.txt").write_text("drop\n")

    exact_keep, kept_roots = build_exact_keep(tmp_path, [])
    delete_rest(
        tmp_path, exact_keep, [], False, True, mode="delete", kept_roots=kept_roots
    )
    assert (dotdir / "settings.json").exists()
    assert (sub / "nested.txt").exists()
    assert not (tmp_path / "drop.txt").exists()


def test_delete_preserves_everything_under_a_glob_matched_directory(tmp_path):
    """Same shell-only bug, but for a directory kept purely because its
    own name matches a --keep glob pattern, not via --dot-dirs."""
    config_dir = tmp_path / "build.out"
    sub = config_dir / "sub"
    sub.mkdir(parents=True)
    (config_dir / "artifact.bin").write_text("binary\n")
    (sub / "nested.bin").write_text("nested\n")

    exact_keep, kept_roots = build_exact_keep(tmp_path, ["*.out"])
    delete_rest(
        tmp_path,
        exact_keep,
        ["*.out"],
        False,
        False,
        mode="delete",
        kept_roots=kept_roots,
    )
    assert (config_dir / "artifact.bin").exists()
    assert (sub / "nested.bin").exists()


# ---------- keeping root removes nothing ----------
#
# See DESIGN.md, "An absent keep list keeps everything". `main()` swaps an
# empty keep list for ["."], which resolves to root. These run the real
# "delete" mode rather than a dry run, because the claim being tested is
# that the removal loop has nothing to iterate over.


def _walk_inputs(root, keep_list):
    """Resolve a keep list the way `main()` does, for the walk to consume."""
    exact_keep, kept_roots = build_exact_keep(root, keep_list)
    protected_dirs, kept_roots = resolve_walk_sets(root, kept_roots, [], False, False)
    return exact_keep, protected_dirs, kept_roots


def test_keeping_root_collects_no_targets(sample_tree):
    """Nothing reaches the removal loop, which is what makes an extra
    guard in main() unnecessary."""
    exact_keep, protected_dirs, kept_roots = _walk_inputs(sample_tree, ["."])
    targets = collect_targets(
        sample_tree,
        sample_tree,
        exact_keep,
        [],
        False,
        False,
        protected_dirs,
        kept_roots,
    )
    assert targets == []


def test_keeping_root_leaves_the_whole_tree_intact(sample_tree):
    before = sorted(p.relative_to(sample_tree) for p in sample_tree.rglob("*"))
    exact_keep, _, kept_roots = _walk_inputs(sample_tree, ["."])
    delete_rest(
        sample_tree, exact_keep, [], False, False, mode="delete", kept_roots=kept_roots
    )
    after = sorted(p.relative_to(sample_tree) for p in sample_tree.rglob("*"))
    assert after == before


def test_keeping_root_spares_dot_entries_without_the_dot_flags(sample_tree):
    """--dot-files/--dot-dirs are off here, so the dotfile survives on the
    kept-root route alone."""
    (sample_tree / ".cache").mkdir()
    (sample_tree / ".cache" / "blob").write_text("x\n")
    exact_keep, _, kept_roots = _walk_inputs(sample_tree, ["."])
    delete_rest(
        sample_tree, exact_keep, [], False, False, mode="delete", kept_roots=kept_roots
    )
    assert (sample_tree / ".env").exists()
    assert (sample_tree / ".cache" / "blob").exists()


def test_keeping_root_spares_symlinks_and_their_targets(linked_tree):
    exact_keep, _, kept_roots = _walk_inputs(linked_tree, ["."])
    delete_rest(
        linked_tree, exact_keep, [], False, False, mode="delete", kept_roots=kept_roots
    )
    assert (linked_tree / "to_dir").is_symlink()
    assert (linked_tree / "to_file").is_symlink()
    assert (linked_tree / "inside").is_symlink()
    assert (linked_tree.parent / "outside" / "real" / "far.md").exists()
    assert (linked_tree / "archive" / "2024" / "stuff.md").exists()


# ---------- "trash" mode ----------


def test_trash_removes_unkept_entries_from_source(sample_tree):
    exact_keep, kept_roots = build_exact_keep(sample_tree, ["keep.md"])
    delete_rest(
        sample_tree, exact_keep, [], False, False, mode="trash", kept_roots=kept_roots
    )
    assert not (sample_tree / "drop.txt").exists()
    assert not (sample_tree / "build").exists()


def test_trash_preserves_exact_kept_file(sample_tree):
    exact_keep, kept_roots = build_exact_keep(sample_tree, ["keep.md"])
    delete_rest(
        sample_tree, exact_keep, [], False, False, mode="trash", kept_roots=kept_roots
    )
    assert (sample_tree / "keep.md").exists()


def test_trash_preserves_everything_under_a_kept_directory(sample_tree):
    exact_keep, kept_roots = build_exact_keep(sample_tree, ["src/"])
    delete_rest(
        sample_tree, exact_keep, [], False, False, mode="trash", kept_roots=kept_roots
    )
    assert (sample_tree / "src").exists()
    assert (sample_tree / "src" / "main.py").exists()


# ---------- already-empty directories ----------
#
# There is no empty-directory cleanup pass (DESIGN.md, "Why there is no
# empty-directory cleanup pass"). These pin down both halves of what its
# removal means: an already-empty directory that is kept survives, and an
# already-empty directory that isn't is still removed -- by the main walk,
# which records it as an ordinary target.


def test_empty_directory_kept_by_dot_dirs_survives(tmp_path):
    """An already-empty dot-directory survives --dot-dirs. The cleanup
    pass used to remove it: it skipped only exact_keep, and --dot-dirs
    never puts anything there."""
    (tmp_path / ".config").mkdir()
    (tmp_path / "drop.txt").write_text("drop\n")

    exact_keep, kept_roots = build_exact_keep(tmp_path, [])
    delete_rest(
        tmp_path, exact_keep, [], False, True, mode="delete", kept_roots=kept_roots
    )
    assert (tmp_path / ".config").is_dir()
    assert not (tmp_path / "drop.txt").exists()


def test_empty_directory_under_an_exact_kept_parent_survives(tmp_path):
    """The broader case: `--keep src/` protects src/scratch/ through
    is_under_kept_dir, but only `src` itself lands in exact_keep, so the
    cleanup pass removed the empty child anyway."""
    (tmp_path / "src" / "scratch").mkdir(parents=True)
    (tmp_path / "src" / "main.py").write_text("print('hi')\n")
    (tmp_path / "drop.txt").write_text("drop\n")

    exact_keep, kept_roots = build_exact_keep(tmp_path, ["src/"])
    delete_rest(
        tmp_path, exact_keep, [], False, False, mode="delete", kept_roots=kept_roots
    )
    assert (tmp_path / "src" / "scratch").is_dir()
    assert (tmp_path / "src" / "main.py").exists()
    assert not (tmp_path / "drop.txt").exists()


def test_empty_directory_kept_by_glob_survives(tmp_path):
    """Same again for a directory kept purely because its own name
    matches a --keep pattern."""
    (tmp_path / "build.out").mkdir()
    (tmp_path / "drop.txt").write_text("drop\n")

    exact_keep, kept_roots = build_exact_keep(tmp_path, ["*.out"])
    delete_rest(
        tmp_path,
        exact_keep,
        ["*.out"],
        False,
        False,
        mode="delete",
        kept_roots=kept_roots,
    )
    assert (tmp_path / "build.out").is_dir()
    assert not (tmp_path / "drop.txt").exists()


def test_empty_directory_kept_by_dot_dirs_survives_trash_mode(tmp_path):
    """The fix isn't delete-only -- `trash` took the same route."""
    (tmp_path / ".config").mkdir()
    (tmp_path / "drop.txt").write_text("drop\n")

    exact_keep, kept_roots = build_exact_keep(tmp_path, [])
    delete_rest(
        tmp_path, exact_keep, [], False, True, mode="trash", kept_roots=kept_roots
    )
    assert (tmp_path / ".config").is_dir()
    assert not (tmp_path / "drop.txt").exists()


def test_unkept_empty_directory_is_still_removed(sample_tree):
    """Regression guard: removing the cleanup pass must not leave unkept
    empty directories behind. The main walk already treats one as an
    ordinary target."""
    exact_keep, kept_roots = build_exact_keep(sample_tree, ["keep.md"])
    delete_rest(
        sample_tree, exact_keep, [], False, False, mode="delete", kept_roots=kept_roots
    )
    assert not (sample_tree / "empty_dir").exists()


def test_unkept_empty_chain_is_still_removed_whole(tmp_path):
    """Same guard for a nested chain, which the cleanup pass used to
    unwind bottom-up. The collapse removes it at the topmost doomed
    directory instead, in one target."""
    (tmp_path / "a" / "b" / "c").mkdir(parents=True)
    (tmp_path / "keep.md").write_text("keep\n")

    exact_keep, kept_roots = build_exact_keep(tmp_path, ["keep.md"])
    delete_rest(
        tmp_path, exact_keep, [], False, False, mode="delete", kept_roots=kept_roots
    )
    assert not (tmp_path / "a").exists()
    assert (tmp_path / "keep.md").exists()


# ---------- symlinks are never descended into ----------
#
# See DESIGN.md, "Symlinks are never descended into". `outside` is built
# as a sibling of `root` (not under it) to stand in for "outside PATH".


def _tree_with_outside_link(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("outside content\n")
    (outside / "README.md").write_text("outside readme\n")
    link = root / "link_to_outside"
    link.symlink_to(outside)
    (root / "junk.txt").write_text("junk\n")
    return root, outside, link


def test_kept_symlink_via_pattern_is_atomic_and_hides_outside_contents(
    tmp_path, capsys
):
    """A symlink kept by a pattern matching its own name must never expose
    what it points at. The exact-path route is covered separately, under
    "identity resolution never dereferences" below."""
    root, _outside, _link = _tree_with_outside_link(tmp_path)
    exact_keep, kept_roots = build_exact_keep(root, ["link_to_*"])
    delete_rest(
        root,
        exact_keep,
        ["link_to_*"],
        False,
        False,
        mode="dry-run",
        kept_roots=kept_roots,
    )
    out = capsys.readouterr().out
    assert "secret.txt" not in out
    assert "README.md" not in out


def test_unkept_symlink_to_dir_is_a_single_atomic_target(tmp_path, capsys):
    root, _outside, link = _tree_with_outside_link(tmp_path)
    exact_keep, kept_roots = build_exact_keep(root, [])
    delete_rest(
        root, exact_keep, [], False, False, mode="dry-run", kept_roots=kept_roots
    )
    lines = [
        line
        for line in capsys.readouterr().out.splitlines()
        if line.startswith(str(root))
    ]
    assert str(link) in lines
    assert not any("secret.txt" in line for line in lines)


def test_delete_commit_removes_a_doomed_symlink_as_the_link_node(tmp_path):
    """The flagship regression: a doomed symlink-to-directory used to
    survive `delete --commit` untouched, because shutil.rmtree() refuses
    to run on a path that is itself a symlink and ignore_errors=True
    swallowed the resulting OSError silently."""
    root, outside, link = _tree_with_outside_link(tmp_path)
    exact_keep, kept_roots = build_exact_keep(root, [])
    delete_rest(
        root, exact_keep, [], False, False, mode="delete", kept_roots=kept_roots
    )
    assert not link.is_symlink()
    assert not link.exists()
    assert outside.is_dir()
    assert (outside / "secret.txt").read_text() == "outside content\n"


def test_dry_run_count_line_does_not_count_a_symlink_as_a_directory(tmp_path, capsys):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "link_to_outside").symlink_to(outside)

    exact_keep, kept_roots = build_exact_keep(root, [])
    delete_rest(
        root, exact_keep, [], False, False, mode="dry-run", kept_roots=kept_roots
    )
    out = capsys.readouterr().out
    assert "1 item would be removed." in out


def test_delete_removes_a_dangling_symlink(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    link = root / "broken"
    link.symlink_to(root / "does_not_exist")

    exact_keep, kept_roots = build_exact_keep(root, [])
    delete_rest(
        root, exact_keep, [], False, False, mode="delete", kept_roots=kept_roots
    )
    assert not link.is_symlink()


def test_collect_targets_does_not_recurse_through_a_self_referential_symlink(
    tmp_path, capsys
):
    """A symlink inside a kept dot-directory that points back at an
    ancestor (here, itself) must not send the walk into a runaway loop --
    it's never descended into at all, regardless of where it points."""
    root = tmp_path / "root"
    dotdir = root / ".dotdir"
    dotdir.mkdir(parents=True)
    (dotdir / "real.txt").write_text("x\n")
    (dotdir / "loop").symlink_to(dotdir)

    exact_keep, kept_roots = build_exact_keep(root, [])
    delete_rest(
        root, exact_keep, [], False, True, mode="dry-run", kept_roots=kept_roots
    )
    out = capsys.readouterr().out
    assert "loop" not in out
    assert "0 items would be removed." in out


# ---------- identity resolution never dereferences ----------


def test_delete_keeps_a_symlink_named_by_its_exact_path(linked_tree):
    """The bug: `--keep "to_dir"` filed the link's *target*, so the named
    link matched nothing during the walk and was deleted. Holds for a
    link to a directory and a link to a file alike."""
    exact_keep, kept_roots = build_exact_keep(linked_tree, ["to_dir", "to_file"])
    delete_rest(
        linked_tree, exact_keep, [], False, False, mode="delete", kept_roots=kept_roots
    )
    assert (linked_tree / "to_dir").is_symlink()
    assert (linked_tree / "to_file").is_symlink()
    assert not (linked_tree / "top.txt").exists()


def test_delete_of_a_named_link_leaves_its_target_untouched(linked_tree):
    """Keeping the link says nothing about what it points at, and a target
    outside PATH is never weed-out's business either way."""
    outside = linked_tree.parent / "outside"
    exact_keep, kept_roots = build_exact_keep(linked_tree, ["to_dir"])
    delete_rest(
        linked_tree, exact_keep, [], False, False, mode="delete", kept_roots=kept_roots
    )
    assert (outside / "real" / "far.md").exists()


def test_delete_of_a_named_link_does_not_spare_its_target_inside_path(linked_tree):
    """The visible damage the old resolve() did: `inside` pointed at
    archive/2024, so archive/2024 became a kept_root and protected a whole
    subtree nobody named. The target is judged on its own now."""
    exact_keep, kept_roots = build_exact_keep(linked_tree, ["inside"])
    delete_rest(
        linked_tree, exact_keep, [], False, False, mode="delete", kept_roots=kept_roots
    )
    assert (linked_tree / "inside").is_symlink()
    assert not (linked_tree / "archive").exists()


def test_delete_through_a_symlink_keeps_only_the_link(linked_tree):
    """A keep entry reaching through a link protects the link via the
    ancestor rule and nothing beyond it, so it lands exactly where
    naming the link on its own would."""
    exact_keep, kept_roots = build_exact_keep(linked_tree, ["inside/stuff.md"])
    delete_rest(
        linked_tree, exact_keep, [], False, False, mode="delete", kept_roots=kept_roots
    )
    assert (linked_tree / "inside").is_symlink()
    assert not (linked_tree / "archive").exists()
