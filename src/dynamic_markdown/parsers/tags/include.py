"""Parser for dynamic-markdown include tags."""

import re
from pathlib import Path
from typing import ClassVar

from dynamic_markdown.parsers.tags.base import TagParser


class IncludeTagParser(TagParser):
    """Resolve ``<include>path</include>`` tags and bare ``@path`` includes.

    Each match is replaced with the parsed content of the referenced file. A path
    starting with ``/`` is resolved as an absolute path; any other path (including
    ``./`` and ``../`` forms) is resolved against the directory of the markdown file
    that contains the tag. ``<include>`` is strict: a missing target raises
    :class:`FileNotFoundError`. The bare ``@path`` form is only recognized when the
    resolved path is an existing file; otherwise the matched text is left unchanged, so
    ordinary text containing ``@`` (e.g. an email address) passes through as-is. Both
    forms share the same cycle detection against the ``visited`` chain and raise
    :class:`ValueError` when mixed across files to form a cycle.
    """

    _pattern: ClassVar[re.Pattern[str]] = re.compile(
        r"<include>(.*?)</include>|@(\S+)", re.DOTALL
    )

    @staticmethod
    def _replace(
        match: re.Match[str],
        current_dir: Path,
        field_source: object | None,
        visited: tuple[Path, ...],
    ) -> str:
        """Substitute one include match with the parsed file content.

        Args:
            match: the regex match for an ``<include>`` tag or a bare
                ``@path``.
            current_dir: directory of the markdown file containing the
                match, used to resolve relative include targets.
            field_source: object whose attributes back field tags in
                included files.
            visited: resolved include paths already active in the
                current parse chain.

        Returns:
            The parsed content of the referenced file, or, for a bare
            ``@path`` that does not resolve to an existing file, the
            original matched text unchanged.

        Raises:
            ValueError: when the include target is already in the
                ``visited`` chain, indicating a cycle.
        """
        from dynamic_markdown.parsers.files.base import DynamicMarkdownFileParser
        from dynamic_markdown.types.files.base import DynamicMarkdownFile

        tag_path = match.group(1)
        strict = tag_path is not None
        raw_path = tag_path.strip() if strict else match.group(2)
        target = (current_dir / raw_path).resolve()

        if not strict and not target.is_file():
            return match.group(0)

        if target in visited:
            chain = " -> ".join(str(p) for p in (*visited, target))
            raise ValueError(f"<include> cycle detected: {chain}")
        included = DynamicMarkdownFile(target)
        return DynamicMarkdownFileParser.parse(
            file=included,
            field_source=field_source,
            _visited=visited,
        )
