"""Read plugins.toml: pipeline settings and the plugin selection."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG = Path("plugins.toml")


@dataclass(frozen=True)
class Settings:
    feed_lines: list[str]
    test_lines: list[str]
    include_experimental: bool = False


@dataclass(frozen=True)
class Config:
    settings: Settings
    # slug -> that plugin's table (overrides come in M2)
    plugins: dict[str, dict] = field(default_factory=dict)

    def select(self, slugs: list[str] | None) -> list[str]:
        """The selected slugs, or the given ones after checking they are selected."""
        if not slugs:
            return list(self.plugins)
        unknown = [s for s in slugs if s not in self.plugins]
        if unknown:
            raise ValueError(f"not in plugins.toml: {', '.join(unknown)}")
        return slugs


def load(path: Path = DEFAULT_CONFIG) -> Config:
    with path.open("rb") as f:
        data = tomllib.load(f)
    s = data.get("settings", {})
    settings = Settings(
        feed_lines=list(s["feed_lines"]),
        test_lines=list(s["test_lines"]),
        include_experimental=bool(s.get("include_experimental", False)),
    )
    return Config(settings=settings, plugins=dict(data.get("plugins", {})))
