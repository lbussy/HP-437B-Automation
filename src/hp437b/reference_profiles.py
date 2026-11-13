"""Reusable reference-test selections and attributed limits; no device configuration."""

import re

from . import acceptance_review as acceptance
from . import provenance as p
from . import reference_suite, report_context
from . import reporting as r

SCHEMA = "hp437b.reference-test-profile.v1"
BINDING = "hp437b.reference-test-profile-binding.v1"
MAX_PROFILE = 16 * 1024


def text(value, maximum):
    p.require(
        isinstance(value, str)
        and 0 < len(value.strip()) <= maximum
        and not any(ord(c) < 32 or ord(c) == 127 for c in value),
        "Profile text must be a nonempty single line",
    )
    return value.strip()


def validate(document):
    p.require(len(r.encoded(document)) <= MAX_PROFILE, "Reference profile exceeds 16 KiB")
    p._keys(
        document,
        (
            "schema",
            "profile_id",
            "revision",
            "description",
            "subject",
            "operator",
            "workflows",
            "criteria",
        ),
    )
    p.require(document["schema"] == SCHEMA, "Unsupported reference profile schema")
    p.require(
        isinstance(document["profile_id"], str)
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", document["profile_id"]),
        "Invalid reference profile ID",
    )
    p.require(
        type(document["revision"]) is int and 1 <= document["revision"] <= 1000000,
        "Profile revision must be an integer from 1 to 1000000",
    )
    p.require(
        document["subject"] == "Internal POWER REF",
        "Reference profiles measure Internal POWER REF, not a transmitter",
    )
    workflows = reference_suite.selection(document["workflows"])
    criteria = acceptance.validate(document["criteria"])
    p.require(
        set(criteria["workflows"]) <= set(workflows),
        "Profile criteria include unselected workflows",
    )
    return {
        **document,
        "description": text(document["description"], 240),
        "operator": report_context.validate_operator(document["operator"]),
        "workflows": workflows,
        "criteria": criteria,
    }


def bind(document, timing):
    document = validate(document)
    p.require(timing in ("before_capture", "post_capture"), "Invalid profile selection timing")
    return dict(
        schema=BINDING,
        profile=document,
        profile_sha256=r.digest(r.encoded(document)),
        selected=timing,
    )


def validate_binding(binding, workflows, criteria):
    p._keys(binding, ("schema", "profile", "profile_sha256", "selected"))
    expected = bind(binding["profile"], binding["selected"])
    p.require(binding == expected, "Reference profile snapshot/hash mismatch")
    p.require(
        expected["profile"]["workflows"] == workflows,
        "Profile workflow selection differs from capture",
    )
    p.require(
        expected["profile"]["criteria"] == acceptance.validate(criteria),
        "Profile criteria differ from assessment",
    )
    return expected["profile"]
