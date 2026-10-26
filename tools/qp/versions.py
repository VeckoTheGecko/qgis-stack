"""Turn plugin versions into conda versions (docs/plan.md section 5.2)."""

import re

# A conda version: optional epoch, then alphanumerics separated by . or _, optional +local.
# Required to start with a digit, so ordering is meaningful.
_CONDA_VERSION = re.compile(r"(\d+!)?\d[A-Za-z0-9_.]*(\+[A-Za-z0-9_.]+)?")


class VersionError(ValueError):
    pass


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
