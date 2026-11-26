"""Exact dial frequencies and nominal drive domains for the combined sweep."""

from . import provenance as p

SCHEMA = "hp437b.automatic-sweep-simulation.v1"
PICO_SCHEMA = "hp437b.automatic-pico-sweep.v1"
SI5351_PLAN_SCHEMA = "hp437b.automatic-pico-si5351-plan.v1"
SI5351_SCHEMA = "hp437b.automatic-pico-si5351.v1"
TIS_1W_SCHEMA = "hp437b.automatic-pico-si5351-tis-1w.v1"
TIS_1W_FIXTURE = "tis-1w"
SI5351_SCHEMAS = (SI5351_SCHEMA, TIS_1W_SCHEMA)
PICO_SCHEMAS = (PICO_SCHEMA, *SI5351_SCHEMAS)
MATRIX_SCHEMAS = (SCHEMA, *PICO_SCHEMAS)
PLAN_SCHEMAS = (*MATRIX_SCHEMAS, SI5351_PLAN_SCHEMA)
SI5351_TARGET = "pico-si5351"
SI5351_UNAVAILABLE = (
    "Configure the authenticated Pico Si5351 USB target before live review or Start"
)
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
TIS_1W_DIALS = {
    band: dial for band, dial in SI5351_DIALS.items() if band not in ("2200m", "630m", "2m")
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


def pico_plan(base):
    return {
        **simulation_plan(base, "pico-gpio"),
        "schema": PICO_SCHEMA,
        "samples": 2,
        "interval_s": 1.0,
        "timeout_s": 30.0,
    }


def si5351_plan(base, *, schema=SI5351_SCHEMA):
    return {
        **simulation_plan(base, "si5351"),
        "schema": schema,
        "frequencies": list(dials_for_schema(schema)),
        "samples": 2,
        "interval_s": 1.0,
        "timeout_s": 30.0,
    }


def catalog():
    return {
        "schema": SCHEMA,
        "bands": bands(DIALS),
        "profiles": [
            {"id": key, "label": label, "drives_ma": list(drives)}
            for key, (label, drives) in PROFILES.items()
        ],
    }


def bands(dials):
    return [
        {"label": name, "dial_hz": hz, "carrier_hz": hz + OFFSET_HZ} for name, hz in dials.items()
    ]


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
    elif plan["schema"] in (*SI5351_SCHEMAS, SI5351_PLAN_SCHEMA):
        p.require(
            plan == si5351_plan(plan, schema=plan["schema"]),
            "Use the exact Pico Si5351 capture settings",
        )
    else:
        p.require(
            plan["samples"] <= 3 and plan["settling_s"] == 0,
            "Automatic simulation accepts 1–3 synthetic readings and has no RF settling phase",
        )


def dials_for_schema(schema):
    if schema == TIS_1W_SCHEMA:
        return TIS_1W_DIALS
    return SI5351_DIALS if schema in (SI5351_SCHEMA, SI5351_PLAN_SCHEMA) else DIALS


def point_data(plan, point):
    if plan["schema"] not in PLAN_SCHEMAS:
        return {}
    dial = dials_for_schema(plan["schema"])[point["frequency"]]
    return {
        "dial_hz": dial,
        "carrier_hz": dial + OFFSET_HZ,
        "drive_ma": PROFILES[plan["profile"]][1][plan["drives"].index(point["drive"])],
    }
