"""Explicit supervised USBGpib bridge; no normal logger or automatic recovery hook."""

import hashlib
import importlib.metadata
import math
import platform
import re
import time
from dataclasses import dataclass
from pathlib import Path

from . import reconciliation as rec
from .errors import CapabilityUnavailable, ProtocolError, TransportError
from .transport import remaining
from .usb488 import go_to_local, local_profile, session_interface

NATIVE_S = 2.0
SHUTDOWN_GRACE_S = NATIVE_S + 1.0
PINS = {"PyVISA": "1.16.2", "PyVISA-py": "0.8.1", "PyUSB": "1.3.1"}
PREPARED = (
    "power_ref_off",
    "direct_reference_path",
    "warmed_up",
    "other_control_apps_closed",
    "operator_available",
)


@dataclass(frozen=True)
class PhysicalTarget:
    resource: str
    adapter_identity: str
    expected_idn: bytes

    def validate(self):
        rec.Target("FAKE::identity-validation", self.adapter_identity, self.expected_idn).validate()
        parts = self.resource.split("::") if isinstance(self.resource, str) else []
        if len(parts) != 6 or parts[0] != "USB0" or parts[4:] != ["0", "INSTR"]:
            raise ValueError("Explicit USB0 vendor/product/serial/interface-zero resource required")
        if not all(re.fullmatch(r"(?:0[xX][0-9A-Fa-f]+|[0-9]+)", part) for part in parts[1:3]):
            raise ValueError("Invalid USB vendor/product IDs")
        ids = [int(part, 16 if part.lower().startswith("0x") else 10) for part in parts[1:3]]
        if (
            ids != [0x03EB, 0x2065]
            or parts[3] != self.adapter_identity
            or any(c.isspace() for c in self.resource)
        ):
            raise ValueError("Only the explicitly named 03eb:2065 adapter is supported")


def _matching_usb(serial):
    """Descriptor preflight before VISA asserts REN; never select a fallback device."""
    import usb.core
    import usb.util

    devices = []
    matches = []
    try:
        devices = list(usb.core.find(find_all=True, idVendor=0x03EB, idProduct=0x2065))
        for device in devices:
            if device.serial_number == serial:
                if device.manufacturer != "XyphroLabs" or device.product != "GpibUsb":
                    raise ProtocolError("USB descriptor profile changed")
                interfaces = list(device.get_active_configuration())
                if len(interfaces) != 1 or (
                    interfaces[0].bInterfaceNumber,
                    interfaces[0].bInterfaceClass,
                    interfaces[0].bInterfaceSubClass,
                    interfaces[0].bInterfaceProtocol,
                ) != (0, 0xFE, 3, 1):
                    raise ProtocolError("USB488 interface profile changed")
                matches.append(device)
        if not matches:
            raise FileNotFoundError("Selected adapter is absent; no fallback selected")
        if len(matches) != 1:
            raise ProtocolError("Ambiguous USB identity; multiple matching adapters")
    except usb.core.USBError as exc:
        if exc.errno == 13:
            raise PermissionError("USB access denied") from exc
        raise
    finally:
        for device in devices:
            usb.util.dispose_resources(device)


class _Bridge:
    """Synchronous pinned VISA inside the supervisor child, with no nested workers."""

    capabilities = frozenset({"read", "write", "eom"})

    def __init__(self, resource):
        self.resource = resource
        self.manager = self.handle = None
        self.metadata = {}

    def _ms(self, deadline):
        return max(1, math.ceil(min(NATIVE_S, remaining(deadline)) * 1000))

    def open(self, timeout):
        import pyvisa

        versions = {name: importlib.metadata.version(name) for name in PINS}
        if versions != PINS:
            raise CapabilityUnavailable(
                "Physical reconciliation requires the pinned backend versions"
            )
        serial = self.resource.split("::")[3]
        deadline = time.monotonic() + timeout
        _matching_usb(serial)
        self.manager = pyvisa.ResourceManager("@py")
        self.handle = self.manager.open_resource(self.resource, open_timeout=self._ms(deadline))
        self.handle.timeout = self._ms(deadline)
        self.handle.read_termination = self.handle.write_termination = None
        self.handle.send_end = True
        interface = session_interface(self.manager, self.handle)
        device = getattr(interface, "usb_dev", None)
        if (
            getattr(device, "idVendor", None),
            getattr(device, "idProduct", None),
            getattr(device, "serial_number", None),
        ) != (0x03EB, 0x2065, serial):
            raise ProtocolError("Opened USB identity differs from selected adapter")
        profile = local_profile(interface, self._ms(deadline))
        if profile is None:
            raise CapabilityUnavailable("Qualified local-return profile is required")
        self.capabilities = type(self).capabilities | {"go_to_local"}
        self.metadata = {
            "resource": self.resource,
            "adapter_identity": serial,
            "versions": versions,
            "local_return_profile": profile["profile"],
            "native_timeout_s": NATIVE_S,
        }

    def write(self, data, deadline):
        self.handle.timeout = self._ms(deadline)
        if self.handle.write_raw(data) != len(data):
            raise TransportError("Partial reconciliation write; no retry permitted")

    def read(self, deadline):
        from pyvisa.constants import StatusCode

        self.handle.timeout = self._ms(deadline)
        raw, status = self.handle.visalib.read(self.handle.session, 4097)
        if len(raw) > 4096 or status != StatusCode.success:
            raise ProtocolError("Incomplete/oversized reconciliation reply")
        return bytes(raw)

    def return_local(self, deadline):
        return go_to_local(session_interface(self.manager, self.handle), self._ms(deadline))

    def close(self):
        try:
            if self.handle is not None:
                self.handle.close()
        finally:
            if self.manager is not None:
                self.manager.close()


@dataclass(frozen=True)
class _PhysicalFactory:
    def __call__(self, resource, attempt):
        return _Bridge(resource)


def run_physical(
    output,
    *,
    target,
    prepared,
    equipment,
    confirmed,
    prior_worker_stopped,
    workflow_lock_root,
    failed_run_id,
    policy=None,
    cancelled=lambda: False,
    _factory=None,
):
    """Separate supervised entry point. Calling this explicitly can open hardware.

    _factory exists for offline integration tests only; injected evidence is labeled.
    Neither this bridge nor its receipt establishes continuous RF state or repairs
    an already-wedged device. No reference switching, reset, retry of a sample, or
    workflow resumption is included.
    """
    if type(target) is not PhysicalTarget:
        raise ValueError("PhysicalTarget required")
    target.validate()
    if confirmed is not True or any(prepared.get(key) is not True for key in PREPARED):
        raise ValueError("Fresh supervised/reference-off preparation must be confirmed")
    if not isinstance(equipment, dict) or any(
        not isinstance(equipment.get(key), str) or not equipment[key].strip()
        for key in ("meter_serial", "sensor_serial")
    ):
        raise ValueError("Record meter and sensor label identities")
    policy = (
        policy
        if policy is not None
        else rec.Policy(max_attempts=1, total_s=60, attempt_s=30, retry_delay_s=0)
    )
    policy.validate()
    if policy.attempt_s < 6 or policy.total_s < 10:
        raise ValueError(
            "Physical budgets require at least 6 seconds per attempt and 10 seconds total"
        )
    if _factory is not None and getattr(_factory, "simulation", None) is not True:
        raise ValueError("Only an explicitly simulated integration-test factory may be injected")
    root = Path(workflow_lock_root)
    root.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(target.resource.encode()).hexdigest()
    return rec._run(
        output,
        target=target,
        factory=_factory or _PhysicalFactory(),
        lock_root=root / "reconciliation",
        worker_lock_path=root / (key + ".lock"),
        failed_run_id=failed_run_id,
        prior_worker_stopped=prior_worker_stopped,
        policy=policy,
        cancelled=cancelled,
        mode="physical",
        shutdown_grace_s=SHUTDOWN_GRACE_S,
        context=dict(
            evidence_origin="injected_fake" if _factory is not None else "physical_bridge",
            supervised=True,
            equipment_labels=equipment,
            prepared=prepared,
            host=platform.platform(),
            native_timeout_s=NATIVE_S,
            shutdown_grace_s=SHUTDOWN_GRACE_S,
        ),
    )
