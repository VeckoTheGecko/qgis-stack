from qp.edit import add_plugin

TEXT = """# header

[settings]
feed_lines = ["4.2"]

[plugins.alpha]

# about gamma
[plugins.gamma]
add_run = ["x"]
"""


def test_inserts_sorted_before_next_tables_comment(tmp_path):
    path = tmp_path / "plugins.toml"
    path.write_text(TEXT)
    assert add_plugin(path, "Beta")
    assert path.read_text() == TEXT.replace("# about gamma", "[plugins.Beta]\n\n# about gamma")


def test_appends_last_and_refuses_duplicates(tmp_path):
    path = tmp_path / "plugins.toml"
    path.write_text(TEXT)
    assert add_plugin(path, "zeta")
    assert path.read_text().endswith('add_run = ["x"]\n\n[plugins.zeta]\n')
    assert not add_plugin(path, "zeta")


def test_first_table(tmp_path):
    path = tmp_path / "plugins.toml"
    path.write_text(TEXT)
    assert add_plugin(path, "aardvark")
    assert "[settings]\nfeed_lines" in path.read_text()
    assert '"4.2"]\n\n[plugins.aardvark]\n\n[plugins.alpha]' in path.read_text()
