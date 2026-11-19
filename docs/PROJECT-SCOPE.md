# Current project scope

Build automated measurement/test workflows using the HP 437B and its sensor, with traceable equipment provenance, deterministic reports, and agent-assisted analysis of the equipment under test.

Human-started operation is the selected mode. The implemented interface covers POWER REF workflows, guided transmitter captures, explicit meter preparation, saved-run reports/history, portable packages, and optional supplied-limit assessments. WF-04–WF-06 also have synthetic/shared-fake implementations. AI/provider automation is deferred; automatic radio/supply drivers are optional.

Software implementation, host/device interaction, and measurement accuracy are separate questions. Use software tests for workflow correctness, named current-equipment checks for hardware compatibility, and applicable calibration/fixture evidence for measurement claims. Synthetic results remain explicitly synthetic.

Current meter identity/calibration are in [equipment](EQUIPMENT.md). Project interaction checks on that meter remain pending. Equipment onboarding does not require blanket repetition of every software test or block software development. Only perform hardware work selected for actual use, with recorded setup, finite budgets, and operator supervision.

The [plan](PLAN.md), [open work](OPEN-WORK.md), and [validation guide](VALIDATION.md) define the current boundaries. No extra POWER REF feature or automatic-driver requirement is implied by the remaining physical-use opportunities.
