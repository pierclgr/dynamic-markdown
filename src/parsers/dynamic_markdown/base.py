"""Parser for the harness dynamic-markdown language."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from src.parsers.base import Parser
from src.parsers.dynamic_markdown.tags.field import FieldTagParser
from src.parsers.dynamic_markdown.tags.include import IncludeTagParser
from src.parsers.dynamic_markdown.tags.script import ScriptTagParser

if TYPE_CHECKING:
    from src.types.dynamic_markdown.file import DynamicMarkdownFile


class DynamicMarkdownParser(Parser):
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

    Tags are resolved in the order ``<include>`` then ``<script>`` then
    ``<field>``. Includes recurse through :meth:`parse` so an included
    file may use any of the three tags itself; scripts and fields are
    resolved in a single pass and their substituted text is **not**
    re-parsed. ``<include>`` paths and file-backed ``<script>`` tags
    are resolved against the caller-supplied ``base_dir``, which is
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
        content = cls._script_tag_parser.parse(content, base_dir=base_dir)
        content = cls._field_tag_parser.parse(content, field_source=field_source)
        return content
