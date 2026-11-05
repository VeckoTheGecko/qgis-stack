---
title: The pipeline
description: How QStack turns plugins.qgis.org into conda packages, and the commands and tasks maintainers use.
sidebar:
  order: 1
banner:
  content: AI-generated (Claude Opus 5.5, <code>claude-opus-5-5</code>) and not yet human-verified.
---

The pipeline is a small Python tool, `qp` (in `tools/qp/`), driven by
`plugins.toml`. The [design plan](/maintainers/plan/) has the full reasoning.

```
plugins.qgis.org feeds ──► qp generate ──► recipes/ ──► qp build ──► output/ ──► qp upload ──► prefix.dev
       (XML, ZIPs)        plugins.toml      (rattler-build)  (tests in QGIS)   (local channel)
```

For each selected plugin, `qp generate`:

1. reads the plugins.qgis.org feeds for each QGIS line in `settings.feed_lines`;
2. downloads every listed version's ZIP (cached in `.cache/qp/`);
3. reads `metadata.txt` for the version and the QGIS range, and the licence
   from `LICENSE`;
4. applies the overrides from `plugins.toml`;
5. writes a rattler-build recipe that downloads the same ZIP from its stable
   URL, checks it against the recipe, and copies the plugin into
   `share/qgis/python/plugins/<slug>`.

## Commands

Run them with `pixi run qp <command>` from the repository root.

| Command      | Does                                                                            | Status       |
| ------------ | ------------------------------------------------------------------------------- | ------------ |
| `feed`       | Fetch and cache the plugins.qgis.org feeds                                      | ✅           |
| `add <slug>` | Add a plugin to `plugins.toml`, sorted                                          | ✅           |
| `generate`   | Write recipes to `recipes/`                                                     | ✅           |
| `build`      | Build (and test, unless `--no-test`) into `output/`                             | ✅           |
| `validate`   | Check built packages: layout, licence, no binaries                              | ✅           |
| `check`      | Config, naming collisions, conda-forge clashes, build numbers against a channel | ✅           |
| `schema`     | Print the JSON schema of `plugins.toml`                                         | ✅           |
| `catalogue`  | Write this site's plugin table from a channel's repodata                        | ✅           |
| `plan`       | List selected versions not yet on the channel                                   | ✅           |
| `upload`     | Upload built packages not yet on the prefix.dev channel                         | ✅           |
| `scan-deps`  | Suggest `add_run` from a plugin's imports                                       | planned (M3) |
| `top`        | Suggest popular plugins not yet selected                                        | planned (M8) |

## pixi tasks

| Task            | Does                                                         |
| --------------- | ------------------------------------------------------------ |
| `test`          | Unit tests (offline)                                         |
| `test-network`  | Tests that download from plugins.qgis.org                    |
| `lint`, `fmt`   | ruff over `tools/`                                           |
| `schema`        | Regenerate `plugins.schema.json`                             |
| `install-hooks` | Install the lefthook git hooks                               |
| `docs-data`     | Write the catalogue data from a channel (default: `output/`) |
| `docs-dev`      | Serve this site locally with live reload                     |
| `docs-build`    | Build this site into `docs/dist/`                            |
| `docs-check`    | Type-check the site and check formatting                     |
| `docs-fmt`      | Format the site with prettier                                |

The docs tasks run in a separate `docs` environment with Node.js and pnpm, so
the pipeline environment stays small.

## Working on these docs

The site is [Starlight](https://starlight.astro.build) in `docs/`. Pages are
Markdown/MDX in `docs/src/content/docs/`; the sidebar is set in
`docs/astro.config.mjs`.

```sh
pixi run qp build --no-test   # optional: some packages for the catalogue
pixi run docs-data            # catalogue data from output/
pixi run docs-dev             # http://localhost:4321
```

Link to other pages root-relative, without the base path
(`/guides/enabling-plugins/`): a rehype plugin in `astro.config.mjs` adds the
base, and [starlight-links-validator](https://github.com/HiDeoo/starlight-links-validator)
then checks every link at build time, so a broken link fails the build.

## CI

| Workflow             | Does                                                                                                                                                                               | Status                                 |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| `docs.yaml`          | Build the site on pull requests; build and deploy to GitHub Pages on `main`                                                                                                        | ✅                                     |
| `pr.yaml`            | Pull requests and `main`: lint, tests, `plugins.schema.json` up to date, `qp check`; build and test the packages not yet on the channel (all of them without a channel). No upload | ✅                                     |
| `sync.yaml`          | Daily: fetch feeds, plan, generate, build and test, validate, upload                                                                                                               | ✅ (untested until the channel exists) |
| `package-tests.yaml` | Nightly: test published packages against the newest QGIS                                                                                                                           | planned (M8)                           |

All workflows read the channel from the repository variable `QSTACK_CHANNEL`
(e.g. `https://prefix.dev/qstack`). Until it's set, `sync.yaml` does nothing,
`pr.yaml` builds every plugin, and the docs catalogue is empty.

## Publishing

The channel is the only state. A package is identified by its name, version and
build number. `qp plan`, `qp build --channel` and `qp upload` all skip what the
channel already has, so a failed or repeated sync just carries on where the last one
stopped. A plugin that fails to generate or build doesn't block the others; the run
uploads what passed and then fails, so the failure shows up.

One-off setup:

1. Create the channel on [prefix.dev](https://prefix.dev). Start with a test
   channel (e.g. `qstack-test`).
2. In the channel's settings, add this GitHub repository and the workflow
   `sync.yaml` as a trusted publisher. Uploads then use GitHub's OIDC token, with
   no API key stored anywhere.
3. Set the repository variable `QSTACK_CHANNEL` to the channel URL, e.g.
   `https://prefix.dev/qstack-test`.
4. Run **Sync** by hand (Actions → Sync → Run workflow), first with **dry run**.

To upload from your own machine instead, set `PREFIX_API_KEY` (or log in with
`pixi auth login prefix.dev --token <key>`) and run:

```sh
pixi run qp build --channel https://prefix.dev/qstack-test
pixi run qp validate
pixi run qp upload --channel https://prefix.dev/qstack-test --dry-run  # then without
```

A changed `add_run`, licence or other override for an already published version
needs a higher `build_number`; `qp check --channel <url>` catches a missing bump.
