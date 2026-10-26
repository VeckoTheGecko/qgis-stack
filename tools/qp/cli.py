"""Command-line entry point. Commands follow docs/plan.md section 8; unimplemented ones
say which milestone adds them and exit with NOT_IMPLEMENTED."""

import argparse
from collections.abc import Callable
from dataclasses import dataclass, field

NOT_IMPLEMENTED = 2


@dataclass(frozen=True)
class Command:
    name: str
    help: str
    milestone: str
    add_arguments: Callable[[argparse.ArgumentParser], None] = field(default=lambda parser: None)


def _plugin_filter(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--plugin", metavar="SLUG", action="append", help="only this plugin")


def _slug(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("slug", help="plugin slug on plugins.qgis.org")


def _top(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-n", type=int, default=50, help="number of plugins (default: 50)")


COMMANDS = [
    Command("feed", "fetch and cache the plugins.qgis.org feeds for the QGIS lines", "M1"),
    Command("plan", "list selected plugin versions not yet on the channel", "M5"),
    Command("generate", "write rattler-build recipes to recipes/", "M1", _plugin_filter),
    Command("build", "build and test the generated recipes into output/", "M1", _plugin_filter),
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
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)
    for command in COMMANDS:
        sub = subparsers.add_parser(command.name, help=command.help, description=command.help)
        command.add_arguments(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = next(c for c in COMMANDS if c.name == args.command)
    print(f"qp {command.name}: not implemented yet (planned for {command.milestone})")
    return NOT_IMPLEMENTED
