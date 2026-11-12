"""OQ-01 inherited startup protection, using sentinel backends only."""

import os
import subprocess
import sys
from pathlib import Path


def test_guard_canaries_in_parent_exec_and_spawn():
    assert os.environ.get("HP437B_OFFLINE_GUARD") == "active", "Use tools/offline_qa.py"
    script = Path(__file__).parents[1] / "tools/offline_canary.py"
    result = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True, timeout=20
    )
    assert result.returncode == 0, result.stderr
    assert "parent, exec, spawn" in result.stdout


def test_startup_import_failure_exits_before_application(tmp_path):
    guard = Path(__file__).parents[1] / "tools/offline_guard"
    (tmp_path / "pyvisa.py").write_text("raise RuntimeError('synthetic startup import failure')\n")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(guard) + os.pathsep + str(tmp_path)
    result = subprocess.run(
        [sys.executable, "-c", "print('application must not run')"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 86
    assert "application must not run" not in result.stdout
    assert "synthetic startup import failure" in result.stderr
