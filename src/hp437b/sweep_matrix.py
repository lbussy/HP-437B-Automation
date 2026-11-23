"""Exact dial frequencies and nominal drive domains for the combined sweep."""

from . import provenance as p

SCHEMA = "hp437b.automatic-sweep-simulation.v1"
OFFSET_HZ = 1500
DIALS = {
    "2200m": 136000,
    "630m": 474200,
    "160m": 1836600,
    "80m": 3568600,
    "60m": 5364700,
    "40m": 7038600,
    "30m": 10138700,
    "20m": 14095600,
    "17m": 18104600,
    "15m": 21094600,
    "12m": 24924600,
    "10m": 28124600,
    "6m": 50293000,
}
PROFILES = {
    "pico-gpio": ("Pico direct GPIO", (2, 4, 8, 12)),
    "si5351": ("Si5351", (2, 4, 6, 8)),
    "pi-bcm283x": ("Pi 1, 2, 3, Zero, and Zero 2 W", (2, 4, 6, 8, 10, 12, 14, 16)),
    "pi-bcm2711": ("Pi 4, Pi 400, and CM4", (1, 2, 3, 4, 5, 6, 7, 8)),
    "pi-rp1": ("Pi 5 and other RP1 models", (2, 4, 8, 12)),
}


def simulation_plan(base, profile):
    p.require(profile in PROFILES, "Unknown sweep drive profile")
    return {
        **base,
        "schema": SCHEMA,
        "profile": profile,
        "series": "combined",
        "order": "drive",
        "frequencies": list(DIALS),
        "drives": [f"{ma} mA" for ma in PROFILES[profile][1]],
        "samples": 3,
        "settling_s": 0.0,
    }


def catalog():
    return {
        "schema": SCHEMA,
        "bands": [
            {"label": name, "dial_hz": hz, "carrier_hz": hz + OFFSET_HZ}
            for name, hz in DIALS.items()
        ],
        "profiles": [
            {"id": key, "label": label, "drives_ma": list(drives)}
            for key, (label, drives) in PROFILES.items()
        ],
    }


def validate(plan):
    profile = plan["profile"]
    p.require(isinstance(profile, str) and profile in PROFILES, "Unknown sweep drive profile")
    p.require(
        plan["series"] == "combined"
        and plan["order"] == "drive"
        and plan["frequencies"] == list(DIALS)
        and plan["drives"] == [f"{ma} mA" for ma in PROFILES[profile][1]],
        "Automatic simulation requires the exact drive-first profile matrix",
    )
    p.require(
        plan["samples"] <= 3 and plan["settling_s"] == 0,
        "Automatic simulation accepts 1–3 synthetic readings and has no RF settling phase",
    )


def point_data(plan, point):
    if plan["schema"] != SCHEMA:
        return {}
    dial = DIALS[point["frequency"]]
    return {
        "dial_hz": dial,
        "carrier_hz": dial + OFFSET_HZ,
        "drive_ma": PROFILES[plan["profile"]][1][plan["drives"].index(point["drive"])],
    }
