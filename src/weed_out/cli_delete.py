"""
        weed-out -- Delete

https://github.com/east-van-ai/weed-out

Permanently remove everything under PATH except what's kept. No undo.

The bare verb is a dry run: it prints what would go and touches nothing.
--commit is what removes. Run `weed-out tree` first to see what would go,
or use `weed-out trash` for a removal that can be recovered.

Keep entries come from --keep, comma-separated, and from a .weed-out-ignore
file at PATH, one per line, with # comments and blank lines allowed. The two
are merged. With neither, everything is kept, and --commit is refused.
"""

from pathlib import Path

from weed_out import errors
from weed_out.delete import run_removal

HELP = "permanently remove everything not kept; no undo"
USAGE = (
    "weed-out delete PATH [--keep LIST] [--dry-run | --commit] "
    "[--dot-files] [--dot-dirs]"
)
SLOTS = ("PATH",)


def run(path: str, args) -> None:
    """Run the removal pipeline with permanent deletion as the disposal."""
    root = Path(path).resolve()

    if not root.is_dir():
        raise errors.ReadinessError(f"{root} is not a directory")

    run_removal(root, args, "delete")
