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
        raw: raw text content of the file as read from disk.
        content: cached parsed content, if the file has been parsed.
    """

    _parser: type[DynamicMarkdownFileParser] = DynamicMarkdownFileParser

    def __init__(self, path: Path | str) -> None:
        """Initialize the file with its raw text content.

        Args:
            path: filesystem path of the file to load.
        """
        if not isinstance(path, Path):
            path = Path(path)
        self.path: Path = path
        self.raw: str = path.read_text()
        self.content: str | None = None

    def parse(
        self,
        tool: object | None = None,
    ) -> None:
        """Parse and expand raw content, then caches it.

        Resolves ``<include>``/``@path``, ``<script>`` and ``<field>``
        tags in :attr:`raw`. A path starting with ``/`` resolves as an
        absolute path; any other ``<include>``/``@path`` target and
        file-backed ``<script>`` target resolves against :attr:`path`'s
        own directory. ``<field>`` tags are replaced with
        ``str(getattr(tool, name))``.

        Args:
            tool: object whose attributes back ``<field>`` tags. May
                be ``None`` when :attr:`raw` contains no ``<field>``
                tag.

        Tag-specific errors from the parser are allowed to propagate.
        """
        self.content = self._parser.parse(
            file=self,
            field_source=tool,
        )

    def reload(self) -> None:
        """Reload raw content from disk and clear cached parsed content."""
        self.raw = self.path.read_text()
        self.content = None
