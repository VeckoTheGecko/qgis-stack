"""Check built packages before upload (docs/plan.md section 8; after Octoconda's
validate_conda_package.py): only the plugin's files, a licence, no binaries."""

import io
import json
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

# Executable formats: ELF, Mach-O (32/64-bit, both byte orders, fat); PE is checked
# separately, since "MZ" alone could start a text file.
_MAGIC = (
    b"\x7fELF",
    b"\xfe\xed\xfa\xce",
    b"\xfe\xed\xfa\xcf",
    b"\xce\xfa\xed\xfe",
    b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe",
)
_BINARY_SUFFIXES = {".so", ".dylib", ".dll", ".pyd", ".exe", ".pyc"}


def is_binary(path: PurePosixPath, content: bytes) -> bool:
    if path.suffix.lower() in _BINARY_SUFFIXES or content.startswith(_MAGIC):
        return True
    if content[:2] == b"MZ" and len(content) >= 64:  # PE: "PE\0\0" at e_lfanew
        offset = int.from_bytes(content[60:64], "little")
        return content[offset : offset + 4] == b"PE\0\0"
    return False


def _members(conda: Path) -> tuple[dict[str, bytes], dict[str, bytes]]:
    """(info files, payload files) of a .conda package."""
    info, pkg = {}, {}
    with zipfile.ZipFile(conda) as outer:
        for inner in outer.namelist():
            if not inner.endswith(".tar.zst"):
                continue
            target = info if inner.startswith("info-") else pkg
            with tarfile.open(fileobj=io.BytesIO(outer.read(inner)), mode="r:zst") as tar:
                for member in tar.getmembers():
                    if member.isfile():
                        target[member.name] = tar.extractfile(member).read()
    return info, pkg


def validate(conda: Path) -> list[str]:
    info, pkg = _members(conda)
    index = json.loads(info["info/index.json"])
    about = json.loads(info.get("info/about.json", b"{}"))
    name = index["name"]
    slug = about.get("extra", {}).get("qgis_plugin_slug")
    if not slug:
        return [f"{conda.name}: no extra.qgis_plugin_slug in info/about.json"]

    problems = []
    if index.get("noarch") != "generic":
        problems.append(f"{conda.name}: not noarch: generic")
    if not any(n.startswith("info/licenses/") for n in info):
        problems.append(f"{conda.name}: no licence in info/licenses/")

    plugin_dir = PurePosixPath("share/qgis/python/plugins") / slug
    tests_dir = PurePosixPath("etc/conda/test-files") / name
    if f"{plugin_dir}/metadata.txt" not in pkg:
        problems.append(f"{conda.name}: no {plugin_dir}/metadata.txt")
    for path, content in sorted(pkg.items()):
        p = PurePosixPath(path)
        if not (p.is_relative_to(plugin_dir) or p.is_relative_to(tests_dir)):
            problems.append(f"{conda.name}: unexpected file {path}")
        elif is_binary(p, content):
            problems.append(f"{conda.name}: binary file {path}")
    return problems
