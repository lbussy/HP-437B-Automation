# HP 437B Automation

Use this repository for HP 437B/8482A control and logging work. Start with README.md, docs/PLAN.md, docs/OPEN-WORK.md, and docs/VALIDATION.md. CONTRIBUTING.md defines repository conventions.

## Current state

This is a planning/documentation repository. USBGpib V2 is recommended, and Python/PyVISA/PyVISA-py is provisional. No purchase, logger, device connection, or hardware qualification is established. Read current records before proceeding. Distinguish user decisions, assistant proposals, software tests, and physical bench evidence.

## Equipment references

Unmodified publisher manuals are in output/pdf/hp-437b-8482a/. Consult the operating manual for commands and procedures, service manual for service/performance work, and sensor manual plus the individual sensor label/certificate for limits and calibration factors. Do not assume modern SCPI syntax. Preserve publisher originals and original manifests. Annotations, OCR, and previews are derived files.

## Working practices

Use ignored tmp/ or temp/ for scratch files. Do not commit credentials, raw local measurements, or local tool state. Use Oxford commas. Keep plans and open tasks current, and check Markdown links and git diff --check after edits. Do not claim backend or host support until required hardware checks pass.

Keep original work under LICENSE and preserve third-party notices. Do not create a remote, push, or publish without user authorization. Generic Radio Stuff retains historical source imports; this project owns the active HP plan and backlog. Do not copy private chat exports here or publish them incidentally.
