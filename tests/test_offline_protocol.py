"""OQ-04 source-backed finite reply fields; no opaque payload interpretation."""

from decimal import Decimal

import pytest

from hp437b import protocol
from hp437b.errors import ProtocolError


def test_all_measurement_error_codes_and_unit_tags():
    # Appendix A and shared numeric output: XX=01..49 is an error, not power.
    for code in range(1, 50):
        for prefix in ("", "+"):
            raw = f"{prefix}9.00{code:02d}E+40\r\n".encode()
            for unit in ("W", "dBm", "%", "dB"):
                reply = protocol.measurement(raw, unit)
                assert reply.error_code == code and reply.value is None
                assert reply.raw == raw and reply.unit == unit
    for code in (0, 50, 99):
        with pytest.raises(ProtocolError):
            protocol.measurement(f"9.00{code:02d}E+40\r\n".encode(), "W")
    assert protocol.measurement(b"-0.0000E-99\r\n", "W").value == Decimal("-0E-103")


def test_every_ascii_byte_reply_and_stb_boundary():
    # §3-34: three decimal digits, then CR LF; STB bit 7 is unused.
    for value in range(256):
        raw = f"{value:03d}\r\n".encode()
        assert protocol.byte_value(raw) == value
        if value <= 127:
            assert protocol.byte_value(raw, 127) == value
        else:
            with pytest.raises(ProtocolError):
                protocol.byte_value(raw, 127)
    for raw in (b"-01\r\n", b"+01\r\n", b"1.0\r\n", b"256\r\n", b"0000\r\n", b"000\n"):
        with pytest.raises(ProtocolError):
            protocol.byte_value(raw)


def test_each_sm_finite_field_and_units():
    # Fig 3-5/Table 3-3: independent field variation, not Cartesian coverage.
    base = b"000000110010001A0002000001\r\n"
    fields = [
        (0, 2, range(50), "measurement_error"),
        (2, 2, range(100), "entry_error"),
        (4, 2, (0, 6, 8), "operating_mode"),
        (6, 2, (1, 2, 3, 4, 5, 11, 12, 13, 14, 15), "range_code"),
        (10, 2, range(20), "filter_code"),
        (16, 1, (0, 1), "reference_on"),
        (18, 1, (0, 1), "standby"),
        (19, 1, (0, 1, 2), "group_trigger"),
        (20, 1, (0, 1), "limits_on"),
        (21, 1, (0, 1, 2), "limit_result"),
        (23, 1, (0, 1), "offset_on"),
        (24, 1, (0, 1), "duty_on"),
    ]
    for offset, width, choices, attribute in fields:
        for choice in choices:
            raw = base[:offset] + f"{choice:0{width}d}".encode() + base[offset + width :]
            parsed = protocol.status(raw)
            assert getattr(parsed, attribute) == choice and parsed.raw == raw
    for log, relative, unit_code, unit in [
        (0, 0, 0, "W"),
        (1, 0, 1, "dBm"),
        (0, 1, 2, "%"),
        (1, 1, 3, "dB"),
    ]:
        raw = bytearray(base)
        raw[14], raw[17], raw[25] = 48 + log, 48 + relative, 48 + unit_code
        assert protocol.status(bytes(raw)).unit == unit
    for index in range(26):
        raw = base[:index] + b"\xff" + base[index + 1 :]
        with pytest.raises(ProtocolError):
            protocol.status(raw)


def test_opaque_snapshot_byte_preservation_and_size_boundaries():
    for value in range(256):
        raw = b"@2" + bytes([value]) * 58
        assert protocol.snapshot(raw) == raw
    for size in (0, 2, 59, 61, 4096, 65537):
        with pytest.raises(ProtocolError):
            protocol.snapshot(b"@2" + b"X" * max(0, size - 2))
