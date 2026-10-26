"""Turn plugin versions into conda versions (the design plan section 5.2)."""

import re

# A conda version: optional epoch, then alphanumerics separated by . or _, optional +local.
# Required to start with a digit, so ordering is meaningful.
_CONDA_VERSION = re.compile(r"(\d+!)?\d[A-Za-z0-9_.]*(\+[A-Za-z0-9_.]+)?")


# QGIS-Django's VersionField.to_python: drop zero padding, and the "#" fill of empty parts.
_SERVER_UNPAD = re.compile(r"(^|(?<=\.))0+(?!(\.|$|-))|\.#+")


class VersionError(ValueError):
    pass


def server_form(version: str) -> str:
    """The version plugins.qgis.org stores, lists in the feed and puts in download URLs,
    for a metadata.txt version (docs/src/content/docs/background/plugin-versions.md).

    Mirrors QGIS-Django: PluginVersion.clean_version keeps the last space-separated
    word, then VersionField pads 4 dot-separated parts for sorting and strips the
    padding on read. That round trip is lossy: 1.05 -> 1.5, 1.0.0a2 -> 1.0.a2,
    1.2.3.4.5 -> 1.2.3.4.
    """
    version = version.strip()
    if version.rfind(" ") > 0:
        version = version.rsplit(" ")[-1]
    version += "." * max(0, 3 - version.count("."))
    parts = [part.rjust(3, "0") if part else "###" for part in version.split(".")[:4]]
    return _SERVER_UNPAD.sub("", ".".join(parts))


def normalize(upstream: str, overrides: dict[str, str] | None = None) -> str:
    """The conda version for a plugin version.

    An explicit override wins. Otherwise: a leading "v" is dropped, a "-" before a
    pre-release tag is dropped (2.0.0-beta1 -> 2.0.0beta1) and any other "-" becomes
    ".". Anything still not a valid conda version raises VersionError, to be fixed
    with a `version` override in plugins.toml.
    """
    if overrides and upstream in overrides:
        version = overrides[upstream]
    else:
        version = re.sub(r"^[vV](?=\d)", "", upstream.strip())
        version = re.sub(r"-(?=[A-Za-z])", "", version)
        version = version.replace("-", ".")
    if not _CONDA_VERSION.fullmatch(version):
        raise VersionError(
            f"version {upstream!r} has no conda form; "
            f'add `version = {{ "{upstream}" = "..." }}` to its plugins.toml table'
        )
    return version
