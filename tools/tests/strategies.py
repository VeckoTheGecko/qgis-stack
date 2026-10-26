"""Hypothesis strategies for QGIS plugin version strings (docs/plugin-versions.md).

plugins.qgis.org accepts any `version` in metadata.txt, but real ones follow a loose
grammar:

    version := [prefix] release [sep tag [num_sep number]]
    release := number ("." number){0..4}

e.g. 1.5.2, v4.23.1, 2026.6.12, 2.0.0-beta1, 1.5.3.post2, 1.0-alpha.1, 1.1.0-qgis4.
"""

from hypothesis import strategies as st

# Pre-release, post-release and dev tags that PEP 440 knows, as authors spell them.
PEP440_TAGS = ("a", "b", "c", "rc", "alpha", "beta", "pre", "preview", "dev", "post")
# Seen on plugins.qgis.org but not PEP 440.
OTHER_TAGS = ("hotfix", "qgis", "master", "p", "final", "C", "D")

# Small numbers, plus calendar versions such as 2026.6.12.
numbers = st.one_of(st.integers(0, 20), st.integers(2000, 2030)).map(str)


@st.composite
def plugin_versions(draw, *, pep440: bool = False, canonical: bool = False) -> str:
    """Versions as authors write them in metadata.txt.

    pep440: only versions `packaging.version.Version` parses.
    canonical: only versions plugins.qgis.org keeps unchanged, so the feed version
        equals the metadata.txt version (`qp.versions.server_form(v) == v`).
    """
    prefixes = ["", "v", "V"] if pep440 else ["", "v", "V", "v.", "ver."]
    prefix = draw(st.sampled_from(prefixes))
    # The site keeps only 4 dot-separated parts, and "v." is one of them.
    max_size = 4 - prefix.count(".") if canonical else 5
    release = draw(st.lists(numbers, min_size=1, max_size=max_size))
    version = prefix + ".".join(release)
    parts = prefix.count(".") + len(release)

    tag = draw(st.none() | st.sampled_from(PEP440_TAGS if pep440 else PEP440_TAGS + OTHER_TAGS))
    if tag is None:
        return version
    sep = draw(st.sampled_from(["", "-", "."]))
    # The site strips a leading zero that's followed by a letter: 1.0.0a2 -> 1.0.a2.
    if canonical and sep == "" and release[-1] == "0":
        sep = "-"
    number = draw(st.none() | numbers)
    num_sep = "" if number is None else draw(st.sampled_from(["", ".", "-"]))
    if canonical and parts + (sep == ".") + (num_sep == ".") > 4:
        return version
    return version + sep + tag + num_sep + (number or "")


# Anything an author could put on the `version =` line: one line, non-blank.
metadata_versions = st.text(
    st.characters(codec="utf-8", exclude_categories=("Cc", "Cs", "Zl", "Zp")),
    min_size=1,
    max_size=32,
).filter(str.strip)
