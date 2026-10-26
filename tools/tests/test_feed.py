from qp import feed

XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<plugins>
  <pyqgis_plugin name="Demo" version="1.0" plugin_id="7">
    <download_url>https://plugins.qgis.org/plugins/demo/version/1.0/download/</download_url>
    <experimental>False</experimental><deprecated>False</deprecated>
  </pyqgis_plugin>
  <pyqgis_plugin name="Demo" version="2.0-beta" plugin_id="7">
    <download_url>https://plugins.qgis.org/plugins/demo/version/2.0-beta/download/</download_url>
    <experimental>True</experimental><deprecated>False</deprecated>
  </pyqgis_plugin>
  <pyqgis_plugin name="Other" version="3" plugin_id="8">
    <download_url>https://plugins.qgis.org/plugins/Other_Plugin/version/3/download/</download_url>
    <experimental>False</experimental><deprecated>True</deprecated>
  </pyqgis_plugin>
  <pyqgis_plugin name="Broken" version="1" plugin_id="9">
    <download_url>https://example.org/elsewhere.zip</download_url>
  </pyqgis_plugin>
</plugins>
"""


def test_parse():
    entries = feed.parse(XML)
    assert [(e.slug, e.version) for e in entries] == [
        ("demo", "1.0"),
        ("demo", "2.0-beta"),
        ("Other_Plugin", "3"),  # slug from the download URL, not the display name
    ]
    assert entries[0].plugin_id == "7"
    assert entries[1].experimental
    assert entries[2].deprecated


def test_versions_dedupes_across_feeds_and_skips_experimental():
    entries = feed.parse(XML) + feed.parse(XML)  # e.g. the 3.40 and 4.2 feeds
    assert [e.version for e in feed.versions(entries, "demo")] == ["1.0"]
    assert [e.version for e in feed.versions(entries, "demo", include_experimental=True)] == [
        "1.0",
        "2.0-beta",
    ]
    assert feed.versions(entries, "missing") == []


def test_load_reads_cache(tmp_path):
    path = feed.feed_path("4.2", tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(XML)
    assert len(feed.load(["4.2"], tmp_path)) == 3
