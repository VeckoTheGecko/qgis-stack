"""What a sync run has to do: packages not yet on the channel (the design plan section 8).

A package is identified by (name, version, build_number). The channel is the state:
anything already there is skipped, so build and upload can be re-run safely.
"""

from collections.abc import Iterable
from pathlib import Path

from qp.channel import Record

Key = tuple[str, str, int]


def published(records: Iterable[Record]) -> set[Key]:
    return {(r.name, r.version, r.build_number) for r in records}


def package_key(path: Path) -> Key:
    """(name, version, build_number) from a package file name such as
    qgis-plugin-latlontools-4.0.4-h4616a5c_0.conda. Versions and build strings have no
    dashes, so the name is everything before the last two."""
    stem = path.name.removesuffix(".conda").removesuffix(".tar.bz2")
    name, version, build = stem.rsplit("-", 2)
    return name, version, int(build.rsplit("_", 1)[1])
