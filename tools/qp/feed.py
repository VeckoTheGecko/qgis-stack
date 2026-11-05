"""The plugins.qgis.org feed (plugins.xml?qgis=X.Y) and plugin ZIP downloads, cached
under .cache/qp/."""

import re
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

FEED_URL = "https://plugins.qgis.org/plugins/plugins.xml?qgis={line}"
DOWNLOAD_URL = "https://plugins.qgis.org/plugins/{slug}/version/{version}/download/"
CACHE_DIR = Path(".cache/qp")
# plugins.qgis.org (Cloudflare) rejects urllib's default User-Agent.
USER_AGENT = "qgis-stack"

_SLUG_FROM_URL = re.compile(r"/plugins/([^/]+)/version/([^/]+)/download/")


@dataclass(frozen=True)
class FeedEntry:
    slug: str
    version: str
    plugin_id: str
    name: str
    download_url: str
    experimental: bool
    deprecated: bool


def fetch(url: str, headers: dict[str, str] | None = None) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(request) as response:
        return response.read()


def feed_path(line: str, cache_dir: Path = CACHE_DIR) -> Path:
    return cache_dir / "feeds" / f"{line}.xml"


def update(lines: Iterable[str], cache_dir: Path = CACHE_DIR) -> list[Path]:
    """Download the feed of every QGIS line into the cache."""
    paths = []
    for line in lines:
        path = feed_path(line, cache_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(fetch(FEED_URL.format(line=line)))
        paths.append(path)
    return paths


def parse(xml: bytes) -> list[FeedEntry]:
    entries = []
    for plugin in ET.fromstring(xml):
        url = plugin.findtext("download_url") or ""
        match = _SLUG_FROM_URL.search(url)
        if not match:
            continue
        entries.append(
            FeedEntry(
                slug=match.group(1),
                version=plugin.get("version", ""),
                plugin_id=plugin.get("plugin_id", ""),
                name=plugin.get("name", ""),
                download_url=url,
                experimental=plugin.findtext("experimental") == "True",
                deprecated=plugin.findtext("deprecated") == "True",
            )
        )
    return entries


def load(lines: Iterable[str], cache_dir: Path = CACHE_DIR) -> list[FeedEntry]:
    """Entries of all cached feeds; feeds missing from the cache are downloaded."""
    entries = []
    for line in lines:
        path = feed_path(line, cache_dir)
        if not path.exists():
            update([line], cache_dir)
        entries.extend(parse(path.read_bytes()))
    return entries


def versions(
    entries: Iterable[FeedEntry], slug: str, include_experimental: bool = False
) -> list[FeedEntry]:
    """One entry per distinct version of a plugin across the feeds."""
    seen: dict[str, FeedEntry] = {}
    for entry in entries:
        if entry.slug == slug and (include_experimental or not entry.experimental):
            seen.setdefault(entry.version, entry)
    return list(seen.values())


def download(slug: str, version: str, cache_dir: Path = CACHE_DIR) -> bytes:
    """The plugin ZIP from the stable download URL, cached."""
    path = cache_dir / "zips" / f"{slug}-{version}.zip"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(fetch(DOWNLOAD_URL.format(slug=slug, version=version)))
    return path.read_bytes()
