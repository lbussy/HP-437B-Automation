from decimal import Decimal

import pytest

from hp437b import protocol
from hp437b.errors import ProtocolError


def test_signed_power_and_error_sentinel():
    value = protocol.measurement(b"-3.0123E+01\r\n", "dBm")
    assert value.value == Decimal("-30.123")
    assert value.raw == b"-3.0123E+01\r\n"
    error = protocol.measurement(b"9.0031E+40\r\n", "W")
    assert error.value is None and error.error_code == 31
    assert protocol.measurement(b"-1.0000E-09\r\n", "W").value == Decimal("-1E-9")


@pytest.mark.parametrize(
    "raw",
    [
        b"NaN\r\n",
        b"+1.0000E+00",
        b"1.0000E+00\r\n",
        b"9.0050E+40\r\n",
        b"+1.0000E+41\r\n",
        b"\xff\r\n",
    ],
)
def test_malformed_power(raw):
    with pytest.raises(ProtocolError):
        protocol.measurement(raw, "W")


def test_status_fields_from_manual_schema():
    # AA=00 aa=00 BB=00 CC=11 cc=00 DD=10 dd=00; E=1 F=A G=0 H=0 I=0 J=2 K=0 L=0 M=0 N=0 O=0 P=1
    raw = b"000000110010001A0002000001\r\n"
    status = protocol.status(raw)
    assert (status.unit, status.range_code, status.filter_code) == ("dBm", 11, 10)
    assert status.reserved == ("00", "00", "A", "0") and status.raw == raw
    # Change H=1 and P=3 to relative logarithmic units.
    altered = bytearray(raw)
    altered[17], altered[25] = ord("1"), ord("3")
    assert protocol.status(bytes(altered)).unit == "dB"


@pytest.mark.parametrize("index,char", [(0, "X"), (6, "9"), (15, "B"), (22, "1"), (25, "3")])
def test_invalid_or_inconsistent_status(index, char):
    raw = bytearray(b"000000110010001A0002000001\r\n")
    raw[index] = ord(char)
    with pytest.raises(ProtocolError):
        protocol.status(bytes(raw))


def test_status_short_frame():
    with pytest.raises(ProtocolError):
        protocol.status(b"0000\r\n")


def test_identification_and_query_bytes():
    result = protocol.identification(b"HEWLETT-PACKARD, 437B,, 1.9\r\n")
    assert result.model == "437B" and result.serial == "" and result.firmware == "1.9"
    assert protocol.byte_value(b"012\r\n", 127) == 12
    for raw in (b"256\r\n", b"12\r\n", b"012", b"ABC\r\n"):
        with pytest.raises(ProtocolError):
            protocol.byte_value(raw)
    with pytest.raises(ProtocolError):
        protocol.identification(b"ACME,OTHER,,1.0\r\n")


def test_binary_snapshot_preserves_newlines():
    raw = b"@2" + bytes(range(58))
    assert protocol.snapshot(raw) == raw
    for invalid in (raw[:-1], raw + b"\r\n", b"Q2" + raw[2:]):
        with pytest.raises(ProtocolError):
            protocol.snapshot(invalid)


@pytest.mark.parametrize("value", [True, "NaN", "Infinity", "1E-1000000", "0.1" * 100, "1;PR"])
def test_number_rejects_invalid_precision_and_injection(value):
    with pytest.raises(ValueError):
        protocol.number(value, "0", "150", "0.1")
