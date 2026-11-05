"""Command-line entry point. Commands follow the design plan section 8; unimplemented ones
say which milestone adds them and exit with NOT_IMPLEMENTED."""

import argparse
import shutil
import subprocess
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


def _recipes(cfg, slugs: list[str]) -> tuple[list, list[str]]:
    """Recipes for every non-skipped plugin version in the feeds, and the problems hit
    on the way (plugin not in the feeds, licence or version needing an override, ...)."""
    from qp import feed, recipe

    entries = feed.load(cfg.settings.feed_lines)
    recipes, problems = [], []
    for slug in slugs:
        plugin = cfg.plugins[slug]
        if plugin.skip:
            print(f"{slug}: skipped ({plugin.skip})")
            continue
        found = feed.versions(entries, slug, cfg.settings.include_experimental)
        if not found:
            lines = ", ".join(cfg.settings.feed_lines)
            problems.append(f"{slug}: not in the feeds for QGIS {lines}")
        for entry in found:
            try:
                data = feed.download(slug, entry.version)
                recipes.append(recipe.generate(entry, data, cfg.settings.test_lines, plugin))
            except ValueError as e:
                problems.append(f"{slug} {entry.version}: {e}")
    return recipes, problems


def _load(args: argparse.Namespace):
    from qp import config

    cfg = config.load(args.config)
    return cfg, cfg.select(getattr(args, "plugin", None))


def _report(problems: list[str]) -> int:
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


def _generate(args: argparse.Namespace) -> int:
    from qp import recipe

    cfg, slugs = _load(args)
    recipes, problems = _recipes(cfg, slugs)
    for generated in recipes:
        out = args.recipes_dir / generated.dirname
        if out.exists():
            shutil.rmtree(out)
        print(recipe.write(generated, args.recipes_dir))
    return _report(problems)


def _check(args: argparse.Namespace) -> int:
    from qp import channel, check, feed

    cfg, slugs = _load(args)
    feed_slugs = {e.slug for e in feed.load(cfg.settings.feed_lines)}
    problems = check.sorted_tables(cfg)
    problems += check.naming(cfg, feed_slugs)
    problems += check.conda_forge_clash(cfg, channel.conda_forge_names())
    recipes, generate_problems = _recipes(cfg, slugs)
    problems += generate_problems
    target = args.channel or cfg.settings.channel
    if target:
        problems += check.build_numbers(recipes, channel.records(target))
    else:
        print("no channel given: build numbers not checked (--channel or settings.channel)")
    if not problems:
        print(f"OK: {len(slugs)} plugins, {len(recipes)} recipes")
    return _report(problems)


def _target(args: argparse.Namespace, cfg) -> str | None:
    return args.channel or cfg.settings.channel


def _plan(args: argparse.Namespace) -> int:
    from qp import channel, plan

    cfg, slugs = _load(args)
    target = _target(args, cfg)
    if not target:
        print("no channel given (--channel or settings.channel)", file=sys.stderr)
        return 1
    recipes, problems = _recipes(cfg, slugs)
    have = plan.published(channel.records(target))
    todo = [r for r in recipes if (r.name, r.version, r.build_number) not in have]
    print(f"{len(todo)} of {len(recipes)} packages not on {target}")
    for r in todo:
        print(f"- {r.name} {r.version} (build {r.build_number})")
    return _report(problems)


def _upload(args: argparse.Namespace) -> int:
    from qp import channel, config, plan

    cfg = config.load(args.config)
    target = _target(args, cfg)
    if not target:
        print("no channel given (--channel or settings.channel)", file=sys.stderr)
        return 1
    try:
        name = channel.prefix_channel(target)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    paths = args.packages or sorted(args.output_dir.glob("noarch/qgis-plugin-*.conda"))
    have = plan.published(channel.records(target))
    todo = [p for p in paths if plan.package_key(p) not in have]
    print(f"{len(todo)} of {len(paths)} packages not on {target}")
    if not todo:
        return 0
    # Authentication: PREFIX_API_KEY, the keychain, or trusted publishing in CI.
    cmd = ["rattler-build", "upload", "prefix", "--channel", name, "--skip-existing"]
    cmd += [str(p) for p in todo]
    if args.dry_run:
        print(" ".join(cmd))
        return 0
    return subprocess.run(cmd, check=False).returncode


def _catalogue(args: argparse.Namespace) -> int:
    from qp import catalogue, channel, config

    cfg = config.load(args.config)
    target = args.channel or cfg.settings.channel
    if not target:
        print("no channel given (--channel or settings.channel)", file=sys.stderr)
        return 1
    entries = catalogue.entries(channel.records(target), cfg)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(catalogue.dumps(entries))
    print(f"wrote {args.output} ({len(entries)} packages from {target})")
    return 0


def _validate(args: argparse.Namespace) -> int:
    from qp import validate

    paths = args.packages or sorted(args.output_dir.glob("noarch/qgis-plugin-*.conda"))
    if not paths:
        print(f"no packages in {args.output_dir}/noarch; run `qp build` first")
        return 1
    problems = [p for path in paths for p in validate.validate(path)]
    if not problems:
        print(f"OK: {len(paths)} packages")
    return _report(problems)


def _add(args: argparse.Namespace) -> int:
    from qp import config, edit, feed

    settings = config.load(args.config).settings
    if args.slug not in {e.slug for e in feed.load(settings.feed_lines)}:
        print(f"{args.slug}: not in the feeds for QGIS {', '.join(settings.feed_lines)}")
        return 1
    if not edit.add_plugin(args.config, args.slug):
        print(f"{args.slug}: already in {args.config}")
        return 1
    print(f"added [plugins.{args.slug}] to {args.config}")
    return 0


def _build(args: argparse.Namespace) -> int:
    from qp import build

    dirs = build.recipe_dirs(args.recipes_dir, args.plugin)
    if not dirs:
        print(f"no generated recipes in {args.recipes_dir}; run `qp generate` first")
        return 1
    if args.channel:
        from qp import channel, plan

        have = plan.published(channel.records(args.channel))
        for d in [d for d in dirs if build.recipe_key(d) in have]:
            print(f"{d.name}: already on {args.channel}, skipped")
        dirs = [d for d in dirs if build.recipe_key(d) not in have]
    failed = [d.name for d in dirs if build.build(d, args.output_dir, not args.no_test) != 0]
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


def _build_args(parser: argparse.ArgumentParser) -> None:
    _plugin_filter(parser)
    parser.add_argument(
        "--no-test", action="store_true", help="skip the QGIS tests (fast, for iterating)"
    )
    parser.add_argument("--channel", help="skip packages already on this channel (URL or dir)")


def _plan_args(parser: argparse.ArgumentParser) -> None:
    _plugin_filter(parser)
    _check_args(parser)


def _upload_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--channel", help="prefix.dev channel URL (default: settings.channel)")
    parser.add_argument("--dry-run", action="store_true", help="print the upload command only")
    parser.add_argument("packages", nargs="*", type=Path, help="default: output/noarch/*")


def _schema(args: argparse.Namespace) -> int:
    from qp import config

    schema = config.json_schema()
    if args.output:
        args.output.write_text(schema)
        print(f"wrote {args.output}")
    else:
        print(schema, end="")
    return 0


def _schema_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-o", "--output", type=Path, help="write here instead of stdout")


def _check_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--channel", help="published channel: URL or local dir (e.g. output)")


def _catalogue_args(parser: argparse.ArgumentParser) -> None:
    _check_args(parser)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("docs/src/data/plugins.json"),
        help="%(default)s",
    )


def _validate_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("packages", nargs="*", type=Path, help="default: output/noarch/*")


def _top(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-n", type=int, default=50, help="number of plugins (default: 50)")


COMMANDS = [
    Command("feed", "fetch and cache the plugins.qgis.org feeds", "M1", run=_feed),
    Command(
        "plan", "list selected plugin versions not yet on the channel", "M5", _plan_args, _plan
    ),
    Command("generate", "write rattler-build recipes to recipes/", "M1", _plugin_filter, _generate),
    Command(
        "build", "build and test the generated recipes into output/", "M1", _build_args, _build
    ),
    Command(
        "validate",
        "check built packages: layout, licence, no binaries",
        "M2",
        _validate_args,
        _validate,
    ),
    Command(
        "upload",
        "upload built packages not yet on the prefix.dev channel",
        "M5",
        _upload_args,
        _upload,
    ),
    Command("add", "add a plugin to plugins.toml", "M2", _slug, _add),
    Command("schema", "print the JSON schema of plugins.toml", "M2", _schema_args, _schema),
    Command("top", "suggest the most-downloaded plugins not yet selected", "M8", _top),
    Command("scan-deps", "suggest add_run entries from a plugin's ZIP", "M3", _slug),
    Command(
        "check",
        "sanity checks: config, naming collisions, overrides vs channel",
        "M2",
        _check_args,
        _check,
    ),
    Command(
        "catalogue",
        "write the docs site's plugin table from the channel's repodata",
        "M6",
        _catalogue_args,
        _catalogue,
    ),
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
    from qp.channel import ChannelError
    from qp.config import ConfigError

    try:
        return command.run(args)
    except (ConfigError, ChannelError) as e:
        print(e, file=sys.stderr)
        return 1
