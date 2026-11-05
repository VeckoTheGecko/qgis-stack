---
title: Enabling plugins
description: Where QGIS finds conda-installed plugins, and how to have them start enabled.
sidebar:
  order: 2
banner:
  content: AI-generated (Claude Opus 5.5, <code>claude-opus-5-5</code>) and not yet human-verified.
---

## Where the plugins go

Packages install into QGIS's **system plugin directory**,
`$CONDA_PREFIX/share/qgis/python/plugins/<slug>`. QGIS scans it at startup, so
no `QGIS_PLUGINPATH` is needed.

QGIS looks in three places. When the same plugin is in more than one, the
first wins:

| Priority | Location                    | Set by                  |
| -------- | --------------------------- | ----------------------- |
| 1        | `QGIS_PLUGINPATH`           | environment variable    |
| 2        | `<profile>/python/plugins`  | Plugin Manager installs |
| 3        | `share/qgis/python/plugins` | QGIS Stack packages     |

So a plugin that the Plugin Manager installed or upgraded in your profile
**shadows** the conda one. Use a profile inside the workspace
(`qgis --profiles-path $PIXI_PROJECT_ROOT/.qgis`) to keep them apart.

## Starting enabled

Installed plugins start disabled. QGIS reads which are enabled from the
`[PythonPlugins]` section of the profile's settings, and falls back to a
**global settings file** for anything the profile doesn't set. Point
`QGIS_GLOBAL_SETTINGS_FILE` at a file that lists your plugins:

```ini title="qgis-plugins.ini"
[PythonPlugins]
QuickOSM=true
DataPlotly=true
```

The keys are the plugin slugs (folder names), not the package names.

Setting `QGIS_GLOBAL_SETTINGS_FILE` replaces the global settings QGIS ships,
which hold defaults such as the OpenStreetMap XYZ connection. So combine the
bundled file with yours in an activation script:

```sh title="activate.sh"
mkdir -p "$PIXI_PROJECT_ROOT/.qgis"
cat "$CONDA_PREFIX/share/qgis/resources/qgis_global_settings.ini" \
  "$PIXI_PROJECT_ROOT/qgis-plugins.ini" \
  > "$PIXI_PROJECT_ROOT/.qgis/qgis_global_settings.ini"
```

```toml title="pixi.toml"
[activation]
scripts = ["activate.sh"]

[activation.env]
QGIS_GLOBAL_SETTINGS_FILE = "$PIXI_PROJECT_ROOT/.qgis/qgis_global_settings.ini"
```

A plugin you turn off in QGIS stays off: the profile setting wins over the
global one.

Shipping this with the packages, so that `pixi add qgis-stack-x` is enough,
is planned (see section 11 of the [design plan](/maintainers/plan/)).

## Plugins under development

Put work-in-progress plugins in a folder on `QGIS_PLUGINPATH`. It has the
highest priority, so it overrides a packaged version of the same plugin:

```toml title="pixi.toml"
[activation.env]
QGIS_PLUGINPATH = "$PIXI_PROJECT_ROOT/plugins"
```

## Running QGIS headless

A fresh profile stores a random authentication password in the OS keychain at
startup. Without a desktop session, that blocks forever. For headless runs
(tests, CI), create the profile first with these settings in its
`QGIS4.ini`:

```ini
[authentication]
generate-random-password-for-keychain=false
use-password-helper=false
```

Setting them in the global settings file had no effect when tested.
