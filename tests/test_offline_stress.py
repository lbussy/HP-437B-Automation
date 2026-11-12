"""Bounded optional synthetic campaigns. HP437B_STRESS=1 opts in.

OQ-04/05/06, seed 4378482. Use tools/offline_qa.py --seconds 180.
No random input is presumed invalid merely because it was mutated.
"""

import csv
import json
import os
import random
import time
from decimal import Decimal

import pytest
from test_transport import connected

from hp437b import protocol
from hp437b.errors import OperationTimeout, ProtocolError
from hp437b.instrument import Instrument
from hp437b.logger import collect
from hp437b.simulation import DemoTransport

pytestmark = pytest.mark.skipif(
    os.environ.get("HP437B_STRESS") != "1", reason="opt-in bounded synthetic campaign"
)


def test_seeded_measurement_campaign():
    rng = random.Random(4378482)
    for _ in range(2500):
        text = f"{rng.choice('+-')}{rng.randrange(10)}.{rng.randrange(10000):04d}E{rng.randrange(-99, 40):+03d}"
        raw = text.encode() + b"\r\n"
        result = protocol.measurement(raw, "W")
        assert result.value == Decimal(text) and result.raw == raw and result.error_code is None
        # These mutations have independent rejection oracles: non-ASCII,
        # missing LF, and oversize. Other mutations may be valid/unspecified.
        bad = [raw[: rng.randrange(len(raw))] + b"\xff" + raw, raw[:-1], raw + b"X" * 4097]
        for mutated in bad:
            with pytest.raises(ProtocolError):
                protocol.measurement(mutated, "W")


def test_five_thousand_synthetic_rows(tmp_path):
    wire = DemoTransport()
    path = tmp_path / "synthetic-stress.csv"
    record = collect(Instrument(wire), path, count=5000, interval=0, unit="W", simulation=True)
    with path.open() as handle:
        rows = list(csv.DictReader(handle))
    saved = json.loads(path.with_name(path.name + ".session.json").read_text())
    assert record["rows"] == saved["rows"] == len(rows) == 5000
    assert record["status"] == "completed" and saved["simulation"] and wire.closed
    assert [int(r["sequence"]) for r in rows] == list(range(1, 5001))
    assert all(
        r["session_id"] == saved["session_id"] and r["unit"] == "W" and r["status"] == "ok"
        for r in rows
    )
    assert all(
        Decimal(r["value"]) == Decimal("0.000001") and r["raw_hex"] == b"+1.0000E-06\r\n".hex()
        for r in rows
    )
    assert all(
        float(a["elapsed_s"]) <= float(b["elapsed_s"]) for a, b in zip(rows, rows[1:], strict=False)
    )


def test_thirty_real_ipc_late_replies():
    for mode in ["late_error", "late_ok", "late_disconnect"] * 10:
        transport = connected(mode)
        process = transport._process
        sent = []
        original = transport._pipe.send

        def send(message, sent=sent, original=original):
            sent.append(message)
            original(message)

        transport._pipe.send = send
        start = time.monotonic()
        try:
            with pytest.raises(OperationTimeout):
                transport.read(start + 0.2)
            expected = {
                "late_error": "worker_error_received",
                "late_ok": "late_result_discarded",
                "late_disconnect": "worker_disconnected",
            }[mode]
            assert transport.read_deadline_cleanup["status"] == expected
            assert len(sent) == 1 and sent[0][:2] == ("read", None)
            assert transport._pipe is None and transport._process is None and process._closed
            assert time.monotonic() - start < 2.0
        finally:
            transport.close()
