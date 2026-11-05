from qp import check
from qp.channel import Record
from qp.config import Config, Plugin, Settings
from qp.recipe import Recipe

SETTINGS = Settings(feed_lines=["4.2"], test_lines=["4.2"])


def config(*plugins: Plugin) -> Config:
    return Config(settings=SETTINGS, plugins={p.slug: p for p in plugins})


def test_sorted_tables():
    ordered = config(Plugin(slug="alpha"), Plugin(slug="Beta"), Plugin(slug="gamma"))
    assert check.sorted_tables(ordered) == []
    problems = check.sorted_tables(config(Plugin(slug="gamma"), Plugin(slug="alpha")))
    assert problems and "alpha, gamma" in problems[0]


def test_naming_ok():
    feed = {"quick_map_services", "QuickOSM", "profile-manager", "profile_manager"}
    cfg = config(Plugin(slug="quick_map_services"), Plugin(slug="profile_manager"))
    assert check.naming(cfg, feed) == []


def test_naming_default_collides_with_unselected_feed_plugin():
    problems = check.naming(config(Plugin(slug="auto_save")), {"auto_save", "Auto_save"})
    assert problems == [
        "auto_save: qgis-stack-auto_save is also the default name of Auto_save on "
        "plugins.qgis.org; set an explicit `name`"
    ]


def test_naming_explicit_names_resolve_collision():
    cfg = config(
        Plugin(slug="auto_save", name="qgis-stack-auto_save"),
        Plugin(slug="Auto_save", name="qgis-stack-auto_save-legacy"),
    )
    assert check.naming(cfg, {"auto_save", "Auto_save"}) == []


def test_naming_duplicate_names():
    cfg = config(Plugin(slug="a", name="qgis-stack-x"), Plugin(slug="b", name="qgis-stack-x"))
    assert check.naming(cfg, set()) == ["a, b: all named qgis-stack-x"]


def test_conda_forge_clash():
    cfg = config(Plugin(slug="manager"), Plugin(slug="demo"))
    assert check.conda_forge_clash(cfg, {"qgis", "qgis-stack-manager"}) == [
        "manager: qgis-stack-manager exists on conda-forge"
    ]


def recipe(depends, build_number=0, license="GPL-2.0-or-later") -> Recipe:
    return Recipe("qgis-stack-demo", "1.0", build_number, depends, license, data={})


def record(depends, build_number=0, license="GPL-2.0-or-later") -> Record:
    return Record("qgis-stack-demo", "1.0", build_number, depends, license)


QGIS = "qgis >=3.32.0,<=4.99.99"


def test_build_numbers_unchanged_or_unpublished():
    assert check.build_numbers([recipe([QGIS])], [record([QGIS])]) == []
    assert check.build_numbers([recipe([QGIS])], []) == []
    # whitespace and order don't count as changes
    assert check.build_numbers([recipe(["b", QGIS])], [record([QGIS, " b"])]) == []


def test_build_numbers_missing_bump():
    problems = check.build_numbers([recipe([QGIS, "plotly"])], [record([QGIS])])
    assert len(problems) == 1
    assert "depends" in problems[0] and "set build_number = 1" in problems[0]
    problems = check.build_numbers([recipe([QGIS], license="MIT")], [record([QGIS])])
    assert "license GPL-2.0-or-later -> MIT" in problems[0]


def test_build_numbers_compare_with_newest_build():
    published = [record([QGIS]), record([QGIS, "plotly"], build_number=1)]
    assert check.build_numbers([recipe([QGIS, "plotly"], build_number=1)], published) == []
    assert check.build_numbers([recipe([QGIS, "plotly"], build_number=2)], published) == []
    problems = check.build_numbers([recipe([QGIS])], published)
    assert problems == ["qgis-stack-demo 1.0: build_number 0 is below the published 1"]
