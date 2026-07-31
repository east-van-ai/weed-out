"""
Unit tests for weed_out.cli's keep-list resolution helpers.

These call the functions directly (no subprocess), using the sample_tree
fixture from conftest.py. See DESIGN.md's "The Keep/Delete Pipeline" for
the intent behind each of these passes.
"""

from weed_out.keep import (
    build_exact_keep,
    build_protected_dirs,
    deepen_pattern,
    is_directly_kept,
    is_glob,
    is_real_dir,
    is_under_kept_dir,
    narrowing_pattern_hints,
    path_pattern_match,
    read_ignore_file,
    resolve_walk_sets,
    should_keep,
)

# ---------- is_glob ----------


def test_is_glob_recognizes_each_wildcard():
    assert is_glob("*.md")
    assert is_glob("file?.txt")
    assert is_glob("[abc].txt")
    assert is_glob("src/**/*.py")


def test_is_glob_false_for_exact_paths():
    assert not is_glob("README.md")
    assert not is_glob("src/main.py")
    assert not is_glob(".config")


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


def test_exact_keep_collapses_dot_and_dot_dot_lexically(sample_tree):
    """Lexical normalization is not a loss of the old resolve(): `.` and
    `..` still collapse, they just collapse as text."""
    exact_keep, kept_roots = build_exact_keep(sample_tree, ["src/../keep.md", "./src"])
    assert (sample_tree / "keep.md") in exact_keep
    assert (sample_tree / "src") in kept_roots


# ---------- "." keeps everything ----------
#
# See DESIGN.md, "An absent keep list keeps everything". `main()` swaps an
# empty keep list for ["."], so these state why that swap needs no other
# machinery: "." names root, and root protects its whole subtree.


def test_dot_resolves_to_root_itself(sample_tree):
    exact_keep, kept_roots = build_exact_keep(sample_tree, ["."])
    assert exact_keep == {sample_tree}
    assert kept_roots == {sample_tree}


def test_dot_adds_no_ancestors_above_root(sample_tree):
    """The parent chain stops at root, so nothing outside PATH is named."""
    exact_keep, _ = build_exact_keep(sample_tree, ["."])
    assert not any(p in exact_keep for p in sample_tree.parents)


def test_keeping_root_keeps_every_entry_at_every_depth(sample_tree):
    """The whole point: should_keep says yes to everything under root."""
    exact_keep, kept_roots = build_exact_keep(sample_tree, ["."])
    protected_dirs, kept_roots = resolve_walk_sets(
        sample_tree, kept_roots, [], False, False
    )
    for entry in sample_tree.rglob("*"):
        assert should_keep(
            entry,
            sample_tree,
            exact_keep,
            [],
            False,
            False,
            protected_dirs,
            kept_roots,
        ), entry


def test_keeping_root_survives_on_the_kept_roots_route(sample_tree):
    """Not via protected_dirs: rglob never yields root, so nothing is
    directly kept and protected_dirs stays empty. is_under_kept_dir is
    what carries every entry."""
    _, kept_roots = build_exact_keep(sample_tree, ["."])
    protected_dirs, kept_roots = resolve_walk_sets(
        sample_tree, kept_roots, [], False, False
    )
    assert protected_dirs == set()
    assert kept_roots == {sample_tree}
    assert is_under_kept_dir(sample_tree / "notes" / "design.md", kept_roots)


# ---------- build_exact_keep: identity resolution never dereferences ----------


def test_exact_keep_names_the_symlink_not_its_target(linked_tree):
    """A --keep entry naming a symlink must file the link's own path.
    resolve() filed the target instead, a path the walk never produces,
    so the named link was removed and its target protected in its place."""
    _exact_keep, kept_roots = build_exact_keep(linked_tree, ["to_dir", "to_file"])
    assert kept_roots == {linked_tree / "to_dir", linked_tree / "to_file"}


def test_exact_keep_does_not_drag_in_a_targets_ancestor_chain(linked_tree):
    """Nothing outside PATH may enter exact_keep. The old resolve() pulled
    the target's own parent chain in behind it."""
    exact_keep, _kept_roots = build_exact_keep(linked_tree, ["to_dir", "to_file"])
    outside = linked_tree.parent / "outside"
    assert not any(p == outside or outside in p.parents for p in exact_keep)


def test_exact_keep_of_a_link_inside_path_leaves_its_target_alone(linked_tree):
    """The target being *inside* PATH is the case where dereferencing did
    visible damage: archive/2024 became a kept_root and protected a whole
    subtree nobody named."""
    exact_keep, kept_roots = build_exact_keep(linked_tree, ["inside"])
    assert kept_roots == {linked_tree / "inside"}
    assert (linked_tree / "archive" / "2024") not in exact_keep


def test_exact_keep_through_a_symlink_keeps_only_the_link(linked_tree):
    """You cannot reach through a link. The entry itself matches nothing
    the walk produces, but the ancestor rule still protects the link, so
    it behaves exactly like naming the link on its own."""
    exact_keep, kept_roots = build_exact_keep(linked_tree, ["to_dir/far.md"])
    assert (linked_tree / "to_dir") in exact_keep
    assert kept_roots == {linked_tree / "to_dir" / "far.md"}
    outside = linked_tree.parent / "outside"
    assert not any(p == outside or outside in p.parents for p in exact_keep)


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
    _exact_keep, kept_roots = build_exact_keep(sample_tree, ["*.md"])
    patterns = ["*.md"]
    protected, _directly_kept_dirs = build_protected_dirs(
        sample_tree, kept_roots, patterns, False, False
    )
    assert (sample_tree / "notes").resolve() in protected
    assert sample_tree.resolve() in protected


def test_directory_with_no_kept_descendant_is_not_protected(sample_tree):
    _exact_keep, kept_roots = build_exact_keep(sample_tree, ["*.md"])
    patterns = ["*.md"]
    protected, _directly_kept_dirs = build_protected_dirs(
        sample_tree, kept_roots, patterns, False, False
    )
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


# ---------- build_protected_dirs: directly_kept_dirs (the dot-dir/glob-dir
# shell-only bug) ----------


def test_dotdir_is_collected_as_directly_kept_dir(tmp_path):
    """DESIGN.md's shell-only bug: a directory kept only via --dot-dirs
    must land in directly_kept_dirs so its contents can be protected too,
    not just the directory entry itself."""
    dotdir = tmp_path / ".config"
    dotdir.mkdir()
    (dotdir / "settings.json").write_text("{}\n")
    _protected, directly_kept_dirs = build_protected_dirs(
        tmp_path, set(), [], False, True
    )
    assert dotdir.resolve() in directly_kept_dirs


def test_glob_matched_directory_is_collected_as_directly_kept_dir(tmp_path):
    """Same bug, but for a directory kept because its own name matches a
    --keep glob pattern rather than via --dot-dirs."""
    config_dir = tmp_path / "build.out"
    config_dir.mkdir()
    (config_dir / "artifact.bin").write_text("binary\n")
    _protected, directly_kept_dirs = build_protected_dirs(
        tmp_path, set(), ["*.out"], False, False
    )
    assert config_dir.resolve() in directly_kept_dirs


def test_regular_kept_file_is_not_collected_as_directly_kept_dir(sample_tree):
    """directly_kept_dirs only ever holds directories -- a kept file must
    never show up in it."""
    _exact_keep, kept_roots = build_exact_keep(sample_tree, ["keep.md"])
    _protected, directly_kept_dirs = build_protected_dirs(
        sample_tree, kept_roots, [], False, False
    )
    assert (sample_tree / "keep.md").resolve() not in directly_kept_dirs


def test_dotdir_contents_survive_once_merged_into_kept_roots(tmp_path):
    """The actual fix: once directly_kept_dirs is unioned into kept_roots
    (as resolve_walk_sets does for both walks), a file nested inside a
    --dot-dirs-kept directory is protected via is_under_kept_dir, not just
    the directory shell."""
    dotdir = tmp_path / ".config"
    sub = dotdir / "sub"
    sub.mkdir(parents=True)
    nested = sub / "nested.txt"
    nested.write_text("nested\n")

    _exact_keep, kept_roots = build_exact_keep(tmp_path, [])
    _protected, kept_roots = resolve_walk_sets(tmp_path, kept_roots, [], False, True)
    assert is_under_kept_dir(nested.resolve(), kept_roots)
    assert is_under_kept_dir(sub.resolve(), kept_roots)


# ---------- build_protected_dirs: a named file's ancestors are shells ----------


def test_ancestor_of_a_named_file_is_not_a_directly_kept_dir(named_file_tree):
    """A directory dragged into exact_keep by a named descendant was never
    named itself, so it must not reach directly_kept_dirs -- that set is
    what protects a whole subtree."""
    _exact_keep, kept_roots = build_exact_keep(named_file_tree, ["src/main.py"])
    _protected, directly_kept_dirs = build_protected_dirs(
        named_file_tree, kept_roots, [], False, False
    )
    assert (named_file_tree / "src").resolve() not in directly_kept_dirs


def test_ancestor_of_a_named_file_is_still_protected(named_file_tree):
    """The up direction is untouched: the ancestor still survives as a
    shell, because a kept descendant sits inside it."""
    _exact_keep, kept_roots = build_exact_keep(named_file_tree, ["src/main.py"])
    protected, _directly_kept_dirs = build_protected_dirs(
        named_file_tree, kept_roots, [], False, False
    )
    assert (named_file_tree / "src").resolve() in protected
    assert named_file_tree.resolve() in protected


def test_should_keep_named_file_survives_but_its_sibling_does_not(named_file_tree):
    """The bug at the helper level: --keep src/main.py keeps src/ and
    main.py, and removes junk.txt beside it."""
    exact_keep, kept_roots = build_exact_keep(named_file_tree, ["src/main.py"])
    protected, kept_roots = resolve_walk_sets(
        named_file_tree, kept_roots, [], False, False
    )

    def keep(p):
        return should_keep(
            p, named_file_tree, exact_keep, [], False, False, protected, kept_roots
        )

    src = named_file_tree / "src"
    assert keep(src)
    assert keep(src / "main.py")
    assert not keep(src / "junk.txt")


# ---------- resolve_walk_sets ----------


def test_resolve_walk_sets_merges_directly_kept_dirs_into_kept_roots(tmp_path):
    """The union the walks depend on: a directory kept only via --dot-dirs
    comes back inside kept_roots, so its contents are protected too."""
    dotdir = tmp_path / ".config"
    dotdir.mkdir()
    (dotdir / "settings.json").write_text("{}\n")
    _protected, kept_roots = resolve_walk_sets(tmp_path, set(), [], False, True)
    assert dotdir.resolve() in kept_roots


def test_resolve_walk_sets_keeps_the_entries_it_was_given(sample_tree):
    """The named entries are merged with the discovered ones, not replaced
    by them."""
    _exact_keep, named = build_exact_keep(sample_tree, ["keep.md"])
    _protected, kept_roots = resolve_walk_sets(sample_tree, named, [], False, False)
    assert named <= kept_roots


def test_resolve_walk_sets_leaves_protected_dirs_untouched(sample_tree):
    """Only the second return value is folded -- protected_dirs comes
    straight through from build_protected_dirs."""
    _exact_keep, named = build_exact_keep(sample_tree, ["src/main.py"])
    expected, _directly_kept_dirs = build_protected_dirs(
        sample_tree, named, ["*.md"], False, False
    )
    protected, _kept_roots = resolve_walk_sets(
        sample_tree, named, ["*.md"], False, False
    )
    assert protected == expected


# ---------- should_keep (integration of all three signals) ----------


def test_should_keep_true_for_file_under_exact_kept_directory(sample_tree):
    exact_keep, kept_roots = build_exact_keep(sample_tree, ["src/"])
    protected, _directly_kept_dirs = build_protected_dirs(
        sample_tree, kept_roots, [], False, False
    )
    main_py = sample_tree / "src" / "main.py"
    assert should_keep(
        main_py, sample_tree, exact_keep, [], False, False, protected, kept_roots
    )


def test_should_keep_false_for_unrelated_file(sample_tree):
    exact_keep, kept_roots = build_exact_keep(sample_tree, ["src/"])
    protected, _directly_kept_dirs = build_protected_dirs(
        sample_tree, kept_roots, [], False, False
    )
    drop_txt = sample_tree / "drop.txt"
    assert not should_keep(
        drop_txt, sample_tree, exact_keep, [], False, False, protected, kept_roots
    )


def test_should_keep_true_for_protected_dir_sibling_via_glob(sample_tree):
    exact_keep, kept_roots = build_exact_keep(sample_tree, ["*.md"])
    patterns = ["*.md"]
    protected, _directly_kept_dirs = build_protected_dirs(
        sample_tree, kept_roots, patterns, False, False
    )
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
    protected, _directly_kept_dirs = build_protected_dirs(
        sample_tree, kept_roots, patterns, False, False
    )
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
    _exact_keep, kept_roots = build_exact_keep(sample_tree, patterns)
    protected, _directly_kept_dirs = build_protected_dirs(
        sample_tree, kept_roots, patterns, False, False
    )
    assert (sample_tree / "src").resolve() in protected
    assert sample_tree.resolve() in protected


# ---------- is_real_dir (symlinks are never treated as directories) ----------


def test_is_real_dir_true_for_a_regular_directory(sample_tree):
    assert is_real_dir(sample_tree / "src")


def test_is_real_dir_false_for_a_symlink_to_a_directory(tmp_path):
    target = tmp_path / "outside"
    target.mkdir()
    link = tmp_path / "link_to_outside"
    link.symlink_to(target)
    assert not is_real_dir(link)


def test_is_real_dir_false_for_a_regular_file(sample_tree):
    assert not is_real_dir(sample_tree / "keep.md")


def test_is_real_dir_false_for_a_dangling_symlink(tmp_path):
    link = tmp_path / "broken"
    link.symlink_to(tmp_path / "does_not_exist")
    assert not is_real_dir(link)


def test_directly_kept_symlinked_dot_dir_still_lands_in_directly_kept_dirs(tmp_path):
    """A directly-kept symlinked directory still gets classified as one in
    build_protected_dirs -- this stays true even though nothing is ever
    descended into on the far side of it (see DESIGN.md, "Symlinks are
    never descended into"): the classification is harmless once nothing
    walks past it, not wrong."""
    target = tmp_path / "outside"
    target.mkdir()
    dotdir = tmp_path / ".config"
    dotdir.symlink_to(target)
    _protected, directly_kept_dirs = build_protected_dirs(
        tmp_path, set(), [], False, True
    )
    assert dotdir in directly_kept_dirs


# ---------- narrowing-pattern hints ----------


def test_deepen_pattern_inserts_globstar_before_the_last_segment():
    assert deepen_pattern("/*.md") == "**/*.md"
    assert deepen_pattern("src/*.py") == "src/**/*.py"
    assert deepen_pattern("src/weed_out/*.py") == "src/weed_out/**/*.py"


def test_no_hints_without_a_candidate_pattern(sample_tree):
    """Bare patterns and patterns already using ** are never candidates, so
    the tree is not walked at all for them."""
    assert narrowing_pattern_hints(sample_tree, []) == []
    assert narrowing_pattern_hints(sample_tree, ["*.md"]) == []
    assert narrowing_pattern_hints(sample_tree, ["**/*.md"]) == []


def test_hint_reports_what_the_deep_form_would_have_matched(sample_tree):
    (hint,) = narrowing_pattern_hints(sample_tree, ["/*.md"])
    assert "'/*.md' matches 1 path, but '**/*.md' would match 2." in hint


def test_no_hint_when_the_deep_form_matches_no_more(sample_tree):
    """A deliberately scoped pattern is compared against its own ** form,
    not against every file of that name under PATH -- so scoping something
    that has nothing nested below it stays silent."""
    assert narrowing_pattern_hints(sample_tree, ["notes/*.md"]) == []
