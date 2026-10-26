import io
import zipfile

import pytest

GPL2 = """                    GNU GENERAL PUBLIC LICENSE
                       Version 2, June 1991
"""
GPL3 = """                    GNU GENERAL PUBLIC LICENSE
                       Version 3, 29 June 2007
"""
MIT = """Permission is hereby granted, free of charge, to any person obtaining a copy"""

OR_LATER_HEADER = '''"""
/***************************************************************************
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 ***************************************************************************/
"""
'''


def plugin_zip(slug: str, files: dict[str, str]) -> bytes:
    """A plugin ZIP with the given files under <slug>/."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, text in files.items():
            zf.writestr(f"{slug}/{name}", text)
    return buf.getvalue()


def metadata_txt(version="1.0", qgis_min="3.32", qgis_max: str | None = "4.99", **extra) -> str:
    lines = ["[general]", "name=Demo", f"version={version}", f"qgisMinimumVersion={qgis_min}"]
    if qgis_max is not None:
        lines.append(f"qgisMaximumVersion={qgis_max}")
    lines += ["description=A demo plugin", "description[de]=Ein Demo-Plugin"]
    lines += [f"{k}={v}" for k, v in extra.items()]
    return "\n".join(lines) + "\n"


@pytest.fixture
def demo_zip():
    return plugin_zip(
        "demo",
        {
            "metadata.txt": metadata_txt(
                homepage="https://example.org", repository="https://example.org/git"
            ),
            "LICENSE": GPL2,
            "__init__.py": OR_LATER_HEADER + "def classFactory(iface): ...\n",
        },
    )
