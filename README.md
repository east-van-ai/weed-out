# weed-out - delete everything except what you keep

`weed-out` deletes everything in a directory tree except what you tell it
to keep. It's `rm` turned inside out: you name what survives, and the rest
goes.

```text
$ weed-out tree . --keep "src/,README.md"

Tree under /home/go/proj ([REMOVE] marks what would be removed):

├── build/  [REMOVE]
├── src/
│   └── main.py
├── README.md
└── notes.txt  [REMOVE]

3 kept, 2 to remove (1 directory collapsed -- contents not listed).
```

## Why

Most cleanup tools ask what to remove. That's backwards when the keep list
is short and the cruft is long: prepping a repo for release, clearing build
output, pruning a folder back to a known-good set. Nobody wants to list
every cache directory some other tool left behind.

Naming what survives has a quieter benefit too. A release checklist that
says `rm secret.txt` tells every reader that `secret.txt` existed. A
`weed-out` command names only the keep list, so it says nothing about what
was thrown away.

## Install

Python 3.9 or newer. One small dependency,
[`send2trash`](https://pypi.org/project/Send2Trash/), installs along with it.

```bash
pipx install "git+https://github.com/east-van-ai/weed-out.git"
```

## Usage

`weed-out COMMAND PATH [flags]`. `PATH` is required, so use `.` for the
current directory.

```bash
# Look first: a tree with [REMOVE] tags, nothing touched
weed-out tree . --keep "src/**/*.py,README.md"

# Send everything else to the OS trash, recoverable
weed-out trash . --keep "src/**/*.py,README.md" --commit

# Delete everything else for good, no undo
weed-out delete . --keep "src/**/*.py,README.md" --commit
```

Nothing is removed until you type `--commit`. Without it, `delete` and
`trash` only list what they would remove. `tree` never removes anything,
and it doesn't accept `--commit` at all.

## The keep list

`--keep` takes a comma-separated list of paths and glob patterns.

- `README.md` or `src/` keeps that exact file or folder. A kept folder
  keeps everything inside it.
- `*.md` has no slash, so it matches by filename at any depth.
- `src/*.py` has a slash, so it matches that location only. A `*` stops
  at the next `/`, and `**` crosses folders: `src/**/*.py`.

A folder survives whenever anything inside it is kept, so you never have
to name the folders on the way down.

To stop retyping the list, put it in a `.weed-out-ignore` file at `PATH`,
one entry per line, `#` for comments. `weed-out` reads it automatically and
merges it with `--keep`.

With no keep list at all, `weed-out` keeps everything. That makes
`weed-out tree .` a safe way to look around. `--commit` refuses to run
without a keep list, since an empty one there is more likely a mistake.

## Before you commit

- Run `tree` first on anything you'd be upset to lose, and actually read
  it.
- `delete --commit` has no undo. Commit to git or back up first. `trash`
  is recoverable, but it isn't a backup.
- Symlinks are never followed. A link is kept or removed as the link
  itself, never its target.
- Matching follows your file system's case rules. macOS ignores case by
  default, and Linux usually doesn't.

## Documentation

- [CLI.md](docs/CLI.md): every command, flag, and exit code.
- [DESIGN.md](docs/DESIGN.md): how the walk decides what survives, and why.
- [CHANGELOG.md](CHANGELOG.md): what changed in each release.

## Use of AI

Code and documentation are written in collaboration with remote and local AI; design
decisions, code review, semantic and auditory review, and final judgement stay human.

---

**East Van AI** · AI for the rest of us! · Vancouver, BC, Canada

[github.com/east-van-ai](https://github.com/east-van-ai) · <east-van-ai@proton.me>

Copyright (c) 2026 Go Nakamaru
