"""The plugin catalogue on the docs site (docs/src/data/plugins.json), from channel repodata."""

import json
from collections.abc import Iterable

from rattler import MatchSpec, Version

from qp.channel import Record
from qp.check import names
from qp.config import Config

PLUGIN_PAGE = "https://plugins.qgis.org/plugins/{slug}/"


def entries(records: Iterable[Record], config: Config) -> list[dict]:
    """One entry per published package, describing its newest version (conda ordering)."""
    slugs = {name: slug for slug, name in names(config).items()}
    by_name: dict[str, list[Record]] = {}
    for record in records:
        by_name.setdefault(record.name, []).append(record)
    result = []
    for name, published in by_name.items():
        published.sort(key=lambda r: (Version(r.version), r.build_number), reverse=True)
        newest = published[0]
        specs = [MatchSpec(d) for d in newest.depends]
        qgis = next((str(s.version or "") for s in specs if s.name.normalized == "qgis"), "")
        slug = slugs.get(name)
        result.append(
            {
                "name": name,
                "slug": slug,
                "url": PLUGIN_PAGE.format(slug=slug) if slug else None,
                "version": newest.version,
                "build_number": newest.build_number,
                "versions": list(dict.fromkeys(r.version for r in published)),
                "qgis": qgis,
                "depends": [str(s) for s in specs if s.name.normalized != "qgis"],
                "license": newest.license,
            }
        )
    return sorted(result, key=lambda e: e["name"])


def dumps(catalogue: list[dict]) -> str:
    return json.dumps(catalogue, indent=2) + "\n"
