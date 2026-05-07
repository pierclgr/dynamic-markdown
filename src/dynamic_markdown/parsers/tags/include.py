"""Parser for dynamic-markdown include tags."""

import re
from pathlib import Path
from typing import ClassVar

from dynamic_markdown.parsers.tags.base import TagParser


class IncludeTagParser(TagParser):
    """Resolve ``<include>relative/path</include>`` tags.

    Each match is replaced with the parsed content of the referenced file. ``<include>``
    cycles are detected against the ``visited`` chain and raise :class:`ValueError`.
    """

    _pattern: ClassVar[re.Pattern[str]] = re.compile(
        r"<include>(.*?)</include>", re.DOTALL
    )

    @staticmethod
    def _replace(
        match: re.Match[str],
        base_dir: Path,
        field_source: object | None,
        visited: tuple[Path, ...],
    ) -> str:
        """Substitute one include tag with the parsed file content.

        Args:
            match: the regex match for an include tag.
            base_dir: directory used to resolve the include target.
            field_source: object whose attributes back field tags in
                included files.
            visited: resolved include paths already active in the
                current parse chain.

        Returns:
            The parsed content of the referenced file.

        Raises:
            ValueError: when the include target is already in the
                ``visited`` chain, indicating a cycle.
        """
        from dynamic_markdown.parsers.files.base import DynamicMarkdownFileParser
        from dynamic_markdown.types.files.base import DynamicMarkdownFile

        target = (base_dir / match.group(1).strip()).resolve()
        if target in visited:
            chain = " -> ".join(str(p) for p in (*visited, target))
            raise ValueError(f"<include> cycle detected: {chain}")
        included = DynamicMarkdownFile(target)
        return DynamicMarkdownFileParser.parse(
            file=included,
            base_dir=base_dir,
            field_source=field_source,
            _visited=visited,
        )
