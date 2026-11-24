# Contributing

Keep requirements, proposals, implementation, and measured results distinct. Use the [plan](docs/PLAN.md) for decisions and [open work](docs/OPEN-WORK.md) for status. Cite primary sources and exact manual sections for technical claims.

## Conventions

- Use Oxford commas, UTF-8, LF line endings, and the supplied EditorConfig/Git attributes.
- Describe only current equipment, calibration, behavior, and limitations in maintained prose. Omit development chronology and accounts of earlier states. Keep source attribution and hashes in provenance metadata.
- Preserve publisher PDFs and original manifests byte for byte. Save OCR, annotations, and previews separately.
- Keep scratch work in ignored `tmp/` or `temp/`. Keep credentials, local tool state, and raw measurements out of Git.
- Use relative links within the repository. Describe private provenance sources in text so public documentation remains self-contained.
- Keep original work under the MIT license, preserve third-party notices, and record provenance for additions.
- Use `devel` as the initial default branch and `codex/` for task branches unless instructed otherwise.

## Review checks

Check changed Markdown and local links, run `git diff --check`, and verify reference integrity with `python tools/check_docs.py` and `shasum -a 256 -c SHA256SUMS.txt` from `references/`. Run relevant software tests when implementation exists. Hardware claims require recorded bench evidence, separate from simulated or software-only checks.

No hardware test should transmit RF or change a live setup merely to validate documentation. Future hardware procedures must identify signal levels, sensor limits, and the actual load/attenuation path. Do not bundle a proprietary VISA runtime or publish publisher manuals without establishing applicable redistribution rights.
