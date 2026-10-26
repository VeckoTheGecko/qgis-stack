"""Command-line entry point. Commands follow docs/plan.md section 8; unimplemented ones
say which milestone adds them and exit with NOT_IMPLEMENTED."""

import argparse
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

NOT_IMPLEMENTED = 2


def _feed(args: argparse.Namespace) -> int:
    from qp import config, feed

    settings = config.load(args.config).settings
    for path in feed.update(settings.feed_lines):
        print(f"{path}: {len(feed.parse(path.read_bytes()))} plugins")
    return 0


def _generate(args: argparse.Namespace) -> int:
    from qp import config, feed, recipe

    cfg = config.load(args.config)
    try:
        slugs = cfg.select(args.plugin)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    entries = feed.load(cfg.settings.feed_lines)
    failed = False
    for slug in slugs:
        found = feed.versions(entries, slug, cfg.settings.include_experimental)
        if not found:
            print(f"{slug}: not in the feeds for QGIS {', '.join(cfg.settings.feed_lines)}")
            failed = True
            continue
        for entry in found:
            try:
                data = feed.download(slug, entry.version)
                generated = recipe.generate(entry, data, cfg.settings.test_lines)
            except ValueError as e:
                print(f"{slug} {entry.version}: {e}", file=sys.stderr)
                failed = True
                continue
            out = args.recipes_dir / generated.dirname
            if out.exists():
                shutil.rmtree(out)
            print(recipe.write(generated, args.recipes_dir))
    return 1 if failed else 0


def _build(args: argparse.Namespace) -> int:
    from qp import build

    dirs = build.recipe_dirs(args.recipes_dir, args.plugin)
    if not dirs:
        print(f"no generated recipes in {args.recipes_dir}; run `qp generate` first")
        return 1
    failed = [d.name for d in dirs if build.build(d, args.output_dir) != 0]
    for name in failed:
        print(f"FAILED: {name}", file=sys.stderr)
    return 1 if failed else 0


@dataclass(frozen=True)
class Command:
    name: str
    help: str
    milestone: str
    add_arguments: Callable[[argparse.ArgumentParser], None] = field(default=lambda parser: None)
    run: Callable[[argparse.Namespace], int] | None = None


def _plugin_filter(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--plugin", metavar="SLUG", action="append", help="only this plugin")


def _slug(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("slug", help="plugin slug on plugins.qgis.org")


def _top(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-n", type=int, default=50, help="number of plugins (default: 50)")


COMMANDS = [
    Command("feed", "fetch and cache the plugins.qgis.org feeds", "M1", run=_feed),
    Command("plan", "list selected plugin versions not yet on the channel", "M5"),
    Command("generate", "write rattler-build recipes to recipes/", "M1", _plugin_filter, _generate),
    Command(
        "build", "build and test the generated recipes into output/", "M1", _plugin_filter, _build
    ),
    Command("validate", "check built packages: layout, licence, no binaries", "M2"),
    Command("upload", "upload built packages to the prefix.dev channel", "M5"),
    Command("add", "add a plugin to plugins.toml", "M2", _slug),
    Command("top", "suggest the most-downloaded plugins not yet selected", "M8", _top),
    Command("scan-deps", "suggest add_run entries from a plugin's ZIP", "M3", _slug),
    Command("check", "sanity checks: config, naming collisions, overrides vs channel", "M2"),
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qp", description="Turn QGIS plugins from plugins.qgis.org into conda packages."
    )
    parser.add_argument("--config", type=Path, default=Path("plugins.toml"), help="%(default)s")
    parser.add_argument("--recipes-dir", type=Path, default=Path("recipes"), help="%(default)s")
    parser.add_argument("--output-dir", type=Path, default=Path("output"), help="%(default)s")
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)
    for command in COMMANDS:
        sub = subparsers.add_parser(command.name, help=command.help, description=command.help)
        command.add_arguments(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = next(c for c in COMMANDS if c.name == args.command)
    if command.run is None:
        print(f"qp {command.name}: not implemented yet (planned for {command.milestone})")
        return NOT_IMPLEMENTED
    return command.run(args)
