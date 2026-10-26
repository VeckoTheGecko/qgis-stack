"""Sanity checks over plugins.toml (the design plan sections 5.1, 5.8 and 8).

Each check returns a list of problems; an empty list means it passed.
"""

from collections import defaultdict
from collections.abc import Iterable

from qp.channel import Record
from qp.config import Config
from qp.naming import package_name
from qp.recipe import Recipe


def names(config: Config) -> dict[str, str]:
    """slug -> package name, for every selected plugin."""
    return {slug: p.name or package_name(slug) for slug, p in config.plugins.items()}


def sorted_tables(config: Config) -> list[str]:
    expected = sorted(config.order, key=str.lower)
    if config.order == expected:
        return []
    return ["[plugins.*] tables aren't sorted (case-insensitive); expected: " + ", ".join(expected)]


def naming(config: Config, feed_slugs: Iterable[str]) -> list[str]:
    """No two plugins share a package name, now or later.

    A selected plugin without an explicit `name` must not take the default name of any
    *other* plugin on plugins.qgis.org, selected or not: whichever was added first would
    otherwise own the name for good. Such pairs need an explicit `name`.
    """
    problems = []
    chosen = names(config)
    by_name = defaultdict(list)
    for slug, name in chosen.items():
        by_name[name].append(slug)
    for name, slugs in sorted(by_name.items()):
        if len(slugs) > 1:
            problems.append(f"{', '.join(sorted(slugs))}: all named {name}")

    defaults = defaultdict(set)
    for slug in feed_slugs:
        defaults[package_name(slug)].add(slug)
    for slug, plugin in config.plugins.items():
        if plugin.name:
            continue
        others = defaults[package_name(slug)] - {slug}
        if others:
            problems.append(
                f"{slug}: {package_name(slug)} is also the default name of "
                f"{', '.join(sorted(others))} on plugins.qgis.org; set an explicit `name`"
            )
    return problems


def conda_forge_clash(config: Config, conda_forge: set[str]) -> list[str]:
    """Strict channel priority would hide conda-forge's package of the same name."""
    return [
        f"{slug}: {name} exists on conda-forge"
        for slug, name in names(config).items()
        if name in conda_forge
    ]


def _norm(spec: str) -> str:
    return " ".join(spec.split())


def build_numbers(recipes: Iterable[Recipe], published: Iterable[Record]) -> list[str]:
    """A published version whose dependencies or licence change needs a higher
    build_number: same version and build number would be skipped as already uploaded."""
    newest: dict[tuple[str, str], Record] = {}
    for record in published:
        key = (record.name, record.version)
        if key not in newest or record.build_number > newest[key].build_number:
            newest[key] = record
    problems = []
    for recipe in recipes:
        record = newest.get((recipe.name, recipe.version))
        if record is None or recipe.build_number > record.build_number:
            continue
        where = f"{recipe.name} {recipe.version}"
        if recipe.build_number < record.build_number:
            problems.append(
                f"{where}: build_number {recipe.build_number} is below the published "
                f"{record.build_number}"
            )
            continue
        changes = []
        if sorted(map(_norm, recipe.depends)) != sorted(map(_norm, record.depends)):
            changes.append(f"depends {record.depends} -> {recipe.depends}")
        if recipe.license != record.license:
            changes.append(f"license {record.license} -> {recipe.license}")
        if changes:
            problems.append(
                f"{where}: changed since build {record.build_number} was published "
                f"({'; '.join(changes)}); set build_number = {record.build_number + 1}"
            )
    return problems
