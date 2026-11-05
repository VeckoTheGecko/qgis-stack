#!/usr/bin/env bash
set -euo pipefail

# The ZIP contains a duplicate LICENSE entry, so overwrite quietly instead of prompting.
unzip -o -q "${PLUGIN}-${PLUGIN_VERSION}.zip"

meta="${PLUGIN}/metadata.txt"

get() {
  sed -n "s/^$1[[:space:]]*=[[:space:]]*//p" "$meta" | head -n1 | tr -d '\r'
}

# Mirror pyplugin_installer.version_compare.isCompatible: two-part versions
# get .0 (min) or .99 (max) appended.
pad() {
  local v
  v=$(printf '%s' "$1" | tr -cd '0-9.')
  case "$v" in
    *.*.*) printf '%s' "$v" ;;
    *) printf '%s.%s' "$v" "$2" ;;
  esac
}

meta_version=$(get version)
meta_min=$(pad "$(get qgisMinimumVersion)" 0)
raw_max=$(get qgisMaximumVersion)
# QGIS defaults an empty max to "<major of min>.99".
meta_max=$(pad "${raw_max:-${meta_min%%.*}.99}" 99)

fail=0
check() {
  if [[ "$2" != "$3" ]]; then
    echo "ERROR: recipe $1=$2 but metadata.txt says $3" >&2
    fail=1
  fi
}
# PLUGIN_META_VERSION is set when plugins.qgis.org lists a normalised form of the
# metadata.txt version (e.g. 1.0.a2 for 1.0.0a2).
check version "${PLUGIN_META_VERSION:-$PLUGIN_VERSION}" "$meta_version"
check qgis_min "$QGIS_MIN" "$meta_min"
check qgis_max "$QGIS_MAX" "$meta_max"
if (( fail )); then
  echo "Regenerate the recipe with qp generate." >&2
  exit 1
fi

dest="${PREFIX}/share/qgis/python/plugins/${PLUGIN}"
mkdir -p "$(dirname "$dest")"
cp -R "$PLUGIN" "$dest"
find "$dest" \( -name '__pycache__' -o -name '*.pyc' \) -prune -exec rm -rf {} +
