"""Check that the installed plugin is visible to, compatible with, and importable by QGIS.

Usage: python test_plugin.py SLUG [--no-import]
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import Qgis, QgsApplication

app = QgsApplication([], False)
app.initQgis()

import qgis.utils
from pyplugin_installer.version_compare import isCompatible, pyQgisVersion

plugin = sys.argv[1]
sys_plugin_path = os.path.join(QgsApplication.pkgDataPath(), "python", "plugins")
print(f"QGIS {Qgis.QGIS_VERSION}, system plugin path {sys_plugin_path}")

# A standalone QgsApplication doesn't set up plugin paths; the desktop app sets
# them to include pkgDataPath()/python/plugins (QgsPythonUtilsImpl::pluginsPath).
qgis.utils.plugin_paths = [sys_plugin_path]
sys.path.insert(0, sys_plugin_path)
qgis.utils.updateAvailablePlugins()
assert plugin in qgis.utils.available_plugins, qgis.utils.available_plugins

meta = qgis.utils.pluginMetadata
qgis_min = meta(plugin, "qgisMinimumVersion")
qgis_max = meta(plugin, "qgisMaximumVersion")
if qgis_max == "__error__":  # pluginMetadata's value for a missing key
    # QGIS treats a missing max as "<major of min>.99".
    qgis_max = qgis_min.split(".")[0] + ".99"
assert isCompatible(pyQgisVersion(), qgis_min, qgis_max), (pyQgisVersion(), qgis_min, qgis_max)

if "--no-import" not in sys.argv[2:]:
    assert qgis.utils.loadPlugin(plugin), f"failed to import {plugin}"
    assert hasattr(sys.modules[plugin], "classFactory")
print(f"{plugin} {meta(plugin, 'version')} OK (QGIS {qgis_min}..{qgis_max})")

app.exitQgis()
