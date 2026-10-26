"""Generate a rattler-build recipe for one plugin version (the design plan section 5)."""

import hashlib
import shutil
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import yaml

from qp import feed, license, metadata, versions
from qp.config import Plugin
from qp.feed import FeedEntry
from qp.naming import package_name

TEMPLATE_FILES = ["build.sh", "test_plugin.py"]


@dataclass(frozen=True)
class Recipe:
    name: str
    version: str  # conda version
    build_number: int
    depends: list[str]  # rendered run requirements, as they end up in repodata
    license: str
    data: dict

    @property
    def dirname(self) -> str:
        return f"{self.name}-{self.version}"


def _line(version: str) -> tuple[int, int]:
    major, minor = version.split(".")[:2]
    return int(major), int(minor)


def _xyz(version: str) -> tuple[int, int, int]:
    major, minor, patch = version.split(".")[:3]
    return int(major), int(minor), int(patch)


def oldest_test_line(test_lines: list[str], qgis_min: str, qgis_max: str) -> str | None:
    """The oldest QGIS line to test against: inside the plugin's range, and not the
    newest test line (the unpinned `qgis` test covers that)."""
    lo, hi = _line(qgis_min), _line(qgis_max)
    lines = sorted(test_lines, key=_line)
    in_range = [line for line in lines if lo <= _line(line) <= hi]
    if not in_range or in_range[0] == lines[-1]:
        return None
    return in_range[0]


def _qgis_range(plugin: Plugin, meta: metadata.PluginMetadata) -> tuple[str, str]:
    """The QGIS range for `run`: metadata.txt's, or the override, which may only narrow
    it. QGIS refuses to load a plugin outside its metadata.txt range, so widening would
    need a patch to metadata.txt."""
    if not plugin.qgis:
        return meta.qgis_min, meta.qgis_max
    qgis_min, qgis_max = metadata.qgis_range(plugin.qgis.min, plugin.qgis.max)
    if _xyz(qgis_min) < _xyz(meta.qgis_min) or _xyz(qgis_max) > _xyz(meta.qgis_max):
        raise ValueError(
            f"{plugin.slug}: qgis override {qgis_min}..{qgis_max} widens metadata.txt's "
            f"{meta.qgis_min}..{meta.qgis_max}; QGIS won't load the plugin outside the latter"
        )
    return qgis_min, qgis_max


def _plugin_test(qgis_spec: str, test_import: bool) -> dict:
    script = "python test_plugin.py ${{ plugin }}" + ("" if test_import else " --no-import")
    return {
        "files": {"recipe": ["test_plugin.py"]},
        "requirements": {"run": [qgis_spec]},
        "script": [script],
    }


def generate(
    entry: FeedEntry, data: bytes, test_lines: list[str], plugin: Plugin | None = None
) -> Recipe:
    """The recipe for a plugin version, from its feed entry, ZIP bytes and overrides."""
    slug = entry.slug
    plugin = plugin or Plugin(slug=slug)
    meta = metadata.read(data, slug)
    if meta.version != entry.version:
        raise ValueError(f"{slug}: metadata.txt version {meta.version} != feed {entry.version}")
    version = versions.normalize(entry.version, plugin.version)
    # The version in plugins.qgis.org URLs and metadata.txt, when it differs.
    src_version = "${{ version }}" if version == entry.version else "${{ upstream_version }}"

    qgis_min, qgis_max = _qgis_range(plugin, meta)
    # build.sh checks the ZIP's metadata.txt against these; with a qgis override they
    # are the metadata values, not the context's.
    check_min = "${{ qgis_min }}" if qgis_min == meta.qgis_min else meta.qgis_min
    check_max = "${{ qgis_max }}" if qgis_max == meta.qgis_max else meta.qgis_max

    plugin_dir = "share/qgis/python/plugins/${{ plugin }}"
    tests: list[dict] = [
        {
            "package_contents": {
                "files": [f"{plugin_dir}/metadata.txt", f"{plugin_dir}/__init__.py"],
            }
        },
        _plugin_test("qgis", plugin.test.import_),
    ]
    oldest = oldest_test_line(test_lines, qgis_min, qgis_max)
    if oldest:
        tests.append(_plugin_test(f"qgis {oldest}.*", plugin.test.import_))
    if plugin.test.commands:
        tests.append({"requirements": {"run": ["qgis"]}, "script": list(plugin.test.commands)})

    name = plugin.name or package_name(slug)
    sha256 = hashlib.sha256(data).hexdigest()
    spdx = plugin.license or license.detect(data, slug)
    about = {
        "homepage": meta.homepage,
        "repository": meta.repository,
        "summary": meta.description,
        "license": spdx,
        "license_file": "${{ plugin }}/LICENSE",
    }
    context = {"plugin": slug, "version": version}
    if version != entry.version:
        context["upstream_version"] = entry.version
    context |= {"qgis_min": qgis_min, "qgis_max": qgis_max}

    recipe = {
        "context": context,
        "package": {"name": name, "version": "${{ version }}"},
        "source": {
            "url": feed.DOWNLOAD_URL.format(slug="${{ plugin }}", version=src_version),
            "sha256": sha256,
            "file_name": f"${{{{ plugin }}}}-{src_version}.zip",
        },
        "build": {
            "number": plugin.build_number,
            "noarch": "generic",
            "script": {
                "file": "build.sh",
                "env": {
                    "PLUGIN": "${{ plugin }}",
                    "PLUGIN_VERSION": src_version,
                    "QGIS_MIN": check_min,
                    "QGIS_MAX": check_max,
                },
            },
        },
        "requirements": {
            "build": ["unzip"],
            "run": ["qgis >=${{ qgis_min }},<=${{ qgis_max }}", *plugin.add_run],
        },
        "tests": tests,
        "about": {k: v for k, v in about.items() if v},
        "extra": {
            "qgis_plugin_slug": slug,
            "qgis_plugin_version": entry.version,
            "qgis_plugin_id": entry.plugin_id,
            "source_sha256": sha256,
        },
    }
    return Recipe(
        name=name,
        version=version,
        build_number=plugin.build_number,
        depends=[f"qgis >={qgis_min},<={qgis_max}", *plugin.add_run],
        license=spdx,
        data=recipe,
    )


HEADER = "# Generated by `qp generate` from plugins.qgis.org; do not edit.\n"


def write(recipe: Recipe, recipes_dir: Path) -> Path:
    """Write recipe.yaml plus the build and test scripts to recipes_dir/<name>-<version>/."""
    out = recipes_dir / recipe.dirname
    out.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(recipe.data, sort_keys=False, allow_unicode=True, width=100)
    (out / "recipe.yaml").write_text(HEADER + text)
    templates = resources.files("qp") / "templates"
    for name in TEMPLATE_FILES:
        with resources.as_file(templates / name) as src:
            shutil.copy2(src, out / name)
    return out
