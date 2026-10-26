# How QGIS plugins are created, stored, tracked and hosted

Notes compiled 2026-10-22. QGIS 4.x (Qt6) is the current major release; most details also apply to QGIS 3.x.

## 1. What a plugin is

A QGIS plugin is mostly a **Python package folder** that QGIS imports at startup. C++ plugins are possible but rare outside the core ones; this document covers Python plugins.

Minimal layout:

```
my_plugin/
├── __init__.py        # must define classFactory(iface)
├── metadata.txt       # required; INI-style metadata
├── main.py            # the plugin class (any name)
├── icon.png
├── LICENSE            # required for the official repo
└── README.md          # expected by the official repo
```

### The required Python interface

```python
# __init__.py
def classFactory(iface):          # iface: QgisInterface
    from .main import MyPlugin
    return MyPlugin(iface)

# main.py
class MyPlugin:
    def __init__(self, iface):
        self.iface = iface

    def initGui(self):            # called when the plugin is enabled
        ...                       # add actions, menus, toolbars, processing providers

    def unload(self):             # called when disabled/uninstalled
        ...                       # remove everything initGui added
```

That's the whole contract. Inside it you use the PyQGIS API (`qgis.core`, `qgis.gui`) and Qt through `qgis.PyQt`. Import Qt from `qgis.PyQt` rather than `PyQt5`/`PyQt6` directly so one codebase works on both QGIS 3 and 4.

Common variants:
- **Processing provider plugins** add algorithms to the Processing toolbox instead of, or as well as, GUI actions. They set `hasProcessingProvider=yes`.
- **Server plugins** run inside QGIS Server. They set `server=True` and define `serverClassFactory(serverIface)`.

## 2. `metadata.txt`

An INI file with a `[general]` section.

| Field | Required | Notes |
|---|---|---|
| `name` | ✅ | Display name |
| `qgisMinimumVersion` | ✅ | e.g. `3.28` |
| `description` | ✅ | One line, in English |
| `about` | ✅ | Longer description |
| `version` | ✅ | Plugin version string. Free-form, and plugins.qgis.org may rewrite it: see [docs/plugin-versions.md](docs/plugin-versions.md) |
| `author`, `email` | ✅ | Email is not shown publicly |
| `repository` | ✅ | Public source code URL (the official repo checks it) |
| `qgisMaximumVersion` | – | If empty, set to `<major>.99` on upload. **Set to `4.99` to declare QGIS 4 support** |
| `tracker`, `homepage` | – (expected) | The official repo's guidelines expect both |
| `tags`, `category`, `icon` | – | Discovery and UI |
| `experimental`, `deprecated` | – | Flags that control visibility in Plugin Manager |
| `changelog` | – | Shown in Plugin Manager |
| `plugin_dependencies` | – | **Other QGIS plugins** only, e.g. `OtherPlugin==1.12` (QGIS ≥ 3.8) |
| `hasProcessingProvider`, `server` | – | See above |
| `supportsQt6` | deprecated | Replaced by `qgisMaximumVersion ≥ 4.0` |

**Gap:** there is no field for Python package dependencies (`numpy`, `torch`, etc.). This is the main reason plugin installs are fragile (see [the Pixi angle](#7-relevance-to-pixi)).

## 3. Creating a plugin: tooling

- **Plugin Builder** (a QGIS plugin) generates a template with a UI, resources, i18n and tests. The template is somewhat dated and generates `resources_rc.py` and similar files that the official repo asks you not to ship.
- Community templates, e.g. [opengeos/qgis-plugin-template](https://github.com/opengeos/qgis-plugin-template), are leaner and more modern.
- **Plugin Reloader** (a plugin) reloads your plugin without restarting QGIS. It's essential during development.
- **qgis-plugin-ci** (PyPI) packages, translates, builds a changelog and uploads to plugins.qgis.org. It's the usual choice for CI/CD.
- **pb_tool**: an older CLI to compile and deploy Plugin Builder projects.

Dev loop: symlink your source folder into the profile's plugins directory, or put it on `QGIS_PLUGINPATH`. Then enable it and use Plugin Reloader.

## 4. Where plugins are stored locally

Plugins are installed **per user profile**:

| OS | Default path (QGIS 3) |
|---|---|
| Linux | `~/.local/share/QGIS/QGIS3/profiles/<profile>/python/plugins/` |
| macOS | `~/Library/Application Support/QGIS/QGIS3/profiles/<profile>/python/plugins/` |
| Windows | `%APPDATA%\QGIS\QGIS3\profiles\<profile>\python\plugins\` |

Check the QGIS 4 path on your own install; the `QGIS3` path segment may differ there.

- Which plugins are **enabled** is stored separately, in `<profile>/QGIS/QGIS3.ini` under `[PythonPlugins]`.
- `QGIS_PLUGINPATH` (env var) adds extra search directories. Plugins found there load normally but sit outside the Plugin Manager's install/update flow.
- `--profiles-path <dir>` (CLI flag) moves the whole profile tree, which is useful for project-local, reproducible setups.
- Core plugins (Processing, DB Manager, etc.) ship inside the QGIS install, not in the profile.

## 5. Hosting and distribution

### The official repository: plugins.qgis.org
- A Django app ([qgis/QGIS-Django](https://github.com/qgis/QGIS-Django)) that serves an XML feed (`plugins.xml?qgis=<version>`). QGIS filters the feed by your QGIS version.
- **Upload** a ZIP through the web UI, or through the API (used by `qgis-plugin-ci`). You need a plugins.qgis.org account.
- **Approval:** a new plugin is reviewed by staff before it's public. Later versions from trusted maintainers are auto-approved.
- **Security scanning (blocking):** every upload is scanned with **Bandit** and **detect-secrets**. Any finding blocks that version from download and approval until you upload a clean version. Expect to fix things like Bandit B105 false positives on variable names containing "password" or "token". See [Security Scanning](https://plugins.qgis.org/docs/security-scanning).
- Plugin pages show downloads, ratings, versions, and the QGIS-version compatibility range. The site also lists "QGIS 4 ready" plugins.

### History: has it always been plugins.qgis.org?
- **QGIS ≤ 1.7:** the default sources were `pyqgis.org/repo/official` and `pyqgis.org/repo/contributed`, plus about 12 pre-configured personal and organisational repos.
- **QGIS 1.8 (2012):** switched to `plugins.qgis.org/plugins/plugins.xml` and flagged the old repos as deprecated. Every release since (2.x, 3.x, 4.x) uses this same URL, with HTTPS by 2.18.
- Per-version differences come from the `?qgis=X.Y` query parameter, not from different hosts. In 3.x and later the installer re-adds the official repo if it's missing from settings.

### Custom / private repositories
- Any web server can host a `plugins.xml` in the same format, plus the ZIPs. Users add the URL under *Plugins → Manage and Install Plugins → Settings*.
- Repositories can sit behind authentication using the QGIS auth manager.
- `file://` URLs work too, which is handy for offline or air-gapped environments.
- Organisations often distribute curated plugin sets this way, sometimes combined with a startup script or a preconfigured profile.

### Manual install
- *Install from ZIP* in Plugin Manager, or unzip into the plugins folder and enable it.

## 6. Hard requirements: licensing and packaging

### Licence
- QGIS is GPL. The official repository requires the plugin licence to be **"compatible with the GPLv2 or later"** (e.g. GPL-2.0+, GPL-3.0, and permissive licences such as MIT/BSD/Apache-2.0, though Apache-2.0 is compatible with GPLv3 only).
- **A `LICENSE` file must be in the ZIP.**
- You must respect the licences of any bundled libraries and resources.
- Background: a Python plugin imports and links against GPL'd QGIS APIs. The QGIS project's position is that plugins are therefore subject to the GPL when distributed. A proprietary plugin you distribute privately is legally a grey area at best; the official repo simply doesn't accept it.

### Packaging rules (official repo)
- **No binaries** (compiled `.so`, `.dll`, `.exe`, wheels with native code).
- **Max 25 MB** ZIP.
- The ZIP contains one top-level folder named after the plugin.
- Exclude generated or junk files: `__pycache__`, `.pyc`, `.git`, `__MACOSX`, compiled `ui_*.py` / `resources_rc.py`.
- Include `README` and `LICENSE`.
- The source must be **publicly accessible** at the `repository` URL (a real repo, not a ZIP download), and must match what you upload.

### Quality expectations at review
- Minimal documentation, PEP 8 / QGIS coding guidelines, works on Windows, Linux and macOS.
- Declare external dependencies in the description or about text, since there is no machine-readable field for them.

## 7. Relevance to Pixi

The "no binaries" rule plus the missing Python-dependency field leaves plugins that need heavy libraries (ML, GDAL extras, etc.) three choices:
1. Vendor pure-Python code into the plugin.
2. Tell users to `pip install` into QGIS's Python (fragile, and differs per OS).
3. Install dependencies at runtime (QPIP-style, or a custom pip subprocess).

A Pixi environment that provides QGIS **and** the plugin's dependencies from conda-forge avoids all three. Only the plugin ZIP itself then needs fetching, e.g. by a pixi task. See `NOTES.md`.

## Sources
- [plugins.qgis.org – publishing requirements](https://plugins.qgis.org/docs/publish)
- [plugins.qgis.org – security scanning](https://plugins.qgis.org/docs/security-scanning)
- [plugins.qgis.org – migrate your plugin to QGIS 4](https://plugins.qgis.org/docs/migrate-qgis4)
- [PyQGIS Developer Cookbook – Structuring Python plugins](https://docs.qgis.org/latest/en/docs/pyqgis_developer_cookbook/plugins/plugins.html)
- [Qt5/Qt6 plugin migration wiki](https://github.com/qgis/QGIS/wiki/Plugin-migration-to-be-compatible-with-Qt5-and-Qt6)
