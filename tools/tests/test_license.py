import pytest
from conftest import GPL2, GPL3, MIT, OR_LATER_HEADER, plugin_zip

from qp.license import LicenseError, detect


def test_gpl2_or_later_from_comment_block(demo_zip):
    assert detect(demo_zip, "demo") == "GPL-2.0-or-later"


@pytest.mark.parametrize(
    ("text", "source", "expected"),
    [
        (GPL2, "x = 1\n", "GPL-2.0-only"),
        (GPL3, "# or (at your option) any later version.\n", "GPL-3.0-or-later"),
        (GPL3, "x = 1\n", "GPL-3.0-only"),
        (MIT, OR_LATER_HEADER, "MIT"),
    ],
)
def test_detect(text, source, expected):
    data = plugin_zip("demo", {"LICENSE": text, "main.py": source})
    assert detect(data, "demo") == expected


def test_missing_license():
    with pytest.raises(LicenseError, match="no demo/LICENSE"):
        detect(plugin_zip("demo", {"main.py": ""}), "demo")


def test_unknown_license():
    with pytest.raises(LicenseError, match="not recognised"):
        detect(plugin_zip("demo", {"LICENSE": "All rights reserved."}), "demo")
