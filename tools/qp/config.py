"""Read plugins.toml: pipeline settings, the plugin selection and per-plugin overrides
(docs/plan.md section 6)."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG = Path("plugins.toml")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Settings:
    feed_lines: list[str]
    test_lines: list[str]
    include_experimental: bool = False
    # Channel already published to: a URL or a local channel directory (M5).
    channel: str | None = None


@dataclass(frozen=True)
class QgisRange:
    min: str
    max: str


@dataclass(frozen=True)
class Plugin:
    """One `[plugins.<slug>]` table."""

    slug: str
    name: str | None = None  # package name, instead of qgis-plugin-<slug lowercased>
    skip: str | None = None  # reason not to build
    note: str | None = None  # provenance, e.g. where add_run came from
    add_run: list[str] = field(default_factory=list)
    qgis: QgisRange | None = None  # replaces metadata.txt's QGIS range
    version: dict[str, str] = field(default_factory=dict)  # upstream -> conda version
    license: str | None = None  # SPDX id, instead of detecting it
    build_number: int = 0
    test_import: bool = True
    test_commands: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Config:
    settings: Settings
    plugins: dict[str, Plugin] = field(default_factory=dict)
    # Table order as written, to check it's sorted.
    order: list[str] = field(default_factory=list)

    def select(self, slugs: list[str] | None) -> list[str]:
        """The selected slugs, or the given ones after checking they are selected."""
        if not slugs:
            return list(self.plugins)
        unknown = [s for s in slugs if s not in self.plugins]
        if unknown:
            raise ConfigError(f"not in plugins.toml: {', '.join(unknown)}")
        return slugs


def _type(slug: str, key: str, value, kind, what: str):
    if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
        raise ConfigError(f"[plugins.{slug}] {key}: expected {what}, got {value!r}")
    return value


def _strings(slug: str, key: str, value) -> list[str]:
    _type(slug, key, value, list, "a list of strings")
    for item in value:
        _type(slug, key, item, str, "a list of strings")
    return list(value)


def _plugin(slug: str, table: dict) -> Plugin:
    allowed = {f for f in Plugin.__dataclass_fields__ if f not in ("slug", "qgis")}
    allowed = (allowed - {"test_import", "test_commands"}) | {"qgis", "test"}
    unknown = sorted(set(table) - allowed)
    if unknown:
        raise ConfigError(f"[plugins.{slug}]: unknown keys {', '.join(unknown)}")

    kwargs: dict = {"slug": slug}
    for key in ("name", "skip", "note", "license"):
        if key in table:
            kwargs[key] = _type(slug, key, table[key], str, "a string")
    if "add_run" in table:
        kwargs["add_run"] = _strings(slug, "add_run", table["add_run"])
    if "build_number" in table:
        kwargs["build_number"] = _type(slug, "build_number", table["build_number"], int, "an int")
    if "version" in table:
        versions = _type(slug, "version", table["version"], dict, "a table")
        for upstream, conda in versions.items():
            _type(slug, f"version.{upstream}", conda, str, "a string")
        kwargs["version"] = dict(versions)
    if "qgis" in table:
        qgis = _type(slug, "qgis", table["qgis"], dict, "a table with min and max")
        if set(qgis) != {"min", "max"}:
            raise ConfigError(f"[plugins.{slug}] qgis: needs exactly min and max")
        kwargs["qgis"] = QgisRange(
            min=_type(slug, "qgis.min", qgis["min"], str, "a string"),
            max=_type(slug, "qgis.max", qgis["max"], str, "a string"),
        )
    if "test" in table:
        test = _type(slug, "test", table["test"], dict, "a table")
        unknown = sorted(set(test) - {"import", "commands"})
        if unknown:
            raise ConfigError(f"[plugins.{slug}] test: unknown keys {', '.join(unknown)}")
        if "import" in test:
            kwargs["test_import"] = _type(slug, "test.import", test["import"], bool, "a bool")
        if "commands" in test:
            kwargs["test_commands"] = _strings(slug, "test.commands", test["commands"])
    return Plugin(**kwargs)


def load(path: Path = DEFAULT_CONFIG) -> Config:
    with path.open("rb") as f:
        data = tomllib.load(f)
    s = data.get("settings", {})
    settings = Settings(
        feed_lines=list(s["feed_lines"]),
        test_lines=list(s["test_lines"]),
        include_experimental=bool(s.get("include_experimental", False)),
        channel=s.get("channel"),
    )
    tables = data.get("plugins", {})
    plugins = {slug: _plugin(slug, table) for slug, table in tables.items()}
    return Config(settings=settings, plugins=plugins, order=list(tables))
