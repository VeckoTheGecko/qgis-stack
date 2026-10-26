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


@pytest.mark.parametrize("command", COMMANDS, ids=lambda c: c.name)
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
