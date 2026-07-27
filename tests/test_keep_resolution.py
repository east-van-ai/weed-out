"""
Unit tests for weed_out.cli's keep-list resolution helpers.

These call the functions directly (no subprocess), using the sample_tree
fixture from conftest.py. See DESIGN.md's "The Keep/Delete Pipeline" for
the intent behind each of these passes.
"""

from weed_out.cli import (
    build_exact_keep,
    build_protected_dirs,
    is_directly_kept,
    is_under_kept_dir,
    path_pattern_match,
    read_ignore_file,
    should_keep,
)

# ---------- read_ignore_file ----------


def test_read_ignore_file_missing_file_returns_empty_list(sample_tree):
    assert read_ignore_file(sample_tree) == []


def test_read_ignore_file_returns_exact_paths_and_patterns(sample_tree):
    (sample_tree / ".weed-out-ignore").write_text("src/\n*.md\n")
    assert read_ignore_file(sample_tree) == ["src/", "*.md"]


def test_read_ignore_file_skips_blank_lines(sample_tree):
    (sample_tree / ".weed-out-ignore").write_text("keep.md\n\n\nsrc/\n")
    assert read_ignore_file(sample_tree) == ["keep.md", "src/"]


def test_read_ignore_file_skips_comment_lines(sample_tree):
    (sample_tree / ".weed-out-ignore").write_text(
        "# this is a comment\nkeep.md\n# another one\n"
    )
    assert read_ignore_file(sample_tree) == ["keep.md"]


def test_read_ignore_file_strips_surrounding_whitespace(sample_tree):
    (sample_tree / ".weed-out-ignore").write_text("  keep.md  \n\tsrc/\t\n")
    assert read_ignore_file(sample_tree) == ["keep.md", "src/"]


# ---------- build_exact_keep ----------


def test_exact_keep_includes_named_file_and_its_parents(sample_tree):
    exact_keep, kept_roots = build_exact_keep(sample_tree, ["keep.md"])
    assert (sample_tree / "keep.md").resolve() in exact_keep
    assert sample_tree.resolve() in exact_keep
    assert (sample_tree / "keep.md").resolve() in kept_roots


def test_glob_entries_are_not_added_to_exact_keep(sample_tree):
    exact_keep, kept_roots = build_exact_keep(sample_tree, ["*.md"])
    assert exact_keep == set()
    assert kept_roots == set()


# ---------- is_directly_kept ----------


def test_pattern_match_by_filename(sample_tree):
    design_md = sample_tree / "notes" / "design.md"
    assert is_directly_kept(design_md, sample_tree, set(), ["*.md"], False, False)


def test_dotfile_not_kept_without_flag(sample_tree):
    dotfile = sample_tree / ".env"
    assert not is_directly_kept(dotfile, sample_tree, set(), [], False, False)


def test_dotfile_kept_with_dot_files_flag(sample_tree):
    dotfile = sample_tree / ".env"
    assert is_directly_kept(dotfile, sample_tree, set(), [], True, False)


# ---------- is_directly_kept: path-scoped glob patterns ----------


def test_path_scoped_pattern_matches_within_its_directory(sample_tree):
    main_py = sample_tree / "src" / "main.py"
    assert is_directly_kept(main_py, sample_tree, set(), ["src/*.py"], False, False)


def test_path_scoped_pattern_does_not_match_same_name_elsewhere(sample_tree):
    """The motivating case: src/*.py must not also protect a same-named
    file living somewhere else under root, e.g. build/main.py."""
    build_main = sample_tree / "build" / "main.py"
    build_main.write_text("print('other')\n")
    assert not is_directly_kept(
        build_main, sample_tree, set(), ["src/*.py"], False, False
    )


def test_path_scoped_pattern_star_does_not_cross_subdirectory(sample_tree):
    (sample_tree / "src" / "pkg").mkdir()
    deep_py = sample_tree / "src" / "pkg" / "deep.py"
    deep_py.write_text("x = 1\n")
    assert not is_directly_kept(deep_py, sample_tree, set(), ["src/*.py"], False, False)


def test_path_scoped_pattern_double_star_crosses_subdirectory(sample_tree):
    (sample_tree / "src" / "pkg").mkdir()
    deep_py = sample_tree / "src" / "pkg" / "deep.py"
    deep_py.write_text("x = 1\n")
    main_py = sample_tree / "src" / "main.py"
    assert is_directly_kept(deep_py, sample_tree, set(), ["src/**/*.py"], False, False)
    assert is_directly_kept(main_py, sample_tree, set(), ["src/**/*.py"], False, False)


def test_leading_slash_on_pattern_is_stripped(sample_tree):
    main_py = sample_tree / "src" / "main.py"
    assert is_directly_kept(main_py, sample_tree, set(), ["/src/*.py"], False, False)


def test_trailing_slash_on_pattern_is_stripped(sample_tree):
    (sample_tree / "src" / "pkg").mkdir()
    deep_py = sample_tree / "src" / "pkg" / "deep.py"
    deep_py.write_text("x = 1\n")
    assert is_directly_kept(deep_py, sample_tree, set(), ["src/**/"], False, False)


def test_bare_pattern_unaffected_by_path_scoped_change(sample_tree):
    src_main = sample_tree / "src" / "main.py"
    build_main = sample_tree / "build" / "main.py"
    build_main.write_text("print('other')\n")
    assert is_directly_kept(src_main, sample_tree, set(), ["*.py"], False, False)
    assert is_directly_kept(build_main, sample_tree, set(), ["*.py"], False, False)


# ---------- path_pattern_match / _segments_match (the matcher itself) ----------


def test_path_pattern_match_anchors_star_to_one_segment():
    assert path_pattern_match("src/main.py", "src/*.py")
    assert not path_pattern_match("src/pkg/deep.py", "src/*.py")


def test_path_pattern_match_double_star_matches_zero_segments():
    assert path_pattern_match("src/main.py", "src/**/main.py")


def test_path_pattern_match_double_star_matches_many_segments():
    assert path_pattern_match("src/a/b/c.py", "src/**/*.py")


def test_path_pattern_match_ignores_leading_and_trailing_slash():
    assert path_pattern_match("src/main.py", "/src/*.py")
    assert path_pattern_match("src/main.py", "src/*.py/")


def test_path_pattern_match_false_for_wrong_location():
    assert not path_pattern_match("tests/main.py", "src/*.py")


# ---------- build_protected_dirs / the protected-directory bug ----------


def test_glob_only_kept_file_protects_its_parent_directory(sample_tree):
    """DESIGN.md's protected-directory bug: notes/design.md is kept only
    via *.md, but notes/ isn't named anywhere in --keep. It must still
    survive."""
    exact_keep, _kept_roots = build_exact_keep(sample_tree, ["*.md"])
    patterns = ["*.md"]
    protected = build_protected_dirs(sample_tree, exact_keep, patterns, False, False)
    assert (sample_tree / "notes").resolve() in protected
    assert sample_tree.resolve() in protected


def test_directory_with_no_kept_descendant_is_not_protected(sample_tree):
    exact_keep, _kept_roots = build_exact_keep(sample_tree, ["*.md"])
    patterns = ["*.md"]
    protected = build_protected_dirs(sample_tree, exact_keep, patterns, False, False)
    assert (sample_tree / "build").resolve() not in protected


# ---------- is_under_kept_dir / the kept-directory-contents bug ----------


def test_file_under_exact_kept_directory_is_under_kept_dir(sample_tree):
    """A directory named directly in --keep must protect everything
    inside it, not just the directory shell itself (see DESIGN.md)."""
    _exact_keep, kept_roots = build_exact_keep(sample_tree, ["src/"])
    main_py = (sample_tree / "src" / "main.py").resolve()
    assert is_under_kept_dir(main_py, kept_roots)


def test_nested_file_under_exact_kept_directory_is_protected_at_any_depth(sample_tree):
    (sample_tree / "src" / "pkg").mkdir()
    (sample_tree / "src" / "pkg" / "deep.py").write_text("x = 1\n")
    _exact_keep, kept_roots = build_exact_keep(sample_tree, ["src/"])
    deep_py = (sample_tree / "src" / "pkg" / "deep.py").resolve()
    assert is_under_kept_dir(deep_py, kept_roots)


def test_file_outside_kept_directory_is_not_under_kept_dir(sample_tree):
    _exact_keep, kept_roots = build_exact_keep(sample_tree, ["src/"])
    drop_txt = (sample_tree / "drop.txt").resolve()
    assert not is_under_kept_dir(drop_txt, kept_roots)


# ---------- should_keep (integration of all three signals) ----------


def test_should_keep_true_for_file_under_exact_kept_directory(sample_tree):
    exact_keep, kept_roots = build_exact_keep(sample_tree, ["src/"])
    protected = build_protected_dirs(sample_tree, exact_keep, [], False, False)
    main_py = sample_tree / "src" / "main.py"
    assert should_keep(
        main_py, sample_tree, exact_keep, [], False, False, protected, kept_roots
    )


def test_should_keep_false_for_unrelated_file(sample_tree):
    exact_keep, kept_roots = build_exact_keep(sample_tree, ["src/"])
    protected = build_protected_dirs(sample_tree, exact_keep, [], False, False)
    drop_txt = sample_tree / "drop.txt"
    assert not should_keep(
        drop_txt, sample_tree, exact_keep, [], False, False, protected, kept_roots
    )


def test_should_keep_true_for_protected_dir_sibling_via_glob(sample_tree):
    exact_keep, kept_roots = build_exact_keep(sample_tree, ["*.md"])
    patterns = ["*.md"]
    protected = build_protected_dirs(sample_tree, exact_keep, patterns, False, False)
    notes_dir = sample_tree / "notes"
    assert should_keep(
        notes_dir,
        sample_tree,
        exact_keep,
        patterns,
        False,
        False,
        protected,
        kept_roots,
    )


def test_should_keep_false_for_sibling_not_itself_kept(sample_tree):
    """notes/ survives because design.md is kept via glob, but
    notes/scratch.txt itself matches nothing and isn't under an
    exact-kept directory, so it should not survive."""
    exact_keep, kept_roots = build_exact_keep(sample_tree, ["*.md"])
    patterns = ["*.md"]
    protected = build_protected_dirs(sample_tree, exact_keep, patterns, False, False)
    scratch = sample_tree / "notes" / "scratch.txt"
    assert not should_keep(
        scratch,
        sample_tree,
        exact_keep,
        patterns,
        False,
        False,
        protected,
        kept_roots,
    )


def test_should_keep_true_for_path_scoped_pattern_parent_directory(sample_tree):
    """src/*.py protects src/main.py directly, and must also drag src/
    (and root) into the protected set, even though "src" itself matches
    nothing in the pattern."""
    patterns = ["src/*.py"]
    exact_keep, _kept_roots = build_exact_keep(sample_tree, patterns)
    protected = build_protected_dirs(sample_tree, exact_keep, patterns, False, False)
    assert (sample_tree / "src").resolve() in protected
    assert sample_tree.resolve() in protected
