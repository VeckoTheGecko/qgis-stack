---
title: Design plan
description: The plan for the pipeline from plugins.qgis.org to a prefix.dev channel.
sidebar:
  order: 2
banner:
  content: AI-generated (Claude Opus 5.5, <code>claude-opus-5-5</code>) and not yet human-verified. Check claims against the linked sources.
---

Status: draft, 2026-10-26. Builds on the hand-written recipe in `recipes/qgis-plugin-quick-map-services/`, the consumer setup in `test-workspace/`, and the flow sketched in `workflow.excalidraw`.

## 1. Goal

Turn QGIS plugins from plugins.qgis.org into conda packages automatically. Patch their metadata where the upstream metadata is incomplete, mainly missing Python dependencies, which today live in READMEs and setup instructions. Publish the packages to a prefix.dev channel. A user can then describe a whole working QGIS setup in one `pixi.toml`:

```toml
[workspace]
channels = ["https://prefix.dev/<channel>", "conda-forge"]

[dependencies]
qgis = "4.2.*"
qgis-plugin-quick_map_services = "*"
qgis-plugin-<something-with-deps> = "*"   # pulls e.g. geopandas, scikit-learn from conda-forge
```

Out of scope for now: patching plugin _code_. The layout leaves room for it (section 12).

## 2. Facts established so far (verified)

| Topic              | Finding                                                                                                                                                                                                                                                   | How verified                                             |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| Source of truth    | `https://plugins.qgis.org/plugins/plugins.xml?qgis=X.Y` has been the only official feed since QGIS 1.8. It returns only the newest version of each plugin that's compatible with X.Y                                                                      | `installer_data.py` on each release branch               |
| Stable download    | `https://plugins.qgis.org/plugins/<slug>/version/<ver>/download/` returns the ZIP                                                                                                                                                                         | curl; also the feed's `<download_url>`                   |
| Older versions     | No public API lists every version of a plugin. Only the feed (newest per QGIS minor) and the HTML pages                                                                                                                                                   | probed `/api/...` routes; `urls.py` has only a write API |
| Feed fields        | name, version, plugin_id, description, about, qgis_minimum/maximum_version, file_name, download_url, author, homepage, tracker, repository, tags, downloads, experimental, deprecated, server, trusted, `external_dependencies`                           | parsed feed                                              |
| Feed size          | QGIS 4.2: 1,591 plugins (189 experimental). QGIS 3.40: 4,222 plugins (1,074 experimental)                                                                                                                                                                 | parsed feed                                              |
| Python deps        | `external_dependencies` is **empty for all 1,591** plugins in the 4.2 feed. `plugin_dependencies` isn't in the feed, only in the ZIP's `metadata.txt`. **Dependencies have to be discovered from the ZIP and patched by us**                              | parsed feed                                              |
| Versions           | 31 of 1,591 aren't plain dotted numbers (`v4.23.1`, `1.5.6a`, `1.5.3.post2`, `2.0.0-beta1`)                                                                                                                                                               | parsed feed                                              |
| Mutability         | Approved versions can't be edited. They **can be deleted**, and `unique_together = (plugin, version)` then allows re-uploading the same version number with a different ZIP                                                                               | `QGIS-Plugins-Website` `views.py` / `models.py`          |
| Licence            | Upload is rejected without `<slug>/LICENSE` in the ZIP; the licence must be GPLv2+-compatible. Old plugins may predate the check                                                                                                                          | `validator.py`; publish docs                             |
| Binaries           | Not allowed in the ZIP, so every plugin is pure Python/data: **always `noarch`**                                                                                                                                                                          | publish docs                                             |
| Compatibility rule | `isCompatible()`: inclusive range on X.Y.Z. A two-part min is padded with `.0`, a two-part max with `.99`. An empty max means `<major of min>.99`                                                                                                         | `version_compare.py`                                     |
| System plugin dir  | `pkgDataPath()/python/plugins` = `$PREFIX/share/qgis/python/plugins` on unix. On Windows QGIS is built with `CMAKE_INSTALL_PREFIX=%LIBRARY_PREFIX%`, so it's `%PREFIX%\Library\share\qgis\python\plugins`. **A single `noarch` package can't cover both** | conda env probe; qgis-feedstock `bld.bat`                |
| Search order       | `QGIS_PLUGINPATH`, then profile `python/plugins`, then system dir. A plugin installed into the profile via Plugin Manager **shadows** the conda one                                                                                                       | `qgspythonutilsimpl.cpp`                                 |
| Enabling           | New plugins start disabled. Only core plugins are auto-enabled (hard-coded list). `[PythonPlugins] <slug>=true` in `QGIS_GLOBAL_SETTINGS_FILE` enables them by default, and the user can still turn them off                                              | `qgspluginregistry.cpp`; control run in test-workspace   |
| QGIS 4 on macOS    | needs `__osx >= 14.0`                                                                                                                                                                                                                                     | pixi solve                                               |
| Headless QGIS      | a fresh profile blocks on the macOS Keychain. Tests must seed `[authentication]` keys in the profile's `QGIS4.ini`                                                                                                                                        | `sample`; test-workspace                                 |

### Answers to the open questions in `message.md`

- **Does `run` assume conda-forge?** No. A recipe's run dependencies are names plus version specs with no channel. They're resolved at install time against the user's channel list. So:
  - Users must list our channel **and** conda-forge. Docs and examples must say so.
  - With pixi's default strict channel priority, if a name exists in our channel, conda-forge's copy of that name is never considered. **We must never publish a name that exists on conda-forge.** The `qgis-plugin-` prefix ensures that, and `check` should verify it (section 9).
- **Are plugin versions immutable?** Mostly, but not guaranteed (see "Mutability" above). Our recipe pins `sha256`, and the built package keeps the original bytes, so a re-uploaded ZIP can't silently change a published package. The sync should detect a hash mismatch for an already-published version and report it rather than rebuild (section 8).

## 3. Reference projects

### 3.1 RoboStack (`RoboStack/robostack`): features and what we need

RoboStack builds conda packages for every ROS 2 distribution from one repo. Tooling: the `vinca` recipe generator, rattler-build, pixi, GitHub Actions. Uploads go to prefix.dev and anaconda.org.

| RoboStack feature                                                                           | What it does there                               | Need here?                                                        | Our equivalent                                                                                                  |
| ------------------------------------------------------------------------------------------- | ------------------------------------------------ | ----------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `rosdistro_snapshot.yaml` (generated, committed)                                            | Pins every package's version, source URL and tag | **Partly**                                                        | Feed fetched at sync time. The published channel is the record of what's built; no committed snapshot (see 4.1) |
| `rosdistro_additional_recipes.yaml`                                                         | Packages from outside rosdistro (git URL + rev)  | Later                                                             | `source = { url = ... }` override for plugins hosted only on GitHub                                             |
| `packages_select_by_deps`                                                                   | Explicit selection plus dependency closure       | **Yes**                                                           | `[plugins.<slug>]` tables in `plugins.toml`; closure over `plugin_dependencies`                                 |
| `packages_exclude` / `packages_skip`                                                        | Don't build, with or without dropping dependents | **Yes**                                                           | `skip = "reason"`                                                                                               |
| `robostack.yaml` (rosdep key → conda pkg)                                                   | Maps upstream dependency names to conda-forge    | **Yes, the core of dependency discovery**                         | `mappings.toml`: Python import name → conda-forge package, used by the dependency scanner                       |
| `patch/dependencies.yaml` (`add_host`, `add_run`)                                           | Fixes missing or wrong dependencies per package  | **Yes, the main patch mechanism**                                 | `add_run` and a narrowing `qgis` override in `plugins.toml`. No `host` needed                                   |
| `pkg_additional_info.yaml`                                                                  | build_number, cmake args, dummy packages         | **Yes (subset)**                                                  | `build_number`, `version` override, `license` override, test options                                            |
| `patch/*.patch` (+ `.osx`/`.win`)                                                           | Source patches                                   | Later (section 12)                                                | `patches/<slug>/*.patch`                                                                                        |
| Pinning (`conda_build_config.yaml`, conda-forge migrations)                                 | ABI-compatible builds                            | **No**: noarch, no host deps                                      | none                                                                                                            |
| Distro mutex package                                                                        | One ROS distro per env                           | **No**                                                            | The `qgis` version range from `metadata.txt` does this job                                                      |
| `package_name_mode: both`                                                                   | Old and new names side by side                   | No, but naming is a **one-way decision** (5.1)                    | none                                                                                                            |
| `shared/` vs `distros/<d>/`                                                                 | Settings shared across ROS distros               | **No**: one channel serves QGIS 3 and 4 via the `qgis` constraint | none                                                                                                            |
| `shared/tests/<pkg>.yaml`                                                                   | Per-package tests                                | **Yes**                                                           | Generic test for every plugin, plus extra commands in `plugins.toml`                                            |
| `check-deps` (solve all deps before building)                                               | Catches pin conflicts early                      | **Yes, cheap**                                                    | Solve each plugin with min and max QGIS before building                                                         |
| ABI check                                                                                   | Library ABI changes                              | No                                                                | none                                                                                                            |
| Staged builds by dependency depth, build branches, timings                                  | Thousands of compiled packages                   | **No**: each plugin builds in seconds; one job is enough          | none                                                                                                            |
| Upload to prefix.dev with OIDC trusted publishing, `--skip-existing`, test-channel variable | Secret-free publishing                           | **Yes**                                                           | Same; `rattler-build upload prefix`                                                                             |
| `rs check` + YAML sorting                                                                   | Repo sanity in CI                                | **Yes**                                                           | `check` task: TOML schema, sorted keys, name collisions, conda-forge name clash                                 |
| robostack-bot (issue forms, comment commands)                                               | `add-package`, `rebuild`, snapshot updates       | Later                                                             | "Plugin request" issue form → bot PR adding `[plugins.<slug>]`                                                  |
| Nightly package tests against newest deps                                                   | Catches breakage from conda-forge                | **Yes**: QGIS releases can break plugins                          | Nightly re-test of published plugins against the newest QGIS                                                    |
| Weekly dependency report issue                                                              | Tracks conflicts                                 | Later                                                             | Optional                                                                                                        |
| `AGENTS.md` + `.claude/skills/`                                                             | Agent procedures                                 | Nice to have                                                      | Short `AGENTS.md`; skills for "add plugin", "fix deps"                                                          |
| Docs site (Starlight) with package tables generated from the channel                        | User docs + catalogue                            | **Yes**                                                           | `docs/` (section 10)                                                                                            |

### 3.2 Octoconda (`prefix-dev/octoconda`): mentioned in `message.md`

Octoconda generates rattler-build recipes from GitHub release binaries and pushes them to a prefix.dev channel.

| Octoconda feature                                                                                             | Need here?                                                | Notes                                                                                               |
| ------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| One TOML config: list of sources with optional per-package overrides (`name`, `platforms`, `deprecated`, ...) | **Yes**: matches "patched via a TOML file" in the diagram | `plugins.toml`                                                                                      |
| **The channel is the state**: query published versions, generate recipes only for what's missing              | **Yes**                                                   | Removes the need for a committed snapshot                                                           |
| `max-import-releases`                                                                                         | Yes, adapted                                              | How many versions per plugin to import, bounded by what the feed exposes (2)                        |
| Scheduled sync (every 2 h, matrix split by name)                                                              | Yes, simpler                                              | Daily cron; no split needed at our scale                                                            |
| `add-repo` / `top-repos` discovery                                                                            | Yes, adapted                                              | `add <slug>`; `top --n 50` ranked by feed `downloads`                                               |
| `validate_conda_package.py` (checks layout of the built `.conda`)                                             | **Yes**                                                   | Check the payload is only `share/qgis/python/plugins/<slug>/**` + licence, and contains no binaries |
| `deprecated = true`                                                                                           | Yes                                                       | Also read the feed's `deprecated` flag                                                              |
| Written in Rust                                                                                               | No                                                        | Python, like RoboStack's tools and our existing script                                              |

### 3.3 Takeaway

Our problem is much smaller than RoboStack's: no compilation, no ABI, no pinning, no build matrix, almost no plugin-to-plugin dependencies. It's a little bigger than Octoconda's: we need metadata patches, a dependency mapping, and real tests.

**Proposed hybrid:** Octoconda's stateless "sync what's missing" loop and TOML config, plus RoboStack's dependency patches and mapping, per-package tests, `check`, nightly tests, publishing setup and docs site.

## 4. Architecture

```
plugins.qgis.org feed(s) ─┐
                          ├─► sync: which (slug, version) are selected and not yet on the channel?
prefix.dev channel ───────┘                │
                                           ▼
plugins.toml (selection + overrides) ─► generate: download ZIP, sha256, read metadata.txt,
mappings.toml                           apply overrides ─► recipes/<pkg>/recipe.yaml (gitignored)
                                           │
                                           ▼
                                 rattler-build build + test (QGIS min line & newest)
                                           │
                                           ▼
                                 validate package ─► upload (prefix.dev, trusted publishing, --skip-existing)
```

### 4.1 Decision: no committed snapshot

RoboStack commits a snapshot because rosdistro syncs are curated releases of thousands of interdependent packages. Plugins are independent, so here:

- New upstream versions of **selected** plugins flow through automatically on the scheduled sync, gated by tests (Octoconda model).
- Reviewable changes are only those to `plugins.toml` and `mappings.toml`.
- Reproducibility comes from the channel plus the recipe embedded in every built package (`info/recipe/`). The source `sha256` is recorded in the package (`extra.source_sha256`).
- _Alternative if you want PR review of every version bump:_ the sync opens a PR that updates a committed `snapshot.toml` (RoboStack model). The cost is a bot and a merge step per update.

### 4.2 Which versions get built

The feed only shows the newest version per QGIS minor. The sync queries a configured list of QGIS lines (`feed_lines`, e.g. `["3.40", "3.44", "4.0", "4.2"]`, where LTR + latest matter) and builds every distinct version it sees that isn't on the channel. Over time the channel collects history even though the feed doesn't keep it. A version can also be listed explicitly with `versions = ["1.5.1"]` (download URL known, metadata read from the ZIP).

## 5. Recipe generation

### 5.1 Naming (permanent: decide before the first publish)

A conda name can't be renamed or reassigned once published: users pin it, and the channel keeps it. The slug → name mapping has to avoid collisions **for every slug that could ever exist**, not just today's.

What constrains it:

- Slugs match `[A-Za-z][A-Za-z0-9_-]+`. Conda names are lowercase `[a-z0-9_.-]`, so **case is the only thing we must fold**.
- plugins.qgis.org rejects a new slug that differs from an existing one **only in case** (`package_name__iexact` in `Plugin.clean()`). Since 2024-11, new slugs must be Python identifiers (`str.isidentifier()`), so **no `-`**. Legacy slugs are exempt from both rules.
- In the 3.40 + 4.2 feeds: 3,849 distinct slugs, 1,173 with uppercase, 2,031 with `_`, 214 with `-` (all legacy).

Options:

| Mapping                                          | Collisions today (3.40 + 4.2 feeds)                                                                                                                                                 | Can new ones appear?                                                                                                                                                                                              |
| ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| lowercase + `_` → `-` (what the QMS recipe used) | 6: `AI_Agent`/`ai_agent`, `Auto_save`/`auto_save`, `PE3D_Downloader`/`pe3d_downloader`, `PLUGIN`/`plugin`, `Redistricting`/`redistricting`, **`profile-manager`/`profile_manager`** | **Yes.** Any new `foo_bar` collides with a legacy `foo-bar`, because the site's case-insensitive check doesn't treat `-` and `_` as the same. 214 hyphenated legacy slugs are potential collision targets forever |
| **lowercase only, keep `_` and `-`**             | 5 (the case-only pairs above)                                                                                                                                                       | **No.** Case-only duplicates have been blocked upstream since the `iexact` check, so the set is frozen to legacy pairs and can be resolved once, now                                                              |

**Decision: `qgis-plugin-<slug.lower()>`, keeping `_`** (e.g. `qgis-plugin-quick_map_services`, `qgis-plugin-quickosm`). It's less conventional-looking than dashes; conda-forge prefers `-` but allows `_`. In exchange the mapping is injective apart from case, and the collision set is closed.

Rules that go with it:

- **Collisions never resolve automatically.** If two slugs map to one name, `check` fails and the generator refuses both until `plugins.toml` gives each colliding slug an explicit `name = "..."`. No first-come-first-served: with automatic tie-breaking, whichever slug was selected first would own the plain name, and selection order would decide permanent names.
- **Known legacy collisions are caught up front.** _(As built in M2:)_ instead of a separate `naming.toml`, `check` compares every selected plugin's default name with the default names of **all** slugs in the cached feeds, selected or not. A plugin whose default name is shared needs an explicit `name`. Older feed lines (back to 3.0) can be added to `feed_lines` to widen the net.
- **Names are claimed only by publishing.** Before uploading a new name, `check` confirms the channel has no package with that name built from a _different_ slug (compare `extra.qgis_plugin_slug`). That guards against a rename upstream or a mapping change.
- **No clash with conda-forge** (strict channel priority would hide theirs): checked against conda-forge repodata.
- The exact slug is kept in `extra.qgis_plugin_slug`. It's also the install folder name, which QGIS uses as the plugin ID, so it must stay exact.

### 5.2 Versions

Normalisation, in order: strip a leading `v`; `-` → `.`/drop per conda rules (`2.0.0-beta1` → `2.0.0beta1`); otherwise keep it as is. Validate with `rattler` version parsing and fail closed if it can't be parsed: the `version` override in TOML then fixes it. The original string stays in `extra.qgis_plugin_version` because the build check compares against `metadata.txt`. The site can rewrite versions, so the feed version isn't always the one in `metadata.txt`; see [Plugin version strings](/background/plugin-versions/).

### 5.3 QGIS constraint

From `metadata.txt` with QGIS's own padding rule: `qgis >=<min>,<=<max>` (already implemented in `tools/sync_qgis_plugin_recipe.py` and `build.sh`). The override `qgis = { min = "3.40", max = "3.44" }` (padded the same way) can only **narrow** the declared range, e.g. when a plugin claims 4.x support but breaks there. QGIS refuses to load a plugin outside its `metadata.txt` range, so widening it, e.g. a stale max of `3.99` for a plugin that really works on 4.x, needs a patch to `metadata.txt` (section 12). `generate` rejects a widening override.

### 5.4 Platforms: two noarch variants

Because the system plugin dir differs (section 2), each plugin is built as two `noarch: generic` variants, the conda-forge pattern for platform-specific noarch packages:

- `__unix` → `share/qgis/python/plugins/<slug>`
- `__win` → `Library/share/qgis/python/plugins/<slug>`

The build step is a small Python script, not `build.sh`, so the same code runs everywhere. It replaces `unzip` + bash, reusing the metadata check from `build.sh`. **Needs verification:** rattler-build's variant syntax for `__unix`/`__win` noarch variants, and a Windows test run.

### 5.5 Dependencies

- `run`: the `qgis` constraint + `add_run` from `plugins.toml`. _Not yet:_ other selected plugins named in `plugin_dependencies`. These use plugin **names**, not slugs, so they need a name → slug lookup.
- No `host`/`build` deps beyond the build script's Python (build-only).
- Run deps carry no channel (section 2). Names must exist on conda-forge, and `check` verifies that by solving.

### 5.6 Metadata

- `about.license`: SPDX string from the override, otherwise guessed from the LICENSE text (GPL-2.0-or-later / GPL-3.0-or-later / MIT ...). Fail closed and require an override if it can't be guessed.
- `license_file: <slug>/LICENSE`.
- `about.homepage` / `repository` from the feed. Summary from `description`.
- `extra`: `qgis_plugin_slug`, `qgis_plugin_version`, `qgis_plugin_id`, `source_sha256`.

### 5.7 Tests (generated for every plugin)

The existing `test_plugin.py`, run against **two** QGIS versions: the oldest available QGIS line inside the plugin's range, and the newest. It checks that QGIS discovers the plugin, that `isCompatible()` accepts it, and that it imports. Also:

- `test.import = false` override for plugins with side effects at import.
- `test.commands = [...]` for extras, e.g. `python -c "import geopandas"` to prove an `add_run` dependency resolves.
- The headless profile seeding from `test-workspace/` (Keychain workaround) moves into the test harness.

### 5.8 Rebuilds after a metadata patch

Changing `add_run` for an already published version needs a new build: `build_number` + 1 in the plugin's TOML table (RoboStack's per-package build numbers). The rattler-build hash doesn't change with deps, so the sync would otherwise skip it as existing.

- **Guard** _(as built in M2; no overrides hash needed):_ the channel's `repodata.json` already records each build's `depends` and `license`. `check --channel` compares them with what the recipe would produce for the same version. If they differ at the same `build_number`, it fails and names the change and the number to set.
- **Open:** whether prefix.dev supports repodata patching or removing a broken build. Verify. Until then a fix always means a new build that supersedes the old one.

## 6. Configuration files (TOML)

### `plugins.toml`

_(As built:)_ validated by pydantic models in `tools/qp/config.py`: strict types, unknown keys rejected, every problem reported with its `[table]`. `qp schema` (`pixi run schema`, also run by a pre-commit hook) generates `plugins.schema.json` from those models. The `#:schema ./plugins.schema.json` line at the top of `plugins.toml` gives completion, hover docs and checking in editors built on Taplo, such as VS Code's Even Better TOML.

The selection, plus the "patched via a TOML file" layer from the diagram.

```toml
[settings]
channel = "<prefix-channel>"
feed_lines = ["3.40", "3.44", "4.0", "4.2"]   # feeds to query (4.2)
test_lines = ["3.40", "3.44", "4.2"]          # QGIS lines on conda-forge to test against (5.7); it has no 4.0
include_experimental = false

[plugins.quick_map_services]                  # key = slug (exact, case-sensitive)

[plugins.QuickOSM]
version = { "2.0.0-beta1" = "2.0.0beta1" }    # only if auto-normalisation fails

[plugins.some_ml_plugin]
add_run = ["scikit-learn >=1.3", "geopandas"]
build_number = 1                              # bumped after add_run changed for a published version
test.commands = ["python -c 'import sklearn, geopandas'"]
note = "deps from README: https://..."        # why: keeps provenance of README-only setup steps

[plugins.broken_plugin]
skip = "imports qgis._3d which conda-forge QGIS doesn't build"
```

### `mappings.toml`

Python import name → conda-forge package. It's the counterpart of RoboStack's `robostack.yaml` and is used only by the scanner:

```toml
[imports]
sklearn = "scikit-learn"
cv2 = "opencv"
yaml = "pyyaml"
osgeo = "gdal"        # already provided by qgis: listed so the scanner stays quiet
```

## 7. Dependency discovery (the "README" pain point)

`qp scan-deps <slug>` reports candidate `add_run` entries for a human to confirm. It doesn't change config.

1. Read `requirements.txt` / `requirements*.txt` / `pyproject.toml` in the ZIP if present (QPIP convention).
2. Static AST scan of imports. Drop stdlib, `qgis.*`, `PyQt*`/`qgis.PyQt`, the plugin's own modules, and anything already in the QGIS env. Map the rest through `mappings.toml`, then through a PyPI → conda mapping (e.g. prefix.dev's parselmouth data; **verify availability**).
3. Show the plugin's `about`/README text with dependency hints (lines mentioning pip/install/requires).

Output is a suggested TOML block plus "unmapped imports" that need a decision.

## 8. Sync, build and publish

- **CLI** (Python package in `tools/` or `src/`, run via pixi tasks; name `qp` is a placeholder):
  - `feed`: fetch and cache feeds for `feed_lines`.
  - `plan`: selected versions minus the channel's (via `py-rattler` repodata). Prints what would be built.
  - `generate [--plugin S]`: write `recipes/`.
  - `build [--plugin S]`: rattler-build with tests, into `output/`.
  - `validate`: package layout and no-binaries check (from Octoconda).
  - `upload`: `rattler-build upload prefix --skip-existing`.
  - `add <slug>` / `top --n N`: add entries to `plugins.toml`.
  - `scan-deps <slug>`.
  - `check`: schema, sorted, naming collisions, conda-forge name clash, overrides hash vs channel, every `add_run` solvable with min and max QGIS.
- **Hash drift:** if a published version's upstream ZIP `sha256` differs from `extra.source_sha256`, report it (log/issue). Never rebuild silently.
- **Publishing:** prefix.dev trusted publishing (OIDC, `id-token: write`; the channel's _Settings → Repository Access_ authorises the workflow). Use a repository variable for the target channel, like RoboStack's `ROBOSTACK_UPLOAD_CHANNEL`, to use a test channel first.
- **Experimental versions:** skipped by default. prefix.dev label support is **unverified**; otherwise use a separate channel.

## 9. CI (GitHub Actions)

| Workflow             | Trigger                                  | Does                                                                                                                                          |
| -------------------- | ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `pr.yaml`            | pull request                             | `check`, unit tests, generate + build + test the plugins whose TOML entry changed (or all, if tooling changed). No upload                     |
| `sync.yaml`          | daily cron, manual                       | `plan` → `generate` → `build` (tests) → `validate` → `upload`; failures summarised in the job summary / an issue                              |
| `package-tests.yaml` | nightly                                  | `rattler-build test` on the newest published build of every plugin against the newest QGIS; one rolling issue with failures (RoboStack model) |
| `docs.yaml`          | push to main (docs/ or channel data), PR | build Starlight; deploy to GitHub Pages on main                                                                                               |

Builds run on `ubuntu-latest`. Being noarch, a Windows job tests the `__win` variant on a sample of plugins, weekly or per PR (labelled).

## 10. Docs site (`docs/`, Starlight)

Modelled on `RoboStack/robostack.github.io`, which uses Astro + Starlight + Svelte, pnpm, a pixi environment for the tooling, and generated package tables.

- **Tooling:** a pixi feature `docs` with `nodejs` + `pnpm`. Tasks `docs-install`, `docs-dev`, `docs-build`, `docs-check` (`astro check`, prettier). It's a separate pixi environment, so the pipeline env stays small.
- **Pages:**
  - _Getting started:_ `pixi.toml` with both channels and the macOS ≥ 14 note.
  - _How plugins are enabled:_ global settings, profile shadowing, `pixi run qgis`.
  - _Plugin catalogue:_ table of published plugins with QGIS range, version and extra deps. Generated at build time from channel repodata into `docs/src/data/plugins.json` by a script, like RoboStack's `ensure-tables`/`compare_pkg_completeness.py`.
  - _Request a plugin / add dependencies:_ the TOML workflow.
  - _Maintainers:_ the pipeline, CI, publishing setup.
  - _FAQ:_ licensing, immutability, Windows.
  - _Background:_ port `qgis-plugin-system.md` (now `background/plugin-system.md`) and the relevant `NOTES.md` findings.
- **Deploy:** GitHub Pages (`withastro/action` or the pixi + `ghp-import` route RoboStack uses).
- No need for RoboStack's `build.format: "file"`; that keeps legacy URLs.

**As built (M6, 2026-10-26):** the project is named **QStack**.

- Astro 7 + Starlight 0.42, no Svelte. The catalogue is an Astro component (`PluginTable.astro`) over `docs/src/data/plugins.json`, written by `qp catalogue` (`pixi run docs-data [channel]`), which orders versions with py-rattler. An empty or missing file renders a "nothing published" note.
- Extra tasks: `docs-data`, `docs-fmt`.
- `starlight-links-validator` fails the build on broken internal links. Pages link root-relative; a Sätteri hast plugin in `astro.config.mjs` adds the GitHub Pages base path first.
- Deploy: `.github/workflows/docs.yaml` with `actions/configure-pages` → `upload-pages-artifact` → `deploy-pages`. The channel comes from the repository variable `QSTACK_CHANNEL`.
- lefthook: prettier on staged docs files (pre-commit); `docs-check` + `docs-build` when pushing docs changes.
- AI-written pages carry a "not yet human-verified" banner.
- Not done: deployment (no remote yet).

## 11. Runtime enablement shipped with the packages

Today `test-workspace/activate.sh` enables plugins per workspace. Moving this into packages would make `pixi add qgis-plugin-x` enough on its own:

- Each plugin package drops `share/qgis/plugins-enabled.d/<slug>.ini` (`[PythonPlugins] <slug>=true`).
- A small helper package `qgis-plugin-activation`, depended on by every plugin, ships `etc/conda/activate.d/qgis-plugins.{sh,bat}`. It merges QGIS's bundled `qgis_global_settings.ini` + all fragments into `$CONDA_PREFIX/share/qgis/qgis_global_settings.pixi.ini` and sets `QGIS_GLOBAL_SETTINGS_FILE`.
- **To verify:**
  - pixi runs package `activate.d` scripts (it has to for conda-forge's own activation; check on all OSes).
  - Behaviour when the user already sets `QGIS_GLOBAL_SETTINGS_FILE`: probably merge theirs in.
  - Whether writing into the env at activation is acceptable, compared with a `post-link` script, which pixi doesn't run by default.
- Profile shadowing (a Plugin Manager upgrade overrides the conda copy) gets documented, and handled later if possible, e.g. a global setting that stops Plugin Manager offering upgrades.

## 12. Future: code patches

- `patches/<slug>/<version-range>/*.patch` (git format-patch, with reasons), applied by rattler-build.
- This needs rattler-build to extract the ZIP itself. Today `file_name:` disables extraction. Either name the downloaded file `*.zip` so extraction happens, or unzip in a prior source step. Check this when we get there.
- A patch changes package contents, so it needs a `build_number` bump, and the overrides hash should include the patch hashes.

## 13. Repository layout (target)

```
pixi.toml               pipeline env (python, rattler-build, py-rattler, pyyaml/tomli-w) + tasks; feature "docs"
plugins.toml            selection + overrides
mappings.toml           import → conda-forge mapping
tools/qp/               generator package (feed, metadata, naming, versions, recipe, channel, cli)
tools/templates/        recipe.yaml.j2, build_plugin.py, test_plugin.py
tools/tests/            unit tests (+ golden test: generated QMS recipe == current hand-written one)
recipes/                generated, gitignored
output/                 local channel, gitignored
patches/                (future)
docs/                   Starlight site (this plan is docs/src/content/docs/maintainers/plan.md)
test-workspace/         consumer example; switches from path dep to the channel once published
.github/workflows/      pr.yaml, sync.yaml, package-tests.yaml, docs.yaml
AGENTS.md               short notes for agents (RoboStack-style)
```

`recipes/qgis-plugin-quick-map-services/` becomes the golden reference and then gets deleted. `tools/sync_qgis_plugin_recipe.py` is absorbed into `tools/qp`.

## 14. Milestones

| #     | Milestone                                  | Done when                                                                                                                                                                          |
| ----- | ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| M0 ✅ | Tool skeleton + root `pixi.toml`           | `pixi run qp --help` works; unit tests run                                                                                                                                         |
| M1 ✅ | Generator for one plugin                   | Generated QMS recipe matches the hand-written one apart from the package name, now `qgis-plugin-quick_map_services` (golden test); builds, and tests pass on QGIS 3.40 + 4.2       |
| M2    | Overrides + naming/version rules + `check` | `plugins.toml` with ~10 plugins, including one with `add_run` and one with an odd version; `check` catches a collision, a conda-forge name clash and a missing `build_number` bump |
| M3    | Dependency scanner + `mappings.toml`       | `scan-deps` suggests correct `add_run` for 3 plugins with known deps                                                                                                               |
| M4    | `__unix`/`__win` variants                  | Windows CI job installs and tests one plugin                                                                                                                                       |
| M5    | Publish to a **test** prefix.dev channel   | `sync.yaml` uploads via OIDC; `test-workspace` installs from the channel                                                                                                           |
| M6 🚧 | Docs site                                  | `docs-build` in CI; Pages deployed with the catalogue table                                                                                                                        |
| M7    | Packaged enablement (section 11)           | Fresh env with only `pixi add qgis-plugin-x`: plugin active on first launch                                                                                                        |
| M8    | Scale + nightly tests                      | Top ~50 plugins by downloads; nightly test issue; move to the real channel                                                                                                         |
| —     | Later                                      | Request issue form + bot; GitHub-only plugin sources; code patches                                                                                                                 |

## 15. Open questions and risks

- **Package name collisions (high impact, permanent).** Different slugs can map to the same conda name, e.g. `OSM_map` and `osm_map`. 6 such pairs already exist under a dash mapping, and new ones could appear indefinitely. Mitigations, detailed in 5.1:
  - keep `_` (only case-only collisions remain, and upstream blocks new ones);
  - pre-assign names for the known legacy pairs;
  - never auto-resolve a collision;
  - have `check` verify that a name on the channel always belongs to the same slug.

  Residual risks:
  - legacy slugs that haven't been seen yet (older feed lines);
  - upstream relaxing its rules;
  - a plugin being deleted and its slug reused by a different plugin. The name then points at unrelated software; `extra.qgis_plugin_id` (stable per plugin upstream) should be compared too.

- **Channel name / "Prefix mirror".** I've read this as "a prefix.dev channel we own". If you meant something else, e.g. a mirror of conda-forge + our packages, the publish step changes.
- **Community and naming.** Is using "qgis" in package names fine with the QGIS project? Is there interest in hosting under a QGIS or community org? `message.md` looks like the start of that conversation.
- **prefix.dev capabilities:** labels (for experimental versions), deleting or yanking builds, repodata patches.
- **Licensing:** redistributing GPL plugins is fine (the ZIP is the source, and the LICENSE is shipped). Old plugins without a LICENSE are skipped unless a licence override with a source is given.
- **Plugins that pip-install at runtime**, or vendor wheels against the rules: detect with the scanner (look for `pip`/`subprocess` use) and flag them.
- **QGIS-version breakage:** a plugin's declared max may be optimistic. Nightly tests catch import failures, not GUI breakage.
- **Feed coverage:** versions that never appear as "newest" for a queried QGIS line are never seen automatically; list them explicitly.
