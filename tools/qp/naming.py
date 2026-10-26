"""Conda package names for plugin slugs (docs/plan.md section 5.1)."""

import re

PREFIX = "qgis-plugin-"
SLUG_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")


def package_name(slug: str) -> str:
    """`qgis-plugin-<slug lowercased>`, keeping `_` and `-`.

    Only case is folded: plugins.qgis.org rejects new slugs that differ from an
    existing one only in case, so this mapping can't gain new collisions.
    """
    if not SLUG_RE.fullmatch(slug):
        raise ValueError(f"not a plugins.qgis.org slug: {slug!r}")
    return PREFIX + slug.lower()
