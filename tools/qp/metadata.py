"""Read a plugin ZIP: its metadata.txt and the QGIS version range it declares."""

import configparser
import io
import re
import zipfile
from dataclasses import dataclass


@dataclass(frozen=True)
class PluginMetadata:
    version: str
    qgis_min: str  # padded to X.Y.Z like QGIS does
    qgis_max: str
    description: str
    homepage: str | None
    repository: str | None


def pad(version: str, fill: str) -> str:
    """Pad to X.Y.Z like pyplugin_installer.version_compare.isCompatible."""
    version = re.sub(r"[^0-9.]+", "", version)
    return version if version.count(".") >= 2 else f"{version}.{fill}"


def qgis_range(minimum: str, maximum: str | None) -> tuple[str, str]:
    """The inclusive QGIS range QGIS's Plugin Manager applies to a plugin.

    Two-part versions get .0 (min) or .99 (max); an empty max means "<major of min>.99".
    """
    qgis_min = pad(minimum, "0")
    maximum = (maximum or "").strip() or f"{qgis_min.split('.')[0]}.99"
    return qgis_min, pad(maximum, "99")


def read_general(data: bytes, slug: str) -> configparser.SectionProxy:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        text = zf.read(f"{slug}/metadata.txt").decode("utf-8-sig")
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str  # keys are camelCase
    parser.read_string(text)
    return parser["general"]


def read(data: bytes, slug: str) -> PluginMetadata:
    general = read_general(data, slug)
    qgis_min, qgis_max = qgis_range(
        general["qgisMinimumVersion"], general.get("qgisMaximumVersion")
    )
    return PluginMetadata(
        version=general["version"].strip(),
        qgis_min=qgis_min,
        qgis_max=qgis_max,
        description=general.get("description", "").strip(),
        homepage=general.get("homepage", "").strip() or None,
        repository=general.get("repository", "").strip() or None,
    )
