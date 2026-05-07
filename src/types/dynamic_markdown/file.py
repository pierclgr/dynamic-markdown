"""Dynamic markdown file type."""

from __future__ import annotations

from pathlib import Path

from src.parsers.dynamic_markdown.base import DynamicMarkdownParser


class DynamicMarkdownFile:
    """A markdown-like file with dynamic parsing.

    Attributes:
        path: filesystem path the file was loaded from. Used by the
            parser to seed the ``<include>`` cycle-detection chain.
        raw: raw text content of the file as read from disk.
    """

    _parser: type[DynamicMarkdownParser] = DynamicMarkdownParser

    def __init__(self, path: Path | str) -> None:
        """Initialize the file with its raw text content.

        Args:
            path: filesystem path of the file to load.
        """
        if not isinstance(path, Path):
            path = Path(path)
        self.path: Path = path
        self.raw: str = path.read_text()

    def content(
        self,
        base_dir: Path | str,
        tool: object | None = None,
    ) -> str:
        """Parse the raw content and return the fully expanded text.

        Resolves ``<include>``, ``<script>`` and ``<field>`` tags in
        :attr:`raw`. ``<include>`` and file-backed ``<script>`` targets
        are resolved against ``base_dir``. ``<field>`` tags are
        replaced with ``str(getattr(tool, name))``.

        Args:
            base_dir: directory under which relative ``<include>`` and
                file-backed ``<script>`` targets are searched.
            tool: object whose attributes back ``<field>`` tags. May
                be ``None`` when :attr:`raw` contains no ``<field>``
                tag.

        Returns:
            The fully expanded text.

        Tag-specific errors from the parser are allowed to propagate.
        """
        return self._parser.parse(
            file=self,
            base_dir=base_dir,
            field_source=tool,
        )
