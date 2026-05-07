"""Parser for dynamic-markdown script tags."""

import re
import subprocess
import sys
from pathlib import Path
from typing import ClassVar

from src.parsers.dynamic_markdown.tags.base import TagParser


class ScriptTagParser(TagParser):
    """Resolve ``<script>relative/script.py</script>`` tags.

    Each match is replaced with the captured stdout of running the script via
    ``sys.executable``.
    """

    _pattern: ClassVar[re.Pattern[str]] = re.compile(
        r"<script>(.*?)</script>", re.DOTALL
    )

    @staticmethod
    def _replace(match: re.Match[str], base_dir: Path) -> str:
        """Substitute one script tag with the script's stdout.

        Args:
            match: the regex match for a script tag.
            base_dir: directory used to resolve the script target and
                run the script.

        Returns:
            The script's stdout with a single trailing newline
            stripped.
        """
        target = (base_dir / match.group(1).strip()).resolve()
        result = subprocess.run(
            [sys.executable, str(target)],
            cwd=base_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.rstrip("\n")
