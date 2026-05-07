"""Base parser for dynamic-markdown tag substitutions."""

import re
from abc import ABC, abstractmethod
from typing import ClassVar

from dynamic_markdown.parsers.base import Parser


class TagParser(Parser, ABC):
    """Abstract base for parsers handling a single dynamic-markdown tag.

    Subclasses set :attr:`_PATTERN` to the regex matching their tag and implement
    :meth:`_replace` with the per-match substitution logic. The concrete :meth:`parse`
    method walks ``content`` and replaces every match using :meth:`_replace`.
    """

    _pattern: ClassVar[re.Pattern[str]]

    @classmethod
    def parse(cls, content: str, **kwargs) -> str:
        """Substitute every match of :attr:`_PATTERN` via :meth:`_replace`.

        Args:
            content: text in which to substitute tags.
            **kwargs: tag-specific context forwarded to
                :meth:`_replace`.

        Returns:
            ``content`` with every match of :attr:`_PATTERN` replaced.
        """
        return cls._pattern.sub(lambda m: cls._replace(m, **kwargs), content)

    @staticmethod
    @abstractmethod
    def _replace(match: re.Match[str], **kwargs) -> str:
        """Compute the substitution string for a single match.

        Args:
            match: the regex match for a single tag occurrence.
            **kwargs: tag-specific context supplied by :meth:`parse`.

        Returns:
            The text to substitute in place of the matched tag.

        Raises:
            NotImplementedError: when not implemented by a subclass.
        """
        raise NotImplementedError("Subclasses must implement this method.")
