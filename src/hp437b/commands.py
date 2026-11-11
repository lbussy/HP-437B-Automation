"""Validated command registry; ambiguity guards run before encoding or I/O."""

from dataclasses import dataclass

from .errors import CapabilityUnavailable
from .protocol import integer, number


@dataclass(frozen=True)
class Command:
    id: str
    code: str
    kind: str
    family: str
    deferred: str = ""


# Registry entries generated once from the reviewed inventory; maintained with stable IDs.
COMMANDS = {
    "CL": Command("C001", "CL", "W", "Calibration", ""),
    "*CLS": Command("C002", "*CLS", "W", "Status clear", ""),
    "CS": Command("C003", "CS", "W", "Status clear", ""),
    "CT0": Command(
        "C004",
        "CT0",
        "W",
        "Sensor table clear",
        "A03: table clear/edit/label framing awaits resolution",
    ),
    "CT1": Command(
        "C005",
        "CT1",
        "W",
        "Sensor table clear",
        "A03: table clear/edit/label framing awaits resolution",
    ),
    "CT2": Command(
        "C006",
        "CT2",
        "W",
        "Sensor table clear",
        "A03: table clear/edit/label framing awaits resolution",
    ),
    "CT3": Command(
        "C007",
        "CT3",
        "W",
        "Sensor table clear",
        "A03: table clear/edit/label framing awaits resolution",
    ),
    "CT4": Command(
        "C008",
        "CT4",
        "W",
        "Sensor table clear",
        "A03: table clear/edit/label framing awaits resolution",
    ),
    "CT5": Command(
        "C009",
        "CT5",
        "W",
        "Sensor table clear",
        "A03: table clear/edit/label framing awaits resolution",
    ),
    "CT6": Command(
        "C010",
        "CT6",
        "W",
        "Sensor table clear",
        "A03: table clear/edit/label framing awaits resolution",
    ),
    "CT7": Command(
        "C011",
        "CT7",
        "W",
        "Sensor table clear",
        "A03: table clear/edit/label framing awaits resolution",
    ),
    "CT8": Command(
        "C012",
        "CT8",
        "W",
        "Sensor table clear",
        "A03: table clear/edit/label framing awaits resolution",
    ),
    "CT9": Command(
        "C013",
        "CT9",
        "W",
        "Sensor table clear",
        "A03: table clear/edit/label framing awaits resolution",
    ),
    "DA": Command("C014", "DA", "W", "Display", ""),
    "DC0": Command("C015", "DC0", "W", "Duty correction", ""),
    "DC1": Command("C016", "DC1", "W", "Duty correction", ""),
    "DD": Command("C017", "DD", "W", "Display", ""),
    "DF": Command("C018", "DF", "W", "Display", "A07: undocumented detailed firmware alias"),
    "DE": Command("C019", "DE", "W", "Display", ""),
    "DN": Command("C020", "DN", "W", "Cursor", ""),
    "LT": Command("C021", "LT", "W", "Cursor", ""),
    "RT": Command("C022", "RT", "W", "Cursor", ""),
    "UP": Command("C023", "UP", "W", "Cursor", ""),
    "DU": Command("C024", "DU", "W", "Display", ""),
    "DY": Command("C025", "DY", "W", "Duty correction", ""),
    "EN": Command("C026", "EN", "P", "Entry", ""),
    "ERR?": Command("C027", "ERR?", "Q", "Error query", ""),
    "*ESR?": Command("C028", "*ESR?", "Q", "Event status", ""),
    "*ESE": Command("C029", "*ESE", "W", "Event enable", ""),
    "*ESE?": Command("C030", "*ESE?", "Q", "Event enable", ""),
    "ET0": Command(
        "C031",
        "ET0",
        "W",
        "Sensor table edit",
        "A03: table clear/edit/label framing awaits resolution",
    ),
    "ET1": Command(
        "C032",
        "ET1",
        "W",
        "Sensor table edit",
        "A03: table clear/edit/label framing awaits resolution",
    ),
    "ET2": Command(
        "C033",
        "ET2",
        "W",
        "Sensor table edit",
        "A03: table clear/edit/label framing awaits resolution",
    ),
    "ET3": Command(
        "C034",
        "ET3",
        "W",
        "Sensor table edit",
        "A03: table clear/edit/label framing awaits resolution",
    ),
    "ET4": Command(
        "C035",
        "ET4",
        "W",
        "Sensor table edit",
        "A03: table clear/edit/label framing awaits resolution",
    ),
    "ET5": Command(
        "C036",
        "ET5",
        "W",
        "Sensor table edit",
        "A03: table clear/edit/label framing awaits resolution",
    ),
    "ET6": Command(
        "C037",
        "ET6",
        "W",
        "Sensor table edit",
        "A03: table clear/edit/label framing awaits resolution",
    ),
    "ET7": Command(
        "C038",
        "ET7",
        "W",
        "Sensor table edit",
        "A03: table clear/edit/label framing awaits resolution",
    ),
    "ET8": Command(
        "C039",
        "ET8",
        "W",
        "Sensor table edit",
        "A03: table clear/edit/label framing awaits resolution",
    ),
    "ET9": Command(
        "C040",
        "ET9",
        "W",
        "Sensor table edit",
        "A03: table clear/edit/label framing awaits resolution",
    ),
    "EX": Command("C041", "EX", "W", "Exit", ""),
    "FA": Command("C042", "FA", "W", "Filter", ""),
    "FH": Command("C043", "FH", "W", "Filter", ""),
    "FM": Command("C044", "FM", "W", "Filter", ""),
    "FR": Command("C045", "FR", "W", "Frequency", ""),
    "GT0": Command("C046", "GT0", "W", "Group-trigger policy", ""),
    "GT1": Command("C047", "GT1", "W", "Group-trigger policy", ""),
    "GT2": Command("C048", "GT2", "W", "Group-trigger policy", ""),
    "GZ": Command("C049", "GZ", "P", "Frequency unit", ""),
    "HZ": Command("C050", "HZ", "P", "Frequency unit", ""),
    "KZ": Command("C051", "KZ", "P", "Frequency unit", ""),
    "MZ": Command("C052", "MZ", "P", "Frequency unit", ""),
    "ID": Command(
        "C053",
        "ID",
        "Q",
        "Identification",
        "A01: identification alias awaits firmware evidence; use *IDN? candidate",
    ),
    "IDN?": Command(
        "C054",
        "IDN?",
        "Q",
        "Identification",
        "A01: identification alias awaits firmware evidence; use *IDN? candidate",
    ),
    "*IDN?": Command("C055", "*IDN?", "Q", "Identification", ""),
    "KB": Command("C056", "KB", "W", "Calibration factor", ""),
    "LG": Command("C057", "LG", "W", "Units", ""),
    "LN": Command("C058", "LN", "W", "Units", ""),
    "LH": Command("C059", "LH", "W", "High limit", ""),
    "LL": Command("C060", "LL", "W", "Low limit", ""),
    "LM0": Command("C061", "LM0", "W", "Limits enable", ""),
    "LM1": Command("C062", "LM1", "W", "Limits enable", ""),
    "LP": Command(
        "C063", "LP", "Q", "Learn", "A02: ambiguous legacy framing/restore requires evidence"
    ),
    "LP2": Command("C064", "LP2", "Q", "Learn", ""),
    "OC0": Command("C065", "OC0", "W", "Reference output", ""),
    "OC1": Command("C066", "OC1", "W", "Reference output", ""),
    "OD": Command("C067", "OD", "Q", "Display output", ""),
    "OF0": Command("C068", "OF0", "W", "Offset enable", ""),
    "OF1": Command("C069", "OF1", "W", "Offset enable", ""),
    "OS": Command("C070", "OS", "W", "Offset", ""),
    "PCT": Command("C071", "PCT", "P", "Percent terminator", ""),
    "%": Command("C072", "%", "P", "Percent terminator", ""),
    "PR": Command("C073", "PR", "W", "Preset", ""),
    "RA": Command("C074", "RA", "W", "Auto range", ""),
    "RC": Command("C075", "RC", "W", "Recall", ""),
    "RE": Command("C076", "RE", "W", "Resolution", ""),
    "RF0": Command("C077", "RF0", "W", "Table reference factor", ""),
    "RF1": Command("C078", "RF1", "W", "Table reference factor", ""),
    "RF2": Command("C079", "RF2", "W", "Table reference factor", ""),
    "RF3": Command("C080", "RF3", "W", "Table reference factor", ""),
    "RF4": Command("C081", "RF4", "W", "Table reference factor", ""),
    "RF5": Command("C082", "RF5", "W", "Table reference factor", ""),
    "RF6": Command("C083", "RF6", "W", "Table reference factor", ""),
    "RF7": Command("C084", "RF7", "W", "Table reference factor", ""),
    "RF8": Command("C085", "RF8", "W", "Table reference factor", ""),
    "RF9": Command("C086", "RF9", "W", "Table reference factor", ""),
    "RH": Command("C087", "RH", "W", "Range hold", ""),
    "RL0": Command("C088", "RL0", "W", "Relative", ""),
    "RL1": Command("C089", "RL1", "W", "Relative", ""),
    "RL2": Command("C090", "RL2", "W", "Relative", ""),
    "RM": Command("C091", "RM", "W", "Manual range", ""),
    "*RST": Command(
        "C092", "*RST", "W", "Soft reset", "A05: reset/self-test/menu effects require evidence"
    ),
    "RV": Command(
        "C093", "RV", "Q", "Mask read", "A02: ambiguous legacy framing/restore requires evidence"
    ),
    "SE": Command("C094", "SE", "W", "Sensor selection", ""),
    "SM": Command("C095", "SM", "Q", "Status message", ""),
    "SN0": Command(
        "C096", "SN0", "W", "Sensor label", "A03: table clear/edit/label framing awaits resolution"
    ),
    "SN1": Command(
        "C097", "SN1", "W", "Sensor label", "A03: table clear/edit/label framing awaits resolution"
    ),
    "SN2": Command(
        "C098", "SN2", "W", "Sensor label", "A03: table clear/edit/label framing awaits resolution"
    ),
    "SN3": Command(
        "C099", "SN3", "W", "Sensor label", "A03: table clear/edit/label framing awaits resolution"
    ),
    "SN4": Command(
        "C100", "SN4", "W", "Sensor label", "A03: table clear/edit/label framing awaits resolution"
    ),
    "SN5": Command(
        "C101", "SN5", "W", "Sensor label", "A03: table clear/edit/label framing awaits resolution"
    ),
    "SN6": Command(
        "C102", "SN6", "W", "Sensor label", "A03: table clear/edit/label framing awaits resolution"
    ),
    "SN7": Command(
        "C103", "SN7", "W", "Sensor label", "A03: table clear/edit/label framing awaits resolution"
    ),
    "SN8": Command(
        "C104", "SN8", "W", "Sensor label", "A03: table clear/edit/label framing awaits resolution"
    ),
    "SN9": Command(
        "C105", "SN9", "W", "Sensor label", "A03: table clear/edit/label framing awaits resolution"
    ),
    "SP": Command(
        "C106", "SP", "W", "Special menu", "A05: reset/self-test/menu effects require evidence"
    ),
    "*SRE": Command("C107", "*SRE", "W", "Mask set", ""),
    "*SRE?": Command("C108", "*SRE?", "Q", "Mask read", ""),
    "ST": Command("C109", "ST", "W", "Store", ""),
    "*STB?": Command("C110", "*STB?", "Q", "Status byte query", ""),
    "TR0": Command("C111", "TR0", "W", "Trigger", ""),
    "TR1": Command("C112", "TR1", "W", "Trigger", ""),
    "TR2": Command("C113", "TR2", "W", "Trigger", ""),
    "TR3": Command("C114", "TR3", "W", "Trigger", ""),
    "*TST?": Command(
        "C115",
        "*TST?",
        "Q",
        "Self-test query",
        "A05: reset/self-test/menu effects require evidence",
    ),
    "ZE": Command("C116", "ZE", "W", "Zero", ""),
    "@1": Command(
        "C117",
        "@1",
        "B",
        "Legacy mask prefix",
        "A02: ambiguous legacy framing/restore requires evidence",
    ),
    "@2": Command(
        "C118",
        "@2",
        "B",
        "Learn restore prefix",
        "A02: ambiguous legacy framing/restore requires evidence",
    ),
}


def specification(code: str) -> Command:
    if not isinstance(code, str) or code not in COMMANDS:
        raise ValueError("Use an exact documented uppercase command code")
    spec = COMMANDS[code]
    if spec.deferred:
        raise CapabilityUnavailable(f"{spec.id} {spec.code}: {spec.deferred}")
    return spec


def encode(code: str, value: object = None, *, unit: str = "GZ", terminator: str = "EN") -> bytes:
    """Encode a whole command or a contextual token, never arbitrary command text.

    Numeric encoders use exact documented grid values; hardware rounding is left
    to explicit future APIs. Contextual tokens require a compatible transaction.
    """
    specification(code)
    if terminator not in ("EN", "%", "PCT"):
        raise ValueError("Unsupported numeric terminator")
    if code in ("CL", "KB", "DY"):
        low, high, step = {
            "CL": ("50", "120", "0.1"),
            "KB": ("1", "150", "0.1"),
            "DY": ("0.001", "99.999", "0.001"),
        }[code]
        result = code + number(value, low, high, step) + terminator
    elif code in ("OS", "LH", "LL"):
        low, high, step = (
            ("-99.99", "99.99", "0.01") if code == "OS" else ("-299.999", "299.999", "0.001")
        )
        result = code + number(value, low, high, step) + "EN"
    elif code in ("RC", "ST", "RE", "RM", "SE"):
        low, high = {"RC": (0, 10), "ST": (1, 10), "RE": (1, 3), "RM": (0, 5), "SE": (0, 9)}[code]
        result = code + str(integer(value, low, high)) + "EN"
    elif code == "FM":
        count = integer(value, 1, 512)
        if count not in (1, 2, 4, 8, 16, 32, 64, 128, 256, 512):
            raise ValueError("Choose an exact legal filter count; A08 rounding is deferred")
        result = f"FM{count}EN"
    elif code in ("FR", "HZ", "KZ", "MZ", "GZ"):
        from decimal import Decimal

        suffix = unit if code == "FR" else code
        if suffix not in ("HZ", "KZ", "MZ", "GZ"):
            raise ValueError("Expected HZ/KZ/MZ/GZ")
        factor = {"HZ": 1, "KZ": 1000, "MZ": 1000000, "GZ": 1000000000}[suffix]
        text = number(value, "0", "999999900000000")
        number(Decimal(text) * factor, "100000", "999999900000", "100000")
        result = ("FR" if code == "FR" else "") + text + suffix
    elif code.startswith("RF"):
        result = code + number(value, "50", "120", "0.1") + "%"
    elif code in ("*SRE", "*ESE"):
        mask = integer(value, 0, 255)
        if code == "*ESE" and mask & ~0xB8:
            raise ValueError("Only documented ESR enable bits 128/32/16/8 are accepted")
        result = code + str(mask)
    elif code == "DU":
        import re

        if not isinstance(value, str) or not re.fullmatch(r"[A-Z0-9 ]{1,12}", value):
            raise ValueError("Display message requires 1..12 uppercase letters, digits, or spaces")
        result = code + value
    elif code in ("%", "PCT"):
        result = number(value, "0", "150") + code
    else:
        if value is not None:
            raise ValueError(f"{code} accepts no argument")
        result = code
    return result.encode("ascii")
