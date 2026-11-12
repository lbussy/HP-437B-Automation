"""Independent domains from 00437-90047; inventory links give exact pages.

OQ-03: finite masks/enums are exhaustive; decimal domains are sampled boundaries.
No response here is physical evidence.
"""

from decimal import Decimal

import pytest

from hp437b.commands import COMMANDS, encode
from hp437b.errors import CapabilityUnavailable
from hp437b.instrument import Instrument


@pytest.mark.parametrize(
    "code,low,high", [("RC", 0, 10), ("ST", 1, 10), ("RE", 1, 3), ("RM", 0, 5), ("SE", 0, 9)]
)
def test_every_register_range_sensor_choice(code, low, high):
    # Manual command entries C075/C099/C076/C089/C098, not encoder constants.
    for choice in range(low, high + 1):
        assert encode(code, choice) == f"{code}{choice}EN".encode("ascii")
    for invalid in (low - 1, high + 1, "1.5", True, None, "NaN", "Infinity"):
        with pytest.raises(ValueError):
            encode(code, invalid)


def test_all_enable_masks_and_filter_counts():
    # ESR bits 7/5/4/3, §3-31; SRE byte domain §3-30; FM printed 3-63 (A08).
    for mask in range(256):
        assert encode("*SRE", mask) == f"*SRE{mask}".encode("ascii")
        if mask & 0x47:
            with pytest.raises(ValueError):
                encode("*ESE", mask)
        else:
            assert encode("*ESE", mask) == f"*ESE{mask}".encode("ascii")
    for value in range(1, 513):
        if value in (1, 2, 4, 8, 16, 32, 64, 128, 256, 512):
            assert encode("FM", value) == f"FM{value}EN".encode("ascii")
        else:
            with pytest.raises(ValueError):
                encode("FM", value)


@pytest.mark.parametrize(
    "code,low,high,step,suffix",
    [
        ("CL", "50", "120", "0.1", "EN"),
        ("KB", "1", "150", "0.1", "EN"),
        ("DY", "0.001", "99.999", "0.001", "EN"),
        ("OS", "-99.99", "99.99", "0.01", "EN"),
        ("LH", "-299.999", "299.999", "0.001", "EN"),
        ("LL", "-299.999", "299.999", "0.001", "EN"),
    ]
    + [(f"RF{i}", "50", "120", "0.1", "%") for i in range(10)],
)
def test_documented_decimal_boundaries(code, low, high, step, suffix):
    lo, hi, grid = map(Decimal, (low, high, step))
    for value in (lo, lo + grid, hi - grid, hi):
        text = format(value, "f")
        assert encode(code, text) == (code + text + suffix).encode("ascii")
    for value in (lo - grid, hi + grid, lo + grid / 2):
        with pytest.raises(ValueError):
            encode(code, value)
    for invalid in (True, None, "NaN", "Infinity", "-Infinity", "1;PR", "1E999999"):
        with pytest.raises(ValueError):
            encode(code, invalid)


@pytest.mark.parametrize("code", ["CL", "KB", "DY"])
@pytest.mark.parametrize("suffix", ["EN", "%", "PCT"])
def test_all_numeric_terminators(code, suffix):
    assert encode(code, "99.0", terminator=suffix) == (code + "99.0" + suffix).encode()


@pytest.mark.parametrize(
    "unit,low,high",
    [
        ("HZ", "100000", "999999900000"),
        ("KZ", "100", "999999900"),
        ("MZ", "0.1", "999999.9"),
        ("GZ", "0.0001", "999.9999"),
    ],
)
def test_frequency_scales(unit, low, high):
    for value in (low, high):
        assert encode("FR", value, unit=unit) == ("FR" + value + unit).encode()
        assert encode(unit, value) == (value + unit).encode()
    with pytest.raises(ValueError):
        encode("FR", "0", unit=unit)


@pytest.mark.parametrize("code", [c for c, spec in COMMANDS.items() if spec.deferred])
def test_every_guard_before_fake_transport(code, scripted):
    wire = scripted()
    instrument = Instrument(wire)
    # Public dispatch can reject unsupported operation kind before the ambiguity
    # guard; both outcomes must precede transport activity.
    with pytest.raises((CapabilityUnavailable, ValueError)):
        if COMMANDS[code].kind == "Q":
            instrument.query(code)
        else:
            instrument.command(code, confirmed=True)
    assert wire.calls == []


@pytest.mark.parametrize(
    "code",
    [
        "*CLS",
        "CS",
        "DA",
        "DC0",
        "DC1",
        "DD",
        "DE",
        "DN",
        "LT",
        "RT",
        "UP",
        "EN",
        "ERR?",
        "*ESR?",
        "*ESE?",
        "EX",
        "FA",
        "FH",
        "GT0",
        "GT1",
        "GT2",
        "*IDN?",
        "LG",
        "LN",
        "LM0",
        "LM1",
        "LP2",
        "OC0",
        "OC1",
        "OD",
        "OF0",
        "OF1",
        "PR",
        "RA",
        "RH",
        "RL0",
        "RL1",
        "RL2",
        "SM",
        "*SRE?",
        "*STB?",
        "TR0",
        "TR1",
        "TR2",
        "TR3",
        "ZE",
    ],
)
def test_every_no_argument_literal_rejects_extra_value(code):
    with pytest.raises(ValueError):
        encode(code, "INJECT;PR")


def test_display_length_and_character_boundaries():
    for length in range(1, 13):
        text = "A" * length
        assert encode("DU", text) == ("DU" + text).encode()
    for text in ("", "A" * 13, "LOWERcase", "A;PR", "µW", "A\r\n", 123, None):
        with pytest.raises(ValueError):
            encode("DU", text)


@pytest.mark.parametrize(
    "code,value",
    [("PR", None), ("RC", 0), ("ST", 1), ("OC1", None)] + [(f"RF{i}", 99) for i in range(10)],
)
def test_every_confirmation_gate_precedes_io(code, value, scripted):
    wire = scripted()
    for confirmation in (False, 1, "yes", None):
        with pytest.raises(ValueError, match="explicitly confirm"):
            Instrument(wire).command(code, value, confirmed=confirmation)
    assert wire.calls == []
