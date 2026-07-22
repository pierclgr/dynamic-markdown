"""Parser for dynamic-markdown include tags."""

import re
from pathlib import Path
from typing import ClassVar

from dynamic_markdown.parsers.tags.base import TagParser
from dynamic_markdown.parsers.tags.script import ScriptTagParser


class IncludeTagParser(TagParser):
    """Resolve ``<include>path</include>`` tags and bare ``@path`` includes.

    Each match is replaced with the parsed content of the referenced file, wrapped on
    its own lines between a horizontal rule and an HTML comment noting the absolute path
    it was included from (e.g. ``<!-- Included from: /abs/path.md -->``), followed by a
    closing horizontal rule. The comment form keeps the note unambiguously separate from
    the included content itself (an HTML comment can never be mistaken for prose). The
    wrapper is suppressed for a match that falls inside a ``<script>...</script>`` span,
    since there the included text becomes literal script source rather than rendered
    markdown, and the wrapper text would break execution. A path starting with ``/`` is
    resolved as an absolute path; any other path (including ``./`` and ``../`` forms) is
    resolved against the directory of the markdown file that contains the tag.
    ``<include>`` is strict: a missing target raises :class:`FileNotFoundError`. The
    bare ``@path`` form is only recognized when the resolved path is an existing file;
    otherwise the matched text is left unchanged, so ordinary text containing ``@``
    (e.g. an email address) passes through as-is. Both forms share the same cycle
    detection against the ``visited`` chain and raise :class:`ValueError` when mixed
    across files to form a cycle.
    """

    _pattern: ClassVar[re.Pattern[str]] = re.compile(
        r"<include>(.*?)</include>|@(\S+)", re.DOTALL
    )

    @classmethod
    def parse(
        cls,
        content: str,
        current_dir: Path,
        field_source: object | None,
        visited: tuple[Path, ...],
    ) -> str:
        """Substitute every include match in ``content``.

        Args:
            content: text in which to substitute include tags.
            current_dir: directory of the markdown file containing
                ``content``, used to resolve relative include targets.
            field_source: object whose attributes back field tags in
                included files.
            visited: resolved include paths already active in the
                current parse chain.

        Returns:
            ``content`` with every include match replaced.
        """
        script_spans = [m.span() for m in ScriptTagParser._pattern.finditer(content)]
        return cls._pattern.sub(
            lambda m: cls._replace(
                m,
                current_dir=current_dir,
                field_source=field_source,
                visited=visited,
                script_spans=script_spans,
            ),
            content,
        )

    @staticmethod
    def _replace(
        match: re.Match[str],
        current_dir: Path,
        field_source: object | None,
        visited: tuple[Path, ...],
        script_spans: list[tuple[int, int]],
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
            script_spans: character spans of ``<script>`` tags found in
                the content being scanned, used to suppress the
                reference wrapper for includes used as script source.

        Returns:
            The parsed content of the referenced file, or, for a bare
            ``@path`` that does not resolve to an existing file, the
            original matched text unchanged. Unless the match falls
            inside a ``<script>`` span, the content is wrapped in a
            horizontal rule and an HTML comment naming the absolute
            source path.

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
        content = DynamicMarkdownFileParser.parse(
            file=included,
            field_source=field_source,
            _visited=visited,
        )

        in_script = any(start <= match.start() < end for start, end in script_spans)
        if in_script:
            return content
        return f"___\n<!-- Included from: {target} -->\n{content}\n___"
