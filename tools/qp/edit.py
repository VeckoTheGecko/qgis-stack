"""Edit plugins.toml as text, so comments and layout survive."""

import re
from pathlib import Path

_TABLE = re.compile(r"^\[plugins\.([A-Za-z0-9_-]+)\]\s*$", re.M)


def add_plugin(path: Path, slug: str) -> bool:
    """Insert an empty `[plugins.<slug>]` table in sorted (case-insensitive) position.
    Returns False if the plugin is already there."""
    text = path.read_text()
    tables = list(_TABLE.finditer(text))
    if any(m.group(1) == slug for m in tables):
        return False
    block = f"[plugins.{slug}]\n"
    after = next((m for m in tables if m.group(1).lower() > slug.lower()), None)
    if after is None:
        text = text.rstrip("\n") + "\n\n" + block
    else:
        # Before the next table's header, and the comment lines directly above it.
        start = after.start()
        while True:
            prev_end = text.rfind("\n", 0, start - 1) + 1
            if start == 0 or not text[prev_end:start].lstrip().startswith("#"):
                break
            start = prev_end
        text = text[:start] + block + "\n" + text[start:]
    path.write_text(text)
    return True
