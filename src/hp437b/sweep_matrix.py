"""Exact dial frequencies and nominal drive domains for the combined sweep."""

from . import provenance as p

SCHEMA = "hp437b.automatic-sweep-simulation.v1"
PICO_SCHEMA = "hp437b.automatic-pico-sweep.v1"
SI5351_PLAN_SCHEMA = "hp437b.automatic-pico-si5351-plan.v1"
CAPTURE_SCHEMAS = (SCHEMA, PICO_SCHEMA)
MATRIX_SCHEMAS = (*CAPTURE_SCHEMAS, SI5351_PLAN_SCHEMA)
SI5351_TARGET = "pico-si5351"
SI5351_UNAVAILABLE = "Pico Si5351 requires the paired Control/1 contract and RF-free fixtures"
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
SI5351_DIALS = {**DIALS, "2m": 144489000}
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


def pico_plan(base):
    return {
        **simulation_plan(base, "pico-gpio"),
        "schema": PICO_SCHEMA,
        "samples": 2,
        "interval_s": 1.0,
        "timeout_s": 30.0,
    }


def si5351_plan(base):
    return {
        **simulation_plan(base, "si5351"),
        "schema": SI5351_PLAN_SCHEMA,
        "frequencies": list(SI5351_DIALS),
        "samples": 2,
        "interval_s": 1.0,
        "timeout_s": 30.0,
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
        and plan["frequencies"] == list(dials_for_schema(plan["schema"]))
        and plan["drives"] == [f"{ma} mA" for ma in PROFILES[profile][1]],
        "Automatic sweep requires the exact drive-first profile matrix",
    )
    if plan["schema"] == PICO_SCHEMA:
        p.require(plan == pico_plan(plan), "Use the reviewed direct-GPIO Pico capture settings")
    elif plan["schema"] == SI5351_PLAN_SCHEMA:
        p.require(plan == si5351_plan(plan), "Use the exact Pico Si5351 capture settings")
    else:
        p.require(
            plan["samples"] <= 3 and plan["settling_s"] == 0,
            "Automatic simulation accepts 1–3 synthetic readings and has no RF settling phase",
        )


def dials_for_schema(schema):
    return SI5351_DIALS if schema == SI5351_PLAN_SCHEMA else DIALS


def point_data(plan, point):
    if plan["schema"] not in MATRIX_SCHEMAS:
        return {}
    dial = dials_for_schema(plan["schema"])[point["frequency"]]
    return {
        "dial_hz": dial,
        "carrier_hz": dial + OFFSET_HZ,
        "drive_ma": PROFILES[plan["profile"]][1][plan["drives"].index(point["drive"])],
    }
