import json
import subprocess
import sys

from hp437b.cli import main


def test_help_and_capabilities_without_io(capsys):
    result = subprocess.run(
        [sys.executable, "-m", "hp437b.cli", "--help"], capture_output=True, text=True
    )
    assert result.returncode == 0 and "capabilities" in result.stdout
    assert main(["capabilities"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert len(result["commands"]) == 118
    assert "A03" in result["commands"]["C004"]["deferred"]


def test_cli_demo_end_to_end(tmp_path, capsys):
    path = tmp_path / "demo.csv"
    assert main(["demo", "--output", str(path), "--count", "2", "--interval", "0"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result == {"status": "completed", "rows": 2, "simulation": True}
    assert main(["demo", "--output", str(path)]) == 1


def test_cli_invalid_options_before_visa_open(tmp_path):
    assert (
        main(["log", "--resource", "GPIB0::13::INSTR", "--output", str(tmp_path / "bad.csv")]) == 1
    )
    assert not list(tmp_path.iterdir())
