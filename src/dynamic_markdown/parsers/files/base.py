"""Parser for the harness dynamic-markdown language."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from dynamic_markdown.parsers.base import Parser
from dynamic_markdown.parsers.tags.field import FieldTagParser
from dynamic_markdown.parsers.tags.include import IncludeTagParser
from dynamic_markdown.parsers.tags.script import ScriptTagParser

if TYPE_CHECKING:
    from dynamic_markdown.types.files.base import DynamicMarkdownFile


class DynamicMarkdownFileParser(Parser):
    """Expand ``<include>``, ``<script>`` and ``<field>`` tags in dynamic markdown.

    Three special tag types are recognized:

    - ``<include>relative/path</include>`` is replaced with the parsed
      content of the referenced file, so nested tags inside the
      included file are themselves expanded. The replacement is
      wrapped in a horizontal rule and an HTML comment naming the
      absolute source path, unless the tag sits inside a ``<script>``
      span, where the wrapper is suppressed so the included text
      remains valid script source.
    - ``@relative/path`` is a bare alternative to ``<include>``: it is
      replaced the same way, including the reference wrapper, but only
      when the resolved path is an existing file. Otherwise the text
      is left unchanged, so ordinary ``@`` usage (e.g. an email
      address) passes through as-is.
    - ``<script>relative/script.py</script>`` is replaced with the
      captured stdout of running the referenced script via
      ``sys.executable``.
    - ``<script>print("hello")</script>`` is replaced with the
      captured stdout of running the inline Python code via
      ``sys.executable -c``.
    - ``<field>name</field>`` is replaced with
      ``str(getattr(field_source, name))``.

    Tags are resolved in the order ``<include>``/``@path`` then
    ``<field>`` then ``<script>``. Includes recurse through :meth:`parse`
    so an included file may use any of the tags itself. Field tags are
    resolved before scripts so field values may be used in inline script
    source. Script output is final and is not parsed again for
    dynamic-markdown tags. A path starting with ``/`` is resolved as an
    absolute path; any other path is resolved against the directory of
    the markdown file that currently contains the tag, re-derived fresh
    at every level of nested includes rather than propagated from the
    top-level caller. This applies to ``<include>``/``@path`` targets and
    to file-backed ``<script>`` targets and their working directory alike.
    ``<include>`` cycles are detected regardless of which include syntax
    formed them and raise :class:`ValueError`.
    """

    _include_tag_parser: type[IncludeTagParser] = IncludeTagParser
    _script_tag_parser: type[ScriptTagParser] = ScriptTagParser
    _field_tag_parser: type[FieldTagParser] = FieldTagParser

    @classmethod
    def parse(
        cls,
        file: "DynamicMarkdownFile",
        field_source: object | None = None,
        _visited: tuple[Path, ...] = (),
    ) -> str:
        """Parse ``file.raw`` and return the expanded text.

        Args:
            file: the markdown-like file whose ``raw`` content is parsed.
            field_source: object whose attributes back ``<field>``
                tags. When ``None`` the parser still runs, but any
                ``<field>`` tag present raises :class:`ValueError`.
            _visited: internal chain of resolved file paths currently
                being parsed, used to detect ``<include>`` cycles.
                Callers should not pass this argument.

        Returns:
            The fully expanded text with all tag types resolved.

        Tag-specific errors from include, script, and field parsers
        are allowed to propagate.
        """
        resolved_path = file.path.resolve()
        current_dir = resolved_path.parent
        visited = _visited + (resolved_path,)

        content = cls._include_tag_parser.parse(
            file.raw,
            current_dir=current_dir,
            field_source=field_source,
            visited=visited,
        )
        content = cls._field_tag_parser.parse(content, field_source=field_source)
        content = cls._script_tag_parser.parse(content, current_dir=current_dir)
        return content
