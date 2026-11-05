import subprocess
from pathlib import Path

import pytest
import yaml

from qp import build, channel, plan
from qp.channel import Record
from qp.cli import main


@pytest.mark.parametrize(
    ("file", "key"),
    [
        ("qgis-plugin-latlontools-4.0.4-h4616a5c_0.conda", ("qgis-plugin-latlontools", "4.0.4", 0)),
        ("qgis-plugin-profile-manager-1.2-h1_3.conda", ("qgis-plugin-profile-manager", "1.2", 3)),
        ("qgis-plugin-x-2.0.0beta1-h1_0.tar.bz2", ("qgis-plugin-x", "2.0.0beta1", 0)),
    ],
)
def test_package_key(file, key):
    assert plan.package_key(Path("output/noarch") / file) == key


@pytest.mark.parametrize(
    ("url", "name"),
    [
        ("https://prefix.dev/qstack", "qstack"),
        ("https://prefix.dev/qstack-test/", "qstack-test"),
        ("https://prefix.dev/veckothegecko/qgis-stack-test", "veckothegecko/qgis-stack-test"),
    ],
)
def test_prefix_channel(url, name):
    assert channel.prefix_channel(url) == name


@pytest.mark.parametrize(
    "url",
    [
        "output",
        "https://conda.anaconda.org/x",
        "https://prefix.dev/",
        "https://prefix.dev/channels/@veckothegecko/qgis-stack-test",  # the web page
    ],
)
def test_prefix_channel_rejects(url):
    with pytest.raises(ValueError, match="prefix.dev"):
        channel.prefix_channel(url)


def record(name, version, build_number=0):
    return Record(name, version, build_number, [], "GPL-2.0-or-later")


PUBLISHED = [record("qgis-plugin-a", "1.0"), record("qgis-plugin-b", "2.0", 1)]


def write_recipe(recipes_dir: Path, name: str, version: str, number: int = 0) -> Path:
    d = recipes_dir / f"{name}-{version}"
    d.mkdir(parents=True)
    recipe = {
        "context": {"plugin": name, "version": version},
        "package": {"name": name, "version": "${{ version }}"},
        "build": {"number": number},
        "extra": {"qgis_plugin_slug": name.removeprefix("qgis-plugin-")},
    }
    (d / "recipe.yaml").write_text(yaml.safe_dump(recipe))
    return d


def test_build_skips_published(tmp_path, monkeypatch, capsys):
    write_recipe(tmp_path, "qgis-plugin-a", "1.0")  # published
    write_recipe(tmp_path, "qgis-plugin-b", "2.0", 2)  # build_number bumped
    built = []
    monkeypatch.setattr(channel, "records", lambda target: PUBLISHED)
    monkeypatch.setattr(build, "build", lambda d, out, test: built.append(d.name) or 0)
    assert main(["--recipes-dir", str(tmp_path), "build", "--channel", "https://prefix.dev/x"]) == 0
    assert built == ["qgis-plugin-b-2.0"]
    assert "qgis-plugin-a-1.0: already on https://prefix.dev/x, skipped" in capsys.readouterr().out


def test_upload_only_new_packages(tmp_path, monkeypatch, capsys):
    noarch = tmp_path / "noarch"
    noarch.mkdir()
    for file in [
        "qgis-plugin-a-1.0-h1_0.conda",  # published
        "qgis-plugin-b-2.0-h1_1.conda",  # published
        "qgis-plugin-b-2.0-h1_2.conda",  # new build
        "qgis-plugin-c-0.1-h1_0.conda",  # new package
    ]:
        (noarch / file).touch()
    calls = []
    monkeypatch.setattr(channel, "records", lambda target: PUBLISHED)
    monkeypatch.setattr(subprocess, "run", lambda cmd, check: calls.append(cmd) or _Done())
    argv = ["--output-dir", str(tmp_path), "upload", "--channel", "https://prefix.dev/qstack-test"]
    assert main(argv) == 0
    [cmd] = calls
    assert cmd[:4] == ["rattler-build", "upload", "prefix", "--channel"]
    assert cmd[4:6] == ["qstack-test", "--skip-existing"]
    assert [Path(p).name for p in cmd[6:]] == [
        "qgis-plugin-b-2.0-h1_2.conda",
        "qgis-plugin-c-0.1-h1_0.conda",
    ]
    assert "2 of 4 packages not on" in capsys.readouterr().out


def test_upload_needs_prefix_url(tmp_path, capsys):
    assert main(["--output-dir", str(tmp_path), "upload", "--channel", "output"]) == 1
    assert "not a prefix.dev channel URL" in capsys.readouterr().err


class _Done:
    returncode = 0


def test_private_channel_has_a_clear_error(monkeypatch):
    import urllib.error

    def forbidden(url, headers=None):
        raise urllib.error.HTTPError(url, 401, "Unauthorized", {}, None)

    monkeypatch.setattr(channel, "fetch", forbidden)
    with pytest.raises(channel.ChannelError, match="private"):
        channel.records("https://prefix.dev/veckothegecko/qgis-stack-test")


def test_private_channel_uses_api_key(monkeypatch):
    seen = {}

    def fetch(url, headers=None):
        seen.update(headers or {})
        return b'{"packages.conda": {}}'

    monkeypatch.setattr(channel, "fetch", fetch)
    monkeypatch.setenv("PREFIX_API_KEY", "pfx_secret")
    assert channel.records("https://prefix.dev/veckothegecko/qgis-stack-test") == []
    assert seen["Authorization"] == "Bearer pfx_secret"
