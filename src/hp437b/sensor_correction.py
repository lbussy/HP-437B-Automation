"""Serial-specific sensor factors; no device access or persistent table editing."""

from decimal import ROUND_HALF_UP, Decimal
from typing import NamedTuple

PROFILE = "8482a-MY41094127-20261015"
SENSOR_SERIAL = "MY41094127"
SOURCE = "references/calibration/hp-8482a/MY41094127/2026-10-15/originals/HP-8482A-SN-MY41094127-Calibration-2026-10-15.pdf"
# Historical sealed receipts retain this location and the same certificate hash.
LEGACY_SOURCE = (
    "output/pdf/hp-437b-8482a/calibration/HP-8482A-SN-MY41094127-Calibration-2026-10-15.pdf"
)
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

H_PROFILE = "8482h-3318A09219-20261115"
H_SENSOR_SERIAL = "3318A09219"
H_SOURCE = "references/calibration/hp-8482h/3318A09219/2026-11-15/originals/HP-8482H-SN-3318A09219-Calibration-Chart-2026-11-15.pdf"
H_SOURCE_SHA256 = "1e3dfe6ae27de66a4b24b9aef7f98175ffccabb5e41a89f50593f328046d004b"
H_TABLE = tuple(
    (int(Decimal(mhz) * 1_000_000), Decimal(factor))
    for mhz, factor in (
        ("0.1", "99.8"),
        ("0.3", "97.4"),
        ("1", "97.9"),
        ("3", "99.1"),
        ("10", "99.5"),
        ("30", "99.2"),
        ("50", "99.0"),
        ("100", "98.7"),
        ("300", "98.4"),
        ("1000", "98.2"),
        ("2000", "94.8"),
        ("3000", "93.1"),
        ("4000", "90.3"),
        ("4200", "94.1"),
    )
)


class Calibration(NamedTuple):
    profile: str
    serial: str
    source: str
    page: int
    sha256: str
    table: tuple[tuple[int, Decimal], ...]


CALIBRATION_8482A = Calibration(PROFILE, SENSOR_SERIAL, SOURCE, 2, SOURCE_SHA256, TABLE)
CALIBRATION_8482H = Calibration(H_PROFILE, H_SENSOR_SERIAL, H_SOURCE, 1, H_SOURCE_SHA256, H_TABLE)


def correction(profile, sensor_serial, frequency_hz):
    """Interpolate on linear Hz, then round half up to the meter's 0.1% grid.

    The chart span bounds correction lookup, not safe input power or bandwidth.
    No extrapolation, assumed band centers, or substitution of another sensor.
    """
    calibration = next(
        (
            item
            for item in (CALIBRATION_8482A, CALIBRATION_8482H)
            if (profile, sensor_serial) == (item.profile, item.serial)
        ),
        None,
    )
    if calibration is None:
        raise ValueError("Correction profile must match the sensor label serial")
    table = calibration.table
    if type(frequency_hz) is not int or not table[0][0] <= frequency_hz <= table[-1][0]:
        raise ValueError(
            "Use an integer frequency in Hz within the certificate's 100 kHz–4.2 GHz span"
        )
    for hz, value in table:
        if frequency_hz == hz:
            low = high = (hz, value)
            factor = value
            break
    else:
        low, high = next(
            (a, b) for a, b in zip(table, table[1:], strict=False) if a[0] < frequency_hz < b[0]
        )
        factor = low[1] + (high[1] - low[1]) * Decimal(frequency_hz - low[0]) / Decimal(
            high[0] - low[0]
        )
    applied = factor.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return dict(
        profile=profile,
        sensor_serial=sensor_serial,
        frequency_hz=frequency_hz,
        source=calibration.source,
        source_page=calibration.page,
        source_sha256=calibration.sha256,
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
