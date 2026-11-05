"""What's already published: our channel's repodata and conda-forge's package names."""

import json
import os
import re
import urllib.error
from dataclasses import dataclass
from pathlib import Path

from qp.feed import CACHE_DIR, fetch

# https://prefix.dev/<channel> (a primary channel) or https://prefix.dev/<namespace>/<channel>.
# Not the website's /channels/@<namespace>/<channel> page.
PREFIX_URL = re.compile(r"^https://prefix\.dev/([a-z0-9][a-z0-9_-]*(?:/[a-z0-9][a-z0-9_-]*)?)/?$")
CONDA_FORGE_CHANNELDATA = "https://conda.anaconda.org/conda-forge/channeldata.json"


class ChannelError(Exception):
    pass


@dataclass(frozen=True)
class Record:
    name: str
    version: str
    build_number: int
    depends: list[str]
    license: str | None


def records(channel: str) -> list[Record]:
    """noarch packages on a channel: a URL (https://prefix.dev/<namespace>/<channel>)
    or a local channel directory such as output/. A channel that doesn't exist yet is
    empty. A private prefix.dev channel is read with PREFIX_API_KEY, if set."""
    if channel.startswith(("http://", "https://")):
        headers = {}
        if channel.startswith("https://prefix.dev/") and os.environ.get("PREFIX_API_KEY"):
            headers["Authorization"] = f"Bearer {os.environ['PREFIX_API_KEY']}"
        try:
            raw = fetch(f"{channel.rstrip('/')}/noarch/repodata.json", headers)
        except urllib.error.HTTPError as e:
            # Only a missing channel counts as empty: on any other error, a sync
            # would otherwise rebuild everything.
            if e.code == 404:
                return []
            if e.code in (401, 403):
                raise ChannelError(
                    f"{channel} is private: make it public, or set PREFIX_API_KEY "
                    "to a key that can read it"
                ) from e
            raise
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


def prefix_channel(channel: str) -> str:
    """The channel for `rattler-build upload prefix --channel`: <namespace>/<channel>
    (or <channel>) from its URL."""
    match = PREFIX_URL.match(channel)
    if not match:
        raise ValueError(
            f"not a prefix.dev channel URL: {channel} (expected https://prefix.dev/<name>)"
        )
    return match.group(1)


def conda_forge_names(cache_dir: Path = CACHE_DIR, refresh: bool = False) -> set[str]:
    """Every package name on conda-forge (from channeldata.json), cached."""
    path = cache_dir / "conda-forge-names.txt"
    if refresh or not path.exists():
        names = json.loads(fetch(CONDA_FORGE_CHANNELDATA))["packages"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(sorted(names)) + "\n")
    return set(path.read_text().split())
