# Current command and backend scope

The registry covers 118 command/syntax variants: 78 encodable/software-tested and 40 guarded. Encodable includes contextual helpers and polling-dependent procedures, not independently proven hardware operations. The normal transport retains pinned PyVISA/PyVISA-py/PyUSB versions and explicit guards.

ASCII acquisition/status, conditional USB488 local return, isolated diagnostics, tagged serial polling, bounded ZERO/CAL, and reconciliation are implemented paths with separate operating contracts. The isolated polling implementation does not enable general normal-transport bus support. Firmware/resource/setup checks on current meter SN 3125U22346 remain pending.

Persistent table changes, binary restoration, undocumented aliases/menu grammar, broad clear/GET/SRQ/parallel-poll support, and unattended continuation remain guarded or unresolved. See [ambiguities](AMBIGUITIES.md), [coverage](COVERAGE.md), [software](../SOFTWARE.md), and [validation](../VALIDATION.md).

Further expansion is optional and should address a selected workflow need. Software encoding, fakes, and an adapter request constant do not prove physical behavior.
