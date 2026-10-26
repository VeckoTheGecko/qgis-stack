# QGIS plugin version strings

> [!WARNING]
> **AI-generated, not yet human-verified.** Written by Claude Opus 5.5 (`claude-opus-5-5`) in Claude Code, October 2026. Check claims against the linked sources before relying on them.

This is about the plugin's own `version` field in `metadata.txt`, not QGIS versions (`qgisMinimumVersion`/`qgisMaximumVersion`).

**Summary:**
- Nothing validates the format.
- plugins.qgis.org rewrites some versions when it stores them, so the version in the feed and the download URL isn't always the one in `metadata.txt`.
- QGIS compares versions with PEP 440 from 3.44 onwards, and with a homegrown algorithm before that.
- Real-world versions are nearly all dotted numbers, with a long tail of prefixes, tags and junk.

## 1. The official rule

- `version` is a required `metadata.txt` key (`PLUGIN_REQUIRED_METADATA` in the site's [validator.py](https://github.com/qgis/QGIS-Django/blob/master/qgis-app/plugins/validator.py)).
- The [PyQGIS cookbook](https://docs.qgis.org/latest/en/docs/pyqgis_developer_cookbook/plugins/plugins.html) only says "version in dotted notation".
- Neither the site nor QGIS checks the format. `latest`, `release` and `ver.1.4` are all live on plugins.qgis.org.

## 2. What plugins.qgis.org does with it

Upload goes through three steps ([models.py](https://github.com/qgis/QGIS-Django/blob/master/qgis-app/plugins/models.py), [forms.py](https://github.com/qgis/QGIS-Django/blob/master/qgis-app/plugins/forms.py)):

1. **The validator** strips the value.
2. **`PluginVersion.clean_version`** keeps only the last space-separated word: `version.rsplit(" ")[-1]`.
3. **`VersionField`** (`max_length=32`) stores the string in a sortable form:
   - On write, `vjust` splits on `.`, keeps the **first 4 parts**, and left-pads each part to 3 characters with `0`. An empty part becomes `###`.
   - On read, `VERSION_RE = r"(^|(?<=\.))0+(?!(\.|$|-))|\.#+"` removes leading zeros from each part (unless a `.`, `-` or end of string follows them) and removes the `###` parts.

The feed (`<version>`), the download URL (`/plugins/<slug>/version/<version>/download/`) and the uniqueness check (`unique_together = ("plugin", "version")`) all use this **stored** form. `qp.versions.server_form` reproduces it.

### Lossy round trip

| `metadata.txt` | Stored / feed / URL | Why | Seen in |
|---|---|---|---|
| `1.0.0a2` | `1.0.a2` | the part `0a2` starts with a `0` followed by a letter, and `VERSION_RE` strips it | `arches_project` |
| `0.1 beta` | `beta` | last word only | `OpenStaR_DT` |
| `1.0.0 - Initial release` | `release` | last word only | `ebv_cube_visualizer` |
| `2.0.20250411T184347.eotsv_2.0` | `2.0.20250411T184347.eotsv_2` | only 4 parts kept | `timeseriesviewerplugin` |
| `1.05` | `1.5` | leading zero stripped | emulated with `server_form` |
| `1.0a` | `1.a` | as `1.0.0a2` | emulated |

The first four were checked against the `metadata.txt` in the ZIPs downloaded from the site.

### Consequences

- **The feed/URL version can differ from `metadata.txt`.** Anything that compares the two needs `server_form(metadata_version) == feed_version`, not plain equality.
- **Collisions.** `1.05` and `1.5` have the same stored form, so uploading one after the other is rejected as a duplicate version.
- **Undownloadable versions.** The download route matches `(?P<version>[^\/]+)` ([urls.py](https://github.com/qgis/QGIS-Django/blob/master/qgis-app/plugins/urls.py)). A version containing `/` is stored, but no URL can reach it.

## 3. How QGIS compares plugin versions

The Plugin Manager uses `compareVersions` in [`pyplugin_installer/version_compare.py`](https://github.com/qgis/QGIS/blob/master/python/pyplugin_installer/version_compare.py) to decide whether an installed plugin is upgradeable. It returns 0 for equal, 1 if `a` is newer and 2 if `b` is newer.

Both versions first go through `normalizeVersion`:
- convert to uppercase;
- strip the first matching prefix from `VERSION`, `VER.`, `VER`, `V.`, `V`, `REVISION`, `REV.`, `REV`, `R.`, `R`.

What happens next depends on the QGIS version.

| QGIS | Algorithm |
|---|---|
| ≤ 3.42 ([release-3_40](https://github.com/qgis/QGIS/blob/release-3_40/python/pyplugin_installer/version_compare.py)) | **Legacy.** Chop into number and word runs, using `.`, `-`, `_` and space as delimiters (`0.03-120_rc7foo` → `0, 03, 120, RC, 7, FOO`), then compare pairwise. Numbers compare numerically unless they start with `0`. A longer list wins, except that a trailing `ALPHA` < `BETA` < `PREVIEW` < `RC` < `TRUNK` sorts below no suffix. |
| ≥ 3.44 ([release-3_44](https://github.com/qgis/QGIS/blob/release-3_44/python/pyplugin_installer/version_compare.py), from [4aa5bc367d](https://github.com/qgis/QGIS/commit/4aa5bc367d), "Use PEP440 standard for version comparison", Feb 2025) | **`packaging.version.Version`** if both parse. Otherwise, plain string comparison of the uppercased strings. |

### Quirks of `normalizeVersion`

- **It removes every occurrence of the prefix, not just the leading one.** It checks the prefix with `s[:len(i)] == i` but removes it with `s.replace(i, "")`. So `v1.0.dev1` → `V1.0.DEV1` → `1.0.DE1`, which is no longer PEP 440 and falls back to string comparison.
- **Words that start with `R` lose it:** `release` → `ELEASE`.
- **PEP 440 is lenient.** `1.1.C` parses as `1.1rc0`, a release candidate, so it sorts *below* `1.1`.
- **Mixed pairs fall back to strings.** If only one side isn't PEP 440 (e.g. `1.0.3-qgis4` vs `1.0.4`), both are compared as strings, so `10.0` < `9.0`.

## 4. Versions in the wild

From the cached feeds for QGIS 3.40, 3.44, 4.0 and 4.2: **4580 slug/version pairs, 787 distinct versions.**

**Dot-separated parts:**

| Parts | Count |
|---|---|
| 3 | 2888 |
| 2 | 1632 |
| 4 | 36 |
| 1 | 24 |

**Shapes** (digit runs → `9`, letter runs → `a`):

| Shape | Count | Example |
|---|---|---|
| `9.9.9` | 2807 | `1.5.2` |
| `9.9` | 1619 | `3.3` |
| `a9.9.9` | 43 | `v4.23.1` |
| `9.9.9.9` | 25 | |
| `9.9.9-a9` | 21 | `2.0.0-beta1` |
| `9` | 20 | |
| `a9.9` | 8 | `v1.5` |
| `9.9.9-a` | 5 | `1.2.0-beta` |
| `a` | 4 | `latest` |
| others | ≤ 4 each | `1.5.3.post2`, `0.9+20260317`, `1.0-2`, `1.0.a2`, `v.0.1.4` |

No feed version has a part with a leading zero, which is consistent with the stored form (section 2).

**Not PEP 440 even after `normalizeVersion`: 13 distinct versions.** QGIS ≥ 3.44 compares these as strings.
- `0.0.6-hotfix1`
- `0.5.20230630T235901.master`
- `0.9.20210222T174536.master`
- `1.0.2-qgis3`
- `1.0.3-qgis4`
- `1.1.0-qgis4`
- `1.1.1.p3`
- `1.1.D`
- `2.0.20250411T184347.eotsv_2`
- `2.4.0.baf147b`
- `beta`
- `latest`
- `release`

**Rejected by `qp.versions.normalize`: 5 distinct versions.** These need a `version = { "<upstream>" = "<conda>" }` override in `plugins.toml`.
- `beta`
- `latest`
- `release`
- `v.0.1.4`
- `ver.1.4`

## 5. Implications for the pipeline

**Mismatched versions fail today.**
- `qp.recipe.generate` raises when the `metadata.txt` version differs from the feed version.
- `build.sh` checks `PLUGIN_VERSION`, which is the feed version, against `metadata.txt`.
- So the plugins in the round-trip table above can't be built.

**Proposed fix (not done):**
- compare `server_form(metadata_version)` with the feed version;
- keep the feed version for the URL and file name;
- pass the `metadata.txt` version to the build script separately, for its check.

**Open question: ordering.** Does conda order `normalize()`d versions the way QGIS ≥ 3.44 orders them with PEP 440? If not, the newest build pixi picks may not be the one the Plugin Manager calls newest. One way to answer it is a property test with [py-rattler](https://github.com/conda/rattler)'s `Version`.

## 6. Testing: the grammar and Hypothesis strategies

The format is free-form, but nearly all real versions fit a loose grammar:

```
version := [prefix] release [sep tag [num_sep number]]
prefix  := "v" | "V" | "v." | "ver."
release := number ("." number){0..4}
sep, num_sep := "" | "-" | "."
tag     := a | b | c | rc | alpha | beta | pre | preview | dev | post      (PEP 440)
         | hotfix | qgis | master | p | final | C | D                    (seen, not PEP 440)
```

`number` is small (0–20) or calendar-like (2000–2030, as in `2026.6.12`).

`tools/tests/strategies.py` turns this into Hypothesis strategies:

**`plugin_versions(pep440=False, canonical=False)`** generates versions as authors write them.
- `pep440=True` keeps to the `""`/`v`/`V` prefixes and PEP 440 tags, so `packaging.version.Version` accepts every result.
- `canonical=True` avoids what the site rewrites:
  - a `0` part glued to a tag (`1.0.0a2`);
  - more than 4 parts, where a `v.` prefix counts as a part.

  With it, `server_form(v) == v`.

**`metadata_versions`** generates anything an author could put on the `version =` line: one line, non-blank, up to 32 characters.

**Properties tested:**
- **`normalize`** gives a valid conda version for every `pep440` version, and is idempotent.
- **`server_form`** is idempotent on any `metadata_versions` string (re-uploading the stored form doesn't change it).
- **`server_form`** is the identity on `canonical` versions.
- **Last-word rule:** `server_form(f"{anything} {v}") == server_form(v)`.
