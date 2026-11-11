# HP 437B capability inventory

Phase 1 inventory, November 11, 2026. The manual-backed reference covers118 command/syntax variants in50 functional families, plus20 GPIB operation entries. The bus count includes one documented controller-role exclusion.

| Document | Purpose |
| --- | --- |
| [Commands](COMMANDS.md) | Exact spellings, argument domains, output formats, state effects, prerequisites, and source references |
| [GPIB operations](GPIB.md) | Bus semantics, proposed API mapping, adapter claims, and released-backend evidence |
| [Coverage matrix](COVERAGE.md) | Separate documentation, implementation, software-test, Mac, and Pi statuses |
| [Ambiguities](AMBIGUITIES.md) | Nine source/transport question groups with precise resolution needs |
| [Review and completion](REVIEW.md) | Reconciliation, adversarial findings, validation, and Phase 2 recommendation |

Use the [counting convention](COMMANDS.md#source-and-counting-convention) when interpreting totals. The matrix's manual-verification status establishes accurate documentation of supplied sources, including their conflicts. Physical qualification remains a separate status for each host and unit.
