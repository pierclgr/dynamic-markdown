"""Tests for dynamic-markdown parsing behavior."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from dynamic_markdown.types.files.base import DynamicMarkdownFile


def _write(path: Path, content: str) -> Path:
    """Write text content to ``path`` and return it.

    Returns:
        The path that was written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def _parse(
    tmp_path: Path,
    content: str,
    tool: object | None = None,
) -> str:
    """Load and parse temporary dynamic-markdown content.

    Returns:
        The parsed dynamic-markdown content.
    """
    source = _write(tmp_path / "source.md", content)
    return DynamicMarkdownFile(source, tool=tool).content


def _wrap(path: Path, content: str) -> str:
    """Build the expected reference-wrapped form of included ``content``.

    Returns:
        ``content`` wrapped as :class:`IncludeTagParser` wraps it, noting
        the resolved absolute ``path`` it was included from.
    """
    return f"___\n<!-- Included from: {path.resolve()} -->\n{content}\n___"


def test_file_loads_raw_content_from_path_and_string(tmp_path: Path) -> None:
    """Load and parse content when initialized with both ``Path`` and ``str``."""
    path = _write(tmp_path / "source.md", "hello")
    file = DynamicMarkdownFile(path)

    assert file.raw == "hello"
    assert file.content == "hello"
    assert DynamicMarkdownFile(str(path)).raw == "hello"


def test_reload_is_an_alias_of_load() -> None:
    """Expose ``reload`` as an alias of ``load``."""
    assert DynamicMarkdownFile.reload is DynamicMarkdownFile.load


def test_file_missing_source_raises_file_not_found(tmp_path: Path) -> None:
    """Raise ``FileNotFoundError`` when the source file is missing."""
    with pytest.raises(FileNotFoundError):
        DynamicMarkdownFile(tmp_path / "missing.md")


def test_file_load_delegates_to_parser_and_caches_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pass parser arguments through and cache parsed content."""
    file = DynamicMarkdownFile(_write(tmp_path / "source.md", "raw"))
    tool = object()
    seen: dict[str, object] = {}

    class _Parser:
        """Test parser recording the received call."""

        @classmethod
        def parse(cls, **kwargs: object) -> str:
            """Record parser arguments and return parsed content.

            Returns:
                Static parsed content.
            """
            seen.update(kwargs)
            return "parsed"

    monkeypatch.setattr(DynamicMarkdownFile, "_parser", _Parser)

    assert file.load(tool=tool) is None
    assert file.content == "parsed"
    assert seen == {
        "file": file,
        "field_source": tool,
        "_visited": (),
    }


def test_file_content_returns_cached_content_without_reparsing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return cached content without delegating to the parser again."""
    file = DynamicMarkdownFile(_write(tmp_path / "source.md", "raw"))
    calls = 0

    class _Parser:
        """Test parser counting received calls."""

        @classmethod
        def parse(cls, **kwargs: object) -> str:
            """Count parser calls and return parsed content.

            Returns:
                Static parsed content with the call count.
            """
            nonlocal calls
            calls += 1
            return f"parsed {calls}"

    monkeypatch.setattr(DynamicMarkdownFile, "_parser", _Parser)

    assert file.load() is None
    assert file.content == "parsed 1"
    assert file.content == "parsed 1"
    assert calls == 1


def test_file_load_refreshes_cached_content(tmp_path: Path) -> None:
    """Update cached content every time ``load`` is called."""
    file = DynamicMarkdownFile(
        _write(tmp_path / "source.md", "<field>name</field>"),
        tool=SimpleNamespace(name="first"),
    )
    assert file.content == "first"

    file.load(tool=SimpleNamespace(name="second"))
    assert file.content == "second"


def test_file_reload_rereads_raw_and_reparses_content(tmp_path: Path) -> None:
    """Reread raw content from disk and reparse it on reload."""
    path = _write(tmp_path / "source.md", "first")
    file = DynamicMarkdownFile(path)

    assert file.content == "first"
    _write(path, "second")

    file.reload()

    assert file.raw == "second"
    assert file.content == "second"


def test_plain_text_without_tags_is_unchanged(tmp_path: Path) -> None:
    """Leave content without dynamic-markdown tags unchanged."""
    assert _parse(tmp_path, "plain\ntext") == "plain\ntext"


def test_field_tags_are_replaced_and_whitespace_is_stripped(tmp_path: Path) -> None:
    """Replace multiple field tags with stripped attribute names."""
    tool = SimpleNamespace(name="bash", timeout=30)

    assert (
        _parse(
            tmp_path,
            "<field> name </field>: <field>timeout</field>",
            tool=tool,
        )
        == "bash: 30"
    )


def test_field_tag_without_field_source_raises_value_error(tmp_path: Path) -> None:
    """Raise ``ValueError`` when a field tag has no field source."""
    with pytest.raises(ValueError, match="requires a field_source"):
        _parse(tmp_path, "<field>name</field>")


def test_field_tag_missing_attribute_raises_attribute_error(tmp_path: Path) -> None:
    """Raise ``AttributeError`` when the field source lacks the attribute."""
    with pytest.raises(AttributeError):
        _parse(tmp_path, "<field>missing</field>", tool=SimpleNamespace())


def test_include_tag_replaces_file_content_and_strips_whitespace(
    tmp_path: Path,
) -> None:
    """Replace an include tag with the referenced file content."""
    intro = _write(tmp_path / "parts" / "intro.md", "included")

    assert _parse(tmp_path, "before <include> parts/intro.md </include> after") == (
        f"before {_wrap(intro, 'included')} after"
    )


def test_include_tags_resolve_relative_to_the_including_files_own_directory(
    tmp_path: Path,
) -> None:
    """Resolve each nested include path against its own including file."""
    first = _write(tmp_path / "b" / "first.md", "first <include>c/second.md</include>")
    second = _write(tmp_path / "b" / "c" / "second.md", "second")
    _write(tmp_path / "c" / "second.md", "wrong directory")

    assert _parse(tmp_path, "<include>b/first.md</include>") == _wrap(
        first, f"first {_wrap(second, 'second')}"
    )


def test_included_content_can_contain_script_and_field_tags(tmp_path: Path) -> None:
    """Expand script and field tags inside included content."""
    intro = _write(
        tmp_path / "parts" / "intro.md",
        '<script>print("hello")</script> <field>name</field>',
    )

    assert _parse(
        tmp_path,
        "<include>parts/intro.md</include>",
        tool=SimpleNamespace(name="tool"),
    ) == _wrap(intro, "hello tool")


def test_missing_include_raises_file_not_found(tmp_path: Path) -> None:
    """Raise ``FileNotFoundError`` when an included file is missing."""
    with pytest.raises(FileNotFoundError):
        _parse(tmp_path, "<include>missing.md</include>")


def test_include_cycle_raises_value_error(tmp_path: Path) -> None:
    """Raise ``ValueError`` when includes form a cycle."""
    _write(tmp_path / "a.md", "<include>b.md</include>")
    _write(tmp_path / "b.md", "<include>a.md</include>")

    with pytest.raises(ValueError, match="<include> cycle detected"):
        DynamicMarkdownFile(tmp_path / "a.md")


def test_bare_include_resolves_relative_to_the_including_files_directory(
    tmp_path: Path,
) -> None:
    """Replace a bare ``@path`` include relative to the including file."""
    intro = _write(tmp_path / "parts" / "intro.md", "included")

    assert _parse(tmp_path, "before @parts/intro.md after") == (
        f"before {_wrap(intro, 'included')} after"
    )


def test_bare_include_supports_dot_and_dotdot_relative_paths(tmp_path: Path) -> None:
    """Resolve ``./`` and ``../`` bare includes against the including file."""
    top = _write(tmp_path / "top.md", "top")
    sibling = _write(tmp_path / "nested" / "sibling.md", "sibling")
    child = _write(
        tmp_path / "nested" / "child.md",
        "start @./sibling.md then @../top.md end",
    )

    assert _parse(tmp_path, "<include>nested/child.md</include>") == _wrap(
        child,
        f"start {_wrap(sibling, 'sibling')} then {_wrap(top, 'top')} end",
    )


def test_bare_include_with_leading_slash_resolves_as_absolute_path(
    tmp_path: Path,
) -> None:
    """Resolve a bare include starting with ``/`` as an absolute path."""
    target = _write(tmp_path / "notes.md", "note")

    assert _parse(tmp_path, f"before @{target} after") == (
        f"before {_wrap(target, 'note')} after"
    )


def test_bare_include_falls_back_to_literal_text_when_target_is_missing(
    tmp_path: Path,
) -> None:
    """Leave a bare ``@`` token unchanged when it does not resolve to a file."""
    assert _parse(tmp_path, "reach me at user@example.com for details") == (
        "reach me at user@example.com for details"
    )


def test_bare_include_recursively_parses_included_content(tmp_path: Path) -> None:
    """Expand tags inside content included via the bare ``@path`` syntax."""
    intro = _write(
        tmp_path / "parts" / "intro.md",
        '<script>print("hello")</script> <field>name</field>',
    )

    assert _parse(
        tmp_path, "@parts/intro.md", tool=SimpleNamespace(name="tool")
    ) == _wrap(intro, "hello tool")


def test_bare_include_does_not_raise_for_missing_target_unlike_include_tag(
    tmp_path: Path,
) -> None:
    """Contrast the strict ``<include>`` tag with the bare form's fallback."""
    with pytest.raises(FileNotFoundError):
        _parse(tmp_path, "<include>missing.md</include>")

    assert _parse(tmp_path, "@missing.md") == "@missing.md"


def test_include_cycle_raises_value_error_when_mixing_tag_and_bare_syntax(
    tmp_path: Path,
) -> None:
    """Raise ``ValueError`` for a cycle formed across both include syntaxes."""
    _write(tmp_path / "a.md", "<include>b.md</include>")
    _write(tmp_path / "b.md", "@a.md")

    with pytest.raises(ValueError, match="<include> cycle detected"):
        DynamicMarkdownFile(tmp_path / "a.md")


def test_existing_python_script_path_runs_as_file(tmp_path: Path) -> None:
    """Run an existing ``.py`` script path as a file."""
    _write(tmp_path / "data.txt", "from cwd")
    _write(
        tmp_path / "scripts" / "read_data.py",
        'from pathlib import Path\nprint(Path("data.txt").read_text())\n',
    )

    assert _parse(tmp_path, "<script>scripts/read_data.py</script>") == "from cwd"


def test_existing_non_python_script_path_runs_as_file(tmp_path: Path) -> None:
    """Run an existing non-``.py`` script path as a Python file."""
    _write(tmp_path / "scripts" / "runner", 'print("from file")\n')

    assert _parse(tmp_path, "<script> scripts/runner </script>") == "from file"


def test_included_files_script_tag_resolves_relative_to_its_own_directory(
    tmp_path: Path,
) -> None:
    """Resolve an included file's script path and cwd against its own directory."""
    _write(tmp_path / "data.txt", "top-level data")
    _write(tmp_path / "parts" / "data.txt", "nested data")
    _write(
        tmp_path / "parts" / "read_data.py",
        'from pathlib import Path\nprint(Path("data.txt").read_text())\n',
    )
    report = _write(tmp_path / "parts" / "report.md", "<script>read_data.py</script>")

    assert _parse(tmp_path, "<include>parts/report.md</include>") == _wrap(
        report, "nested data"
    )


def test_missing_python_script_path_raises_called_process_error(tmp_path: Path) -> None:
    """Raise ``CalledProcessError`` for missing file-backed Python scripts."""
    with pytest.raises(subprocess.CalledProcessError):
        _parse(tmp_path, "<script>scripts/missing.py</script>")


def test_inline_one_line_python_script_runs(tmp_path: Path) -> None:
    """Run one-line inline Python code."""
    assert _parse(tmp_path, '<script>print("inline")</script>') == "inline"


def test_inline_multiline_python_script_runs(tmp_path: Path) -> None:
    """Run multiline inline Python code."""
    content = """<script>
for value in ["a", "b"]:
    print(value)
</script>"""

    assert _parse(tmp_path, content) == "a\nb"


def test_invalid_inline_script_raises_called_process_error(tmp_path: Path) -> None:
    """Raise ``CalledProcessError`` for invalid inline Python code."""
    with pytest.raises(subprocess.CalledProcessError):
        _parse(tmp_path, "<script>not python text</script>")


def test_runtime_error_in_inline_script_raises_called_process_error(
    tmp_path: Path,
) -> None:
    """Raise ``CalledProcessError`` when inline Python exits with an error."""
    with pytest.raises(subprocess.CalledProcessError):
        _parse(tmp_path, '<script>raise ValueError("bad")</script>')


def test_script_stdout_replaces_tag_and_trailing_newline_is_stripped(
    tmp_path: Path,
) -> None:
    """Replace script tags with stdout and strip the trailing newline."""
    assert _parse(tmp_path, '<script>print("value")</script>') == "value"


def test_fields_are_expanded_inside_script_source_before_execution(
    tmp_path: Path,
) -> None:
    """Expand field tags inside script source before executing scripts."""
    assert (
        _parse(
            tmp_path,
            '<script>print("<field>name</field>")</script>',
            tool=SimpleNamespace(name="tool"),
        )
        == "tool"
    )


def test_script_output_field_tags_are_not_reparsed(tmp_path: Path) -> None:
    """Leave field tags dynamically emitted by script output unchanged."""
    assert (
        _parse(
            tmp_path,
            '<script>print("<" + "field>name</" + "field>")</script>',
            tool=SimpleNamespace(name="tool"),
        )
        == "<field>name</field>"
    )


def test_includes_inside_script_source_are_expanded_before_execution(
    tmp_path: Path,
) -> None:
    """Expand literal includes inside script source before executing scripts."""
    _write(tmp_path / "part.md", "included")

    assert (
        _parse(
            tmp_path,
            '<script>print("<include>part.md</include>")</script>',
        )
        == "included"
    )


def test_included_script_source_is_parsed_before_execution(tmp_path: Path) -> None:
    """Parse included script source before executing the assembled script."""
    _write(tmp_path / "scripts" / "body.py", 'print("<field>name</field>")')

    assert (
        _parse(
            tmp_path,
            "<script><include>scripts/body.py</include></script>",
            tool=SimpleNamespace(name="tool"),
        )
        == "tool"
    )


def test_script_output_include_tags_are_not_reparsed(tmp_path: Path) -> None:
    """Leave include tags dynamically emitted by script output unchanged."""
    _write(tmp_path / "part.md", "included")

    assert (
        _parse(
            tmp_path,
            '<script>print("<" + "include>part.md</" + "include>")</script>',
        )
        == "<include>part.md</include>"
    )


def test_field_output_script_tags_are_executed_but_include_tags_are_not(
    tmp_path: Path,
) -> None:
    """Execute script tags emitted by field output after the include pass."""
    _write(tmp_path / "part.md", "included")
    tool = SimpleNamespace(
        value='<script>print("x")</script><include>part.md</include>'
    )

    assert _parse(tmp_path, "<field>value</field>", tool=tool) == (
        "x<include>part.md</include>"
    )
