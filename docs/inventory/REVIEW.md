# Inventory validation method

The inventory accounts for **118 command/syntax variants**, **50 functional families**, and **20 bus-operation entries**, including one controller-role exclusion. It preserves exact manual spellings, source pages, parameter domains, side effects, contextual tokens, and unresolved ambiguities.

Use [COMMANDS.md](COMMANDS.md) for counting and source semantics, [GPIB.md](GPIB.md) for transport profiles, and [AMBIGUITIES.md](AMBIGUITIES.md) for unresolved questions. The [coverage matrix](COVERAGE.md) separates software/guard tests from current-meter Mac/Pi observations. Host checks for SN 3125U22346 are pending.

`python tools/check_docs.py` checks local Markdown links/anchors, table boundaries, all 138 registry IDs in the matrix/parameter ledger, and reference PDF hashes. Inventory/source reconciliation does not establish physical command execution or RF accuracy.
