"""OQ-01 task/command deadline enforcement before and during execution."""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

RUNNER = Path(__file__).parents[1] / "tools/offline_qa.py"


def test_supervisor_times_out_owned_process():
    start = time.monotonic()
    result = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--seconds",
            "0.1",
            "--",
            sys.executable,
            "-c",
            "import time; time.sleep(30)",
        ],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 124, result.stderr
    assert "deadline reached" in result.stderr
    assert time.monotonic() - start < 4


@pytest.mark.parametrize(
    "deadline,final,expected",
    [
        ("past", False, 124),
        ("reserve", False, 124),
        ("nan", False, 2),
        ("inf", False, 2),
        ("reserve", True, 0),
    ],
)
def test_global_deadline_and_final_reserve(tmp_path, deadline, final, expected):
    marker = tmp_path / "started.txt"
    env = os.environ.copy()
    env["HP437B_QA_DEADLINE"] = {
        "past": str(time.time() - 1),
        "reserve": str(time.time() + 10),
    }.get(deadline, deadline)
    command = [sys.executable, str(RUNNER), "--seconds", "2"]
    if final:
        command.append("--final")
    command += [
        "--",
        sys.executable,
        "-c",
        "import pathlib,sys; pathlib.Path(sys.argv[1]).write_text('started')",
        str(marker),
    ]
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=5)
    assert result.returncode == expected, result.stderr
    assert marker.exists() == (expected == 0)
