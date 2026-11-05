import json

from qp import catalogue, config
from qp.channel import Record
from qp.cli import main

CONFIG = config.parse(
    {
        "settings": {"feed_lines": ["4.2"], "test_lines": ["4.2"]},
        "plugins": {"QuickOSM": {}, "demo": {"name": "qgis-stack-demo2"}},
    }
)


def record(name, version, build_number=0, depends=("qgis >=3.40.0,<=4.99.99",)):
    return Record(name, version, build_number, list(depends), "GPL-2.0-or-later")


def test_newest_version_by_conda_ordering():
    records = [
        record("qgis-stack-quickosm", "2.10.0"),
        record("qgis-stack-quickosm", "2.9.1"),
        record("qgis-stack-quickosm", "2.10.0", 1, ["qgis >=3.40.0,<=4.99.99", "pandas"]),
    ]
    [entry] = catalogue.entries(records, CONFIG)
    assert entry["version"] == "2.10.0"  # not "2.9.1", as a string sort would say
    assert entry["build_number"] == 1
    assert entry["versions"] == ["2.10.0", "2.9.1"]
    assert entry["qgis"] == ">=3.40.0,<=4.99.99"
    assert entry["depends"] == ["pandas"]
    assert entry["slug"] == "QuickOSM"
    assert entry["url"] == "https://plugins.qgis.org/plugins/QuickOSM/"


def test_name_override_and_unknown_package():
    records = [record("qgis-stack-demo2", "1.0"), record("qgis-stack-gone", "1.0")]
    by_name = {e["name"]: e for e in catalogue.entries(records, CONFIG)}
    assert by_name["qgis-stack-demo2"]["slug"] == "demo"
    assert by_name["qgis-stack-gone"]["slug"] is None  # published, no longer selected
    assert by_name["qgis-stack-gone"]["url"] is None


def test_cli_writes_json(tmp_path):
    cfg = tmp_path / "plugins.toml"
    cfg.write_text('[settings]\nfeed_lines = ["4.2"]\ntest_lines = ["4.2"]\n[plugins.demo]\n')
    out = tmp_path / "data" / "plugins.json"
    channel = tmp_path / "channel"  # doesn't exist yet: nothing published
    argv = ["--config", str(cfg), "catalogue", "--channel", str(channel), "-o", str(out)]
    assert main(argv) == 0
    assert json.loads(out.read_text()) == []


def test_cli_needs_a_channel(tmp_path, capsys):
    cfg = tmp_path / "plugins.toml"
    cfg.write_text('[settings]\nfeed_lines = ["4.2"]\ntest_lines = ["4.2"]\n')
    assert main(["--config", str(cfg), "catalogue"]) == 1
    assert "no channel" in capsys.readouterr().err
