"""Explicit UI preparation actions using the accepted bounded ZERO/CAL runners."""

import hashlib
import html
from dataclasses import dataclass
from pathlib import Path

from . import diagnostics_cal as cal
from . import diagnostics_physical as diagnostics
from . import provenance as p
from . import reporting as r
from .operator_jobs import atomic, read
from .reconciliation_physical import PhysicalTarget
from .simulation import status_fixture

COMMON = diagnostics.PREPARED + ("warmed_up", "adjustment_confirmed")


def keys(action):
    p.require(action in ("ZERO", "CAL"), "Select ZERO or CAL")
    return COMMON + (
        ("no_rf_input",)
        if action == "ZERO"
        else ("direct_reference_path", "zero_ready", "factor_confirmed")
    )


def configuration(document):
    p._keys(
        document,
        (
            "resource",
            "expected_idn",
            "meter_serial",
            "sensor_serial",
            "workflow_lock_root",
            "known_issues",
        ),
    )
    target(document).validate()
    for key in ("meter_serial", "sensor_serial"):
        p.require(
            isinstance(document[key], str) and 1 <= len(document[key].strip()) <= 256,
            "Record meter and sensor identities",
        )
    p.require(
        isinstance(document["known_issues"], list)
        and all(isinstance(x, str) and len(x) <= 1000 for x in document["known_issues"])
        and len(document["known_issues"]) <= 20,
        "Invalid equipment issues",
    )
    lock = document["workflow_lock_root"]
    p.require(
        isinstance(lock, str) and Path(lock).is_absolute(),
        "Use the established absolute shared workflow lock root",
    )
    return p._json(r.encoded(document))


def target(config):
    resource = config["resource"]
    p.require(isinstance(resource, str), "Explicit USB resource required")
    parts = resource.split("::")
    p.require(len(parts) == 6, "Explicit adapter resource required")
    identity = config["expected_idn"]
    p.require(
        isinstance(identity, str) and len(identity) <= 256, "Expected identification required"
    )
    return PhysicalTarget(resource, parts[3], identity.encode("ascii"))


def inputs(action, mode, prepared, factor, source):
    expected = keys(action)
    p.require(mode in ("synthetic", "physical"), "Select a preparation source")
    p.require(
        (
            isinstance(prepared, dict)
            and set(prepared) == set(expected)
            and all(v is True for v in prepared.values())
        )
        if mode == "physical"
        else prepared == {},
        "Confirm every preparation item afresh",
    )
    if action == "CAL":
        factor = cal.factor_text(factor)
        p.require(
            isinstance(source, str) and 1 <= len(source.strip()) <= 256,
            "Record the sensor REF CAL FACTOR source",
        )
        return factor, source.strip()
    p.require(factor is None and source is None, "ZERO does not accept a CAL factor")
    return None, None


@dataclass
class SimulationFactory:
    simulation = True

    def __call__(self, resource):
        return SimulationWire(resource)


class SimulationWire:
    """Explicit software model; never loads VISA, USB, or a physical backend."""

    capabilities = frozenset({"read", "write", "eom", "go_to_local"})

    def __init__(self, resource):
        self.metadata = dict(
            resource=resource, adapter_identity=resource.split("::")[3], simulation=True
        )
        self.captured_raw = b""
        self.read_status = None
        self.zero_poll_receipt = None
        self.tag = 2
        self.done = False
        self.standby = False
        self.pending = None
        self.last_write_complete = self.read_started = False
        self.cal_read_timeout_s = None

    def open(self, timeout):
        pass

    def write(self, raw, deadline):
        self.captured_raw, self.read_status = b"", None
        self.last_write_complete, self.read_started = False, False
        self.pending = raw
        if raw == b"CS":
            self.done = False
        elif raw == b"ZE" or raw.startswith(b"CL"):
            self.done = True
        elif raw == b"TR3":
            self.standby = False
        self.last_write_complete = True

    def read(self, deadline):
        self.read_started = True
        if self.pending == b"*IDN?":
            raw = b"HEWLETT-PACKARD,437B,,1.8\r\n"
        elif self.pending == b"SM":
            raw = bytearray(status_fixture(logarithmic=False))
            raw[18] = ord("1") if self.standby else ord("0")
            raw = bytes(raw)
        elif self.pending in (b"*ESE?", b"*SRE?"):
            raw = b"000\r\n"
        elif self.pending == b"TR1":
            self.standby = True
            raw = b"+0.0400E-06\r\n"
        else:
            raise ValueError("Unexpected simulated preparation query")
        self.captured_raw, self.read_status = raw, 0
        return raw

    def zero_poll(self, deadline, *, cancelled):
        byte = 2 if self.done else 0
        value = dict(
            tag=self.tag,
            adapter_status_byte=byte,
            capabilities_hex="",
            control_hex=bytes((1, self.tag, byte)).hex(),
            interrupt_hex=bytes((0x80 | self.tag, byte)).hex(),
            simulation=True,
        )
        self.tag += 1
        self.zero_poll_receipt = value
        return value

    def return_local(self, deadline):
        return dict(status="accepted", simulation=True)

    def close(self):
        pass


def run(path, request, emit, *, factory=None):
    action, mode = request["workflows"][0], request["meter_mode"]
    factor, source = inputs(
        action, mode, request["prepared"], request["reference_factor"], request["factor_source"]
    )
    config = (
        configuration(request["preparation_config"])
        if mode == "physical"
        else dict(
            resource="USB0::0x03EB::0x2065::SIMULATED::0::INSTR",
            expected_idn="HEWLETT-PACKARD,437B,,1.8",
            meter_serial="SIMULATED-METER",
            sensor_serial="SIMULATED-SENSOR",
            workflow_lock_root=str(path / "simulation-locks"),
            known_issues=[],
        )
    )
    emit(phase="running", current=action, index=1)
    result = diagnostics.run_physical(
        path / "capture",
        target=target(config),
        prepared={
            k: True for k in keys(action) if k not in ("adjustment_confirmed", "factor_confirmed")
        }
        if mode == "synthetic"
        else {
            k: v
            for k, v in request["prepared"].items()
            if k not in ("adjustment_confirmed", "factor_confirmed")
        },
        equipment={k: config[k] for k in ("meter_serial", "sensor_serial")},
        confirmed=True,
        prior_worker_stopped=True,
        workflow_lock_root=config["workflow_lock_root"],
        supervised_zero=action == "ZERO",
        confirmed_zero=action == "ZERO",
        supervised_cal=action == "CAL",
        confirmed_cal=action == "CAL",
        cal_reference_factor=factor,
        cal_factor_source=source,
        work_s=45 if action == "ZERO" else cal.WORK_S,
        total_s=50 if action == "ZERO" else cal.TOTAL_S,
        cancelled=lambda: (path / "cancel.requested").exists(),
        _factory_override=SimulationFactory() if mode == "synthetic" else factory,
    )
    receipt = path / "capture/diagnostics.json"
    digest = hashlib.sha256(receipt.read_bytes()).hexdigest()
    assessment = result[action.lower() + "_assessment"]
    final_status = next(
        (
            q["value"]
            for q in reversed(result["queries"])
            if q["step_id"] in ("after.SM", "final.SM")
            and q["status"] == "completed"
            and q.get("accepted_before_deadline")
        ),
        None,
    )
    summary = dict(
        reference_off_observed=not final_status["reference_on"] if final_status else None,
        action=action,
        mode=mode,
        execution=result["status"],
        receipt_sha256=digest,
        elapsed_s=result["elapsed_s"],
        equipment=result["equipment_labels"],
        reference_factor=factor,
        factor_source=source,
        assessment=assessment,
        local_return=result.get("local_return"),
        failed_read_shutdown=result.get("cal_failed_read_shutdown"),
        transport_closed=result["transport_closed"],
        operator=request["operator"],
        started_utc=request["started_utc"],
        front_panel_confirmation="pending" if mode == "physical" else "not_applicable",
        known_issues=config["known_issues"],
    )
    atomic(path / "preparation-result.json", summary)
    emit(
        phase="finished" if result["status"] == "completed" else "failed",
        current=None,
        outcome=result["status"],
        error=None
        if result["status"] == "completed"
        else "Preparation stopped. Inspect the receipt and reconcile the front panel; no retry ran.",
        results=[
            dict(
                workflow=action,
                execution=result["status"],
                acceptance="Not a DUT test",
                completed_points=int(result["status"] == "completed"),
                requested_points=1,
            )
        ],
    )


def artifact(path, name):
    p.require(name in ("receipt.json", "receipt.html"), "Unknown preparation artifact")
    summary = read(path / "preparation-result.json")
    receipt = path / "capture/diagnostics.json"
    p.require(
        not receipt.is_symlink() and receipt.stat().st_size <= 512 * 1024,
        "Invalid preparation receipt",
    )
    raw = receipt.read_bytes()
    p.require(
        hashlib.sha256(raw).hexdigest() == summary["receipt_sha256"], "Preparation receipt changed"
    )
    if name == "receipt.json":
        return raw, "application/json", False

    def e(value):
        return html.escape(
            "Yes"
            if value is True
            else "No"
            if value is False
            else "Not verified"
            if value is None
            else str(value)
            .replace("not_applicable", "Not applicable")
            .replace("synthetic", "Simulation — no hardware")
        )

    a = summary["assessment"]
    fields = [
        ("Outcome", summary["execution"]),
        ("Source", summary["mode"]),
        ("Started", summary["started_utc"]),
        ("Operator", summary["operator"] or "Not recorded"),
        ("Meter", summary["equipment"]["meter_serial"]),
        ("Sensor", summary["equipment"]["sensor_serial"]),
        ("Elapsed", f"{summary['elapsed_s']:.2f} seconds"),
        ("REF CAL FACTOR", summary["reference_factor"] or "Not used"),
        ("Factor source", summary["factor_source"] or "Not used"),
        ("Completion observed", a["completion_indication_observed"]),
        (
            "Reference off observed",
            summary["reference_off_observed"],
        ),
        ("Local return", (summary["local_return"] or {}).get("status", "Not verified")),
        ("Transport closed", summary["transport_closed"]),
        ("Front-panel observation", summary["front_panel_confirmation"]),
        ("Known equipment issues", "; ".join(summary["known_issues"]) or "None recorded"),
    ]
    rows = "".join(f'<tr><th scope="row">{e(k)}</th><td>{e(v)}</td></tr>' for k, v in fields)
    body = f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Meter preparation receipt</title><link rel="stylesheet" href="/app.css"><main class="preparation-receipt"><h1>{e(summary["action"])} preparation receipt</h1><p>{e(summary["mode"])} · {e(summary["execution"])}</p><p>Preparation record; no transmitter output test or accuracy verdict. Front-panel confirmation is recorded separately.</p><table><caption>Recorded preparation result</caption><tbody>{rows}</tbody></table><p class="hint">Original receipt SHA-256: {e(summary["receipt_sha256"])}</p><p><a href="receipt.json">Open raw runner receipt JSON</a></p></main></html>'
    return body.encode(), "text/html; charset=utf-8", False
