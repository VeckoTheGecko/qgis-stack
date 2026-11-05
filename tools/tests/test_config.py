import json
from pathlib import Path

import pytest

from qp import config
from qp.config import ConfigError, QgisRange, TestOptions

ROOT = Path(__file__).parents[2]
SETTINGS = '[settings]\nfeed_lines = ["4.2"]\ntest_lines = ["4.2"]\n'


def load(tmp_path, text: str, settings: str = SETTINGS) -> config.Config:
    path = tmp_path / "plugins.toml"
    path.write_text(settings + text)
    return config.load(path)


def test_overrides(tmp_path):
    cfg = load(
        tmp_path,
        """
[plugins.demo]
name = "qgis-stack-demo2"
add_run = ["plotly", "pandas >=2", "libopencv * *qt6*"]
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
    assert demo.slug == "demo"
    assert demo.name == "qgis-stack-demo2"
    assert demo.add_run == ["plotly", "pandas >=2", "libopencv * *qt6*"]
    assert demo.qgis == QgisRange(min="3.40", max="3.99")
    assert demo.version == {"1.0-beta": "1.0b"}
    assert (demo.license, demo.build_number) == ("MIT", 2)
    assert demo.test == TestOptions(import_=False, commands=["python -c 'import plotly'"])
    assert cfg.plugins["other"].skip == "broken"
    assert cfg.order == ["demo", "other"]
    assert cfg.settings.include_experimental is False


def test_defaults(tmp_path):
    plugin = load(tmp_path, "[plugins.demo]\n").plugins["demo"]
    assert plugin == config.Plugin(slug="demo")
    assert plugin.test.import_ and plugin.test.commands == []


@pytest.mark.parametrize(
    ("table", "message"),
    [
        ("add_runs = []", "[plugins.demo] add_runs: Extra inputs are not permitted"),
        ('add_run = "plotly"', "[plugins.demo] add_run: Input should be a valid list"),
        ("add_run = [1]", "[plugins.demo] add_run[0]: Input should be a valid string"),
        ('add_run = ["conda-forge::plotly"]', "channels can't be given"),
        ('add_run = ["Plotly"]', "isn't a conda-forge package name"),
        ('build_number = "1"', "[plugins.demo] build_number: Input should be a valid integer"),
        ("build_number = true", "[plugins.demo] build_number: Input should be a valid integer"),
        ("build_number = -1", "build_number: Input should be greater than or equal to 0"),
        ('qgis = { min = "3.40" }', "[plugins.demo] qgis.max: Field required"),
        ('qgis = { min = "3.x", max = "4" }', "qgis.min: String should match pattern"),
        ("test.imports = false", "[plugins.demo] test.imports: Extra inputs are not permitted"),
        ('test.import = "no"', "[plugins.demo] test.import: Input should be a valid boolean"),
        ("version = { '1' = 1 }", "[plugins.demo] version.1: Input should be a valid string"),
        ('name = "Demo"', "[plugins.demo] name: String should match pattern"),
        ('slug = "other"', "[plugins.demo] slug: not allowed; the slug is the table key"),
    ],
)
def test_plugin_errors(tmp_path, table, message):
    with pytest.raises(ConfigError, match="plugins.toml:") as exc:
        load(tmp_path, f"[plugins.demo]\n{table}\n")
    assert message in str(exc.value)


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        ('[settings]\ntest_lines = ["4.2"]\n', "[settings] feed_lines: Field required"),
        (
            '[settings]\nfeed_lines = []\ntest_lines = ["4.2"]\n',
            "[settings] feed_lines: List should have at least 1 item",
        ),
        (
            '[settings]\nfeed_lines = ["4"]\ntest_lines = ["4.2"]\n',
            "[settings] feed_lines[0]: String should match pattern",
        ),
        # A string used to be read with bool(), so "false" meant True.
        (SETTINGS + 'include_experimental = "false"\n', "Input should be a valid boolean"),
        (SETTINGS + "feeds = 1\n", "[settings] feeds: Extra inputs are not permitted"),
        ('feed_lines = ["4.2"]\n', "[settings]: Field required"),
    ],
)
def test_settings_errors(tmp_path, settings, message):
    with pytest.raises(ConfigError) as exc:
        load(tmp_path, "", settings=settings)
    assert message in str(exc.value)


def test_other_errors(tmp_path):
    with pytest.raises(ConfigError, match=r"\[plugins.1bad\]: String should match"):
        load(tmp_path, '[plugins."1bad"]\n')
    with pytest.raises(ConfigError, match="plugin: Extra inputs are not permitted"):
        load(tmp_path, "[plugin.demo]\n")
    with pytest.raises(ConfigError, match="plugins.toml: "):
        load(tmp_path, "[plugins.demo\n")  # not TOML


def test_all_errors_reported_at_once(tmp_path):
    with pytest.raises(ConfigError) as exc:
        load(tmp_path, '[plugins.a]\nbuild_number = -1\n[plugins.b]\nadd_run = [""]\n')
    assert str(exc.value).count("\n  [plugins.") == 2


def test_select(tmp_path):
    cfg = load(tmp_path, "[plugins.a]\n[plugins.b]\n")
    assert cfg.select(None) == ["a", "b"]
    assert cfg.select(["b"]) == ["b"]
    with pytest.raises(ConfigError, match="not in plugins.toml: c"):
        cfg.select(["c"])


def test_repository_plugins_toml_is_valid():
    assert config.load(ROOT / "plugins.toml").plugins


def test_schema_is_up_to_date():
    """plugins.schema.json is generated: `pixi run schema` after changing config.py."""
    assert (ROOT / "plugins.schema.json").read_text() == config.json_schema()
    schema = json.loads(config.json_schema())
    plugin = schema["$defs"]["Plugin"]["properties"]
    assert "slug" not in plugin  # the table key, not a field
    assert "import" in schema["$defs"]["TestOptions"]["properties"]
