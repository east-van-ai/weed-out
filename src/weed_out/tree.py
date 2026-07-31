"""Read-only tree display for the `tree` command."""

from pathlib import Path

from weed_out.keep import is_real_dir, should_keep


def print_tree(
    directory: Path,
    keep_root: Path,
    exact_keep,
    patterns,
    dot_files,
    dot_dirs,
    protected_dirs,
    kept_roots,
    prefix="",
):
    """Print `directory` as a tree, tagging entries that would be removed.

    Returns a `(kept, removed, collapsed)` tally covering this directory
    and everything printed below it, for the summary line `main()` ends
    with. `collapsed` counts removed directories, whose contents are
    deliberately not listed -- nothing inside a directory that isn't
    kept can be kept either, so there is nothing below it worth showing.
    """
    try:
        entries = sorted(directory.iterdir(), key=lambda x: (x.is_file(), x.name))
    except PermissionError:
        return 0, 0, 0

    kept = removed = collapsed = 0
    for i, entry in enumerate(entries):
        keep = should_keep(
            entry,
            keep_root,
            exact_keep,
            patterns,
            dot_files,
            dot_dirs,
            protected_dirs,
            kept_roots,
        )
        is_dir = is_real_dir(entry)
        connector = "└── " if i == len(entries) - 1 else "├── "
        if entry.is_symlink():
            try:
                target = str(entry.readlink())
            except OSError:
                target = "?"
            name = f"{entry.name} -> {target}"
        else:
            name = f"{entry.name}/" if is_dir else entry.name
        tag = "" if keep else "  [REMOVE]"
        print(f"{prefix}{connector}{name}{tag}")

        if not keep:
            removed += 1
            collapsed += is_dir  # tagged and not descended into
            continue

        kept += 1
        if is_dir:
            extension = "    " if i == len(entries) - 1 else "│   "
            sub_kept, sub_removed, sub_collapsed = print_tree(
                entry,
                keep_root,
                exact_keep,
                patterns,
                dot_files,
                dot_dirs,
                protected_dirs,
                kept_roots,
                prefix + extension,
            )
            kept += sub_kept
            removed += sub_removed
            collapsed += sub_collapsed

    return kept, removed, collapsed


def format_summary(kept: int, removed: int, collapsed: int) -> str:
    """Render the tally `print_tree` returns as the closing summary line."""
    summary = f"{kept} kept, {removed} to remove"
    if collapsed:
        noun = "directory" if collapsed == 1 else "directories"
        summary += f" ({collapsed} {noun} collapsed -- contents not listed)"
    return summary + "."
