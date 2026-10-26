import pytest
from conftest import metadata_txt, plugin_zip

from qp import metadata
from qp.naming import package_name


@pytest.mark.parametrize(
    ("minimum", "maximum", "expected"),
    [
        ("3.32", "4.99", ("3.32.0", "4.99.99")),
        ("3.32.1", "3.40.2", ("3.32.1", "3.40.2")),
        ("3.4", None, ("3.4.0", "3.99.99")),  # empty max: <major of min>.99
        ("3.4", "  ", ("3.4.0", "3.99.99")),
        ("v3.16", "3.99", ("3.16.0", "3.99.99")),  # non-digits stripped, like QGIS
    ],
)
def test_qgis_range(minimum, maximum, expected):
    assert metadata.qgis_range(minimum, maximum) == expected


def test_read(demo_zip):
    meta = metadata.read(demo_zip, "demo")
    assert meta.version == "1.0"
    assert (meta.qgis_min, meta.qgis_max) == ("3.32.0", "4.99.99")
    assert meta.description == "A demo plugin"
    assert meta.homepage == "https://example.org"


def test_read_bom_and_no_max():
    data = plugin_zip("demo", {"metadata.txt": "﻿" + metadata_txt(qgis_max=None)})
    assert metadata.read(data, "demo").qgis_max == "3.99.99"


@pytest.mark.parametrize(
    ("slug", "name"),
    [
        ("quick_map_services", "qgis-plugin-quick_map_services"),
        ("QuickOSM", "qgis-plugin-quickosm"),
        ("profile-manager", "qgis-plugin-profile-manager"),
        ("profile_manager", "qgis-plugin-profile_manager"),  # no collision with the above
    ],
)
def test_package_name(slug, name):
    assert package_name(slug) == name


@pytest.mark.parametrize("slug", ["", "1plugin", "has space", "dots.in.slug"])
def test_package_name_rejects(slug):
    with pytest.raises(ValueError):
        package_name(slug)
