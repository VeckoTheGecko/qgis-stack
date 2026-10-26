"""Build generated recipes with rattler-build."""

import subprocess
from pathlib import Path

import yaml

CHANNELS = ["conda-forge"]


def recipe_dirs(recipes_dir: Path, slugs: list[str] | None = None) -> list[Path]:
    """Generated recipe directories, optionally only those of the given plugin slugs."""
    dirs = []
    for path in sorted(recipes_dir.glob("*/recipe.yaml")):
        slug = yaml.safe_load(path.read_text())["extra"]["qgis_plugin_slug"]
        if slugs is None or slug in slugs:
            dirs.append(path.parent)
    return dirs


def build(recipe_dir: Path, output_dir: Path) -> int:
    cmd = ["rattler-build", "build", "--recipe", str(recipe_dir), "--output-dir", str(output_dir)]
    for channel in CHANNELS:
        cmd += ["--channel", channel]
    return subprocess.run(cmd, check=False).returncode
