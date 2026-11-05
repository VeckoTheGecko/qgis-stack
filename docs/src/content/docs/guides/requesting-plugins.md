---
title: Requesting a plugin
description: How plugins get into QGIS Stack, and how to fix their metadata with overrides.
sidebar:
  order: 4
banner:
  content: AI-generated (Claude Opus 5.5, <code>claude-opus-5-5</code>) and not yet human-verified.
---

QGIS Stack only packages the plugins listed in `plugins.toml` at the root of the
repository. Each plugin is one table, keyed by its slug on plugins.qgis.org
(the last part of its URL, case-sensitive). An empty table is enough when the
plugin's own metadata is right:

```toml title="plugins.toml"
[plugins.QuickOSM]
```

To request a plugin, open a pull request that adds its table. A request issue
form is planned.

## Adding a plugin

From a clone of the repository, with [pixi](https://pixi.sh) installed:

```sh
pixi run qp add QuickOSM                         # adds [plugins.QuickOSM], sorted
pixi run qp generate --plugin QuickOSM           # writes recipes/
pixi run qp build --plugin QuickOSM --no-test    # quick build into output/
pixi run qp build --plugin QuickOSM              # build and test in QGIS (slow)
pixi run qp check                                # naming, overrides, licences
```

`qp add` checks that the slug is on plugins.qgis.org. `qp check` catches
package-name collisions and names already taken on conda-forge.

## Overrides

Overrides fix what the plugin's metadata gets wrong or leaves out. Editors
with TOML schema support (e.g. VS Code with Even Better TOML) complete and
check them, using `plugins.schema.json`.

| Key             | Use                                                                                                                                                                                        |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `add_run`       | Extra run dependencies from conda-forge, e.g. `["plotly", "pandas"]`. Plain names or `name version`; no channels.                                                                          |
| `test.commands` | Extra test commands, e.g. importing the added dependencies.                                                                                                                                |
| `test.import`   | Set to `false` for plugins that can't be imported headless.                                                                                                                                |
| `qgis`          | `{ min = "3.40", max = "3.44" }` to **narrow** the declared range, e.g. when a plugin claims 4.x support but breaks there. It can't widen it: QGIS would refuse to load the plugin anyway. |
| `version`       | `{ "<upstream>" = "<conda>" }` for versions with no conda form, such as `latest`. See [plugin version strings](/background/plugin-versions/).                                              |
| `license`       | SPDX id, when it can't be detected from the plugin's `LICENSE`.                                                                                                                            |
| `name`          | A different package name, when the default collides with another plugin's.                                                                                                                 |
| `build_number`  | Raise it when an override changes an already published version.                                                                                                                            |
| `skip`          | Don't build this plugin, with the reason.                                                                                                                                                  |
| `note`          | Why the overrides are there, e.g. where `add_run` came from.                                                                                                                               |

For example:

```toml title="plugins.toml"
[plugins.DataPlotly]
add_run = ["plotly", "pandas"]
test.commands = ["python -c 'import plotly, pandas'"]
note = "imports plotly and pandas at load time and doesn't bundle them"
```

## What gets packaged

- Every version of the plugin that the plugins.qgis.org feeds list for QGIS
  3.40, 3.44, 4.0 and 4.2. Each feed lists the newest compatible version only,
  so this is usually one to three versions per plugin.
- Experimental versions are skipped.
- Plugins must have a GPL-compatible licence, as plugins.qgis.org requires.
  Packages include the plugin's `LICENSE` and are checked for binaries.
