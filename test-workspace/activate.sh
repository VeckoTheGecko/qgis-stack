# Build the QGIS global settings file from the defaults shipped with QGIS plus
# qgis-plugins.ini. Pointing QGIS_GLOBAL_SETTINGS_FILE at our own file replaces
# the bundled one, so its defaults (OSM XYZ connection, snapping, ...) are kept here.
mkdir -p "$PIXI_PROJECT_ROOT/.qgis"
cat "$CONDA_PREFIX/share/qgis/resources/qgis_global_settings.ini" \
  "$PIXI_PROJECT_ROOT/qgis-plugins.ini" \
  > "$PIXI_PROJECT_ROOT/.qgis/qgis_global_settings.ini"
