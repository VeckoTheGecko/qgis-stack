"""What's already published: our channel's repodata and conda-forge's package names."""

import json
from dataclasses import dataclass
from pathlib import Path

from qp.feed import CACHE_DIR, fetch

CONDA_FORGE_CHANNELDATA = "https://conda.anaconda.org/conda-forge/channeldata.json"


@dataclass(frozen=True)
class Record:
    name: str
    version: str
    build_number: int
    depends: list[str]
    license: str | None


def records(channel: str) -> list[Record]:
    """noarch packages on a channel: a URL (https://prefix.dev/<channel>) or a local
    channel directory such as output/. A channel that doesn't exist yet is empty."""
    if channel.startswith(("http://", "https://")):
        try:
            raw = fetch(f"{channel.rstrip('/')}/noarch/repodata.json")
        except OSError:
            return []
    else:
        path = Path(channel) / "noarch" / "repodata.json"
        if not path.exists():
            return []
        raw = path.read_bytes()
    repodata = json.loads(raw)
    packages = {**repodata.get("packages", {}), **repodata.get("packages.conda", {})}
    return [
        Record(
            name=p["name"],
            version=p["version"],
            build_number=p.get("build_number", 0),
            depends=list(p.get("depends", [])),
            license=p.get("license"),
        )
        for p in packages.values()
    ]


def conda_forge_names(cache_dir: Path = CACHE_DIR, refresh: bool = False) -> set[str]:
    """Every package name on conda-forge (from channeldata.json), cached."""
    path = cache_dir / "conda-forge-names.txt"
    if refresh or not path.exists():
        names = json.loads(fetch(CONDA_FORGE_CHANNELDATA))["packages"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(sorted(names)) + "\n")
    return set(path.read_text().split())
