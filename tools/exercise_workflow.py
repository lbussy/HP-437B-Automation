"""Exercise POWER REF workflow v1 with explicit fakes only; never opens hardware.

Prototype for WF-01: python tools/exercise_workflow.py --output NEW_DIRECTORY
Run through tools/offline_qa.py. The physical adapter path is not implemented.
"""

import argparse
import csv
import hashlib
import json
import platform
import statistics
import subprocess
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext
from importlib.metadata import version
from pathlib import Path

from hp437b import protocol
from hp437b.errors import OperationTimeout, ProtocolError, TransportError
from hp437b.instrument import Instrument
from hp437b.logger import collect
from hp437b.provenance import export_wf01, sidecar_path
from hp437b.simulation import status_fixture

SCENARIOS = (
    "nominal",
    "slow",
    "malformed",
    "timeout",
    "cancel",
    "instrument-error",
    "source-off-failure",
)
STAGES = ("S00", "S10", "S20", "S30", "S40", "S50", "S60", "S70")


def save(path, value):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


class Bench:
    """Synthetic source, virtual host clock, and auditable fake transactions."""

    def __init__(self, scenario):
        self.scenario = scenario
        self.now = 0.0
        self.source = False
        self.local = True
        self.role = "S00"
        self.reads = 0
        self.trace = []
        self.uncertain = False

    def sleep(self, amount):
        if self.scenario == "cancel" and self.role == "S40" and self.reads == 3:
            raise KeyboardInterrupt("synthetic cancellation between completed samples")
        self.now += amount

    def utc(self):
        return datetime(2026, 11, 12, tzinfo=UTC) + timedelta(seconds=self.now)

    def event(self, operation, **data):
        self.trace.append(
            {
                "mode": "synthetic",
                "stage": self.role,
                "elapsed_s": self.now,
                "operation": operation,
                **data,
            }
        )


class FakeWire:
    capabilities = frozenset({"read", "write", "eom", "go_to_local"})
    metadata = {"transport": "WF-01 explicit fake", "hardware": "none", "simulation": True}

    def __init__(self, bench):
        self.bench = bench
        self.pending = None
        self.closed = False
        self.local_return = None
        self.bench.event("session_open")

    def write(self, data, deadline):
        assert not self.closed and self.pending is None
        self.bench.event("write", raw_hex=data.hex())
        self.bench.local = False
        if data in (b"OC0", b"OC1"):
            if self.bench.scenario == "source-off-failure" and self.bench.role == "S50":
                raise TransportError("injected reference-off transfer failure")
            self.bench.source = data == b"OC1"
        elif data in (b"*IDN?", b"SM", b"TR2"):
            self.pending = data
        elif data not in (b"RL0", b"LN", b"TR3"):
            raise AssertionError(f"Unexpected synthetic command: {data!r}")

    def read(self, deadline):
        assert not self.closed and self.pending is not None
        request, self.pending = self.pending, None
        if request == b"*IDN?":
            raw = b"HEWLETT-PACKARD,437B,SYNTHETIC-437B-001,1.9\r\n"
        elif request == b"SM":
            raw = bytearray(status_fixture(logarithmic=False))
            raw[16] = ord("1" if self.bench.source else "0")
            raw = bytes(raw)
        else:
            self.bench.reads += 1
            self.bench.now += (
                2.5 if self.bench.scenario == "slow" and self.bench.role == "S40" else 0.02
            )
            if self.bench.role == "S40" and self.bench.reads == 4:
                if self.bench.scenario == "timeout":
                    self.bench.event("read_error", category="synthetic timeout")
                    raise OperationTimeout("injected timeout; no real IPC/USB timeout occurred")
                if self.bench.scenario == "malformed":
                    raw = b"MALFORMED\r\n"
                elif self.bench.scenario == "instrument-error":
                    raw = b"9.0031E+40\r\n"
                else:
                    raw = self.sample()
            else:
                raw = self.sample()
        self.bench.event("read", raw_hex=raw.hex())
        return raw

    def sample(self):
        index = max(0, self.bench.reads - 2)
        if self.bench.source:
            value = ("0.000987", "0.000988", "0.000989", "0.000988", "0.000987", "0.000989")[
                index % 6
            ]
        else:
            value = ("-0.00000005", "-0.00000004", "-0.00000006")[index % 3]
        mantissa, exponent = format(Decimal(value), "+.4E").split("E")
        return (mantissa + "E" + f"{int(exponent):+03d}" + "\r\n").encode("ascii")

    def return_local(self, deadline):
        self.bench.local = True
        self.local_return = {"status": "accepted", "mode": "synthetic"}
        self.bench.event("go_to_local")

    def close(self):
        if not self.closed:
            self.bench.event("session_close")
            self.closed = True


class StageInstrument(Instrument):
    """Workflow policy over existing APIs; generic collect semantics stay unchanged."""

    def __init__(self, wire, expected_source):
        super().__init__(wire)
        self.expected_source = expected_source

    def read_status(self):
        result = super().read_status()
        if (
            result.unit != "W"
            or result.reference_on != self.expected_source
            or result.relative
            or result.offset_on
            or result.duty_on
            or result.measurement_error
            or result.entry_error
            or result.range_code not in range(11, 16)
            or result.filter_code not in range(10, 20)
        ):
            raise ProtocolError("Workflow status precondition mismatch")
        return result

    def acquire(self, trigger="TR2"):
        result = super().acquire(trigger)
        if result.error_code:
            raise ProtocolError(f"Workflow stops on instrument error {result.error_code}")
        return result


def inspect_stage(path, mode="synthetic"):
    """Recompute valid-row results from stored evidence, not simulation state."""
    metadata = json.loads(path.with_name(path.name + ".session.json").read_text())
    with path.open() as handle:
        rows = list(csv.DictReader(handle))
    assert metadata["simulation"] is (mode == "synthetic") and metadata["rows"] == len(rows)
    assert [int(row["sequence"]) for row in rows] == list(range(1, len(rows) + 1))
    values, times = [], []
    for row in rows:
        assert row["session_id"] == metadata["session_id"] and row["unit"] == "W"
        assert datetime.fromisoformat(row["received_utc"]).utcoffset() is not None
        elapsed = float(row["elapsed_s"])
        assert elapsed >= 0 and (not times or elapsed >= times[-1])
        times.append(elapsed)
        if row["status"] == "ok":
            value = Decimal(row["value"])
            assert value.is_finite()
            assert protocol.measurement(bytes.fromhex(row["raw_hex"]), "W").value == value
            values.append(value)
        else:
            assert row["status"] in ("failed", "interrupted", "instrument_error")
    with localcontext() as context:
        context.prec = 34
        mean = sum(values) / len(values) if values else None
        sd = (
            (sum((x - mean) ** 2 for x in values) / (len(values) - 1)).sqrt()
            if len(values) >= 2
            else None
        )
        p2p = max(values) - min(values) if values else None
        metrics = {
            "mean_W": mean,
            "min_W": min(values) if values else None,
            "max_W": max(values) if values else None,
            "peak_to_peak_W": p2p,
            "sample_sd_W": sd,
            "relative_peak_to_peak_percent": 100 * p2p / abs(mean) if mean else None,
            "first_to_last_change_W": values[-1] - values[0] if values else None,
        }
    gaps = [b - a for a, b in zip(times, times[1:], strict=False)]
    return {
        "mode": mode,
        "csv": "stages/" + path.name,
        "session_id": metadata["session_id"],
        "stage_status": metadata["status"],
        "attempted": len(rows),
        "valid": len(values),
        "nonvalid": len(rows) - len(values),
        "receipt_span_s": times[-1] - times[0] if times else None,
        "median_receipt_spacing_s": statistics.median(gaps) if gaps else None,
        "min_receipt_spacing_s": min(gaps) if gaps else None,
        "max_receipt_spacing_s": max(gaps) if gaps else None,
        "metrics": {k: str(v) if v is not None else None for k, v in metrics.items()},
        "undefined_reason": "fewer than two valid values for SD; empty/zero denominator metrics are null",
        "evidence": [{"sequence": row["sequence"], "status": row["status"]} for row in rows],
    }


def render(record, analysis):
    lines = [
        "# POWER REF workflow exercise report",
        "",
        "**SYNTHETIC — no physical instrument or RF source was used.**",
        "",
        f"Execution: **{record['status']}**. Scenario: `{record['scenario']}`. Virtual elapsed time: {record['elapsed_s']:.3f} s.",
        "",
        "This executed prototype uses real Instrument/collect code with explicit fakes and a virtual clock. The sustained stage requests a 300-second start window; counts and receipt spans below are actual synthetic results.",
        "",
        "## Configuration and provenance",
        "",
        "Workflow: power-reference-v1. Nominal source: 50 MHz / 0.001 W (declared, not independently measured). Absolute W; requested interval 1 s; timeout 10 s. Fictional meter SYNTHETIC-437B-001 and sensor SYNTHETIC-8482A-001. No calibration, physical setup, or accuracy claim applies. Source control, zero corrections, automatic range/filter, and local restoration are simulated.",
        "",
        f"Software: `{record['software']['commit']}`; dirty tree: `{record['software']['dirty']}`. Prototype/definition hashes are in workflow.json. Agent commentary: not used; deterministic report only.",
        "",
        "## Stages",
        "",
        "| Stage | State | Reason |",
        "| --- | --- | --- |",
    ]
    for stage, detail in record["stages"].items():
        lines.append(
            f"| {stage} | {detail['status']} | {detail.get('error', '').replace('|', '/')} |"
        )
    lines += [
        "",
        "## Stored-data results",
        "",
        "| Stage | Attempted / valid / nonvalid | Mean (mW) | Peak-to-peak (mW) | Sample SD (mW) | Median spacing (s) |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for stage, result in analysis["stages"].items():

        def presentation(key, result=result):
            text = result["metrics"][key]
            return f"{Decimal(text) * 1000:.9g}" if text is not None else "undefined"

        lines.append(
            f"| [{stage}]({result['csv']}) | {result['attempted']} / {result['valid']} / {result['nonvalid']} | {presentation('mean_W')} | {presentation('peak_to_peak_W')} | {presentation('sample_sd_W')} | {result['median_receipt_spacing_s']} |"
        )
    lines += [
        "",
        f"Data integrity: **{analysis['integrity']}**. Measurement criteria: **not evaluated**; no accuracy/stability limits were supplied.",
        "",
        "Comparisons (W, valid subsets only): `"
        + json.dumps(analysis["comparisons"])
        + "`. Null denotes unavailable evidence, not zero.",
        "",
    ]
    if "S40" in analysis["stages"] and analysis["stages"]["S40"]["metrics"]["mean_W"] is not None:
        mean = Decimal(analysis["stages"]["S40"]["metrics"]["mean_W"])
        lines += [
            f"S40 valid-subset mean versus nominal: {(mean - Decimal('.001')) * 1000:.9g} mW ({100 * (mean - Decimal('.001')) / Decimal('.001'):.9g}%). This is descriptive, not an accuracy or compliance verdict. A failed/interrupted stage remains partial regardless of available statistics.",
            "",
        ]
    lines += [
        "## Final state and limitations",
        "",
        f"Final source state: **{record['final_state']['source']}**. Final local state: **{record['final_state']['local']}**. These are synthetic outcomes only.",
        "",
        "Negative source-off readings are retained as descriptive baseline observations, not calibrated low-power results or baseline corrections. Means are sample-weighted; SD uses n−1. Invalid rows are excluded numerically and retained diagnostically. Setup probes are excluded. Actual receipt spans are not the configured start window or integration time.",
        "",
        "A malformed/failed transaction prevents blind source-off/status/local traffic. Unknown final state requires operator recovery in a future physical runner. No physical path, real worker timeout/abort, hardware recovery, chart rendering, or external agent integration is exercised here.",
        "",
        "## Evidence",
        "",
        "See [workflow.json](workflow.json), [analysis.json](analysis.json), [transaction trace](trace.json), and [artifact hashes](artifacts.json). Every CSV has its existing session sidecar. Statistics are recomputed from saved CSV rows; raw frames and row references remain available. Input/profile, source state, and software identity are in the workflow manifest.",
        "",
    ]
    return "\n".join(lines)


def run(output, scenario="nominal"):
    if scenario not in SCENARIOS:
        raise ValueError("Choose an explicit supported synthetic scenario")
    output = Path(output)
    if sidecar_path(output).exists():
        raise FileExistsError("Provenance sidecar path already exists")
    output.mkdir()  # Refuse existing directories, before constructing any session.
    (output / "stages").mkdir()
    bench = Bench(scenario)
    root = Path(__file__).resolve().parents[1]
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True))
    record = {
        "mode": "synthetic",
        "simulation": True,
        "workflow_id": "power-reference-v1",
        "run_id": str(uuid.uuid4()),
        "scenario": scenario,
        "status": "running",
        "started_utc": bench.utc().isoformat(),
        "software": {
            "commit": commit,
            "dirty": dirty,
            "prototype_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "python": platform.python_version(),
            "dependencies": {name: version(name) for name in ("PyVISA", "PyVISA-py", "PyUSB")},
        },
        "definition_sha256": hashlib.sha256(
            (root / "docs/workflows/POWER-REFERENCE-V1.md").read_bytes()
        ).hexdigest(),
        "profile": {
            "unit": "W",
            "interval_s": 1,
            "timeout_s": 10,
            "sustained_duration_s": 300,
            "baseline_count": 3,
            "short_count": 3,
            "observation_s": 20,
        },
        "stages": {s: {"status": "pending"} for s in STAGES},
        "provenance": {
            "meter": "SYNTHETIC-437B-001",
            "sensor": "SYNTHETIC-8482A-001",
            "calibration_records": None,
            "known_equipment_issues": "not applicable to synthetic equipment",
        },
    }
    # A crash leaves an explicit starting/running checkpoint, not a completed run.
    save(output / "starting.json", record)
    for name, source in (
        ("definition.md", root / "docs/workflows/POWER-REFERENCE-V1.md"),
        ("prototype.py", Path(__file__)),
        ("LICENSE", root / "LICENSE"),
    ):
        with (output / name).open("xb") as handle:
            handle.write(source.read_bytes())

    def begin(stage):
        bench.role, bench.reads = stage, 0
        record["stages"][stage] = {"status": "running", "start_s": bench.now}

    def done():
        record["stages"][bench.role].update(status="completed", end_s=bench.now)

    def session(action):
        instrument = StageInstrument(FakeWire(bench), bench.role in ("S20", "S30", "S40"))
        try:
            action(instrument)
        finally:
            # Prototype observes existing uncertainty state; never attempts repair.
            bench.uncertain |= instrument._uncertain
            try:
                instrument.close()
            except BaseException:
                bench.uncertain = True
                raise

    def control(on):
        def action(instrument):
            instrument.command("OC1" if on else "OC0", confirmed=True)
            instrument.expected_source = on
            if on:
                bench.sleep(20)
            instrument.configure_absolute("W")
            instrument.acquire()
            instrument.read_status()

        session(action)

    def capture(stage, duration=None):
        begin(stage)
        instrument = StageInstrument(FakeWire(bench), stage in ("S30", "S40"))
        try:
            collect(
                instrument,
                output / "stages" / f"{stage}.csv",
                count=None if duration else 3,
                duration=duration,
                interval=1,
                unit="W",
                simulation=True,
                clock=lambda: bench.now,
                sleep=bench.sleep,
                utcnow=bench.utc,
                context={
                    "workflow_id": record["workflow_id"],
                    "workflow_run_id": record["run_id"],
                    "stage_id": stage,
                    "mode": "synthetic",
                    "sensor_serial": "SYNTHETIC-8482A-001",
                },
            )
            # Independent post-capture status in a fresh session; collect closed its own.
            session(lambda i: (i.configure_absolute("W"), i.acquire(), i.read_status()))
            done()
        finally:
            bench.uncertain |= instrument._uncertain

    try:
        begin("S00")
        session(lambda i: (i.configure_absolute("W"), i.acquire(), i.read_status()))
        done()
        capture("S10")
        begin("S20")
        control(True)
        done()
        capture("S30")
        capture("S40", duration=300)
        begin("S50")
        control(False)
        done()
        capture("S60")
        record["status"] = "completed"
    except BaseException as exc:
        if not isinstance(exc, (Exception, KeyboardInterrupt)):
            raise
        record["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        record["stages"][bench.role].update(
            status=record["status"], error=f"{type(exc).__name__}: {exc}", end_s=bench.now
        )
        if not bench.uncertain and bench.source:
            failed_stage = bench.role
            try:
                bench.role = "S50-cleanup"
                control(False)
            except Exception as cleanup:
                record["cleanup_error"] = str(cleanup)
            finally:
                bench.role = failed_stage
        for stage in STAGES:
            if record["stages"][stage]["status"] == "pending" and stage != "S70":
                record["stages"][stage] = {
                    "status": "skipped",
                    "error": "previous stage did not complete",
                }
    begin("S70")
    analysis = {
        "mode": "synthetic",
        "integrity": "pass",
        "measurement_criteria": "not_evaluated",
        "stages": {},
    }
    for path in sorted((output / "stages").glob("*.csv")):
        try:
            analysis["stages"][path.stem] = inspect_stage(path)
        except Exception as exc:
            analysis["integrity"] = "fail"
            analysis.setdefault("errors", []).append(f"{path.name}: {type(exc).__name__}: {exc}")
            record["status"] = "failed"

    def stage_mean(stage):
        text = analysis["stages"].get(stage, {}).get("metrics", {}).get("mean_W")
        return Decimal(text) if text is not None else None

    comparisons = {}
    with localcontext() as context:
        context.prec = 34
        for label, a, b in (
            ("short_to_sustained_mean_change_W", "S30", "S40"),
            ("baseline_mean_change_W", "S10", "S60"),
        ):
            before, after = stage_mean(a), stage_mean(b)
            comparisons[label] = (
                str(after - before) if before is not None and after is not None else None
            )
        mean = stage_mean("S40")
        comparisons["nominal_delta_W"] = str(mean - Decimal(".001")) if mean is not None else None
        comparisons["nominal_delta_percent"] = (
            str(100 * (mean - Decimal(".001")) / Decimal(".001")) if mean is not None else None
        )
    analysis["comparisons"] = comparisons
    analysis["scope"] = (
        "available valid subsets only; null means unavailable; no pooled or baseline-corrected signal"
    )
    record["final_state"] = {
        "source": "unknown" if bench.uncertain else ("on" if bench.source else "off"),
        "local": "unknown" if bench.uncertain else str(bench.local).lower(),
        "origin": "synthetic only",
    }
    record.update(elapsed_s=bench.now, finished_utc=bench.utc().isoformat())
    done()
    save(output / "analysis.json", analysis)
    save(output / "trace.json", {"mode": "synthetic", "events": bench.trace})
    with (output / "report.md").open("x", encoding="utf-8") as handle:
        handle.write(render(record, analysis))
    inventory = {
        str(p.relative_to(output)): {
            "bytes": p.stat().st_size,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        }
        for p in sorted(output.rglob("*"))
        if p.is_file()
    }
    # Inventory the final manifest's intended bytes, then write it last. A report
    # storage failure cannot leave a completed workflow manifest behind.
    final_bytes = (json.dumps(record, indent=2, allow_nan=False) + "\n").encode()
    inventory["workflow.json"] = {
        "bytes": len(final_bytes),
        "sha256": hashlib.sha256(final_bytes).hexdigest(),
    }
    save(output / "artifacts.json", {"mode": "synthetic", "artifacts": inventory})
    save(output / "workflow.json", record)
    export_wf01(output, sidecar_path(output))
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--scenario", choices=SCENARIOS, default="nominal")
    parser.add_argument(
        "--report-output",
        type=Path,
        help="Publish provenance and a richer deterministic report after the capture closes",
    )
    parser.add_argument("--report-no-plots", action="store_true")
    args = parser.parse_args()
    if args.report_no_plots and args.report_output is None:
        parser.error("--report-no-plots requires --report-output")
    if args.report_output is not None:
        from hp437b.workflow_report import preflight, publish

        preflight(args.output, args.report_output, plots=not args.report_no_plots)
    result = run(args.output, args.scenario)
    if args.report_output is not None:
        publish(args.output, args.report_output, plots=not args.report_no_plots)
    print(
        json.dumps(
            {
                "mode": "synthetic",
                "status": result["status"],
                "output": str(args.output),
                "final_state": result["final_state"],
            }
        )
    )
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
