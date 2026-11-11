"""Explicit USBTMC opening in a subprocess: an expired RPC terminates its worker.

The parent never issues a retry or instrument recovery command. Clean local
return uses a project-local USB488 extension; other bus operations stay guarded.
"""

import importlib.metadata
import math
import multiprocessing
import re
import threading
import time
from contextlib import suppress
from typing import Protocol

from .errors import CapabilityUnavailable, OperationTimeout, TransportError
from .usb488 import go_to_local, local_profile, session_interface


class Transport(Protocol):
    capabilities: frozenset[str]

    def write(self, data: bytes, deadline: float) -> None: ...
    def read(self, deadline: float) -> bytes: ...
    def close(self) -> None: ...


def remaining(deadline: float) -> float:
    left = deadline - time.monotonic()
    if not math.isfinite(left) or left <= 0:
        raise OperationTimeout("Operation deadline expired; reconcile instrument state")
    return left


def _worker(pipe, resource: str, max_bytes: int) -> None:
    manager = handle = None
    try:
        import pyvisa
        from pyvisa.constants import StatusCode

        while True:
            operation, payload, milliseconds = pipe.recv()
            try:
                if operation == "open":
                    result = {
                        name: importlib.metadata.version(name)
                        for name in ("PyVISA", "PyVISA-py", "PyUSB")
                    }
                    if result != {"PyVISA": "1.16.2", "PyVISA-py": "0.8.1", "PyUSB": "1.3.1"}:
                        raise RuntimeError(
                            "Transport evidence is pinned to the declared dependency versions"
                        )
                    manager = pyvisa.ResourceManager("@py")
                    handle = manager.open_resource(resource, open_timeout=milliseconds)
                    handle.timeout = milliseconds
                    handle.read_termination = None
                    handle.write_termination = None
                    handle.send_end = True
                    profile = local_profile(session_interface(manager, handle), milliseconds)
                    if profile is not None:
                        result["local_return_profile"] = profile["profile"]
                elif operation == "close":
                    break
                else:
                    handle.timeout = milliseconds
                    if operation == "write":
                        count = handle.write_raw(payload)
                        if count != len(payload):
                            raise RuntimeError("Partial command write; device state is uncertain")
                        result = None
                    elif operation == "read":
                        result, status = handle.visalib.read(handle.session, max_bytes + 1)
                        if len(result) > max_bytes or status != StatusCode.success:
                            raise RuntimeError(
                                "Oversized/incomplete message; preserve stream boundaries"
                            )
                        result = bytes(result)
                    elif operation == "go_to_local":
                        result = go_to_local(session_interface(manager, handle), milliseconds)
                    else:
                        raise RuntimeError("Unknown transport operation")
                pipe.send(("ok", result))
            except Exception as exc:
                pipe.send(("error", f"{type(exc).__name__}: {exc}"))
    except (EOFError, BrokenPipeError):
        pass
    finally:
        if handle is not None:
            with suppress(Exception):
                handle.close()
        if manager is not None:
            with suppress(Exception):
                manager.close()
        pipe.close()


class VisaTransport:
    """No I/O at construction. Call open() explicitly; only @py USB INSTR is supported."""

    capabilities = frozenset({"write", "read", "eom"})

    def __init__(self, resource: str, *, max_bytes: int = 4096):
        if not isinstance(resource, str) or not re.fullmatch(r"USB[0-9]*::[^\s]+::INSTR", resource):
            raise ValueError("Supply an explicit USBTMC USB…::INSTR resource")
        if (
            isinstance(max_bytes, bool)
            or not isinstance(max_bytes, int)
            or not 60 <= max_bytes <= 65536
        ):
            raise ValueError("max_bytes must be 60..65536")
        self.resource = resource
        self.max_bytes = max_bytes
        self._process = self._pipe = None
        self._lock = threading.RLock()
        self.metadata: dict[str, str] = {}
        self.local_return: dict | None = None

    def open(self, timeout: float = 10.0) -> None:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Finite positive open timeout required")
        with self._lock:
            if self._process is not None:
                raise TransportError("Transport is already open")
            self.capabilities = type(self).capabilities
            self.local_return = None
            context = multiprocessing.get_context("spawn")
            parent, child = context.Pipe()
            self._pipe = parent
            self._process = context.Process(
                target=_worker, args=(child, self.resource, self.max_bytes)
            )
            self._process.daemon = True
            deadline = time.monotonic() + timeout
            try:
                self._process.start()
                self.metadata = self._rpc("open", None, deadline)
                self.capabilities = type(self).capabilities
                if "local_return_profile" in self.metadata:
                    self.capabilities |= {"go_to_local"}
                self.local_return = None
            except BaseException:
                self._stop()
                raise
            finally:
                child.close()

    def _stop(self) -> None:
        process, pipe = self._process, self._pipe
        self._process = self._pipe = None
        if pipe is not None:
            pipe.close()
        if process is not None:
            if process.pid is not None:
                if process.is_alive():
                    process.terminate()
                process.join(timeout=0.5)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=0.5)
            process.close()

    def _rpc(self, operation: str, payload: bytes | None, deadline: float):
        with self._lock:
            if self._pipe is None:
                raise TransportError("Explicitly open the transport before I/O")
            try:
                timeout = remaining(deadline)
                self._pipe.send((operation, payload, max(1, math.ceil(timeout * 1000))))
                if not self._pipe.poll(remaining(deadline)):
                    raise OperationTimeout(f"{operation} deadline expired; no automatic retry")
                outcome, result = self._pipe.recv()
                if outcome != "ok":
                    raise TransportError(result)
                remaining(deadline)
                return result
            except BaseException as exc:
                self._stop()
                if isinstance(exc, (EOFError, OSError)):
                    raise TransportError(
                        "VISA worker disconnected; device state uncertain"
                    ) from exc
                raise

    def write(self, data: bytes, deadline: float) -> None:
        if not isinstance(data, bytes) or len(data) > self.max_bytes:
            raise ValueError("Expected a bounded byte command")
        self._rpc("write", data, deadline)

    def read(self, deadline: float) -> bytes:
        return self._rpc("read", None, deadline)

    def bus(self, operation: str, deadline: float):
        raise CapabilityUnavailable(f"{operation}: A09, PyVISA-py 0.8.1 USB bus control deferred")

    def return_local(self, deadline: float):
        if "go_to_local" not in self.capabilities:
            raise CapabilityUnavailable("No negotiated USB488 local-return profile")
        self.local_return = {"status": "requested"}
        try:
            self.local_return = self._rpc("go_to_local", None, deadline)
            return self.local_return
        except BaseException as exc:
            self.local_return = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
            raise

    def close(self) -> None:
        with self._lock:
            if self._pipe is not None:
                with suppress(Exception):
                    self._pipe.send(("close", None, 100))
                self._process.join(timeout=0.2)
            self._stop()
