import subprocess
import sys

import pytest

from qp.cli import COMMANDS, NOT_IMPLEMENTED, build_parser, main


def test_help_lists_every_command(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for command in COMMANDS:
        assert command.name in out


def test_command_is_required(capsys):
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2
    assert "required" in capsys.readouterr().err


STUBS = [c for c in COMMANDS if c.run is None]


@pytest.mark.parametrize("command", STUBS, ids=lambda c: c.name)
def test_stub_reports_its_milestone(command, capsys):
    argv = [command.name]
    if command.name in {"add", "scan-deps"}:
        argv.append("quick_map_services")
    assert main(argv) == NOT_IMPLEMENTED
    assert command.milestone in capsys.readouterr().out


def test_arguments():
    parser = build_parser()
    args = parser.parse_args(["generate", "--plugin", "a", "--plugin", "b"])
    assert args.plugin == ["a", "b"]
    assert parser.parse_args(["top"]).n == 50
    assert parser.parse_args(["add", "QuickOSM"]).slug == "QuickOSM"


def test_python_m_qp():
    result = subprocess.run(
        [sys.executable, "-m", "qp", "--help"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
    assert "usage: qp" in result.stdout


def test_generate_unknown_plugin(tmp_path, capsys):
    config = tmp_path / "plugins.toml"
    config.write_text('[settings]\nfeed_lines = ["4.2"]\ntest_lines = ["4.2"]\n[plugins.demo]\n')
    assert main(["--config", str(config), "generate", "--plugin", "nope"]) == 1
    assert "not in plugins.toml: nope" in capsys.readouterr().err


def test_build_without_recipes(tmp_path, capsys):
    assert main(["--recipes-dir", str(tmp_path), "build"]) == 1
    assert "run `qp generate` first" in capsys.readouterr().out


def test_build_no_test_skips_rattler_build_tests(tmp_path, monkeypatch):
    from qp import build

    calls = []
    monkeypatch.setattr(build, "recipe_dirs", lambda recipes_dir, slugs: [tmp_path / "r"])
    monkeypatch.setattr(build.subprocess, "run", lambda cmd, check: calls.append(cmd) or _Done())
    assert main(["build", "--no-test"]) == 0
    assert main(["build"]) == 0
    i = calls[0].index("--test")
    assert calls[0][i : i + 2] == ["--test", "skip"]
    assert "--test" not in calls[1]


class _Done:
    returncode = 0
