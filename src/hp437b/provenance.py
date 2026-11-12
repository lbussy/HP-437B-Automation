"""Versioned, hardware-free run/DUT/equipment provenance and WF-01 import.

Hashes bind records to source bytes; they do not authenticate measurements or
certificates. Import never executes bundle code, follows certificate paths,
contacts equipment, or edits the source bundle.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path, PurePosixPath

SCHEMA = "hp437b.provenance.v1"
BASES = {"supplied", "observed", "derived", "unknown"}
MAX_FILE = 32 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024
MAX_JSON = 16 * 1024 * 1024


class ProvenanceError(ValueError):
    """Invalid, inconsistent, incomplete, or changed provenance evidence."""


def require(condition, message):
    if not condition:
        raise ProvenanceError(message)


def _json(data):
    require(len(data) <= MAX_JSON, "JSON input exceeds 16 MiB")

    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def constant(value):
        raise ProvenanceError(f"Non-finite JSON number: {value}")

    try:
        value = json.loads(data, object_pairs_hook=pairs, parse_constant=constant)
        json.dumps(value, allow_nan=False)
        return value
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ProvenanceError("Invalid bounded JSON") from exc


def _keys(value, expected):
    require(
        isinstance(value, dict) and set(value) == set(expected),
        f"Expected fields: {', '.join(expected)}",
    )


def _text(value):
    require(isinstance(value, str) and bool(value.strip()), "Expected nonempty text")


def _timestamp(value):
    if value is not None:
        try:
            parsed = datetime.fromisoformat(value)
            require(parsed.utcoffset() is not None, "Timestamp requires timezone")
        except (TypeError, ValueError) as exc:
            raise ProvenanceError("Expected timezone-aware ISO timestamp") from exc


def _json_value(value, depth=0):
    require(depth <= 64, "Fact nesting exceeds 64 levels")
    if isinstance(value, dict):
        require(all(isinstance(key, str) for key in value), "JSON object keys must be strings")
        for child in value.values():
            _json_value(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _json_value(child, depth + 1)
    else:
        require(
            type(value) in (str, int, float, bool, type(None)),
            "Facts require native JSON value types",
        )


def fact(value=None, *, basis="unknown", refs=(), observed_at=None, note=""):
    """A JSON value with explicit epistemic basis and evidence references."""
    result = {
        "value": value,
        "basis": basis,
        "refs": list(refs),
        "observed_at": observed_at,
        "note": note,
    }
    _validate_fact(result)
    return result


def _validate_fact(item):
    _keys(item, ("value", "basis", "refs", "observed_at", "note"))
    require(isinstance(item["basis"], str) and item["basis"] in BASES, "Unknown fact basis")
    require(
        isinstance(item["note"], str) and isinstance(item["refs"], list), "Invalid fact annotation"
    )
    _timestamp(item["observed_at"])
    if item["basis"] == "unknown":
        require(
            item["value"] is None and bool(item["note"].strip()),
            "Unknown fact requires null value and reason",
        )
    else:
        require(
            item["value"] is not None and bool(item["refs"]),
            "Known/derived fact requires a value and evidence",
        )
    for ref in item["refs"]:
        _keys(ref, ("evidence_id", "pointer"))
        _text(ref["evidence_id"])
        require(
            isinstance(ref["pointer"], str)
            and (not ref["pointer"] or ref["pointer"].startswith("/"))
            and not re.search(r"~(?![01])", ref["pointer"]),
            "Invalid JSON pointer",
        )
    _json_value(item["value"])
    try:
        encoded = json.dumps(item, allow_nan=False).encode()
    except (ValueError, TypeError, RecursionError) as exc:
        raise ProvenanceError("Facts must be finite JSON values") from exc
    require(len(encoded) <= MAX_JSON, "Fact is too large")


def equipment(equipment_id, role, facts):
    result = {"equipment_id": equipment_id, "role": role, "facts": facts}
    _entity(result, "equipment_id", ("equipment_id", "role", "facts"))
    _text(role)
    return result


def dut(dut_id, kind, equipment_refs, facts):
    result = {
        "dut_id": dut_id,
        "kind": kind,
        "equipment_refs": list(equipment_refs),
        "facts": facts,
    }
    _entity(result, "dut_id", ("dut_id", "kind", "equipment_refs", "facts"))
    _text(kind)
    return result


def record(run_id, mode, workflow_id, facts, subject, devices, evidence):
    result = {
        "schema": SCHEMA,
        "run": {"run_id": run_id, "mode": mode, "workflow_id": workflow_id, "facts": facts},
        "dut": subject,
        "equipment": list(devices),
        "evidence": list(evidence),
    }
    validate(result)
    return result


def _entity(value, id_key, keys):
    _keys(value, keys)
    _text(value[id_key])
    require(isinstance(value["facts"], dict), "Entity facts must be a mapping")
    for name, item in value["facts"].items():
        _text(name)
        _validate_fact(item)


def _relative(name):
    require(
        isinstance(name, str) and name and "\\" not in name and all(ord(c) >= 32 for c in name),
        "Expected relative POSIX path",
    )
    path = PurePosixPath(name)
    require(
        not path.is_absolute() and all(part not in ("", ".", "..") for part in name.split("/")),
        "Unsafe evidence path",
    )
    return path


def validate(value):
    """Validate reusable records, identities, finite values, and reference joins."""
    _keys(value, ("schema", "run", "dut", "equipment", "evidence"))
    require(value["schema"] == SCHEMA, "Unsupported provenance version")
    run = value["run"]
    _entity(run, "run_id", ("run_id", "mode", "workflow_id", "facts"))
    require(
        isinstance(run["mode"], str) and run["mode"] in ("synthetic", "physical"),
        "Invalid declared run mode",
    )
    _text(run["workflow_id"])
    require(
        isinstance(value["equipment"], list) and isinstance(value["evidence"], list),
        "Expected equipment/evidence lists",
    )
    ids = set()
    for item in value["equipment"]:
        _entity(item, "equipment_id", ("equipment_id", "role", "facts"))
        _text(item["role"])
        require(item["equipment_id"] not in ids, "Duplicate equipment identity")
        ids.add(item["equipment_id"])
    subject = value["dut"]
    _entity(subject, "dut_id", ("dut_id", "kind", "equipment_refs", "facts"))
    _text(subject["kind"])
    require(
        isinstance(subject["equipment_refs"], list)
        and all(isinstance(ref, str) and ref for ref in subject["equipment_refs"]),
        "Invalid DUT references",
    )
    require(
        isinstance(subject["equipment_refs"], list)
        and len(set(subject["equipment_refs"])) == len(subject["equipment_refs"]),
        "Invalid DUT equipment references",
    )
    require(all(ref in ids for ref in subject["equipment_refs"]), "DUT refers to missing equipment")
    evidence_ids, names = set(), set()
    for item in value["evidence"]:
        _keys(item, ("evidence_id", "path", "sha256", "bytes"))
        _text(item["evidence_id"])
        _relative(item["path"])
        require(
            item["evidence_id"] not in evidence_ids and item["path"] not in names,
            "Duplicate evidence",
        )
        evidence_ids.add(item["evidence_id"])
        names.add(item["path"])
        require(
            isinstance(item["sha256"], str) and re.fullmatch(r"[a-f0-9]{64}", item["sha256"]),
            "Invalid evidence digest",
        )
        require(
            type(item["bytes"]) is int and 0 <= item["bytes"] <= MAX_FILE, "Invalid evidence size"
        )
    for entity in (run, subject, *value["equipment"]):
        for item in entity["facts"].values():
            require(
                all(ref["evidence_id"] in evidence_ids for ref in item["refs"]),
                "Fact refers to missing evidence",
            )


class Bundle:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.entries = {}
        self.total = 0

    def read(self, name, expected=None):
        _relative(name)
        path = self.root
        for part in name.split("/"):
            path = path / part
            require(not path.is_symlink(), "Symlink evidence is unsupported")
        require(
            path.is_file() and path.stat().st_size <= MAX_FILE,
            f"Missing/oversized evidence: {name}",
        )
        with path.open("rb") as handle:
            data = handle.read(MAX_FILE + 1)
        require(len(data) <= MAX_FILE, "Evidence grew beyond import limit")
        entry = {
            "evidence_id": name,
            "path": name,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        if expected is not None:
            require(
                entry["bytes"] == expected["bytes"] and entry["sha256"] == expected["sha256"],
                f"Evidence mismatch: {name}",
            )
        if name not in self.entries:
            self.total += len(data)
            require(
                self.total <= MAX_TOTAL and len(self.entries) < 4096, "Bundle exceeds import budget"
            )
        else:
            require(self.entries[name] == entry, f"Evidence changed during read: {name}")
        self.entries[name] = entry
        return data

    def json(self, name):
        require(name in self.entries, f"Uninventoried JSON cannot become evidence: {name}")
        return _json(self.read(name, self.entries[name]))

    def inventory(self, name, mode):
        item = _json(self.read(name))
        require(isinstance(item, dict), "Artifact inventory must be an object")
        require(item.get("mode") == mode, f"Inventory mode mismatch: {name}")
        require(isinstance(item, dict), "Artifact inventory must be an object")
        entries = item.get("artifacts")
        require(isinstance(entries, dict) and len(entries) <= 4096, "Invalid artifact inventory")
        for path, expected in entries.items():
            _relative(path)
            require(
                isinstance(expected, dict)
                and type(expected.get("bytes")) is int
                and isinstance(expected.get("sha256"), str),
                "Invalid inventory entry",
            )
            require(path != name, "Inventory must not hash itself")
            self.read(path, expected)
        return item


def _pointer(value, pointer):
    for part in pointer.split("/")[1:] if pointer else []:
        part = part.replace("~1", "/").replace("~0", "~")
        try:
            if isinstance(value, list):
                require(bool(re.fullmatch(r"0|[1-9][0-9]*", part)), "Invalid array pointer")
                value = value[int(part)]
            else:
                value = value[part]
        except (TypeError, KeyError, IndexError) as exc:
            raise ProvenanceError(f"Unresolved evidence pointer: {pointer}") from exc
    return value


def verify(value, source_bundle):
    """Revalidate evidence bytes and all nonempty JSON pointers, without I/O to equipment."""
    validate(value)
    bundle = Bundle(source_bundle)
    by_id = {item["evidence_id"]: item for item in value["evidence"]}
    for item in value["evidence"]:
        bundle.read(item["path"], item)
    for entity in (value["run"], value["dut"], *value["equipment"]):
        for item in entity["facts"].values():
            targets = []
            all_json = True
            for ref in item["refs"]:
                path = by_id[ref["evidence_id"]]["path"]
                if path.endswith(".json"):
                    targets.append(_pointer(bundle.json(path), ref["pointer"]))
                elif ref["pointer"]:
                    raise ProvenanceError("Non-JSON evidence cannot have a JSON pointer")
                else:
                    all_json = False
            if item["basis"] in ("supplied", "observed") and targets and all_json:
                require(
                    json.dumps(item["value"], sort_keys=True, allow_nan=False)
                    == json.dumps(targets, sort_keys=True, allow_nan=False)
                    or (
                        len(targets) == 1
                        and json.dumps(item["value"], sort_keys=True, allow_nan=False)
                        == json.dumps(targets[0], sort_keys=True, allow_nan=False)
                    ),
                    "Copied fact disagrees with its JSON evidence",
                )
    return True


def _identity(mode, role, key):
    return "equipment:" + hashlib.sha256(f"wf01:{mode}:{role}:{key}".encode()).hexdigest()[:32]


def import_wf01(source_bundle):
    """Read a sealed WF-01 success/failure bundle into the reusable v1 model."""
    bundle = Bundle(source_bundle)
    raw = bundle.read("workflow.json")
    workflow = _json(raw)
    require(isinstance(workflow, dict), "Workflow manifest must be an object")
    mode = workflow.get("mode")
    require(
        mode in ("synthetic", "physical") and workflow.get("simulation") is (mode == "synthetic"),
        "Workflow mode/simulation mismatch",
    )
    require(workflow.get("workflow_id") == "power-reference-v1", "Unsupported workflow adapter")
    inventory = bundle.inventory("artifacts.json", mode)
    require("workflow.json" in inventory["artifacts"], "Inventory must bind workflow manifest")
    # Separate post-capture operator attestation must be hash-linked to this bundle.
    supplementary = bundle.root / "completion-artifacts.json"
    if supplementary.exists():
        extra = bundle.inventory("completion-artifacts.json", mode)
        require(
            extra.get("base_inventory_sha256") == bundle.entries["artifacts.json"]["sha256"],
            "Supplement belongs to another capture inventory",
        )
    sessions = workflow.get("sessions", [])
    require(
        isinstance(sessions, list) and all(isinstance(item, dict) for item in sessions),
        "Invalid session records",
    )
    require(
        all(
            item.get("identity") is None or isinstance(item["identity"], dict) for item in sessions
        ),
        "Invalid instrument identity record",
    )
    stages = workflow.get("stages", {})
    require(
        isinstance(stages, dict) and all(isinstance(item, dict) for item in stages.values()),
        "Invalid stage outcomes",
    )
    for stage in ("S10", "S30", "S40", "S60"):
        csv_path = f"stages/{stage}.csv"
        metadata_path = csv_path + ".session.json"
        if stages.get(stage, {}).get("status") == "completed" or csv_path in bundle.entries:
            require(
                csv_path in bundle.entries and metadata_path in bundle.entries,
                "Capture stage requires inventoried CSV/session pair",
            )
    if "operator-confirmation.json" in bundle.entries:
        confirmation = bundle.json("operator-confirmation.json")
        require(isinstance(confirmation, dict), "Invalid operator attestation")
        require(
            confirmation.get("mode") == mode
            and confirmation.get("run_id") == workflow.get("run_id"),
            "Operator attestation mode/run mismatch",
        )
        _timestamp(confirmation.get("confirmed_utc"))
    for name in list(bundle.entries):
        if name.endswith(".csv.session.json"):
            session = bundle.json(name)
            require(
                isinstance(session, dict) and isinstance(session.get("context", {}), dict),
                "Invalid capture session metadata",
            )
            require(
                session.get("instrument") is None or isinstance(session["instrument"], dict),
                "Invalid session identity",
            )
            require(
                session.get("simulation") is (mode == "synthetic"),
                "Session mode disagrees with workflow",
            )
    for name in bundle.entries:
        if name.endswith(".csv.session.json"):
            session_run = bundle.json(name).get("context", {}).get("workflow_run_id")
            require(
                session_run is None or session_run == workflow.get("run_id"),
                "Session belongs to another workflow run",
            )
    for timestamp_key in ("started_utc", "finished_utc"):
        _timestamp(workflow.get(timestamp_key))
    run_id = workflow.get("run_id") or "wf01-import:" + hashlib.sha256(raw).hexdigest()[:32]

    def ref(name, pointer=""):
        require(name in bundle.entries, f"Evidence is unavailable: {name}")
        return {"evidence_id": name, "pointer": pointer}

    def copied(name, pointer, basis="supplied", note=""):
        source = bundle.json(name)
        try:
            value = _pointer(source, pointer)
        except ProvenanceError:
            return fact(note="Not recorded in the source bundle")
        if value is None or (isinstance(value, str) and not value.strip()):
            return fact(
                refs=[ref(name, pointer)],
                note=note or "Source records null; not independently established",
            )
        return fact(value, basis=basis, refs=[ref(name, pointer)], note=note)

    supplied = workflow.get("setup", workflow.get("provenance", {}))
    require(isinstance(supplied, dict), "Invalid source equipment setup")
    setup_pointer = "/setup" if "setup" in workflow else "/provenance"
    label_fields = {
        "meter": "meter_serial" if "setup" in workflow else "meter",
        "sensor": "sensor_serial" if "setup" in workflow else "sensor",
    }
    devices = []
    for role, field in label_fields.items():
        label = supplied.get(field)
        require(
            label is None or isinstance(label, str), "Supplied label identity must be text or null"
        )
        identifier = _identity(mode, role, label or "run:" + run_id)
        facts = {
            "label_serial": copied(
                "workflow.json",
                setup_pointer + "/" + field,
                note="Supplied identity; not promoted to an instrument-returned serial",
            )
        }
        if role == "meter":
            identities = []
            refs = []
            for index, session in enumerate(workflow.get("sessions", [])):
                if session.get("identity"):
                    identities.append(session["identity"])
                    refs.append(ref("workflow.json", f"/sessions/{index}/identity"))
            if not identities:
                for name in bundle.entries:
                    if name.endswith(".csv.session.json") and bundle.json(name).get("instrument"):
                        identities.append(bundle.json(name)["instrument"])
                        refs.append(ref(name, "/instrument"))
            facts["reported_identifications"] = (
                fact(
                    identities,
                    basis="observed",
                    refs=refs,
                    note="Recorded instrument replies; synthetic replies remain synthetic by run mode. Conflicting replies are retained.",
                )
                if identities
                else fact(note="No instrument identity was captured")
            )
            nonblank = [item.get("serial") for item in identities if item.get("serial")]
            facts["reported_serial"] = (
                fact(
                    nonblank,
                    basis="derived",
                    refs=refs,
                    note="Nonblank serials from recorded replies; not the supplied label identity",
                )
                if nonblank
                else fact(
                    refs=refs,
                    note="No nonblank instrument-reported serial; label identity remains supplied",
                )
            )
        facts["known_issues"] = fact(
            note="Source issues are unscoped; retained in run.known_equipment_issues without assigning them to this device"
        )
        facts["calibration_references"] = fact(
            note="Source certificate list is unscoped; retained at run level without inventing per-device applicability or certificate verification"
        )
        if role == "sensor":
            for field in (
                "reference_cal_factor_percent",
                "active_measurement_cal_factor_percent",
                "zero_cal_history",
            ):
                facts[field] = copied(
                    "workflow.json",
                    setup_pointer + "/" + field,
                    note="Retains original historical annotation; import time is not observation time",
                )
        devices.append(equipment(identifier, role, facts))
    adapter_id = (
        supplied.get("adapter", {}).get("inventory_id")
        if isinstance(supplied.get("adapter"), dict)
        else None
    )
    devices.append(
        equipment(
            _identity(mode, "adapter", adapter_id or "run:" + run_id),
            "adapter",
            {
                "supplied_details": copied("workflow.json", setup_pointer + "/adapter"),
                "observed_preparation": copied(
                    "workflow.json",
                    "/adapter_target_preparation",
                    "observed",
                    "Recorded adapter query and volatile preparation, not a firmware binary hash",
                ),
                "resource": copied(
                    "workflow.json",
                    "/resource",
                    note="USB resource is a transport alias; not a permanent hardware identity",
                ),
                "identity_limit": fact(
                    "run-scoped unless an explicit inventory_id is supplied",
                    basis="derived",
                    refs=[ref("workflow.json")],
                    note="No adapter identity merge is inferred from firmware or instrument-named USB serials",
                ),
            },
        )
    )
    hosts = []
    host_refs = []
    for name in bundle.entries:
        if name.endswith(".csv.session.json") and bundle.json(name).get("host"):
            hosts.append(bundle.json(name)["host"])
            host_refs.append(ref(name, "/host"))
    devices.append(
        equipment(
            _identity(mode, "host", "run:" + run_id),
            "host",
            {
                "recorded_platforms": fact(
                    hosts,
                    basis="observed",
                    refs=host_refs,
                    note="Captured host strings; importer performs no current-host discovery",
                )
                if hosts
                else fact(note="No host platform recorded"),
                "software": copied(
                    "workflow.json",
                    "/software",
                    "observed",
                    "Producer-recorded software identity; hashes do not authenticate it",
                ),
            },
        )
    )
    subject = dut(
        "dut:" + run_id,
        "reference_signal",
        [devices[0]["equipment_id"]],
        {
            "description": fact(
                "Internal POWER REF signal measured by the connected sensor",
                basis="derived",
                refs=[ref("workflow.json", "/workflow_id")],
                note="WF-01 adapter semantics; this is not evidence of an external radio/DUT",
            ),
            "declared_signal": copied("workflow.json", setup_pointer + "/signal"),
            "measurement_criteria": fact(
                note="No independently supplied DUT accuracy/compliance criteria in WF-01"
            ),
        },
    )
    facts = {
        field: copied("workflow.json", "/" + source, basis)
        for field, source, basis in (
            ("source_run_id", "run_id", "observed"),
            ("execution_status", "status", "observed"),
            ("started_utc", "started_utc", "observed"),
            ("finished_utc", "finished_utc", "observed"),
            ("configuration", "profile", "supplied"),
            ("software", "software", "observed"),
            ("capture_final_state", "final_state", "observed"),
            ("stage_outcomes", "stages", "observed"),
        )
    }
    # Add the supplied operator only when recorded, preserving legacy imports byte-for-byte.
    operator_pointer = (
        "/operator"
        if "operator" in workflow
        else "/setup/operator"
        if isinstance(workflow.get("setup"), dict) and "operator" in workflow["setup"]
        else None
    )
    if operator_pointer:
        facts["operator"] = copied(
            "workflow.json",
            operator_pointer,
            "supplied",
            "Supplied human operator identity; not independently verified",
        )
    facts["run_identity_basis"] = fact(
        "original run_id"
        if workflow.get("run_id")
        else "derived from source workflow SHA-256; legacy bundle has no original run_id",
        basis="derived",
        refs=[ref("workflow.json")],
        note="Use original run_id when nonempty; otherwise derive local import ID from workflow bytes",
    )
    facts["source_integrity"] = fact(
        "declared source inventories and known mode flags verified",
        basis="derived",
        refs=[ref("artifacts.json")],
        note="Byte-integrity verification, not authenticity, calibration, data-quality, or measurement acceptance",
    )
    facts["supplied_test_intent"] = copied("workflow.json", "/test_purpose")
    facts["workflow_test_intent"] = fact(
        "POWER REF measurement and repeatability",
        basis="derived",
        refs=[ref("workflow.json", "/workflow_id")],
        note="Intent of the recognized WF-01 definition, not an invented user-supplied DUT purpose",
    )
    facts["known_equipment_issues"] = copied(
        "workflow.json",
        setup_pointer + ("/known_issues" if "setup" in workflow else "/known_equipment_issues"),
        note="Run-level supplied issues are not silently attached to every equipment entity",
    )
    facts["calibration_references"] = copied(
        "workflow.json",
        setup_pointer
        + ("/calibration_references" if "setup" in workflow else "/calibration_records"),
        note="Unscoped references/hashes only; importer never follows certificate paths or declares calibration passing",
    )
    facts["signal_path"] = copied("workflow.json", setup_pointer + "/signal")
    facts["prepared_setup"] = copied(
        "workflow.json",
        setup_pointer,
        note="Original supplied setup/provenance, including annotation dates and unknowns; not a fresh preparation check",
    )
    facts["operator_confirmation"] = (
        copied(
            "operator-confirmation.json",
            "",
            "supplied",
            "Post-capture owner attestation remains separate from the captured protocol state",
        )
        if "operator-confirmation.json" in bundle.entries
        else fact(note="No hash-linked operator attestation in this bundle")
    )
    result = record(
        run_id, mode, workflow["workflow_id"], facts, subject, devices, bundle.entries.values()
    )
    verify(result, source_bundle)
    return result


def equipment_history(records):
    """Group stable local equipment IDs without overwriting conflicting assertions."""
    result = {}
    for item in records:
        validate(item)
        for device in item["equipment"]:
            assertion = {
                "run_id": item["run"]["run_id"],
                "mode": item["run"]["mode"],
                "role": device["role"],
                "facts": device["facts"],
                "evidence": item["evidence"],
            }
            history = result.setdefault(device["equipment_id"], [])
            if assertion not in history:
                history.append(assertion)
    return result


def load(path):
    value = _json(Path(path).read_bytes())
    validate(value)
    return value


def write(path, value):
    validate(value)
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def sidecar_path(bundle):
    bundle = Path(bundle)
    return bundle.with_name(bundle.name + ".provenance")


def export_wf01(source_bundle, output):
    """Create a separately hashed additive record; never edit or overwrite source."""
    source = Path(source_bundle).resolve()
    destination = Path(output).absolute()
    require(not destination.exists(), "Provenance output already exists")
    require(
        not destination.resolve().is_relative_to(source),
        "Provenance export must be outside the source bundle",
    )
    value = import_wf01(source)
    # The source's immutable inventories never refer to this new directory.
    destination.mkdir()
    try:
        files = {"provenance.json": value, "equipment-history.json": equipment_history([value])}
        digests = {}
        for name, content in files.items():
            data = (json.dumps(content, indent=2, allow_nan=False) + "\n").encode()
            with (destination / name).open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            digests[name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        manifest = {
            "schema": "hp437b.provenance-export.v1",
            "generator": {
                "module": "hp437b.provenance",
                "module_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            },
            "mode": value["run"]["mode"],
            "artifacts": digests,
        }
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=destination, delete=False
            ) as handle:
                temporary = Path(handle.name)
                json.dump(manifest, handle, indent=2, allow_nan=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination / "artifacts.json")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    except BaseException:
        # Keep partial output as diagnostics, but never a successful export manifest.
        raise
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = export_wf01(args.bundle, args.output)
    except (ProvenanceError, OSError) as exc:
        print(f"PROV-01 export failed: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "schema": result["schema"],
                "run_id": result["run"]["run_id"],
                "mode": result["run"]["mode"],
                "equipment_records": len(result["equipment"]),
                "output": str(args.output),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
