"""Parser for dynamic-markdown script tags."""

import re
import subprocess
import sys
from pathlib import Path
from typing import ClassVar

from src.parsers.dynamic_markdown.tags.base import TagParser


class ScriptTagParser(TagParser):
    """Resolve ``<script>...</script>`` tags.

    Each match is replaced with the captured stdout of running either a referenced
    script file via ``sys.executable`` or inline Python code via ``sys.executable -c``.
    """

    _pattern: ClassVar[re.Pattern[str]] = re.compile(
        r"<script>(.*?)</script>", re.DOTALL
    )

    @staticmethod
    def _replace(match: re.Match[str], base_dir: Path) -> str:
        """Substitute one script tag with the script's stdout.

        Args:
            match: the regex match for a script tag.
            base_dir: directory used to resolve script file targets and
                run scripts.

        Returns:
            The script's stdout with a single trailing newline
            stripped.
        """
        script = match.group(1).strip()
        target = (base_dir / script).resolve()
        command = [sys.executable, "-c", script]
        if target.is_file() or Path(script).suffix == ".py":
            command = [sys.executable, str(target)]

        result = subprocess.run(
            command,
            cwd=base_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.rstrip("\n")
