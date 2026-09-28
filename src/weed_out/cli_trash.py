"""
        weed-out -- Trash

https://github.com/east-van-ai/weed-out

Send everything under PATH except what's kept to the OS trash. Recoverable,
unlike `delete`. A doomed directory lands in the trash as one folder.

The bare verb is a dry run: it prints what would go and touches nothing.
--commit is what moves anything. Run `weed-out tree` first to see what
would go.

Keep entries come from --keep, comma-separated, and from a .weed-out-ignore
file at PATH, one per line, with # comments and blank lines allowed. The two
are merged. With neither, everything is kept, and --commit is refused.
"""

from pathlib import Path

from weed_out import errors
from weed_out.delete import run_removal

HELP = "send everything not kept to the OS trash; recoverable"
USAGE = (
    "weed-out trash PATH [--keep LIST] [--dry-run | --commit] "
    "[--dot-files] [--dot-dirs]"
)
SLOTS = ("PATH",)


def run(path: str, args) -> None:
    """Run the removal pipeline with the OS trash as the disposal."""
    root = Path(path).resolve()

    if not root.is_dir():
        raise errors.ReadinessError(f"{root} is not a directory")

    run_removal(root, args, "trash")
