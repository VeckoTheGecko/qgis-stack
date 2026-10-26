"""Update a QGIS plugin recipe's context from the plugin ZIP's metadata.txt.

Usage: python tools/sync_qgis_plugin_recipe.py RECIPE_DIR [--version VERSION]

Downloads https://plugins.qgis.org/plugins/<plugin>/version/<version>/download/,
then rewrites `version`, `qgis_min`, `qgis_max` and `sha256` in recipe.yaml.
"""

import argparse
import configparser
import hashlib
import io
import re
import urllib.request
import zipfile
from pathlib import Path

URL = "https://plugins.qgis.org/plugins/{plugin}/version/{version}/download/"


def pad(version: str, fill: str) -> str:
    """Pad to X.Y.Z like pyplugin_installer.version_compare.isCompatible."""
    version = re.sub(r"[^0-9.]+", "", version)
    return version if version.count(".") >= 2 else f"{version}.{fill}"


def read_metadata(data: bytes, plugin: str) -> configparser.SectionProxy:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        text = zf.read(f"{plugin}/metadata.txt").decode("utf-8")
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str  # keys are camelCase
    parser.read_string(text)
    return parser["general"]


def context_value(recipe: str, key: str) -> str:
    match = re.search(rf'^  {key}: "?([^"\n]+)"?$', recipe, re.M)
    if not match:
        raise SystemExit(f"context key {key!r} not found in recipe.yaml")
    return match.group(1)


def set_value(recipe: str, key: str, value: str, quote: bool = True) -> str:
    value = f'"{value}"' if quote else value
    return re.sub(rf"^(  {key}:) .*$", rf"\g<1> {value}", recipe, count=1, flags=re.M)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("recipe_dir", type=Path)
    parser.add_argument("--version", help="plugin version (default: current recipe version)")
    args = parser.parse_args()

    path = args.recipe_dir / "recipe.yaml"
    recipe = path.read_text()
    plugin = context_value(recipe, "plugin")
    version = args.version or context_value(recipe, "version")

    url = URL.format(plugin=plugin, version=version)
    # plugins.qgis.org (Cloudflare) rejects urllib's default User-Agent.
    request = urllib.request.Request(url, headers={"User-Agent": "sync-qgis-plugin-recipe"})
    with urllib.request.urlopen(request) as resp:
        data = resp.read()
    general = read_metadata(data, plugin)

    if general["version"] != version:
        raise SystemExit(f"metadata.txt version {general['version']} != requested {version}")

    qgis_min = pad(general["qgisMinimumVersion"], "0")
    # QGIS defaults an empty max to "<major of min>.99".
    raw_max = general.get("qgisMaximumVersion", "").strip() or f"{qgis_min.split('.')[0]}.99"
    qgis_max = pad(raw_max, "99")

    recipe = set_value(recipe, "version", version)
    recipe = set_value(recipe, "qgis_min", qgis_min)
    recipe = set_value(recipe, "qgis_max", qgis_max)
    recipe = set_value(recipe, "sha256", hashlib.sha256(data).hexdigest(), quote=False)
    path.write_text(recipe)
    print(f"{plugin} {version}: qgis >={qgis_min},<={qgis_max}")


if __name__ == "__main__":
    main()
