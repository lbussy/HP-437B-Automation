"""Serial-specific sensor factors; no device access or persistent table editing."""

from decimal import ROUND_HALF_UP, Decimal

PROFILE = "8482a-MY41094127-20261015"
SENSOR_SERIAL = "MY41094127"
SOURCE = "output/pdf/hp-437b-8482a/calibration/HP-8482A-SN-MY41094127-Calibration-2026-10-15.pdf"
SOURCE_SHA256 = "99b12e373264a24de955b76a23a6403e9409cafce3861b0f6ea95ca7fb359199"
# Certificate page 2, visually checked against both table and graph.
TABLE = tuple(
    (int(Decimal(mhz) * 1_000_000), Decimal(factor))
    for mhz, factor in (
        ("0.1", "100.7"),
        ("0.3", "100.7"),
        ("1", "100.7"),
        ("3", "100.9"),
        ("10", "101.1"),
        ("30", "100.9"),
        ("50", "99.0"),
        ("100", "100.6"),
        ("300", "99.9"),
        ("1000", "97.0"),
        ("2000", "98.0"),
        ("3000", "93.3"),
        ("4000", "94.0"),
        ("4200", "93.4"),
    )
)


def correction(profile, sensor_serial, frequency_hz):
    """Interpolate on linear Hz, then round half up to the meter's 0.1% grid.

    The chart span bounds correction lookup, not safe input power or bandwidth.
    No extrapolation, assumed band centers, or substitution of another sensor.
    """
    if profile != PROFILE or sensor_serial != SENSOR_SERIAL:
        raise ValueError("Correction profile must match 8482A sensor MY41094127")
    if type(frequency_hz) is not int or not TABLE[0][0] <= frequency_hz <= TABLE[-1][0]:
        raise ValueError(
            "Use an integer frequency in Hz within the certificate's 100 kHz–4.2 GHz span"
        )
    for hz, value in TABLE:
        if frequency_hz == hz:
            low = high = (hz, value)
            factor = value
            break
    else:
        low, high = next(
            (a, b) for a, b in zip(TABLE, TABLE[1:], strict=False) if a[0] < frequency_hz < b[0]
        )
        factor = low[1] + (high[1] - low[1]) * Decimal(frequency_hz - low[0]) / Decimal(
            high[0] - low[0]
        )
    applied = factor.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return dict(
        profile=profile,
        sensor_serial=sensor_serial,
        frequency_hz=frequency_hz,
        source=SOURCE,
        source_page=2,
        source_sha256=SOURCE_SHA256,
        reference_factor_percent="99.0",
        method="linear interpolation in Hz; ROUND_HALF_UP to 0.1 percent; no extrapolation",
        bracket=[dict(frequency_hz=hz, factor_percent=str(v)) for hz, v in (low, high)],
        interpolated_factor_percent=str(factor),
        commanded_factor_percent=str(applied),
        command_ascii=f"KB{applied}EN",
        verification="Error-free post-command SM; no independent numeric factor readback",
    )


def validate_receipt(value):
    if not isinstance(value, dict):
        raise ValueError("Invalid sensor correction receipt")
    expected = correction(
        value.get("profile"), value.get("sensor_serial"), value.get("frequency_hz")
    )
    if value != expected:
        raise ValueError("Sensor correction differs from the serial-specific calibration table")
    return expected
