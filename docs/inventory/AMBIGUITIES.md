# Source ambiguities and implementation questions

Reviewed November 11, 2026. These are explicit source conflicts or qualification questions. Inventory completion establishes their provenance and boundaries. Resolution belongs to focused Phase 2 research or separately authorized Phase 3 bench work. Each item remains open until its required evidence is recorded.

## A01

Identification spelling and framing. Table 3-5 (00437-90047, printed 3-41/PDF 71) lists `ID` and `IDN?`; §3-21 (printed 3-33/PDF 63) names `*IDN?`. All three are inventoried as documented spellings. Test each on the actual firmware, record raw response spacing/termination, and establish what the next unqualified read returns. Prefer the detailed `*IDN?` spelling as the first candidate, with a timeout/recovery plan. The [November 11 Mac capture](../validation/MAC-20261111.md) returned `HEWLETT-PACKARD,437B,,1.8` plus CRLF through the pinned backend. This establishes C055 on that setup; aliases and next ordinary-read behavior remain untested, so A01 remains open.

## A02

Legacy binary versus ASCII framing. §3-21 Learn Mode (printed 3-32/PDF 62) explicitly invokes `LP2` and returns ASCII `@2` plus58 binary bytes; Table 3-5 lists bare `LP`. Restore uses that captured binary message. Treat the58 bytes as opaque because their field offsets are unspecified. Resolve bare-LP acceptance and exact restore framing with a backed-up known snapshot.

The service-mask prose (§3-29, printed 3-37/PDF 67) describes ASCII values for `@1`/RV, but the HP BASIC require-service example (§3-12, printed 3-22/PDF 52) uses `USING "2A,B";"@1",4`, a binary mask byte. §3-34 (printed 3-40/PDF 70) says service-mask value1byte/EOI while separately specifying three ASCII digits/CRLF for *SRE?. Preserve distinct APIs until raw captures establish RV versus *SRE? and @1 versus *SRE behavior. Read timeout recovery and arbitrary binary CR/LF handling also need qualification.

## A03

Sensor-table syntax and traversal. Table 3-5 footnote2 (printed 3-42/PDF 72) says six ID characters; Sensor Data remote procedure (printed 3-87/PDF 117) and upload example (3-89/PDF 119) specify up to seven. AppendixA-4/PDF 154 describes ID error88 with1–9/A–Z, while the detailed procedure permits0–9/A–Z/underscore. Record six/seven/short-label behavior and case rules using a backed-up spare table.

Summary footnotes mark CTn/ETn as requiring numeric entry/EN; detailed procedure and upload examples send CTn/ETn directly. RF explicitly accepts % or EN; support for PCT on RF is less explicit. ET requires frequency-unit plus percent-factor plus EN per pair, then EX. Verify table-specific numeric domains, ties/rounding, remote deletion, retained REF CF after remote clear, and full-table behavior before destructive editing.

The read-table example (printed 3-90–92/PDF 120–122) uses RFnOD, ETn, OD, and EN rather than a dedicated table query. It allocates14 display characters and uses fixed-position fields. Determine raw OD framing, end-of-table indication, displayed-unit cases, and any data changes caused by traversal. A source-backed traversal workflow is inventoried; a production parser requires those captures.

## A04

Conflicting overview values and examples. Supplemental Table 1-2 (printed 1-9/PDF 19) gives CAL reference range50–150%, while detailed CAL (printed 3-46/PDF 76) and error56 (A-3/PDF 153) specify50–120%. Use50–120% as the documented candidate domain and retain the conflict.

The same overview prints linear resolution3 as0.001%, while detailed RESOLN (printed 3-80/PDF 110) specifies0.01%. Use the detailed mapping, corroborated by the logarithmic progression. CAL FAC example prose says99% but sends `KB99.9%` (printed 3-51/PDF 81); interpret the literal command as99.9%, and generate examples with matching prose. Frequency entry allows up to999.9999GHz as a correction-table lookup, while the actual sensor bandwidth remains a separate physical limit.

## A05

Reset/self-test/menu scope. Table 3-5 (printed 3-42/PDF 72) lists *RST as soft reset and *TST? as self-test query. Detailed SPECIAL text says SELF TEST and INIT have no remote procedure (printed 3-99–100/PDF 129–130). Inventory the summary commands while keeping execution semantics, result formats, persistence, and equivalence to PR/INIT uncertain. Resolve through authoritative firmware-specific documentation or controlled tests with backed-up configuration/calibration context before exposing destructive actions.

SP remote description (printed 3-97/PDF 127) refers to a desired function and parameters, but gives no complete remote selector grammar. Its direct-command alternatives and physical exclusions constrain usage. Special status has no direct remote procedure (3-98/PDF 128); SM supplies some status fields. Avoid assuming SP can bypass the local-only address, self-test, or INIT restrictions.

## A06

Status lifecycle and error selection. §3-30 explicitly distinguishes non-clearing *STB? from serial polling. §3-31 describes *ESR? output but does not explicitly establish read-clear behavior in the supplied text. *CLS names all status registers, with enable-mask persistence unspecified. ERR? has a summary/format entry but lacks detailed selection/queue semantics. *ESE is a weighted-byte mask; exact accepted mask domain/framing and reserved-bit handling need qualification. Verify each behavior with controlled errors, repeated reads, and recorded masks. AppendixA-1/PDF 151 adds SM error-latch side effects beyond the simpler status summary.

## A07

Display aliases and user text boundaries. Table 3-5 printed 3-41/PDF 71 lists DD/DF and limits DD to firmware1.5+. Detailed Display (3-53–54/PDF 83–84) describes DD but omits DF. Test per-firmware aliases. DU permits up to12 alphanumeric/space characters but leaves exact short-message boundaries and command concatenation unclear. Use bounded standalone messages while qualifying raw transport framing.

## A08

Filter rounding and settling. Filter remote procedure (printed 3-63/PDF 93) specifies nearest legal binary count but leaves tie/out-of-domain rounding unclear. Table 1-3 (printed 1-10/PDF 20) lists conditional settling characteristics, not an unconditional logger rate. Validate selected filter behavior and settling under the actual sensor/range/resolution. TR2 allows internal settling and explicitly excludes sensor settling (printed 3-104/PDF 134).

## A09

Adapter/backend bus coverage. [GPIB transport profiles](GPIB.md#transport-evidence-profiles) identify released PyVISA-py 0.8.1 gaps for explicit REN/local control, serial status byte, bus trigger, device clear, raw bus/IFC operations, and uncertain SRQ event/parallel-poll support. Automatic REN assertion at USBTMC initialization is a separate observed source implementation. These are source findings, not bench failures. Phase 2 must select a released solution or an explicit, versioned fix for required operations; Phase 3 must prove actual behavior. ASCII trigger and status queries provide useful candidates but preserve their different semantics.

The [automatic-local extension](../validation/AUTOMATIC-LOCAL.md) addresses G008 for the identified adapter using its advertised USB488 support over the exact pinned session. This does not enable native VISA control_ren, REN deassertion, lockout clearing, serial polling, clear, GET, or SRQ. A09 remains open for those operations and any required physical/host cases.
