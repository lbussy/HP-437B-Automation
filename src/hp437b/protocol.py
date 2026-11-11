"""Pure encoders/parsers. Sources: docs/inventory/COMMANDS.md and cited manual pages."""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

from .errors import ProtocolError

Unit = Literal["W", "dBm", "%", "dB"]


def number(value: object, low: str, high: str, step: str | None = None) -> str:
    if isinstance(value, bool):
        raise ValueError("Boolean is not a numeric parameter")
    if len(str(value)) > 80:
        raise ValueError("Numeric text exceeds supported precision")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Expected a finite decimal number") from exc
    if not result.is_finite() or not Decimal(low) <= result <= Decimal(high):
        raise ValueError(f"Value must be finite and within {low}..{high}")
    if not -12 <= result.as_tuple().exponent <= 15:
        raise ValueError("Numeric exponent exceeds supported precision")
    if step and result % Decimal(step):
        raise ValueError(f"Value must be a multiple of {step}; choose rounding explicitly")
    return format(result, "f")


def integer(value: object, low: int, high: int) -> int:
    text = number(value, str(low), str(high), "1")
    return int(Decimal(text))


def ascii_payload(raw: bytes) -> str:
    if not isinstance(raw, bytes) or len(raw) > 4096:
        raise ProtocolError("Expected a bounded byte reply")
    try:
        return raw.removesuffix(b"\r\n").decode("ascii")
    except UnicodeDecodeError as exc:
        raise ProtocolError("Non-ASCII reply") from exc


@dataclass(frozen=True)
class Measurement:
    value: Decimal | None
    unit: Unit
    error_code: int | None
    raw: bytes


def measurement(raw: bytes, unit: Unit) -> Measurement:
    if unit not in ("W", "dBm", "%", "dB"):
        raise ValueError("Unknown measurement units")
    text = ascii_payload(raw)
    if not raw.endswith(b"\r\n"):
        raise ProtocolError("Measurement reply requires CR LF")
    error = re.fullmatch(r"\+?9\.00([0-9]{2})E\+40", text)
    if error:
        code = int(error[1])
        if not 1 <= code <= 49:
            raise ProtocolError("Invalid measurement error sentinel code")
        return Measurement(None, unit, code, raw)
    if not re.fullmatch(r"[+-][0-9]\.[0-9]{4}E[+-][0-9]{2}", text):
        raise ProtocolError("Expected signed five-digit measurement mantissa")
    value = Decimal(text)
    if abs(value) >= Decimal("1E40"):
        raise ProtocolError("Reserved/invalid measurement magnitude")
    return Measurement(value, unit, None, raw)


@dataclass(frozen=True)
class Identification:
    manufacturer: str
    model: str
    serial: str
    firmware: str
    raw: bytes


def identification(raw: bytes) -> Identification:
    parts = [part.strip() for part in ascii_payload(raw).split(",")]
    if len(parts) != 4 or parts[0] != "HEWLETT-PACKARD" or parts[1] != "437B":
        raise ProtocolError("Expected a documented HP 437B identification reply")
    if not re.fullmatch(r"[0-9]+\.[0-9]+", parts[3]):
        raise ProtocolError("Invalid firmware version")
    return Identification(*parts, raw)


def byte_value(raw: bytes, maximum: int = 255) -> int:
    text = ascii_payload(raw)
    if not raw.endswith(b"\r\n") or not re.fullmatch(r"[0-9]{3}", text):
        raise ProtocolError("Expected three ASCII digits and CR LF")
    value = int(text)
    if value > maximum:
        raise ProtocolError("Status value out of range")
    return value


@dataclass(frozen=True)
class Status:
    measurement_error: int
    entry_error: int
    operating_mode: int
    range_code: int
    filter_code: int
    logarithmic: bool
    reference_on: bool
    relative: bool
    standby: bool
    group_trigger: int
    limits_on: bool
    limit_result: int
    offset_on: bool
    duty_on: bool
    unit: Unit
    reserved: tuple[str, str, str, str]
    raw: bytes


def status(raw: bytes) -> Status:
    text = ascii_payload(raw)
    if len(text) != 26 or not raw.endswith(b"\r\n"):
        raise ProtocolError("SM requires 26 characters followed by CR LF")
    if not text[:14].isdigit() or not text[16:].isdigit():
        raise ProtocolError("Invalid SM field characters")
    pairs = [int(text[i : i + 2]) for i in range(0, 14, 2)]
    aa, entry, mode, rng, _, filt, _ = pairs
    if not 0 <= aa <= 49 or not 0 <= entry <= 99 or mode not in (0, 6, 8):
        raise ProtocolError("Invalid SM errors or operating mode")
    if rng not in (*range(1, 6), *range(11, 16)) or filt not in range(20):
        raise ProtocolError("Invalid SM range/filter")
    # E F G H I J K L M N O P, positions 14..25; reserved F is literal A.
    if text[14] not in "01" or text[15] != "A":
        raise ProtocolError("Invalid SM log/reserved fields")
    if any(text[i] not in "01" for i in (16, 17, 18, 20, 23, 24)):
        raise ProtocolError("Invalid SM boolean field")
    if text[19] not in "012" or text[21] not in "012" or text[25] not in "0123":
        raise ProtocolError("Invalid SM enum")
    reserved = (text[8:10], text[12:14], text[15], text[22])
    if reserved != ("00", "00", "A", "0"):
        raise ProtocolError("Unknown SM reserved-field layout; preserve raw reply for A06")
    unit: Unit = ("W", "dBm", "%", "dB")[int(text[25])]
    expected = (
        ("dB" if text[14] == "1" else "%")
        if text[17] == "1"
        else ("dBm" if text[14] == "1" else "W")
    )
    if unit != expected:
        raise ProtocolError("SM units conflict with scale/relative flags")
    return Status(
        aa,
        entry,
        mode,
        rng,
        filt,
        text[14] == "1",
        text[16] == "1",
        text[17] == "1",
        text[18] == "1",
        int(text[19]),
        text[20] == "1",
        int(text[21]),
        text[23] == "1",
        text[24] == "1",
        unit,
        reserved,
        raw,
    )


def snapshot(raw: bytes) -> bytes:
    if len(raw) != 60 or not raw.startswith(b"@2"):
        raise ProtocolError("Learn snapshot requires @2 plus 58 opaque binary bytes")
    return raw
