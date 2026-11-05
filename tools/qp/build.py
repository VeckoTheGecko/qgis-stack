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


def recipe_key(recipe_dir: Path) -> tuple[str, str, int]:
    """(name, version, build_number) of the package a generated recipe builds."""
    recipe = yaml.safe_load((recipe_dir / "recipe.yaml").read_text())
    return recipe["package"]["name"], recipe["context"]["version"], recipe["build"]["number"]


def build(recipe_dir: Path, output_dir: Path, test: bool = True) -> int:
    """Build one recipe. Without `test`, the recipe's QGIS tests are skipped: each one
    creates a QGIS environment, which makes them slow for iterating on recipes."""
    cmd = ["rattler-build", "build", "--recipe", str(recipe_dir), "--output-dir", str(output_dir)]
    if not test:
        cmd += ["--test", "skip"]
    for channel in CHANNELS:
        cmd += ["--channel", channel]
    return subprocess.run(cmd, check=False).returncode
