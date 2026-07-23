"""Dynamic markdown file type."""

from __future__ import annotations

from pathlib import Path

from dynamic_markdown.parsers.files.base import DynamicMarkdownFileParser


class DynamicMarkdownFile:
    """A markdown-like file with dynamic parsing.

    Attributes:
        path: filesystem path the file was loaded from. Used by the
            parser to seed the ``<include>`` cycle-detection chain and
            as the anchor directory for relative include/script targets.
        raw: raw text content of the file as read from disk, refreshed
            on every load.
        content: parsed content of the file, refreshed on every load.
    """

    _parser: type[DynamicMarkdownFileParser] = DynamicMarkdownFileParser

    def __init__(
        self,
        path: Path | str,
        tool: object | None = None,
        _visited: tuple[Path, ...] = (),
    ) -> None:
        """Initialize the file, loading and parsing its content.

        Args:
            path: filesystem path of the file to load.
            tool: object whose attributes back ``<field>`` tags. May
                be ``None`` when the file's raw content contains no
                ``<field>`` tag.
            _visited: internal chain of resolved file paths already
                active in the current parse chain, used to detect
                ``<include>`` cycles. Callers should not pass this
                argument.
        """
        if not isinstance(path, Path):
            path = Path(path)
        self.path: Path = path
        self._visited = _visited
        self.load(tool=tool)

    def load(self, tool: object | None = None) -> None:
        """Read raw content from disk and parse it, caching the result.

        Resolves ``<include>``/``@path``, ``<script>`` and ``<field>``
        tags in the freshly read content. A path starting with ``/``
        resolves as an absolute path; any other ``<include>``/``@path``
        target and file-backed ``<script>`` target resolves against
        :attr:`path`'s own directory. ``<field>`` tags are replaced
        with ``str(getattr(tool, name))``.

        Args:
            tool: object whose attributes back ``<field>`` tags. May
                be ``None`` when the raw content contains no ``<field>``
                tag.

        Tag-specific errors from the parser are allowed to propagate.
        """
        self.raw: str = self.path.read_text()
        self.content: str = self._parser.parse(
            file=self,
            field_source=tool,
            _visited=self._visited,
        )

    reload = load
