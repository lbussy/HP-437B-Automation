"""Supplied human operator identity, without inferring it from host/login metadata."""

import os


def validate_operator(name):
    if name is None:
        return None
    if (
        not isinstance(name, str)
        or not name.strip()
        or len(name.strip()) > 120
        or any(ord(char) < 32 or ord(char) == 127 for char in name)
    ):
        raise ValueError("Operator must be a nonempty, single-line name of at most 120 characters")
    return name.strip()


def resolve_operator(explicit=None, recorded=None):
    """Explicit argument > captured name > environment default > unknown."""
    environment = os.environ.get("HP437B_OPERATOR") or None
    for name, origin in (
        (explicit, "argument"),
        (recorded, "capture"),
        (environment, "environment"),
    ):
        if name is not None:
            return {"value": validate_operator(name), "basis": "supplied", "origin": origin}
    return {"value": None, "basis": "unknown", "origin": "not_recorded"}
