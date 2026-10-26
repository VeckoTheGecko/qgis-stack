"""Read plugins.toml: pipeline settings, the plugin selection and per-plugin overrides
(docs/plan.md section 6).

The models double as the source of plugins.schema.json (`qp schema`), which editors
use for completion and checking via the `#:schema` line at the top of plugins.toml.
"""

import json
import re
import tomllib
from pathlib import Path
from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)
from pydantic.json_schema import SkipJsonSchema

DEFAULT_CONFIG = Path("plugins.toml")


class ConfigError(ValueError):
    pass


QgisLine = Annotated[str, Field(pattern=r"^\d+\.\d+$", examples=["4.2"])]
QgisVersion = Annotated[str, Field(pattern=r"^\d+\.\d+(\.\d+)?$", examples=["3.40", "3.44.2"])]
Slug = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")]
# A run requirement: conda-forge package name plus optional spec, without a channel, as
# run dependencies resolve against the user's channels (docs/plan.md section 2).
_RUN_SPEC = r"^[a-z0-9_][a-z0-9._-]*(\s+[^:\s][^:]*)?$"


def _run_spec(value: str) -> str:
    if not re.match(_RUN_SPEC, value):
        raise ValueError(
            f"{value!r} isn't a conda-forge package name with an optional version spec "
            "(e.g. 'pandas >=2'); channels can't be given"
        )
    return value


RunSpec = Annotated[
    str,
    AfterValidator(_run_spec),
    Field(json_schema_extra={"pattern": _RUN_SPEC}, examples=["plotly", "pandas >=2"]),
]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Settings(_Model):
    """Pipeline settings."""

    feed_lines: list[QgisLine] = Field(
        min_length=1,
        description="QGIS lines whose plugins.qgis.org feed is read. Each feed lists only the "
        "newest version of every plugin compatible with that line.",
    )
    test_lines: list[QgisLine] = Field(
        min_length=1,
        description="QGIS lines on conda-forge to test against: the oldest one inside a "
        "plugin's range, plus the newest QGIS.",
    )
    include_experimental: bool = Field(
        False, description="Also package versions flagged experimental on plugins.qgis.org."
    )
    channel: str | None = Field(
        None,
        description="Channel already published to, for `qp check`'s build-number check: a "
        "URL (https://prefix.dev/<channel>) or a local channel directory.",
    )


class QgisRange(_Model):
    """QGIS range replacing metadata.txt's. It may only narrow that range: QGIS won't load
    a plugin outside it."""

    min: QgisVersion = Field(description="Lowest QGIS version; two-part gets .0 appended.")
    max: QgisVersion = Field(description="Highest QGIS version; two-part gets .99 appended.")


class TestOptions(_Model):
    """Test options."""

    __test__ = False  # not a pytest test class, despite the name

    model_config = ConfigDict(validate_by_name=True)

    import_: bool = Field(
        True,
        alias="import",
        description="Import the plugin in the test. Turn off for plugins with side effects "
        "at import.",
    )
    commands: list[str] = Field(
        default_factory=list,
        description="Extra test commands, run with the newest QGIS and the package installed.",
    )


class Plugin(_Model):
    """Overrides for one plugin; the table key is the slug on plugins.qgis.org."""

    # Set from the table key, not written in the table.
    slug: SkipJsonSchema[Slug]
    name: str | None = Field(
        None,
        pattern=r"^qgis-plugin-[a-z0-9][a-z0-9._-]*$",
        description="Package name instead of qgis-plugin-<slug lowercased>. Needed when the "
        "default name is shared with another plugin.",
    )
    skip: str | None = Field(None, description="Don't build this plugin, for this reason.")
    note: str | None = Field(
        None, description="Free text: why the overrides are there, e.g. where add_run came from."
    )
    add_run: list[RunSpec] = Field(
        default_factory=list,
        description="Extra run dependencies from conda-forge, e.g. Python packages the plugin "
        "imports but doesn't bundle.",
    )
    qgis: QgisRange | None = None
    version: dict[str, str] = Field(
        default_factory=dict,
        description="Conda version for an upstream version that can't be normalised "
        'automatically, e.g. { "2.0 final" = "2.0" }.',
    )
    license: str | None = Field(
        None, description="SPDX licence id, instead of detecting it from the ZIP."
    )
    build_number: int = Field(
        0,
        ge=0,
        description="Raise it when an override changes an already published version.",
    )
    test: TestOptions = Field(default_factory=TestOptions)


class Config(_Model):
    """plugins.toml: the plugins to package and how."""

    settings: Settings
    plugins: dict[Slug, Plugin] = Field(
        default_factory=dict,
        description="One table per plugin, keyed by its slug on plugins.qgis.org (exact, "
        "case-sensitive) and sorted case-insensitively.",
    )

    @model_validator(mode="before")
    @classmethod
    def _slugs_from_keys(cls, data: Any) -> Any:
        if isinstance(data, dict) and isinstance(data.get("plugins"), dict):
            plugins = {}
            for slug, table in data["plugins"].items():
                if isinstance(table, dict):
                    if "slug" in table:
                        raise ValueError(
                            f"[plugins.{slug}] slug: not allowed; the slug is the table key"
                        )
                    table = {"slug": slug, **table}
                plugins[slug] = table
            data = {**data, "plugins": plugins}
        return data

    @property
    def order(self) -> list[str]:
        """Table order as written, to check it's sorted."""
        return list(self.plugins)

    def select(self, slugs: list[str] | None) -> list[str]:
        """The selected slugs, or the given ones after checking they are selected."""
        if not slugs:
            return list(self.plugins)
        unknown = [s for s in slugs if s not in self.plugins]
        if unknown:
            raise ConfigError(f"not in plugins.toml: {', '.join(unknown)}")
        return slugs


def _where(loc: tuple) -> str:
    """("plugins", "demo", "add_run", 0) -> "[plugins.demo] add_run[0]"."""
    parts = list(loc)
    head = ""
    if parts[:1] == ["plugins"] and len(parts) >= 2:
        head, parts = f"[plugins.{parts[1]}]", parts[2:]
    elif parts[:1] == ["settings"]:
        head, parts = "[settings]", parts[1:]
    tail = ""
    for part in parts:
        tail += f"[{part}]" if isinstance(part, int) else (f".{part}" if tail else str(part))
    return f"{head} {tail}".strip() or "plugins.toml"


def _message(error: ValidationError) -> str:
    lines = []
    for e in error.errors():
        loc = tuple(p for p in e["loc"] if p != "[key]")  # a dict key's own error
        if loc[:1] == ("plugins",) and loc[2:] == ("slug",):
            continue  # derived from the table key, which is reported already
        msg = e["msg"].removeprefix("Value error, ")
        lines.append(f"{_where(loc)}: {msg}" if loc else msg)
    return "\n".join(lines)


def parse(data: dict) -> Config:
    try:
        return Config.model_validate(data)
    except ValidationError as e:
        raise ConfigError(_message(e)) from None


def load(path: Path = DEFAULT_CONFIG) -> Config:
    """Read and validate plugins.toml; errors name the file and each problem's table."""
    with path.open("rb") as f:
        try:
            data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ConfigError(f"{path}: {e}") from None
    try:
        return parse(data)
    except ConfigError as e:
        raise ConfigError(f"{path}:\n  " + str(e).replace("\n", "\n  ")) from None


def json_schema() -> str:
    schema = Config.model_json_schema(by_alias=True)
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", **schema}
    return json.dumps(schema, indent=2) + "\n"
