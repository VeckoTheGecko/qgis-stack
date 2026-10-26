# Exploration notes: Pixi for geospatial / QGIS

Running notes from conversations, newest last.

## 2026-10-22: Pixi and geospatial plugin ecosystems

### Goal
Use Pixi for reproducible geospatial setups. Look for software whose plugin or extension installs are painful and could be streamlined.

### Candidates found (best first)
1. **QGIS.** On conda-forge (`qgis`), along with processing backends (`grass`, `saga`). The pain is plugin Python dependencies being pip-installed into QGIS's bundled Python, all plugins sharing one environment, and per-user profile state.
2. **GDAL driver plugins.** conda-forge splits `libgdal-core` from per-driver packages (`libgdal-netcdf`, `libgdal-hdf5`, `libgdal-arrow-parquet`, ...).
3. **GRASS addons.** `g.extension` compiles from source. Pixi can provide the compilers, and `GRASS_ADDON_BASE` keeps addons project-local.
4. **PostGIS.** `postgresql`, `postgis`, `pgrouting` and `h3-pg` are on conda-forge, so pixi tasks can run a per-project spatial database.
- Poor fits: ArcGIS Pro (proprietary, Esri channel) and ESA SNAP (Java, own update centre).

### QGIS plugin management: weak points
- `metadata.txt` has `plugin_dependencies` (other QGIS plugins only). **No field for Python package dependencies.**
- One shared Python for all plugins means silent version conflicts.
- No pinning or lockfile: the GUI installs the latest compatible version.
- No official CLI. Options: 3Liz's `qgis-plugin-manager` (PyPI) or a manual unzip.
- QGIS upgrades can change the Python version and break pip-installed packages.
- QPIP (OPENGIS.ch) adds opt-in `requirements.txt` support for plugins.

### Sketch: Pixi + QGIS setup
- QGIS and the plugin deps go in `pixi.toml`. The lockfile pins everything conda-side.
- `[activation.env] QGIS_PLUGINPATH = "$PIXI_PROJECT_ROOT/plugins"`
- Launch task: `qgis --profiles-path $PIXI_PROJECT_ROOT/.qgis-profiles`
- Plugins themselves aren't conda packages, so a pixi task fetches pinned ZIPs.
- ⚠️ The first sketch pinned `qgis = "3.40.*"`. QGIS 4.x (Qt6) has since been released, so decide whether to target 3.x LTR or 4.x.

### QGIS plugin creation and hosting
Full write-up in [`qgis-plugin-system.md`](qgis-plugin-system.md). Key points:
- A plugin is a Python package with `classFactory(iface)`, plus a class with `initGui()`/`unload()` and a `metadata.txt`.
- The official repo (plugins.qgis.org) requires a **GPLv2+-compatible licence** and a `LICENSE` file. It also bans **binaries**, caps ZIPs at **25 MB**, and requires a **public source repo**.
- Every upload goes through **blocking Bandit and detect-secrets scans**.
- QGIS 4 compatibility is declared with `qgisMaximumVersion = 4.99`; `supportsQt6` is deprecated.
- The no-binaries rule means heavy dependencies must come from the environment, which is exactly what Pixi can provide.

## 2026-10-23: Has the plugin source always been the same place?

Short answer: **since QGIS 1.8 (2012) there has been one official source, plugins.qgis.org.** QGIS 1.8, 2.x, 3.x and 4.x all hit the same feed. What differs between versions is the `?qgis=X.Y` query string, so the server returns only the plugins and versions compatible with that release.

Checked against the `installer_data.py` source on each release branch:

| QGIS | Default repo URL(s) |
|---|---|
| ≤ 1.7 | `http://pyqgis.org/repo/official` and `http://pyqgis.org/repo/contributed`, **plus ~12 pre-configured author repos** (Carson Farmer, Barry Rowlingson, Faunalia, Sourcepole, GIS-Lab, ...) |
| 1.8 | `http://plugins.qgis.org/plugins/plugins.xml`. The pyqgis.org and author repos move into a `depreciatedRepos` list |
| 2.x (by 2.18) | Same, now `https://`. The deprecated-repos list is still carried |
| 3.x, 4.x | `https://plugins.qgis.org/plugins/plugins.xml`. The legacy list is gone. Users can't remove the official repo: the installer re-adds it if it's missing (they can only disable it) |

How version targeting works today:
- The client appends `?qgis=<major.minor>`, so 3.40.5 sends `?qgis=3.40`.
- The server filters on each plugin version's `qgisMinimumVersion`/`qgisMaximumVersion` and returns the **newest compatible version only**. Older versions aren't listed in the feed.
- Configured repos live in the profile's `QGIS3.ini` under `[app/plugin_repositories]`.

Implication for Pixi: one feed URL serves every version. To pin, record the plugin version and fetch the ZIP directly, e.g. `https://plugins.qgis.org/plugins/<name>/version/<ver>/download/`, rather than trusting what the feed returns.

### Open ideas / next steps
- Scaffold a working `pixi.toml` with a plugin-fetch task and a project-local profile.
- Test it with a couple of plugins that have heavy dependencies.

## 2026-10-23: Fixing metadata of an old conda-forge release

Question: the latest is 0.4.0 and 0.3.1 is already released. How do you change 0.3.1's metadata? There are three routes, depending on how big the change is:

1. **Rebuild on a maintenance branch.** Branch the feedstock (e.g. `v0.3.x`) from the commit that built 0.3.1. Edit the recipe, **bump `build.number`**, and open a PR against that branch. CI uploads from any branch. The new build sorts above the old one, so the solver prefers it. You can't overwrite an existing filename on anaconda.org; artifacts are immutable.
2. **Repodata patch (no rebuild).** Open a PR to `conda-forge/conda-forge-repodata-patches-feedstock` (`recipe/patch_yaml/<pkg>.yaml`, or the older `gen_patch_json.py`). This rewrites `depends`/`constrains` in the channel's `repodata.json`. The `index.json` inside the tarball doesn't change. It's the usual fix for a missing upper bound on old builds.
3. **Mark broken.** Open a PR to `conda-forge/admin-requests`. It moves the files to the `broken` label so the solver no longer sees them.

Relevance for Pixi: Pixi reads the patched repodata, so patches apply to it automatically. A lockfile pins exact files, though, so you need to re-lock to pick up a new build or a patch.

## 2026-10-23: Conda recipe for a QGIS plugin (QuickMapServices)

Recipe: [`recipes/qgis-plugin-quick-map-services/`](recipes/qgis-plugin-quick-map-services/). It was written following the `conda-forge` agent skill, which is installed via `pixi global` (`agent-skill-conda-forge`) and managed by `pixi-skills`. Built with rattler-build 0.74 into `output/` (gitignored local channel).

- **Plugin choice:** NextGIS QuickMapServices 1.5.2, the most-downloaded plugin (~12.8M). Pure Python, GPL-2.0-or-later, `qgisMinimumVersion=3.32`, `qgisMaximumVersion=4.99`.
- **Source:** the stable link `https://plugins.qgis.org/plugins/<slug>/version/<ver>/download/`. `file_name:` stops rattler-build guessing the archive type from the URL, and `build.sh` unzips explicitly. The ZIP contains a duplicate `LICENSE` entry, so it uses `unzip -o`.
- **Install location:** `$PREFIX/share/qgis/python/plugins/<slug>`. That's `QgsApplication.pkgDataPath()/python/plugins`, the *system* plugin dir where `processing` and `db_manager` live, so no `QGIS_PLUGINPATH` is needed. It counts as a core plugin, so it isn't upgradable or removable from Plugin Manager; conda owns it. It still needs enabling once in Plugin Manager.
- **metadata.txt to conda constraint:**
  - QGIS's own rule (`pyplugin_installer.version_compare.isCompatible`) is inclusive on both ends. It pads two-part versions: min gets `.0`, max gets `.99`. An empty max defaults to `<major>.99`.
  - So `3.32`/`4.99` becomes `qgis >=3.32.0,<=4.99.99`.
  - A recipe is rendered before the source is downloaded, so it can't read the ZIP directly. Instead:
    1. `tools/sync_qgis_plugin_recipe.py RECIPE_DIR [--version X]` downloads the ZIP, parses `metadata.txt`, and rewrites `version`/`qgis_min`/`qgis_max`/`sha256` in the recipe context.
    2. `build.sh` re-parses `metadata.txt` and **fails the build** if the recipe has drifted from it.
- **Gotcha:** plugins.qgis.org (Cloudflare) returns 403 to Python urllib's default User-Agent; curl is fine.
- **Verified:**
  - Tests pass on QGIS **4.2.3** (latest) and **3.40.3**. They check the plugin is discovered by `qgis.utils`, passes `isCompatible()` for the running QGIS, and imports.
  - The solver rejects `qgis=3.28`.
  - Changing `qgis_max` to `3.99.99` makes the build fail with a clear message.
- Not done: `conda-smithy lint` (needs a feedstock/staged-recipes layout). Plugin Python deps aren't an issue here (QMS needs none), but plugins that need them would list them in `run:`.

## 2026-10-25: QGIS plugins known for hard dependency setups

Question: which plugins are notoriously hard to set up because of their dependencies? Answered from memory, not yet checked against current plugin metadata.

**Heavy Python scientific/ML stacks** (need packages QGIS doesn't ship):
- **EnMAP-Box**: the classic example. Needs scikit-learn, scipy, matplotlib, numba, h5py, netCDF4, astropy, PyOpenGL, and optionally xgboost/lightgbm. Its docs have separate install guides per OS, and they recommend conda.
- **Semi-Automatic Classification Plugin (SCP)**: from v8 it needs `remotior-sensus` plus scikit-learn, scipy, matplotlib, and optionally PyTorch.
- **Deepness**, **Geo-SAM / GeoAI** and similar deep-learning plugins: need onnxruntime / PyTorch / segment-anything / opencv. CPU vs GPU builds and wheel size make these painful.
- **dzetsaka**: scikit-learn.

**External binaries or toolchains:**
- **OTB provider (Orfeo Toolbox)**: needs a separate OTB install whose version matches.
- **SAGA NextGen provider**: needs a separate SAGA install; SAGA was dropped from core.
- **WhiteboxTools**: needs the WBT binary.
- **LAStools**: Windows binaries, so Wine on macOS/Linux.

**Native libraries bundled as wheels:**
- **Mergin Maps** (`pygeodiff`) and **QFieldSync** (`libqfieldsync`): platform- and Python-ABI-specific builds that can break when QGIS's Python version changes.

**Root causes:**
1. QGIS installers on Windows (OSGeo4W) and macOS ship their own Python, often without a usable pip.
2. Plugins that pip-install into the user site-packages break on QGIS upgrades, or clash with other plugins.
3. pip-installed numpy/scipy can have an ABI mismatch with the GDAL/numpy that QGIS was built against.
4. The Qt6 / QGIS 4 move breaks plugins that pin PyQt5 deps.
5. Helper plugins such as **QPIP** read a `requirements.txt` per plugin and pip-install it.

**Pixi angle:** these are the strongest case for packaging plugins as conda packages. All the deps come from the same conda-forge environment as `qgis`, so ABI consistency is solved for free. EnMAP-Box or SCP would be a good next recipe to test the approach (see [QuickMapServices recipe](recipes/qgis-plugin-quick-map-services/)).

## 2026-10-26: Pixi workspace using the local plugin recipe

[`workspace/`](workspace/) holds a pixi workspace with QGIS 4.2.3 and the QMS package built from `../recipes/.../recipe.yaml`.

- **Source dependency:** `qgis-plugin-quick-map-services = { path = "../recipes/qgis-plugin-quick-map-services/recipe.yaml" }`. Pixi 0.83 accepts a path straight to `recipe.yaml`, but needs `preview = ["pixi-build"]`. Pixi runs rattler-build itself, recipe tests included, during `pixi install`.
- **macOS floor:** `pixi add qgis` silently resolved **3.40.3**. QGIS 4.2.3 needs `__osx >= 14.0` (libpq 18 needs 13.3, moltenvk 1.4 via Qt 6.11 needs 14.0). Set it per platform: `platforms = [{ name = "osx-arm64-14", platform = "osx-arm64", macos = "14.0" }, "linux-64"]`. `[system-requirements]` is deprecated in 0.83.
- **Plugin discovery:** already works, because the package installs into `$CONDA_PREFIX/share/qgis/python/plugins`, QGIS's system plugin dir.
- **Plugin enabling:** a new plugin starts *disabled*. Only `db_manager`, `processing`, `MetaSearch` and the provider plugins are auto-enabled, by a hard-coded list in `qgspluginregistry.cpp`.
  - Fix: `QGIS_GLOBAL_SETTINGS_FILE` plus `[PythonPlugins] quick_map_services=true`. `QgsSettings::value` falls back to the global file when the profile has no value, so the user can still turn the plugin off.
  - Pointing at your own global file *replaces* `$CONDA_PREFIX/share/qgis/resources/qgis_global_settings.ini`, which has real defaults (OSM XYZ connection, snapping). So `activate.sh` concatenates bundled + `qgis-plugins.ini` into `.qgis/` on every activation.
  - Control run without the entry: found but `inactive`. With it: `active`.
- **`QGIS_PLUGINPATH=$PIXI_PROJECT_ROOT/plugins`** is for unpackaged/dev plugins and has the highest priority. Search order: `QGIS_PLUGINPATH`, then the profile's `python/plugins`, then the system dir. So a newer QMS installed via Plugin Manager into the profile would **shadow** the conda one.
- **`pixi run qgis`** uses `--profiles-path .qgis`, a project-local profile.
- **Headless gotcha:** a fresh profile calls `createAndStoreRandomMasterPasswordInKeyChain()` at startup, which blocks forever offscreen (stuck in the macOS Keychain; found with `sample <pid>`).
  - Putting `[authentication] generate-random-password-for-keychain=false` in the *global* file doesn't help. The probable cause is that settings-tree entries go through a static `QgsSettings` that's created before main() attaches the global file. I didn't verify that in the source.
  - So `list-plugins` seeds a throwaway profile's `QGIS4.ini` with those keys instead (`qgis-headless.ini`).
- **`pixi run list-plugins`:** runs QGIS offscreen with `--code check_plugins.py` and prints each plugin, active/inactive, and where it was found. Python stdout is block-buffered under `--code`, so it uses `line_buffering`.

## 2026-10-26: Pipeline plan (RoboStack / Octoconda comparison)

Full plan in [`docs/plan.md`](docs/plan.md). New findings:
- **RoboStack** (`RoboStack/robostack`) is now one monorepo for all ROS 2 distros: vinca + rattler-build + pixi. It has dependency patches (`add_host`/`add_run`), a rosdep → conda mapping, per-package tests, `rs check`, prefix.dev OIDC uploads, robostack-bot and nightly package tests. Most of its complexity (pinning, ABI, staged builds, mutex) doesn't apply to noarch plugins.
- **Octoconda** (`prefix-dev/octoconda`) is a stateless sync. It uses the channel as state, a TOML config with per-package overrides, a cron schedule, and `validate_conda_package.py`. The plan is a hybrid of the two.
- **Feed facts:**
  - `external_dependencies` is empty for all 1,591 plugins in the 4.2 feed, and `plugin_dependencies` isn't in the feed at all. Deps must come from scanning ZIPs plus overrides.
  - 31 versions aren't plain numbers.
  - No public API lists all versions of a plugin.
- **Immutability:** approved versions can't be edited, but can be deleted and the same version number re-uploaded, so pin `sha256` and report drift.
- **Windows:** QGIS installs under `%LIBRARY_PREFIX%`, so the plugin dir is `Library/share/qgis/python/plugins`. Use two noarch variants (`__unix`/`__win`).
- **Run deps carry no channel:** users must list our channel + conda-forge. Never publish a name that exists on conda-forge (strict channel priority).
- **Naming collisions** (raised in review):
  - Mapping slugs with lowercase + `_` → `-` gives **6 collisions** among the 3,849 slugs in the 3.40 + 4.2 feeds, including `profile-manager`/`profile_manager`.
  - plugins.qgis.org blocks case-only duplicates (`package_name__iexact`). Since 2024-11 new slugs must be Python identifiers (no `-`). Under a dash mapping, a new `foo_bar` can still collide with any of the 214 legacy hyphenated slugs.
  - Decision: `qgis-plugin-<slug.lower()>` **keeping `_`**. Only the 5 legacy case-only pairs remain, and they get pre-assigned names. Collisions are never auto-resolved. See docs/plan.md §5.1 / §15.

## 2026-10-26: M0, tool skeleton

On branch `pipeline`.
- The plan moved to `docs/plan.md`.
- Root `pixi.toml` (python 3.14, pytest, ruff) installs the tool editable from `tools/` (`tools/pyproject.toml`, hatchling). The package `qp` provides the `qp` console script.
- `qp` has every command from plan §8 as a stub. Each one says which milestone implements it and exits 2.
- Tasks: `pixi run test` (14 tests), `pixi run lint`, `pixi run fmt`.
- **lefthook:**
  - `lefthook.yml` with pre-commit hooks: `ruff check --fix` then `ruff format` on staged `tools/**/*.py`, re-staged with `stage_fixed`, run sequentially via `priority`. `pixi lock --check` runs when `pixi.toml` or `tools/pyproject.toml` is staged.
  - pre-push hook: `pixi run test`.
  - `lefthook` is a pixi dependency; install the hooks with `pixi run install-hooks`. The hook script uses `lefthook` from `PATH`, falling back to the env's copy. Skip once with `LEFTHOOK=0`.
