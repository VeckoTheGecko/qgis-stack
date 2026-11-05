# QGIS Stack

QGIS plugins from [plugins.qgis.org](https://plugins.qgis.org) as conda packages, so a whole QGIS setup (QGIS, plugins and the plugins' Python dependencies) can be declared in one `pixi.toml` and locked.

> [!NOTE]
> Unofficial, and not affiliated with QGIS.org. Work in progress: packages go to a test channel, [prefix.dev/veckothegecko/qgis-stack-test](https://prefix.dev/channels/@veckothegecko/qgis-stack-test).
> Most of this repository's code and docs were written with Claude Opus 5.5 and are not yet fully human-verified.

## Documentation

The docs site is built from [`docs/`](docs/) and deployed to GitHub Pages by [`.github/workflows/docs.yaml`](.github/workflows/docs.yaml).

- [Getting started](docs/src/content/docs/guides/getting-started.mdx)
- [Enabling plugins](docs/src/content/docs/guides/enabling-plugins.md)
- [Requesting a plugin](docs/src/content/docs/guides/requesting-plugins.md)
- [FAQ](docs/src/content/docs/faq.md)
- [The pipeline](docs/src/content/docs/maintainers/pipeline.md) and the [design plan](docs/src/content/docs/maintainers/plan.md)

Preview it locally:

```sh
pixi run docs-data   # plugin catalogue from the local channel in output/
pixi run docs-dev    # http://localhost:4321
```

## Development

Requires [pixi](https://pixi.sh).

```sh
pixi run install-hooks             # lefthook git hooks
pixi run test                      # unit tests
pixi run qp --help                 # the pipeline tool
pixi run qp generate               # recipes for plugins.toml into recipes/
pixi run qp build --no-test        # build them into output/
```
