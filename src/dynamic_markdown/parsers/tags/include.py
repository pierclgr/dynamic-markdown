"""Parser for dynamic-markdown include tags."""

import re
from pathlib import Path
from typing import ClassVar

from dynamic_markdown.parsers.tags.base import TagParser
from dynamic_markdown.parsers.tags.script import ScriptTagParser


class IncludeTagParser(TagParser):
    """Resolve ``<include>path</include>`` tags and bare ``@path`` includes.

    A match on a file is replaced with the parsed content of that file. A match on a
    directory is replaced with a listing of its direct children instead, one entry per
    line, sorted by name, hidden entries included and subdirectories suffixed with
    ``/``; the listed files are neither read nor parsed, so a listing can never form an
    include cycle. Either replacement is wrapped on its own lines between a horizontal
    rule and an HTML comment noting the absolute path it came from (``<!-- Included from
    /abs/path.md -->`` for a file, ``<!-- Content of directory /abs/dir -->`` for a
    directory), followed by a closing horizontal rule. The comment form keeps the note
    unambiguously separate from the included content itself (an HTML comment can never
    be mistaken for prose). The wrapper is suppressed for a match that falls inside a
    ``<script>...</script>`` span, since there the included text becomes literal script
    source rather than rendered markdown, and the wrapper text would break execution. A
    path starting with ``/`` is resolved as an absolute path; any other path (including
    ``./`` and ``../`` forms) is resolved against the directory of the markdown file
    that contains the tag. ``<include>`` is strict: a missing target raises
    :class:`FileNotFoundError`. The bare ``@path`` form is only recognized when the
    resolved path is an existing file or directory; otherwise the matched text is left
    unchanged, so ordinary text containing ``@`` (e.g. an email address) passes through
    as-is. Both forms share the same cycle detection against the ``visited`` chain and
    raise :class:`ValueError` when mixed across files to form a cycle.
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
        """Substitute one include match with its file content or directory listing.

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
            The parsed content of the referenced file, the listing of the
            referenced directory's direct children, or, for a bare
            ``@path`` that resolves to neither an existing file nor an
            existing directory, the original matched text unchanged.
            Unless the match falls inside a ``<script>`` span, the
            content is wrapped in a horizontal rule and an HTML comment
            naming the absolute source path.

        Raises:
            ValueError: when the include target is already in the
                ``visited`` chain, indicating a cycle.
        """
        from dynamic_markdown.types.files.base import DynamicMarkdownFile

        tag_path = match.group(1)
        strict = tag_path is not None
        raw_path = tag_path.strip() if strict else match.group(2)
        target = (current_dir / raw_path).resolve()

        if not strict and not (target.is_file() or target.is_dir()):
            return match.group(0)

        if target.is_dir():
            note = f"<!-- Content of directory {target} -->"
            content = "\n".join(
                f"{entry.name}/" if entry.is_dir() else entry.name
                for entry in sorted(target.iterdir())
            )
        else:
            if target in visited:
                chain = " -> ".join(str(p) for p in (*visited, target))
                raise ValueError(f"<include> cycle detected: {chain}")
            note = f"<!-- Included from {target} -->"
            content = DynamicMarkdownFile(
                target, tool=field_source, _visited=visited
            ).content

        in_script = any(start <= match.start() < end for start, end in script_spans)
        if in_script:
            return content
        return f"___\n{note}\n{content}\n___"
