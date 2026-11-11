"""Failures distinguish protocol validation, transport, and unknown device state."""


class HP437BError(Exception):
    """Base application error."""


class ProtocolError(HP437BError):
    """An instrument response violates its documented format."""


class CapabilityUnavailable(HP437BError):
    """A source ambiguity or selected transport prevents an operation."""


class StateUncertain(HP437BError):
    """Reconcile device state explicitly before using the connection again."""


class TransportError(HP437BError):
    """A transport failed, possibly after the device accepted an operation."""


class OperationTimeout(TransportError):
    """An operation exceeded its monotonic deadline."""
