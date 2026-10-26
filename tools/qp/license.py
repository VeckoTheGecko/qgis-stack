"""Work out a plugin's SPDX licence from the LICENSE file in its ZIP.

Fails closed: anything not recognised raises LicenseError, to be resolved with a
`license` override in plugins.toml (M2).
"""

import io
import re
import zipfile


class LicenseError(ValueError):
    pass


_OR_LATER = re.compile(r"\bor\s*(?:\(at\s+your\s+option\)\s*)?any\s+later\s+version", re.I)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def _norm_source(text: str) -> str:
    """Source text with comment markers (# and the * of /* */ blocks) removed, so a
    licence header wrapped over comment lines reads as one sentence."""
    return _norm(re.sub(r"[#*]", " ", text))


def _family(text: str) -> str | None:
    """SPDX id of the licence text, without -only/-or-later for the GPL family."""
    text = _norm(text)
    if "GNU GENERAL PUBLIC LICENSE" in text.upper():
        if re.search(r"Version 3, 29 June 2007", text, re.I):
            return "GPL-3.0"
        if re.search(r"Version 2, June 1991", text, re.I):
            return "GPL-2.0"
    if "Permission is hereby granted, free of charge" in text:
        return "MIT"
    return None


def detect(data: bytes, slug: str) -> str:
    """SPDX licence of the plugin. GPL licences are "-or-later" when the plugin's own
    sources say "any later version" (the LICENSE text alone can't tell)."""
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
        license_name = f"{slug}/LICENSE"
        if license_name not in names:
            raise LicenseError(f"{slug}: no {license_name} in the ZIP")
        family = _family(zf.read(license_name).decode("utf-8", errors="replace"))
        if family is None:
            raise LicenseError(f"{slug}: licence text not recognised")
        if not family.startswith("GPL-"):
            return family
        or_later = any(
            _OR_LATER.search(_norm_source(zf.read(n).decode("utf-8", errors="replace")))
            for n in names
            if n.endswith(".py")
        )
    return f"{family}-or-later" if or_later else f"{family}-only"
