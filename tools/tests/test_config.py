import pytest

from qp import config
from qp.config import ConfigError, QgisRange

SETTINGS = '[settings]\nfeed_lines = ["4.2"]\ntest_lines = ["4.2"]\n'


def load(tmp_path, text: str) -> config.Config:
    path = tmp_path / "plugins.toml"
    path.write_text(SETTINGS + text)
    return config.load(path)


def test_overrides(tmp_path):
    cfg = load(
        tmp_path,
        """
[plugins.demo]
name = "qgis-plugin-demo2"
add_run = ["plotly", "pandas >=2"]
qgis = { min = "3.40", max = "3.99" }
version = { "1.0-beta" = "1.0b" }
license = "MIT"
build_number = 2
test.import = false
test.commands = ["python -c 'import plotly'"]
note = "from the README"

[plugins.other]
skip = "broken"
""",
    )
    demo = cfg.plugins["demo"]
    assert demo.name == "qgis-plugin-demo2"
    assert demo.add_run == ["plotly", "pandas >=2"]
    assert demo.qgis == QgisRange("3.40", "3.99")
    assert demo.version == {"1.0-beta": "1.0b"}
    assert (demo.license, demo.build_number, demo.test_import) == ("MIT", 2, False)
    assert demo.test_commands == ["python -c 'import plotly'"]
    assert cfg.plugins["other"].skip == "broken"
    assert cfg.order == ["demo", "other"]


def test_defaults(tmp_path):
    plugin = load(tmp_path, "[plugins.demo]\n").plugins["demo"]
    assert plugin == config.Plugin(slug="demo")


@pytest.mark.parametrize(
    ("table", "message"),
    [
        ("add_runs = []", "unknown keys add_runs"),
        ('add_run = "plotly"', "add_run: expected a list of strings"),
        ("add_run = [1]", "add_run: expected a list of strings"),
        ('build_number = "1"', "build_number: expected an int"),
        ("build_number = true", "build_number: expected an int"),
        ('qgis = { min = "3.40" }', "qgis: needs exactly min and max"),
        ("test.imports = false", "test: unknown keys imports"),
        ('test.import = "no"', "test.import: expected a bool"),
        ("version = { '1' = 1 }", "version.1: expected a string"),
    ],
)
def test_errors(tmp_path, table, message):
    with pytest.raises(ConfigError, match=message):
        load(tmp_path, f"[plugins.demo]\n{table}\n")


def test_select(tmp_path):
    cfg = load(tmp_path, "[plugins.a]\n[plugins.b]\n")
    assert cfg.select(None) == ["a", "b"]
    assert cfg.select(["b"]) == ["b"]
    with pytest.raises(ConfigError, match="not in plugins.toml: c"):
        cfg.select(["c"])
