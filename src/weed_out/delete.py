"""The delete/trash/dry-run walk, and the removal pipeline both commands share."""

import shutil
import sys
from pathlib import Path

from send2trash import send2trash

from weed_out.args import EXIT_ERROR, EXIT_OK
from weed_out.keep import (
    is_real_dir,
    resolve_keep_list,
    resolve_walk_sets,
    should_keep,
    warn_keep_everything,
    warn_narrowing_patterns,
)


def run_removal(root: Path, args, command: str, usage: str) -> int:
    """Resolve the keep list and run the walk for `delete` or `trash`.

    The shared pipeline behind `cli_delete` and `cli_trash`: the two
    commands differ only in disposal, and `command` is the same string
    `delete_rest` takes as its mode, so nothing here branches beyond
    wording. `usage` is the calling command's usage line, printed under
    the one error this pipeline can raise itself.
    """
    exact_keep, kept_roots, patterns, keep_everything = resolve_keep_list(
        root, args.keep
    )

    if keep_everything and args.commit:
        # An absent keep list under --commit is likelier a forgotten
        # argument than an intention (see DESIGN.md, "An absent keep
        # list keeps everything").
        print(
            "weed-out: no keep entries specified "
            "(pass --keep or add a .weed-out-ignore file)",
            file=sys.stderr,
        )
        print(f"Usage: {usage}", file=sys.stderr)
        return EXIT_ERROR

    mode = command if args.commit else "dry-run"

    delete_rest(
        root,
        exact_keep,
        patterns,
        args.dot_files,
        args.dot_dirs,
        mode,
        kept_roots,
    )

    if mode == "dry-run":
        if keep_everything:
            # The usual trailer would point at a --commit that exits 1.
            warn_keep_everything()
        else:
            disposal = (
                "permanently delete"
                if command == "delete"
                else "send everything to the OS trash"
            )
            print(f"\nDry run only. Re-run with --commit to {disposal}.")
        warn_narrowing_patterns(root, patterns)

    return EXIT_OK


def collect_targets(
    directory: Path,
    root: Path,
    exact_keep,
    patterns,
    dot_files,
    dot_dirs,
    protected_dirs,
    kept_roots,
) -> list[Path]:
    """Collect everything to remove, descending only into kept directories.

    A directory that isn't kept cannot contain anything that is -- every
    directly-kept entry protects its whole parent chain -- so an unkept
    directory is recorded whole and never entered (see DESIGN.md,
    "Collapsing doomed directories"). The returned targets are therefore
    pairwise non-nested, and can be removed in any order.
    """
    targets = []
    try:
        entries = sorted(directory.iterdir())
    except PermissionError:
        return targets
    for entry in entries:
        if not should_keep(
            entry,
            root,
            exact_keep,
            patterns,
            dot_files,
            dot_dirs,
            protected_dirs,
            kept_roots,
        ):
            targets.append(entry)
        elif is_real_dir(entry):
            targets.extend(
                collect_targets(
                    entry,
                    root,
                    exact_keep,
                    patterns,
                    dot_files,
                    dot_dirs,
                    protected_dirs,
                    kept_roots,
                )
            )
    return targets


def delete_rest(
    root: Path, exact_keep, patterns, dot_files, dot_dirs, mode: str, kept_roots
):
    """Walk `root` and act on everything that isn't kept.

    `mode` is one of "delete" (permanent, shutil.rmtree/unlink), "trash"
    (recoverable, send2trash -- one call per removal target, and an
    unkept directory is a single target), or "dry-run" (nothing touched,
    just reported).
    """
    protected_dirs, kept_roots = resolve_walk_sets(
        root, kept_roots, patterns, dot_files, dot_dirs
    )
    targets = collect_targets(
        root,
        root,
        exact_keep,
        patterns,
        dot_files,
        dot_dirs,
        protected_dirs,
        kept_roots,
    )

    if mode == "dry-run":
        report_dry_run(targets)
        return

    for entry in targets:
        if not (entry.exists() or entry.is_symlink()):
            continue
        if mode == "delete":
            if is_real_dir(entry):
                shutil.rmtree(entry, ignore_errors=True)
            else:
                entry.unlink()
        else:
            send2trash(entry)


def report_dry_run(targets: list[Path]) -> None:
    """Print the removal targets and a count line, without touching anything.

    The count is of *targets*, not files: one line can stand for a whole
    directory. The trailing clause spells that out whenever any target is
    a directory, and is left off entirely when none is, so the common
    case reads as plainly as it always did.
    """
    # sorted for readability only -- the targets are pairwise non-nested,
    # so no removal order has to be preserved here
    for line in sorted(str(t) for t in targets):
        print(line)

    count = len(targets)
    dir_count = sum(1 for t in targets if is_real_dir(t))
    line = f"\n{count} item{'s' if count != 1 else ''} would be removed"
    if dir_count:
        noun = "directory" if dir_count == 1 else "directories"
        inside = "it" if dir_count == 1 else "them"
        line += f", including {dir_count} {noun} and everything inside {inside}"
    print(line + ".")
