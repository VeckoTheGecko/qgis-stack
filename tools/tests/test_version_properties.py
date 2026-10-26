"""Property tests for plugin version handling, using the strategies in strategies.py."""

import pytest
from hypothesis import example, given
from hypothesis import strategies as st
from packaging.version import Version
from strategies import metadata_versions, plugin_versions

from qp.versions import _CONDA_VERSION, normalize, server_form


@given(plugin_versions(pep440=True))
def test_pep440_strategy_is_pep440(v):
    Version(v)


@given(plugin_versions(pep440=True))
def test_normalize_handles_pep440_versions(v):
    assert _CONDA_VERSION.fullmatch(normalize(v))


@given(plugin_versions())
def test_normalize_is_idempotent(v):
    try:
        conda = normalize(v)
    except ValueError:
        return  # fails closed: needs a `version` override
    assert normalize(conda) == conda


@given(plugin_versions(canonical=True))
def test_server_keeps_canonical_versions(v):
    assert server_form(v) == v


@given(metadata_versions)
@example("1 .2")
def test_server_form_is_idempotent(v):
    assert server_form(server_form(v)) == server_form(v)


@given(st.text("abc. -", min_size=1).filter(str.strip), plugin_versions())
def test_server_keeps_last_word(words, v):
    assert server_form(f"{words.strip()} {v}") == server_form(v)


@pytest.mark.parametrize(
    ("metadata", "feed"),
    [
        # Seen on plugins.qgis.org (metadata.txt in the ZIP vs the feed).
        ("1.0.0a2", "1.0.a2"),
        ("0.1 beta", "beta"),
        ("1.0.0 - Initial release", "release"),
        ("2.0.20250411T184347.eotsv_2.0", "2.0.20250411T184347.eotsv_2"),
        ("v4.23.1", "v4.23.1"),
        ("1.0.0-beta", "1.0.0-beta"),
        ("2rc01", "2rc01"),
        ("1.05", "1.5"),
    ],
)
def test_server_form(metadata, feed):
    assert server_form(metadata) == feed
