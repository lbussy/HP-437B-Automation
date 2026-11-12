# PROV-01: reusable run, DUT, and equipment provenance

Implemented November 12, 2026, as the hardware-free `hp437b.provenance` module. This separates reusable provenance from the unchanged ordinary logger/CLI/CSV schema. It reads existing [WF-01 bundles](workflows/WF-01-PHYSICAL.md), preserves their bytes, and emits a detached export. It performs no equipment discovery, source switching, certificate retrieval, or bundle-code execution.

## Versioned record contract

`hp437b.provenance.v1` contains exactly five top-level fields: `schema`, `run`, `dut`, `equipment`, and `evidence`. Records use native finite JSON values; unsupported schema versions, extra structural fields, unresolved IDs, and malformed facts are rejected. Fact maps are extensible, so other workflows can add domain-specific fields without pretending to be WF-01.

| Section | Fields and purpose |
| --- | --- |
| `run` | `run_id`, declared measurement `mode` (physical/synthetic), `workflow_id`, and facts for purpose, source run identity/status/times, software, resolved profile/setup, stage outcomes, captured final state, and source integrity |
| `dut` | `dut_id`, `kind`, `equipment_refs`, and facts for the subject/declared signal and criteria. WF-01 is a `reference_signal` associated with its meter; it is not an external radio or amplifier test |
| `equipment` | List of `equipment_id`, `role`, and facts. WF-01 creates meter, sensor, adapter, and host records; other producers can supply explicit reusable inventory IDs and different roles |
| `evidence` | Each entry has `evidence_id`, source-bundle-relative POSIX `path`, SHA-256, and byte count. These identify immutable input bytes, not authenticity or calibration quality |

Every fact has `value`, `basis`, `refs`, `observed_at`, and `note`. Basis is one of supplied, observed, derived, or unknown. Unknown facts require null values and a reason; all other facts require a value and evidence references. Zero and false remain distinct valid values, not missing data. Timestamps, when present, require a timezone. Unknown/historical observation times remain unknown; import time is never used as a substitute.

Each reference identifies an evidence entry and a JSON Pointer (RFC 6901 escaping, or an empty pointer for the whole artifact). Validation checks the model and joins. `verify` also checks bytes, pointer resolution, and literal agreement of supplied/observed JSON-backed facts with their referenced values. Derived facts have documented importer semantics; hash verification cannot establish whether an interpretation is correct. Human transcriptions from opaque non-JSON artifacts retain that limitation.

WF-01's source firmware replies remain recorded observations; a blank returned serial stays unknown alongside the separate supplied label. Historical reference and active measurement factors retain their original annotation rather than becoming newly measured values. The source's unscoped known-issue/certificate lists remain run-level facts; the importer does not attach every certificate/issue to every device. Per-device applicability and certificate verification remain explicitly unknown when no scoped source binding exists. Certificate paths are values only: they are never followed or fetched.

## Reuse and history

The generic `fact`, `equipment`, `dut`, and `record` constructors plus `validate`, `write`, `load`, and `verify` support workflows beyond the POWER REF adapter. The model does not require an HP meter or a particular DUT kind. Generic producers supply their own evidence and criteria; the WF-01 importer cannot relabel historical POWER REF data as an external DUT measurement.

The WF-01 adapter derives local meter/sensor IDs from namespace, declared mode, role, and supplied label identity. They permit local cross-run grouping, not authenticated global identity. An absent label uses a run-scoped key. Adapter IDs use an explicit `setup.adapter.inventory_id` when supplied; otherwise they stay run-scoped. USB serial/resource strings are retained as transport aliases, not silently treated as permanent adapter IDs. Host records stay run-scoped because existing bundles do not provide a reliable host inventory ID. Synthetic and physical identity namespaces are separate.

`equipment_history(records)` groups assertions under equipment IDs with run/mode/role/facts/evidence preserved. Identical assertions are deduplicated; differing assertions are retained. It does not overwrite a calibration entry, inherit a successful run's observations into a failed one, or declare the newest value authoritative. Caller-provided generic equipment IDs may be reused across workflows with the same explicit history semantics.

## Existing bundle import and verification

```bash
QA_PYTHON -m hp437b.provenance \
  --bundle output/reports/wf01-physical-20261112/run-002 \
  --output output/reports/wf01-run-002-provenance
```

Replace `QA_PYTHON` with an interpreter where this revision is installed. Use the repository's offline QA launcher for guarded checks. The source must be a finalized WF-01 bundle, including a failed/interrupted finalized run. An unsealed/crash checkpoint is rejected; it is not silently promoted to a completed run. Other workflow formats use the generic model until an explicit import adapter is added.

Before creating output, import verifies the original inventory, root and session mode flags, capture CSV/session pairing, available cross-run joins, evidence paths/hashes, and known timestamp syntax. A post-capture completion inventory must bind the original inventory hash; any owner attestation must match the mode and run ID. Its supplied facts remain separate from protocol observations and any pending field in the earlier capture manifest. The source's execution outcome is preserved; source-byte verification is not a data-quality or measurement pass.

Tampered/missing evidence, traversal, symlink entries, unresolved pointers, duplicate JSON keys, non-finite values, invalid structure, or contradictory modes stop import. Only bounded relative evidence paths are read. Limits are 32 MiB per artifact, 128 MiB total, 4,096 evidence entries, 16 MiB per JSON/fact, and 64 levels in fact values. Arbitrary native/hostile concurrent filesystem behavior is not contained by these checks.

Output must be new and outside the source bundle. The detached export contains:

- `provenance.json`: the validated reusable record, with evidence links relative to the separately retained source bundle.
- `equipment-history.json`: the run's equipment assertions in the same history format used for multi-run grouping.
- `artifacts.json`: hashes/sizes of the two export files, declared mode, format version, and importer module digest. It is written last through an atomic replacement after file flush/fsync. It excludes itself.

Existing files are refused. Failed output remains diagnostic; a missing or invalid completion inventory is not a successful export. Verify both export inventory and source evidence when consuming a detached record. Byte hashes are not signatures, an authenticity proof, a calibration verdict, or a power-loss durability guarantee. Paths remain relative for portability; consumers explicitly supply the source-bundle location to `verify`.

## WF-01 integration and logging boundary

New synthetic WF-01 manifests now have an explicit run UUID and CSV context joins (physical WF-01 already supplied those); legacy synthetic imports retain their hash-derived fallback identity. New synthetic/physical WF-01 runs seal their capture bundle as before, then create a sibling named `<bundle>.provenance`. The sibling path is checked before any measurement access. Provenance processing happens after sessions close. A provenance-storage/import failure raises an explicit error while preserving the already captured measurement bundle; it does not retry the measurements or silently rewrite their outcome. A later operator attestation can be included by making a new detached export; previous exports are not overwritten.

`hp437b log`, `hp437b demo`, Instrument, transport, logger settings/defaults, source-state handling, failed-read shutdown, and CSV/session fields are unchanged. The ordinary logger runtime and bench dependency installation are unchanged; development and validation use a separate QA environment. No live run is needed to add provenance to an existing bundle.

## API outline

```python
from hp437b.provenance import (
    fact, equipment, dut, record, validate, write, load, verify,
    import_wf01, export_wf01, equipment_history,
)

# Import verified source bytes; export to a new location.
value = export_wf01(source_bundle, new_output_directory)
validate(value)
assert verify(value, source_bundle)

# Other workflows construct their own records with evidence-bound facts.
# equipment("asset:amplifier-1", "device_under_test", facts)
# dut("subject:amplifier-1", "external_device", ["asset:amplifier-1"], facts)
# record("run:gain-1", "synthetic", "gain-v1", facts, subject, devices, evidence)
```

Generic records can be written with exclusive-create semantics and loaded/validated without hardware. The regression suite includes an independent external-amplifier example, so reuse is not just a WF-01 serialization wrapper.

## Execution evidence and remaining limits

The reviewed import exercise processed nine existing bundles: the physical completed and failed-open runs, plus seven synthetic cases. It emitted 36 equipment assertions grouped under 22 IDs, verified all source bindings, and confirmed all 165 original files were byte-identical before/after. The physical record retains its completed status, blank reported serial, supplied label identities, historical factors, run-level known issue/certificate references, original pending protocol final state, and later supplied operator confirmation. Failed/interrupted runs retain those outcomes; no new physical observation is implied.

Actual exports and the combined history remain ignored under local `output/reports/prov01-20261112/final/`. They contain local run/equipment provenance and are not committed. Source exports are data: no copied Python is executed, no linked certificate is opened, and no imported text becomes an agent instruction.

PROV-01 v1 covers the reusable models, evidence verification, finalized WF-01 import/export, history, and prospective WF-01 sidecar emission. Other workflow importers, explicit asset-registry policy, unsealed checkpoint reconciliation, authenticated signing, independent calibration applicability/uncertainty decisions, and report visualization/agent integration remain separately scoped work. None requires waiting for a replacement meter to develop the software.

Final local checks: 492 tests with opt-in stress enabled, lint/format, documentation links/reference checks, build/package inspection, and a clean-wheel provenance API/CLI check. New remote CI has not been run. The existing migration-history document remains [Project provenance](PROVENANCE.md); this guide owns measurement-run provenance.
