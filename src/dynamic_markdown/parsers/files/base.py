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
      included file are themselves expanded.
    - ``<script>relative/script.py</script>`` is replaced with the
      captured stdout of running the referenced script via
      ``sys.executable``.
    - ``<script>print("hello")</script>`` is replaced with the
      captured stdout of running the inline Python code via
      ``sys.executable -c``.
    - ``<field>name</field>`` is replaced with
      ``str(getattr(field_source, name))``.

    Tags are resolved in the order ``<include>`` then ``<field>`` then
    ``<script>``. Includes recurse through :meth:`parse` so an included
    file may use any of the three tags itself. Field tags are resolved
    before scripts so field values may be used in inline script source.
    Script output is final and is not parsed again for dynamic-markdown
    tags. ``<include>`` paths and file-backed ``<script>`` tags are
    resolved against the caller-supplied ``base_dir``, which is
    propagated unchanged through nested includes. ``<include>`` cycles
    are detected and raise :class:`ValueError`.
    """

    _include_tag_parser: type[IncludeTagParser] = IncludeTagParser
    _script_tag_parser: type[ScriptTagParser] = ScriptTagParser
    _field_tag_parser: type[FieldTagParser] = FieldTagParser

    @classmethod
    def parse(
        cls,
        file: "DynamicMarkdownFile",
        base_dir: Path | str,
        field_source: object | None = None,
        _visited: tuple[Path, ...] = (),
    ) -> str:
        """Parse ``file.raw`` and return the expanded text.

        Args:
            file: the markdown-like file whose ``raw`` content is parsed.
            base_dir: directory under which relative ``<include>`` and
                file-backed ``<script>`` targets are resolved.
                Propagated unchanged through nested includes.
            field_source: object whose attributes back ``<field>``
                tags. When ``None`` the parser still runs, but any
                ``<field>`` tag present raises :class:`ValueError`.
            _visited: internal chain of resolved file paths currently
                being parsed, used to detect ``<include>`` cycles.
                Callers should not pass this argument.

        Returns:
            The fully expanded text with all three tag types resolved.

        Tag-specific errors from include, script, and field parsers
        are allowed to propagate.
        """
        base_dir = Path(base_dir)
        visited = _visited + (file.path.resolve(),)

        content = cls._include_tag_parser.parse(
            file.raw,
            base_dir=base_dir,
            field_source=field_source,
            visited=visited,
        )
        content = cls._field_tag_parser.parse(content, field_source=field_source)
        content = cls._script_tag_parser.parse(content, base_dir=base_dir)
        return content
