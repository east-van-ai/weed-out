# weed-out DESIGN

The model: what `weed-out` builds, the decisions and refusals under it,
and the rules the walks depend on. The command surface, the grammar and
the exit codes, is in CLI.

## Scope and dependencies

`weed-out` needs Python 3.9 or newer, and CI tests 3.9 through 3.15. The
floor is macOS's system Python, so the tool runs on a stock Mac's own
interpreter. That is why 3.9 stays past its end of life. The tool is built
on the standard library plus one runtime dependency, `send2trash`
(BSD-3-Clause), used only by `trash`.

That dependency cannot be an optional extra. The tool is installed with
`pipx` as a whole package, and a `weed-out[trash]` extra would leave
`trash` broken for anyone who installed the plain one. `send2trash` is
small, stable, and widely used, which is why this one exception is
acceptable. It is not an invitation to add more.

Dependencies live in `pyproject.toml` only: runtime in
`[project] dependencies`, dev tooling in `[dependency-groups]`. There is
no requirements file, because a second file answering the same question
can drift with nothing to catch it. Dev tooling is a group rather than an
extra because an extra is published metadata, and `weed-out[dev]` would
become a supported offer. A group stays in the working copy.

Dev pins are exact while the runtime floor is not. A pinned `ruff`
freezes a rule set, so local and CI agree on what counts as a failure.

## Keep resolution

A keep entry comes from `--keep` or from `.weed-out-ignore`, and every
entry is one of two kinds.

**Exact paths** (`src/`, `README.md`) name one entry. Each drags its
parent chain up to `PATH` along with it, so a kept file always keeps its
folders. A folder kept that way survives as a *shell*: it holds the named
entry and nothing else. `--keep "src/main.py"` leaves `src/` holding only
`main.py`.

**Glob patterns** (`*.md`, `src/**/*.py`) don't name one path, so they
are tested against every entry the walk meets.

### Path-scoped patterns

A pattern's behaviour is decided by whether it contains `/`.

- No `/`: matched against the bare filename at any depth. `*.md` protects
  every `.md` file in the tree.
- A `/`: matched against the path relative to `PATH`, gitignore-style.
  `*` stays inside one segment, and `**` matches zero or more whole
  segments. `src/*.py` protects direct children only, and `src/**/*.py`
  protects any depth. A leading or trailing `/` is stripped first, so
  `/src/*.py` and `src/*.py` are the same pattern.

Anchored matching was chosen over running `fnmatch` on the whole path as
one string. `weed-out` exists to carve release trees, so behaving like
git's own ignore patterns is a goal, not a nicety. `.dockerignore`,
`rsync`, and bash `globstar` anchor the same way.

The cost is accepted. Whole-string matching can only over-protect.
Anchored matching lets a user who forgets `**` under-protect a nested
file and lose it on `--commit`. Three things stand against that: `**` is
taught early wherever the tool is taught, the read-only surfaces warn
when a path pattern provably narrows, and `tree` is always meant to run
first.

The matcher is hand-rolled, applying `fnmatch` one segment at a time.
`PurePath.match()` was rejected because its `**` support arrived only in
Python 3.13, so it would behave differently across the supported range.

### The `.weed-out-ignore` file

A checked-in file holding the same kind of entries as `--keep`, one per
line, so a project states its keep list once.

- **Read automatically, from `PATH` only.** No flag turns it on, and
  nested copies are ignored. Reading it without being asked is safe
  because the file can only add to what survives, never cause a
  deletion. Root-only, because the model is one keep list, not
  per-folder rules.
- **It makes `--keep` optional.** If neither source yields an entry, the
  run keeps everything rather than nothing. Silence must never mean
  "delete everything in `PATH`".
- **One entry per line, `#` for comments.** It diffs cleanly, and a
  comment can say *why* an entry survives, which is the point of checking
  it in.
- **It merges with `--keep`.** Neither can say "delete this", so there is
  nothing to conflict. Anything named in either source survives.
- **No `!pattern` negation, by design.** With only "protected" and "not
  mentioned" as states, no config can delete something you meant to keep
  by accident. If negation is ever added, keep wins.
- **The name** follows `.dockerignore`: an entry is ignored by what the
  tool does, and `weed-out` deletes.

## Walk rules

Four rules the walks depend on. Each is cheap to break by accident.

### Survival propagates both ways

Protection travels **up** from a kept entry and **down** from a kept
directory. Neither direction follows from the other.

- **Up.** Every directly-kept entry protects its whole parent chain. A
  file kept only by a glob still has to protect its folders, even though
  no folder name matches anything in the keep list.
- **Down.** A directly-kept directory protects everything beneath it, at
  any depth.

The down direction has to ignore *how* the directory came to be kept. A
directory kept by a glob on its own name, or by `--dot-dirs`, protects
its contents exactly as one named by path does. Miss this and the shell
survives while its contents are deleted, the opposite of what
`--keep "src/"` and `--dot-dirs` both promise.

It must not fire on a shell, though. A folder kept only because a named
file sits inside it is not a directly-kept directory. Treat it as one and
`--keep "src/main.py"` protects the whole of `src/`.

Together, the two directions guarantee that **an unkept directory
contains nothing kept, at any depth.** The collapse below rests entirely
on that.

### One function decides survival

Everything that decides what survives asks the same function. A second
opinion drifts out of agreement the moment a new way to keep something is
added.

This is why there is no empty-directory cleanup pass. Every directory
already has an answer: kept, protected because something inside survives,
or doomed and removed whole. An unkept empty directory is an ordinary
target. A cleanup pass can only add a wrong answer. Testing emptiness
against one route to survival deletes an empty directory kept by
`--dot-dirs`, or by a glob on its own name.

### Naming a link keeps the link

An exact keep entry is turned into a path without following links. Full
resolution would follow a link in the entry's last component, so
`--keep "some_link"` would name the link's *target*, a path the walk
never produces. The link would be judged unkept and removed. Naming a
thing has to keep that thing.

One consequence, stated rather than engineered away. An entry whose path
runs *through* a symlinked directory, such as `--keep "link/f.txt"`, never
matches, since the walk never goes there. The ancestor rule still keeps
`link` itself, so the entry behaves like `--keep "link"`.

Glob patterns need none of this. They are matched against the entry the
walk produced, so no resolution is involved, and `--keep "link_*"` keeps
the link.

### A symlink is never walked through

Only a real directory is ever descended into or removed as a tree. A
symlink is a leaf, whether it points at a file or a directory, and
whether or not it is kept: kept whole, removed whole, never entered.

A walk that follows a symlink-to-directory treats everything behind it as
part of `PATH`, even when the target lives somewhere else entirely. Two
facts make the rule concrete.

- **A link is removed with `unlink()`, never `rmtree()`.** `rmtree()`
  refuses a path that is itself a symlink. With errors ignored, that
  refusal is silent, so a link `tree` promised to remove would survive
  `--commit`. `unlink()` removes the link and leaves its target alone.
- **`tree` shows every link's target**, as `name -> target`, dangling
  ones included. An entry that looks like a folder but isn't expanded has
  to say why, or "not walked into" reads as "empty".

The dot flags draw the same line. A dot-named symlink is a dotfile, so
`--dot-files` keeps it and `--dot-dirs` does not, whatever it points at.
Asking the target would tie a link's survival to something outside it, and
a dangling link would answer to neither flag. Letting either flag keep any
link spares a few links, but then neither flag means what it says.

### Collapsing doomed directories

Both walks stop at a directory that isn't kept. `tree` prints it as one
tagged line, and removal hands it to `rmtree` or `send2trash` in one call.
Survival propagating both ways is what allows this: no walk ever needs to
look inside a doomed directory to find a survivor. It also means the
removal targets never nest, so they can be removed in any order.

Collapse must not stop *early*. A **kept** directory holding doomed
children still has to be walked into. Recurse when kept, record and stop
when not. Keeping those two cases apart is the whole correctness argument.

The payoff is biggest for `trash`: a 3,000-file `venv/` goes to the OS
trash as one recoverable folder, not 3,000 loose items. For `tree` it is
legibility. Both read-only surfaces report how many targets are collapsed
directories, because without that a collapsed `venv/` reads as one doomed
file, and the preview understates what `--commit` will do. Symlinks never
count as collapsed. A collapsed directory is a real subtree elided for
brevity, and a symlink is a leaf on principle.

## Use of AI

Both the use of AI and its disclosure are deliberate. Code and documentation in
this project are written in collaboration with Artificial Intelligence (AI). The
division of labour: the AI explores, challenges assumptions and edge cases, and
drafts; the human initiates, drafts the designs, explores alongside the AI,
reviews every change, and decides what gets committed.

---

**East Van AI** · AI for the rest of us! · Vancouver, BC, Canada

[github.com/east-van-ai](https://github.com/east-van-ai) · <east-van-ai@proton.me>

Copyright (c) 2026 Go Nakamaru
