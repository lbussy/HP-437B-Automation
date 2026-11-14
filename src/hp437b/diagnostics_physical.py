"""Opt-in supervised diagnostics in one disposable worker; no logging hooks."""

import hashlib
import json
import math
import multiprocessing
import platform
import signal
import time
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path

from . import diagnostics as diag
from . import diagnostics_acquisition as settings
from . import diagnostics_err_selection as selection
from . import diagnostics_lifecycle as life
from . import diagnostics_poll as polling
from . import diagnostics_snapshot as snapshot
from . import protocol
from . import reconciliation as rec
from . import reconciliation_physical as phy
from .errors import ProtocolError
from .instrument import Instrument
from .logger import _atomic_json
from .serial_poll_probe import SerialPollProbe
from .transport import remaining
from .usb488 import session_interface

PREPARED = (
    "power_ref_off",
    "live_readings",
    "rmt_off",
    "no_pending_operation",
    "other_control_apps_closed",
    "operator_available",
)
MESSAGE_BYTES = 32768


class _DiagnosticBridge(phy._Bridge):
    """Keep partial framing evidence without changing the qualified bridge."""

    def __init__(self, resource):
        super().__init__(resource)
        self.captured_raw = b""
        self.read_status = None
        self.poll_receipt = None
        self._poll_probe = None

    def write(self, data, deadline):
        self.captured_raw, self.read_status = b"", None
        super().write(data, deadline)

    def read(self, deadline):
        from pyvisa.constants import StatusCode

        self.handle.timeout = self._ms(deadline)
        raw, status = self.handle.visalib.read(self.handle.session, 4097)
        self.captured_raw, self.read_status = bytes(raw[:4097]), int(status)
        if len(raw) > 4096 or status != StatusCode.success:
            raise ProtocolError("Incomplete/oversized diagnostics reply; no continuation read")
        return bytes(raw)

    def poll_once(self, deadline, *, cancelled):
        if self._poll_probe is None:
            self._poll_probe = SerialPollProbe(
                session_interface(self.manager, self.handle), cancelled=cancelled
            )
        probe = self._poll_probe
        try:
            return probe.poll_once(deadline, confirmed_source_off_idle=True)
        finally:
            self.poll_receipt = probe.receipt


def _factory(resource):
    return _DiagnosticBridge(resource)


def _worker(
    pipe,
    stop,
    target,
    factory,
    deadline,
    lock_path,
    include_latched_reads,
    lifecycle=False,
    err_selection=False,
    numeric_entry=False,
    lp2_snapshot=False,
    acquisition_settings=False,
    original_resolution=None,
    settings_settle_s=20.0,
    settings_restore_refresh_s=4.0,
    serial_poll_probe=False,
):
    signal.signal(signal.SIGINT, signal.SIG_IGN)  # Parent owns cancellation and disposal.
    wire = None
    started = time.monotonic()
    plan = diag.BASIC_QUERIES + (diag.LATCHED_QUERIES if include_latched_reads else ())
    result = dict(
        status="preflight_failed",
        stage="ownership",
        transport_closed=None,
        queries=polling.plan()
        if serial_poll_probe
        else settings.plan(original_resolution, settings_settle_s, settings_restore_refresh_s)
        if acquisition_settings
        else snapshot.plan()
        if lp2_snapshot
        else selection.plan(numeric_entry=numeric_entry)
        if err_selection or numeric_entry
        else life.plan()
        if lifecycle
        else [dict(command=c, effect=diag.EFFECTS[c], status="not_attempted") for c in plan],
    )

    def emit(**message):
        pipe.send_bytes(json.dumps(message, allow_nan=False).encode())

    def check():
        if stop.is_set():
            raise InterruptedError("Diagnostics cancelled; no further commands")
        remaining(deadline)

    def stage(name):
        check()
        result["stage"] = name
        emit(stage=name)

    try:
        with rec._lease(Path(lock_path)):
            try:
                stage("opening")
                wire = factory(target.resource)
                wire.open(timeout=remaining(deadline))
                stage("adapter_identity")
                result["transport"] = dict(wire.metadata)
                if (
                    wire.metadata.get("resource") != target.resource
                    or wire.metadata.get("adapter_identity") != target.adapter_identity
                ):
                    raise ProtocolError("Opened adapter identity changed")
                instrument = Instrument(wire, timeout=min(phy.NATIVE_S, remaining(deadline)))
                stage("instrument_identity")
                observed = instrument.identify()
                result["identification_raw_hex"] = observed.raw.hex()
                if rec._identity(observed) != rec._identity(
                    protocol.identification(target.expected_idn)
                ):
                    raise ProtocolError("Meter identification changed")
                # No SM preflight: reading it could consume error-latch evidence.
                result["status"] = "collecting"

                def before_query(code):
                    stage(code)
                    instrument.timeout = min(phy.NATIVE_S, remaining(deadline))

                def row_ready(row):
                    row["visa_read_status"] = (
                        wire.read_status
                        if row.get("kind") not in ("wait", "command", "poll")
                        and row.get("io_attempted", True)
                        else None
                    )
                    emit(row=row)

                if serial_poll_probe:
                    result["status"], result["serial_poll_assessment"] = polling.collect(
                        instrument,
                        wire,
                        result["queries"],
                        started,
                        deadline=deadline,
                        before_step=before_query,
                        after_step=check,
                        on_row=row_ready,
                        stop=stop,
                    )
                elif acquisition_settings:
                    result["status"], result["acquisition_settings_assessment"] = settings.collect(
                        instrument,
                        result["queries"],
                        started,
                        deadline=deadline,
                        before_step=before_query,
                        after_step=check,
                        on_row=row_ready,
                        raw_reply=lambda: wire.captured_raw,
                    )
                elif lp2_snapshot:
                    result["status"], result["snapshot_assessment"] = snapshot.collect(
                        instrument,
                        result["queries"],
                        started,
                        before_step=before_query,
                        after_step=check,
                        on_row=row_ready,
                        raw_reply=lambda: wire.captured_raw,
                    )
                elif lifecycle or err_selection or numeric_entry:
                    profile = selection if err_selection or numeric_entry else life
                    result["status"], result["lifecycle_assessment"] = profile.collect(
                        instrument,
                        result["queries"],
                        started,
                        before_step=before_query,
                        after_step=check,
                        on_row=row_ready,
                        raw_reply=lambda: wire.captured_raw,
                        **({"numeric_entry": numeric_entry} if profile is selection else {}),
                    )
                else:
                    result["status"] = diag._collect_queries(
                        instrument,
                        result["queries"],
                        started,
                        before_query=before_query,
                        after_query=check,
                        on_row=row_ready,
                        raw_reply=lambda: wire.captured_raw,
                    )
                collection_status = result["status"]
                if collection_status in ("completed", "observation_stop"):
                    result["status"] = "cleanup_failed"
                    stage("free_run")
                    instrument.timeout = min(phy.NATIVE_S, remaining(deadline))
                    instrument.command("TR3")
                    stage("local_return")
                    instrument.timeout = min(phy.NATIVE_S, remaining(deadline))
                    local = instrument.bus("G008")
                    if not isinstance(local, dict) or local.get("status") != "accepted":
                        raise ProtocolError("Local return was not accepted")
                    check()
                    result.update(status=collection_status, local_return=local)
            except Exception as exc:
                if isinstance(exc, InterruptedError):
                    result["status"] = "cancelled"
                result["error"] = f"{type(exc).__name__}: {exc}"[:1000]
                if wire is not None:
                    result["last_transport_raw_hex"] = wire.captured_raw.hex()
            finally:
                if wire is not None:
                    try:
                        # Raw close is permitted after cancellation/failure; no new commands.
                        wire.close()
                        result["transport_closed"] = True
                    except Exception as exc:
                        result.update(
                            status="cleanup_failed",
                            transport_closed=False,
                            close_error=f"{type(exc).__name__}: {exc}"[:1000],
                        )
    except BlockingIOError:
        result.update(status="ownership_busy")
    except Exception as exc:
        result.update(status="worker_failed", error=f"{type(exc).__name__}: {exc}"[:1000])
    try:
        emit(result={k: v for k, v in result.items() if k != "queries"})
    finally:
        pipe.close()


def run_physical(
    output,
    *,
    target,
    prepared,
    equipment,
    confirmed,
    prior_worker_stopped,
    workflow_lock_root,
    include_latched_reads=False,
    lifecycle=False,
    err_selection=False,
    numeric_entry=False,
    numeric_original_settings=None,
    lp2_snapshot=False,
    acquisition_settings=False,
    serial_poll_probe=False,
    original_resolution=None,
    confirmed_reference_control=False,
    confirmed_error_fixtures=False,
    work_s=20.0,
    total_s=25.0,
    cancelled=lambda: False,
    _factory_override=None,
):
    """Explicit hardware entry point; one attempt, no retries or source changes.

    Integration-test factories must declare simulation=True and are labeled as
    injected evidence. Front-panel observations are never inferred from replies.
    """
    if type(target) is not phy.PhysicalTarget:
        raise ValueError("PhysicalTarget required")
    target.validate()
    if (
        confirmed is not True
        or prior_worker_stopped is not True
        or not isinstance(prepared, dict)
        or any(prepared.get(key) is not True for key in PREPARED)
    ):
        raise ValueError("Fresh supervised source-off/idle setup and prior-worker stop required")
    if not isinstance(equipment, dict) or any(
        not isinstance(equipment.get(key), str) or not 1 <= len(equipment[key].strip()) <= 256
        for key in ("meter_serial", "sensor_serial")
    ):
        raise ValueError("Record bounded meter/sensor label identities")
    if type(include_latched_reads) is not bool:
        raise ValueError("Latch reads require an explicit boolean")
    if any(
        type(value) is not bool
        for value in (
            lifecycle,
            err_selection,
            numeric_entry,
            lp2_snapshot,
            acquisition_settings,
            serial_poll_probe,
            confirmed_reference_control,
            confirmed_error_fixtures,
        )
    ):
        raise ValueError("Experiment/fixture selections must be explicit booleans")
    if (
        sum(
            (
                lifecycle,
                err_selection,
                numeric_entry,
                lp2_snapshot,
                acquisition_settings,
                serial_poll_probe,
            )
        )
        > 1
    ):
        raise ValueError("Select only one fixed experiment")
    if serial_poll_probe and include_latched_reads:
        raise ValueError("Serial-poll probe is a separate profile")
    if acquisition_settings and include_latched_reads:
        raise ValueError("Setting checks are a separate profile")
    if lp2_snapshot and include_latched_reads:
        raise ValueError("LP2 snapshot is a separate profile with explicit SM reads")
    experiment = lifecycle or err_selection or numeric_entry
    if experiment and (not confirmed_error_fixtures or include_latched_reads):
        raise ValueError(
            "Fixed experiment requires separate fixed-error confirmation and no passive flag"
        )
    if confirmed_error_fixtures and not experiment:
        raise ValueError("Fixed-error confirmation applies only to a fixed experiment")
    if numeric_entry:
        if (
            not isinstance(numeric_original_settings, dict)
            or set(numeric_original_settings) != {"frequency", "cal_factor"}
            or any(
                not isinstance(value, str)
                or not 1 <= len(value.strip()) <= 80
                or not value.isascii()
                or not value.isprintable()
                for value in numeric_original_settings.values()
            )
        ):
            raise ValueError(
                "Record fresh original FREQ and CAL FAC display values; no automatic restoration"
            )
    elif numeric_original_settings is not None:
        raise ValueError("Original numeric settings apply only to the numeric-entry profile")
    if acquisition_settings:
        if (
            not confirmed_reference_control
            or type(original_resolution) is not int
            or original_resolution not in (1, 2, 3)
        ):
            raise ValueError(
                "Confirm POWER REF control and record original front-panel resolution 1..3"
            )
        if any(prepared.get(key) is not True for key in ("direct_reference_path", "warmed_up")):
            raise ValueError("Prepared warmed-up direct sensor-to-POWER-REF path required")
        if (work_s, total_s) != (60, 65):
            raise ValueError(
                "Setting checks require fixed 60/65-second work/total budgets, including restoration reserve"
            )
    elif original_resolution is not None or confirmed_reference_control:
        raise ValueError("Resolution/reference confirmation apply only to setting checks")
    for name, value, low, high in (("work_s", work_s, 0.25, 60), ("total_s", total_s, 5, 90)):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not low <= value <= high
        ):
            raise ValueError(f"{name} must be finite in {low}..{high}")
    if total_s < work_s + phy.SHUTDOWN_GRACE_S + rec.DISPOSAL_S:
        raise ValueError("Total budget must reserve native finish grace and worker disposal")
    if _factory_override is not None and getattr(_factory_override, "simulation", None) is not True:
        raise ValueError("Only explicitly simulated integration factories may be injected")
    settings_settle_s = (
        getattr(_factory_override, "settings_settle_s", settings.SETTLE_S)
        if _factory_override
        else settings.SETTLE_S
    )
    if acquisition_settings and (
        isinstance(settings_settle_s, bool)
        or not isinstance(settings_settle_s, (int, float))
        or not math.isfinite(settings_settle_s)
        or not 0 <= settings_settle_s <= settings.SETTLE_S
    ):
        raise ValueError("Injected fake settle time must be bounded; physical settle is fixed")
    settings_restore_refresh_s = (
        getattr(_factory_override, "settings_restore_refresh_s", settings.RESTORE_REFRESH_S)
        if _factory_override
        else settings.RESTORE_REFRESH_S
    )
    if acquisition_settings and (
        isinstance(settings_restore_refresh_s, bool)
        or not isinstance(settings_restore_refresh_s, (int, float))
        or not math.isfinite(settings_restore_refresh_s)
        or not 0 <= settings_restore_refresh_s <= settings.RESTORE_REFRESH_S
    ):
        raise ValueError("Injected restore refresh must be bounded; physical refresh is fixed")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    path = output / "diagnostics.json"
    started = time.monotonic()
    deadline, end = started + work_s, started + total_s
    rows = [
        dict(command=c, effect=diag.EFFECTS[c], status="not_attempted")
        for c in diag.BASIC_QUERIES + (diag.LATCHED_QUERIES if include_latched_reads else ())
    ]
    if lifecycle or err_selection or numeric_entry:
        rows = (
            selection.plan(numeric_entry=numeric_entry)
            if err_selection or numeric_entry
            else life.plan()
        )
    if lp2_snapshot:
        rows = snapshot.plan()
    if acquisition_settings:
        rows = settings.plan(original_resolution, settings_settle_s, settings_restore_refresh_s)
    if serial_poll_probe:
        rows = polling.plan()
    result = dict(
        schema="hp437b.diagnostics.physical.v1",
        mode="physical",
        evidence_origin="injected_fake" if _factory_override is not None else "physical_bridge",
        started_utc=datetime.now(UTC).isoformat(),
        status="not_started",
        stage="ownership",
        target=dict(
            resource=target.resource,
            adapter_identity=target.adapter_identity,
            expected_idn_raw_hex=target.expected_idn.hex(),
        ),
        equipment_labels={key: equipment[key] for key in ("meter_serial", "sensor_serial")},
        prepared={key: prepared[key] for key in PREPARED},
        supervised=True,
        physical_identity_verified=False,
        front_panel_confirmation="not_provided",
        health_verdict="Not evaluated; diagnostic replies only",
        include_latched_reads=include_latched_reads,
        lifecycle_profile=lifecycle,
        err_selection_profile=err_selection,
        numeric_entry_profile=numeric_entry,
        lp2_snapshot_profile=lp2_snapshot,
        acquisition_settings_profile=acquisition_settings,
        serial_poll_probe_profile=serial_poll_probe,
        acquisition_settings_plan_version=settings.PLAN_VERSION if acquisition_settings else None,
        original_resolution=original_resolution,
        confirmed_reference_control=confirmed_reference_control,
        settings_prepared={key: prepared[key] for key in ("direct_reference_path", "warmed_up")}
        if acquisition_settings
        else None,
        settings_settle_s=settings_settle_s if acquisition_settings else None,
        settings_restore_refresh_s=settings_restore_refresh_s if acquisition_settings else None,
        numeric_settings_verified=False if numeric_entry else None,
        numeric_original_settings=dict(numeric_original_settings) if numeric_entry else None,
        fixed_error_fixtures_confirmed=confirmed_error_fixtures,
        source_off_basis="Initial operator assertion and SM gate; selected profile controls POWER REF"
        if acquisition_settings
        else "Initial operator assertion and SM gate; no reference-control writes"
        if serial_poll_probe
        else "Fresh operator assertion; no automatic SM preflight or continuous RF proof",
        host=dict(platform=platform.platform(), python=platform.python_version()),
        budgets=dict(
            work_s=work_s,
            total_s=total_s,
            native_call_s=phy.NATIVE_S,
            native_finish_grace_s=phy.SHUTDOWN_GRACE_S,
        ),
        queries=rows,
        worker=None,
        transport_closed=None,
    )
    if serial_poll_probe:
        result["serial_poll_assessment"] = polling.assessment("No worker receipt yet")
    if acquisition_settings:
        result["acquisition_settings_assessment"] = dict(
            stop_reason="No worker restoration receipt yet",
            restoration_attempted=None,
            auto_modes_reference_off_verified=False,
            reference_may_be_on=True,
            resolution_usb_verified=False,
            accepted_full_case=False,
        )
    _atomic_json(path, result)
    root = Path(workflow_lock_root)
    root.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(target.resource.encode()).hexdigest()
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    stop = context.Event()
    process = context.Process(
        target=_worker,
        args=(
            child,
            stop,
            target,
            _factory_override or _factory,
            deadline,
            str(root / (key + ".lock")),
            include_latched_reads,
            lifecycle,
            err_selection,
            numeric_entry,
            lp2_snapshot,
            acquisition_settings,
            original_resolution,
            settings_settle_s,
            settings_restore_refresh_s,
            serial_poll_probe,
        ),
    )
    process.daemon = True
    terminal = None
    worker_result = None
    grace_waited = False

    def receive():
        nonlocal worker_result
        message = json.loads(parent.recv_bytes(MESSAGE_BYTES))
        if "row" in message:
            row = message["row"]
            row["accepted_before_deadline"] = terminal is None and time.monotonic() < deadline
            key = row.get("step_id", row["command"])
            rows[[r.get("step_id", r["command"]) for r in rows].index(key)] = row
        elif "stage" in message:
            result["stage"] = message["stage"]
            for row in rows:
                if row.get("step_id", row["command"]) == message["stage"]:
                    row["status"] = "running"
        else:
            worker_result = message["result"]
        _atomic_json(path, result)

    def finish_native():
        nonlocal grace_waited
        if grace_waited or process.pid is None or worker_result is not None:
            return
        grace_waited = True
        stop.set()
        grace_end = min(end - rec.DISPOSAL_S, time.monotonic() + phy.SHUTDOWN_GRACE_S)
        while worker_result is None and time.monotonic() < grace_end:
            try:
                if parent.poll(min(0.02, max(0, grace_end - time.monotonic()))):
                    receive()
            except (EOFError, OSError, ValueError, KeyError):
                break
        process.join(timeout=max(0, grace_end - time.monotonic()))

    leases = ExitStack()
    try:
        leases.enter_context(rec._lease(root / (key + ".diagnostics.lock")))
        with rec._lease(root / (key + ".lock")):
            pass  # Child holds this shared resource lease through raw close.
        if cancelled():
            terminal = "cancelled"
        else:
            process.start()
            child.close()
            result["status"] = "running"
            while worker_result is None:
                if cancelled():
                    terminal = "cancelled"
                    break
                if time.monotonic() >= deadline:
                    terminal = "deadline"
                    break
                if parent.poll(min(0.02, max(0, deadline - time.monotonic()))):
                    receive()
            if terminal is None and (cancelled() or time.monotonic() >= deadline):
                terminal = "cancelled" if cancelled() else "deadline"
    except BlockingIOError:
        terminal = "ownership_busy"
    except KeyboardInterrupt:
        terminal = "cancelled"
    except Exception as exc:
        terminal = "worker_failed"
        result["supervisor_error"] = f"{type(exc).__name__}: {exc}"[:1000]
    finally:
        try:
            stop.set()
            finish_native()
            if worker_result is not None:
                # Keep parent acceptance flags, never replace them with child copies.
                result.update({k: v for k, v in worker_result.items() if k != "queries"})
            child.close()
            parent.close()
            result["worker"] = rec._dispose(process, end)
            if (
                not result["worker"]["stopped"]
                or result["worker"]["forced"]
                or result["worker"]["exitcode"] not in (None, 0)
            ):
                terminal = terminal or "worker_failed"
            result["status"] = terminal or result["status"]
            for row in rows:
                if row["status"] == "running":
                    row["status"] = "incomplete"
            if result["status"] == "completed" and (
                worker_result is None
                or result["transport_closed"] is not True
                or any(
                    row["status"] != "completed" or not row.get("accepted_before_deadline")
                    for row in rows
                )
            ):
                result["status"] = "worker_failed"
            if "serial_poll_assessment" in result:
                result["serial_poll_assessment"]["accepted_full_case"] = (
                    result["status"] == "completed"
                )
            if "lifecycle_assessment" in result:
                result["lifecycle_assessment"]["accepted_full_case"] = (
                    result["status"] == "completed"
                )
            if "acquisition_settings_assessment" in result:
                result["acquisition_settings_assessment"]["accepted_full_case"] = (
                    result["status"] == "completed"
                )
                accepted_restore = any(
                    row.get("phase") == "restore"
                    and row["command"] == "SM"
                    and row["status"] == "completed"
                    and row.get("accepted_before_deadline")
                    for row in rows
                )
                accepted_reference_on = any(
                    row.get("phase") not in ("baseline", "restore")
                    and row["command"] == "SM"
                    and row["status"] == "completed"
                    and row.get("accepted_before_deadline")
                    and row.get("value", {}).get("reference_on") is True
                    for row in rows
                )
                if (not accepted_restore or not accepted_reference_on) and result[
                    "acquisition_settings_assessment"
                ]["restoration_attempted"]:
                    result["acquisition_settings_assessment"][
                        "auto_modes_reference_off_verified"
                    ] = False
                    result["acquisition_settings_assessment"]["reference_may_be_on"] = True

            if "snapshot_assessment" in result:
                result["snapshot_assessment"]["accepted_full_case"] = (
                    result["status"] == "completed"
                )
            if lp2_snapshot:
                captured = next(
                    (
                        row
                        for row in rows
                        if row["command"] == "LP2"
                        and row["status"] == "completed"
                        and row.get("accepted_before_deadline")
                    ),
                    None,
                )
                if captured is not None:
                    try:
                        raw = protocol.snapshot(bytes.fromhex(captured["raw_hex"]))
                        # Preserve a timely complete capture even if the later acquisition fails.
                        temporary = output / "snapshot.bin.part"
                        with temporary.open("xb") as handle:
                            handle.write(raw)
                        temporary.replace(output / "snapshot.bin")
                        result["snapshot_artifact"] = dict(
                            path="snapshot.bin",
                            length=len(raw),
                            sha256=hashlib.sha256(raw).hexdigest(),
                            source_step_id=captured["step_id"],
                            interpretation="opaque_only; no supported restore or decoded settings",
                        )
                    except Exception as exc:
                        result.update(
                            status="artifact_failed", artifact_error=f"{type(exc).__name__}: {exc}"
                        )
                        if "snapshot_assessment" in result:
                            result["snapshot_assessment"]["accepted_full_case"] = False
            result.update(
                finished_utc=datetime.now(UTC).isoformat(), elapsed_s=time.monotonic() - started
            )
            _atomic_json(path, result)
        finally:
            leases.close()
    return result
