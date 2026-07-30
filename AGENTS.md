# AGENTS.md

This file provides guidance to coding agents when working with code in this
repository.

## Project

`dynamic-markdown` — a markdown-like file format whose content is expanded at
load time by tags: `<include>`/`@path`, `<script>` and `<field>`. Library only,
no CLI. Python ≥ 3.11, no runtime dependencies, `src/` layout, built and managed
with `uv` (`uv_build` backend).

## Commands

Everything runs against the project venv (`.venv/`). The git hooks call binaries
directly (`.venv/bin/ruff`); interactively `uv run <cmd>` also works.

- **Install / sync deps**: `uv sync`
- **Tests**: `uv run pytest tests/`
  - single test: `uv run pytest tests/test_dynamic_markdown.py::test_name`
  - by keyword: `uv run pytest tests/ -k directory`
- **Lint**: `uv run ruff check src/ tests/` (rules `E,F,I`); autofix with
  `ruff check --fix`; format with `uv run ruff format src/ tests/`
- **Docstring completeness** (Google style, enforced on push):
  `uv run ruff check --select=D,DOC --preview src/ tests/`
- **Docstring wrapping**: `uv run docformatter --in-place --recursive --wrap-summaries 88 --wrap-descriptions 88 src/ tests/`

`core.hooksPath` is set to `hooks/`, so the checked-in hooks are active:
`pre-commit` auto-fixes and formats staged `src/`/`tests/` paths, then blocks on
remaining lint errors; `pre-push` runs the docstring check and the full suite.

## Architecture

Two layers, both small:

- `parsers/base.py` — `Parser` ABC, one `parse` classmethod.
- `parsers/tags/base.py` — `TagParser` ABC. A subclass sets `_pattern` (the
  regex for its tag) and implements `_replace(match, **kwargs)`; the inherited
  `parse` walks every match and substitutes it. `IncludeTagParser` overrides
  `parse` because it needs the `<script>` spans of the whole text first.
- `parsers/files/base.py` — `DynamicMarkdownFileParser`, the orchestrator. It
  derives `current_dir` and the `visited` chain, then runs the three parsers.
- `types/files/base.py` — `DynamicMarkdownFile`, the public entry point:
  `DynamicMarkdownFile(path, tool=...)` reads and parses eagerly in `__init__`,
  exposing `raw` and `content`. `load` re-reads and re-parses; `reload` is an
  alias of it. There is no lazy parsing and no `parse` method.

### Invariants that span files

- **Tag order is deliberate**: include → field → script. Includes run first so
  tags inside included files expand too; fields run before scripts so a field
  value can appear in script source; script stdout is final and is never
  re-parsed for tags.
- **Relative paths are relative to the containing file**, not to the top-level
  caller. `DynamicMarkdownFileParser.parse` re-derives `current_dir` from
  `file.path` at every nesting level. A path starting with `/` is absolute.
- **Cycle detection** rides on the `visited` tuple of resolved paths, threaded
  down through `DynamicMarkdownFile(_visited=...)` and back into the include
  parser; a repeat raises `ValueError`. It catches cycles mixing both include
  syntaxes.
- **`include.py` imports `DynamicMarkdownFile` inside `_replace`** on purpose —
  a module-level import would be circular.

### Tag behavior

- `<include>` is strict: a missing target raises `FileNotFoundError`. Bare
  `@path` is lenient: it expands only when the target exists as a file or a
  directory, otherwise the matched text is left untouched, so `user@example.com`
  survives parsing.
- A **file** target is replaced with that file's parsed content, wrapped as
  `___` / `<!-- Included from /abs/path.md -->` / content / `___`.
- A **directory** target is replaced with a flat listing of its direct children
  instead — one name per line, sorted, hidden entries kept, subdirectories
  suffixed `/` — wrapped with `<!-- Content of directory /abs/dir -->`. The
  listed files are never read or parsed, so a listing cannot form a cycle.
- The wrapper is **suppressed when the match sits inside a `<script>` span**,
  since there the included text is script source and the rules and comment would
  break execution. `IncludeTagParser.parse` computes those spans with
  `ScriptTagParser._pattern`.
- `<script>` runs a file when the target exists or ends in `.py`, otherwise runs
  the body inline via `sys.executable -c`. `cwd` is the containing file's
  directory, `check=True`, and one trailing newline is stripped from stdout, so
  a failing script surfaces as `CalledProcessError`.
- `<field>name</field>` becomes `str(getattr(field_source, name))`. No
  `field_source` raises `ValueError`; an unknown attribute raises
  `AttributeError`.

## Tests

One file, `tests/test_dynamic_markdown.py`, plain pytest with `tmp_path`. Four
helpers carry most of the weight: `_write`, `_parse`, and `_wrap` /
`_wrap_directory`, which build the expected wrapper text. Change the wrapper
format in `include.py` and only those two helpers need updating.

`smoke_test/dynamic_markdown/run.py` is **stale**: it still calls the removed
`DynamicMarkdownFile.parse`, so it fails. Do not treat it as a working example.

## Release flow

Past releases are tags only, no GitHub releases:

1. bump `version` in `pyproject.toml`
2. `uv lock` so `uv.lock` records the same version
3. commit both together with the code change
4. `git tag -a vX.Y.Z -m "vX.Y.Z"` (message is just the version)
5. `git push origin main --follow-tags`

History is linear on `main`, with no merge commits or pull requests so far.

## Downstream consumer

The sibling repo `arancio` depends on this package: its `ReadFileTool` expands
every `.md` it reads through `DynamicMarkdownFile`, and its prompt `@mention`
pattern mirrors the bare `@path` syntax here. Wrapper text and tag-syntax
changes are visible to model context there.

## Conventions

- Google-style docstrings on every module, class and function, including
  `Returns` and `Raises` sections; `ruff --select=D,DOC` enforces this on push.
  Docstrings wrap at 88 via `docformatter`.
- Type hints everywhere (arguments, returns, attributes, `ClassVar` patterns).
- PEP 8, enforced by `ruff format` (88 columns).
- Code comments start lowercase and take no ending period; comment only the
  parts that are genuinely subtle.
- Markdown lines wrap at 80 characters, except commands in code blocks, which
  stay on one line.
- Commit messages: past tense, one short sentence, naming the affected files or
  the most significant changes (e.g. "Added directory listing to include tags,
  dropped colon from included file comment, bumped version to 0.3.1").
- Branches: `feature/snake_case`, `fix/snake_case`.
