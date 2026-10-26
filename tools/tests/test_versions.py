import pytest

from qp.versions import VersionError, normalize


@pytest.mark.parametrize(
    ("upstream", "conda"),
    [
        ("1.5.2", "1.5.2"),
        ("2026.6.12", "2026.6.12"),
        ("v4.23.1", "4.23.1"),
        ("V1.5", "1.5"),
        ("1.5.6a", "1.5.6a"),
        ("1.5.3.post2", "1.5.3.post2"),
        ("2.0.0-beta1", "2.0.0beta1"),
        ("1.0-2", "1.0.2"),
        (" 3.3 ", "3.3"),
    ],
)
def test_normalize(upstream, conda):
    assert normalize(upstream) == conda


@pytest.mark.parametrize("upstream", ["", "beta", "1.0 final", "1.0/2", "vNext"])
def test_normalize_rejects(upstream):
    with pytest.raises(VersionError, match="version = "):
        normalize(upstream)


def test_override_wins():
    assert normalize("1.0 final", {"1.0 final": "1.0"}) == "1.0"
    assert normalize("v2", {"v1": "1"}) == "2"


def test_override_is_validated():
    with pytest.raises(VersionError):
        normalize("1.0", {"1.0": "one"})
