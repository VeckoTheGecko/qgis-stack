import io
import json
import tarfile
import zipfile
from pathlib import PurePosixPath

import pytest

from qp.validate import is_binary, validate

NAME = "qgis-plugin-demo"
PLUGIN = "share/qgis/python/plugins/demo"


def _tar_zst(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:zst") as tar:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    return buf.getvalue()


def conda(tmp_path, pkg: dict[str, bytes], index=None, about=None, licenses=True):
    if index is None:
        index = {"name": NAME, "noarch": "generic"}
    if about is None:
        about = {"extra": {"qgis_plugin_slug": "demo"}}
    info = {
        "info/index.json": json.dumps(index).encode(),
        "info/about.json": json.dumps(about).encode(),
    }
    if licenses:
        info["info/licenses/demo/LICENSE"] = b"GPL"
    path = tmp_path / f"{NAME}-1.0-h0_0.conda"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("metadata.json", "{}")
        zf.writestr(f"info-{NAME}.tar.zst", _tar_zst(info))
        zf.writestr(f"pkg-{NAME}.tar.zst", _tar_zst(pkg))
    return path


GOOD = {
    f"{PLUGIN}/metadata.txt": b"[general]",
    f"{PLUGIN}/__init__.py": b"",
    f"etc/conda/test-files/{NAME}/0/test_plugin.py": b"",
}


def test_valid(tmp_path):
    assert validate(conda(tmp_path, GOOD)) == []


def test_problems(tmp_path):
    pkg = {
        f"{PLUGIN}/__init__.py": b"",
        f"{PLUGIN}/lib/_speedups.so": b"",
        f"{PLUGIN}/tool": b"\x7fELF...",
        "bin/demo": b"#!/bin/sh",
    }
    path = conda(tmp_path, pkg, index={"name": NAME}, licenses=False)
    problems = [p.split(": ", 1)[1] for p in validate(path)]
    assert problems == [
        "not noarch: generic",
        "no licence in info/licenses/",
        f"no {PLUGIN}/metadata.txt",
        "unexpected file bin/demo",
        f"binary file {PLUGIN}/lib/_speedups.so",
        f"binary file {PLUGIN}/tool",
    ]


def test_missing_slug(tmp_path):
    assert "no extra.qgis_plugin_slug" in validate(conda(tmp_path, GOOD, about={}))[0]


def _pe() -> bytes:
    header = bytearray(b"MZ" + b"\0" * 62)
    header[60:64] = (64).to_bytes(4, "little")
    return bytes(header) + b"PE\0\0"


@pytest.mark.parametrize(
    ("path", "content", "binary"),
    [
        ("a.py", b"MZ is a text file starting with MZ" + b"." * 64, False),
        ("a.exe.txt", _pe(), True),
        ("a.pyc", b"", True),
        ("a.whl", b"PK\x03\x04", False),  # a wheel is a zip; validated separately later
        ("a.dylib", b"", True),
        ("a", b"\xcf\xfa\xed\xfe", True),
    ],
)
def test_is_binary(path, content, binary):
    assert is_binary(PurePosixPath(path), content) is binary
