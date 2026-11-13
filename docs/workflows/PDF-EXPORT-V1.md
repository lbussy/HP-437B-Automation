# REPORT-EXPORT-01: PDF reports and portable packages, v1

Status: implemented. Covers WF-04–WF-06, their [profile commands](DUT-TEST-PROFILES-V1.md), and [fake suites](TEST-SUITES-V1.md). Existing report defaults and normal logging are unchanged. No hardware, backend, source, or provider access is added. WF-01–WF-03 PDF integration is outside this version's scope.

Use `--pdf` to generate a one-page PDF automatically during report publication. Use `--package` to generate PDFs and a portable ZIP containing reports, provenance, and original sealed evidence. The commands print the PDF/ZIP paths. Open **report.pdf**, rather than an HTML source file, for the human-readable answer.

## Install the optional renderer

Use an isolated reporting environment, leaving the bench environment unchanged:

```bash
python -m venv tmp/pdf-report-env
source tmp/pdf-report-env/bin/activate
python -m pip install -e '.[pdf]'
```

The optional `pdf` extra pins ReportLab 5.1.0, Pillow 13.0.0, and charset-normalizer 3.5.2. Add the existing `reports` extra for plots: `python -m pip install -e '.[reports,pdf]'`. Without Matplotlib, use `--no-plots`. No browser or Pango installation is used. The implementation follows [ReportLab's document/layout APIs](https://docs.reportlab.com/reportlab/userguide/ch5_platypus/); the [pinned renderer distribution](https://pypi.org/project/reportlab/5.1.0/) carries its authoritative code/font notices.

PDF support is optional. Ordinary capture/HTML/Markdown/JSON reporting does not import the renderer. A missing PDF extra is rejected before a requested acquisition starts. PDF generation, ZIP creation, and archive verification do not retry measurements or contact equipment.

## Human-started suite with automatic delivery

```bash
python tools/offline_qa.py --seconds 180 -- python -m hp437b.test_suite run \
  --profile docs/workflows/examples/dut-test-profile-v1.json \
  --operator 'Example operator' \
  --output output/reports/pdf-suite-capture \
  --report-output output/reports/pdf-suite-report --package --no-plots
```

Outputs:

- `pdf-suite-report/report.pdf`: the one-page **RF Output Power Test** suite summary.
- `pdf-suite-report/workflows/WF-04/report.pdf` etc.: individual one-page test results, beside HTML, Markdown, results, provenance, and appendices.
- `pdf-suite-report.zip`: the portable package, a sibling of the report directory.

`--package` implies `--pdf`; `--pdf` alone creates PDFs without a ZIP. Each output/report directory and ZIP must be new. The PDF dependency and sibling ZIP reservation are checked before capture. The same flags work on profile `run`, workflow `synthetic`/`controlled`, and workflow/suite `report` commands. Without either flag, existing report outputs and behavior remain unchanged. Capture-only commands require `--report-output` when PDF/package delivery is requested.

## Export an existing capture without acquiring again

`--bundle` points to the **sealed capture directory**, not an existing report directory:

```bash
python tools/offline_qa.py --seconds 180 -- python -m hp437b.report_delivery export \
  --bundle output/reports/pdf-suite-capture \
  --output output/reports/pdf-suite-report-again --package --no-plots
```

This detects a supported workflow/suite, revalidates native saved results and provenance, and publishes to a new directory. It does not need the original editable profile. Existing workflow `report --pdf`/`report --package` commands provide the same optional delivery.

The report-only command returns 0 on successful publication even when the recorded test failed or was interrupted. New-capture commands retain their existing execution/criteria exit codes. Missing dependencies, invalid input, output collisions, PDF/layout errors, and archive/storage failures return 2.

## Portable contents and verification

Extract the entire ZIP into a fresh directory. Open `report/report.pdf` for the summary, or `report/report.html` for navigation. PDF links to individual reports and HTML links to detail/plots remain relative after relocation.

| Archive path | Contents |
| --- | --- |
| `START-HERE.txt` | Reading and verification instructions |
| `report/` | Complete sealed report bundle, including PDFs, HTML, JSON, provenance, font notices, and child reports |
| `evidence/` | Unmodified sealed capture bundle, including native CSV/session files, controls, profile snapshots, and child captures |
| `package-manifest.json` | Run identity, root inventory hashes, and SHA-256/size for every payload entry |

Provenance evidence IDs remain relative to their original capture roots. For suites, individual reports correspond to `evidence/captures/WF-04/` etc. No private certificate path or URL in a fact is dereferenced or copied automatically. A package includes only inventoried report/capture files; no repository, credentials, host configuration, or unrelated files are collected.

Verify without extraction, using the base package; the PDF extra is not needed:

```bash
python -m hp437b.report_delivery verify --package output/reports/pdf-suite-report.zip
```

Verification checks bounded regular-file paths/types/sizes, duplicate/case-colliding names, SHA-256 entries, root inventory membership, and run identity. It neither executes archive content nor authenticates an author/device. Before packaging, source loaders also rederive results/provenance and check the report/capture identities and source hashes. Hashes establish consistency, not calibration or DUT accuracy.

A report already containing sealed PDFs can be packaged without re-rendering:

```bash
python tools/offline_qa.py -- python -m hp437b.report_delivery package \
  --bundle output/reports/pdf-suite-capture \
  --report output/reports/pdf-suite-report \
  --output output/reports/pdf-suite-copy.zip
```

ZIP creation uses temporary storage and atomic no-overwrite publication. Inputs are rechecked before the final ZIP appears, including changes during copying. No ZIP can be nested inside its report/evidence directories. Payloads are bounded to 256 MiB; existing per-file/bundle import limits also apply. Fixed entry order, timestamps, and permissions make identical payloads reproducible in the tested environment.

## PDF content, provenance, and limitations

PDFs use validated structured results, not HTML parsing or arbitrary templates. Generated local PNG plots can be embedded; no URL/browser/resource fetch is used. Sheets retain DUT/operator/time/conditions, signed pre-RF zero without subtraction, measured values and plane, coverage/decisions, final controls/restoration, supplied limits, and Equipment → Report Harness → Record footer. Full metadata/criteria/corrections and technical evidence remain in JSON/provenance/appendices. Missing data and skipped tests remain unavailable, not zero or PASS.

PDF metadata records renderer/version, Letter size, one-page count, and invariant generation. Embedded Bitstream Vera fonts carry their complete upstream notice in PDF Subject metadata and `font-license.txt`. No publisher manual is modified or included by this feature. Characters outside the embedded font's coverage fail clearly rather than disappearing. Content that cannot fit the one-page layout also fails; capture evidence is preserved and can be re-reported as HTML or to a new report target.

The existing semantic-tag/development-commit Report Harness policy remains in force. Full commit/source hashes are retained in producer metadata. Invariant PDF file dates/IDs support reproducibility; the actual test time is the recorded UTC value printed in the body and saved in evidence. A portable package contains the captured identities/operator as supplied/recorded; use local profile copies for private information.

Reports seal before their sibling ZIP is created. A PDF/rendering error leaves an unsealed report and preserves the capture. A ZIP error leaves the already sealed PDF/HTML reports usable; retry only `package` to a new ZIP path. Temporary archives are removed on failure. No report/storage failure causes acquisition, control cleanup, or software recovery to be retried.

## Validation scope

[Validation results](../VALIDATION.md) distinguish PROFILE-01/SUITE-01 CI from PDF-export tests. Coverage includes real PDF parsing/page counts/metadata/embedded fonts, relative links, Unicode/text escaping, absent optional dependencies before capture, complete/failed/empty runs, immutable sources, legacy fixtures, relocated archives and provenance, byte reproducibility, corruption/path/type/duplicate checks, concurrent-change refusal, storage failures, and installed-wheel operation with and without the PDF extra. `requirements-pdf-test.lock` pins the test-only parser; it is not a runtime dependency.

This accepts offline PDF/delivery software behavior. It does not add physical workflow or backend support, change normal logging, or enable AI/provider automation.
