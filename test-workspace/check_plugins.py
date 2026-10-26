"""Run inside QGIS (qgis --code check_plugins.py): list discovered Python plugins, then quit.

For each plugin: whether it is active, and the plugin path it was found on.
"""

import os
import sys

sys.stdout.reconfigure(line_buffering=True)

import qgis.utils
from qgis.core import QgsApplication, QgsSettings
from qgis.PyQt.QtCore import QTimer


def source(name: str) -> str:
    for path in qgis.utils.plugin_paths:
        if os.path.isdir(os.path.join(path, name)):
            return path
    return "?"


print(f"profile:         {QgsApplication.qgisSettingsDirPath()}")
print(f"global settings: {QgsSettings.globalSettingsPath()}")
print("plugin paths:    " + "\n                 ".join(qgis.utils.plugin_paths))
print()
for name in sorted(qgis.utils.available_plugins, key=str.lower):
    state = "active" if name in qgis.utils.active_plugins else "inactive"
    print(f"{state:9} {name:24} {source(name)}")

QTimer.singleShot(0, QgsApplication.instance().quit)
