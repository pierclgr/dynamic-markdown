"""Parser for dynamic-markdown field tags."""

import re
from typing import ClassVar

from dynamic_markdown.parsers.tags.base import TagParser


class FieldTagParser(TagParser):
    """Resolve ``<field>name</field>`` tags.

    Each match is replaced with ``str(getattr(field_source, name))``.
    """

    _pattern: ClassVar[re.Pattern[str]] = re.compile(r"<field>(.*?)</field>", re.DOTALL)

    @staticmethod
    def _replace(match: re.Match[str], field_source: object | None) -> str:
        """Substitute one field tag with the resolved attribute value.

        Args:
            match: the regex match for a field tag.
            field_source: object whose attributes back field tags.

        Returns:
            ``str(getattr(field_source, name))`` where ``name`` is the
            tag's inner content, stripped.

        Raises:
            ValueError: when ``field_source`` is ``None``.
        """
        name = match.group(1).strip()
        if field_source is None:
            raise ValueError(
                f"<field>{name}</field> requires a field_source, but none was provided."
            )
        return str(getattr(field_source, name))
