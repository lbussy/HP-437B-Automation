# Offline command and parameter coverage

Software-only audit at baseline `9d84059cb7778cbd87f505159df52521003dca8a`; runtime source remains identical to `d399dcfe5366dce9bce327c42e922d692ecd92c4`. The registry reconciles **118 C IDs: 78 encodable, 40 guarded**. Encodable includes eleven contextual helpers and two polling-dependent procedures; it does not mean 78 independently executable operations. The twenty G IDs comprise three byte paths, one conditional GTL path, fifteen normal-API deferrals (including experimental clear), and one C0 exclusion.

Each source link below gives the exact publisher-manual page, prerequisites, state/completion rules, syntax, and future physical case. Those fields are incorporated by reference rather than reinterpreted. See the [physical matrix](../inventory/COVERAGE.md), whose host columns are unchanged. No synthetic case promotes hardware acceptance.

## Test and API key

- **L**: literal no-argument cases in [command tests](../../tests/test_commands.py); each rejects extra arguments through the encoder's common path. Output selections use `Instrument.query`; W actions use `Instrument.command` except the special cases below.
- **N**: decimal boundaries/grid/invalid types and all CL/KB/DY terminators in [parameter tests](../../tests/test_offline_parameters.py); original literal interior cases remain. Finite register/sensor/resolution/range domains and enable-mask candidate domains through 256 are enumerated. FM's ten legal values and all other candidates 1–512 are classified. Decimal/frequency domains are sampled boundaries, not exhaustive.
- **F**: all four frequency scales, both endpoints, original interiors, and zero rejection in the parameter tests. Frequency selection is a lookup domain, not sensor bandwidth qualification.
- **D**: DU has literal, all lengths 1–12, empty/13-character, invalid type, and character/injection rejection cases; all possible 12-character strings are not enumerated.
- **H**: contextual codec only: EN, four unit suffixes, two percent suffixes, and four cursor codes. [Instrument tests](../../tests/test_instrument.py) reject standalone dispatch; complete menu/table workflows remain deferred.
- **P**: CL/ZE procedures use `calibrate`/`zero`, confirmation plus actual polling method/capability, tested with scripted poll fakes; production serial polling stays guarded. No calibration/zero occurs here.
- **Q**: typed parsing/transaction cases in instrument/protocol tests; new [finite reply-field tests](../../tests/test_offline_protocol.py) and opt-in [parser campaign](../../tests/test_offline_stress.py). OD remains bounded ASCII display text; opaque LP2 payload bytes are preserved, not decoded.
- **G**: all forty encode guards plus public dispatch rejection before a scripted transport in the parameter tests. Guard reasons are asserted by existing codec tests. Some public dispatch rejects operation kind before ambiguity; no test weakens either boundary.
- **T**: [transport tests](../../tests/test_transport.py), [failed-transfer tests](../../tests/test_offline_worker.py), and real-IPC stress cover completion/status/size/late/error/no-replay/disposal. [USB488 tests](../../tests/test_usb488.py) use explicit fake transfers. [Clear tests](../../tests/test_usbtmc_clear.py) cover the guarded experimental helper only.

DD needs identified firmware 1.5+, tested at the driver gate. PR/RC/ST/OC1/RFn require `confirmed=True`; cursor/entry helpers need context; TR1/TR2 use acquisition APIs; scale/REL establishes units. Existing [instrument tests](../../tests/test_instrument.py) cover transaction locking, missing polling, confirmation, firmware, unknown units, uncertain-state reuse, and no post-fault I/O. Not every parameter has every invalid type/arity and cross-setting combination tested: these are explicit residual gaps, not claims of completeness.

## Commands

All numeric rows refer to supported exact-grid software domains; ambiguous rounding/legacy aliases remain in the [ambiguity register](../inventory/AMBIGUITIES.md). For each row, future physical behavior and cross-setting interactions remain unqualified except the separately recorded named physical cases.

| ID / code / source | Parameters and framing from inventory | Layer and tests | Additional limitation |
| --- | --- | --- | --- |
| [C001 `CL`](../inventory/COMMANDS.md#c001) | 50.0–120.0 percent; EN, %, or PCT terminates. CLEN reuses the last value. | N/P | Production polling unavailable; procedure fake-tested only |
| [C002 `*CLS`](../inventory/COMMANDS.md#c002) | None. | L | Finite literal/fixture coverage; physical effects pending |
| [C003 `CS`](../inventory/COMMANDS.md#c003) | None. | L | Finite literal/fixture coverage; physical effects pending |
| [C004 `CT0`](../inventory/COMMANDS.md#c004) | The trailing digit selects table 0–9; detailed procedure uses CTn without EN. Summary footnote differs. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C005 `CT1`](../inventory/COMMANDS.md#c005) | The trailing digit selects table 0–9; detailed procedure uses CTn without EN. Summary footnote differs. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C006 `CT2`](../inventory/COMMANDS.md#c006) | The trailing digit selects table 0–9; detailed procedure uses CTn without EN. Summary footnote differs. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C007 `CT3`](../inventory/COMMANDS.md#c007) | The trailing digit selects table 0–9; detailed procedure uses CTn without EN. Summary footnote differs. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C008 `CT4`](../inventory/COMMANDS.md#c008) | The trailing digit selects table 0–9; detailed procedure uses CTn without EN. Summary footnote differs. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C009 `CT5`](../inventory/COMMANDS.md#c009) | The trailing digit selects table 0–9; detailed procedure uses CTn without EN. Summary footnote differs. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C010 `CT6`](../inventory/COMMANDS.md#c010) | The trailing digit selects table 0–9; detailed procedure uses CTn without EN. Summary footnote differs. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C011 `CT7`](../inventory/COMMANDS.md#c011) | The trailing digit selects table 0–9; detailed procedure uses CTn without EN. Summary footnote differs. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C012 `CT8`](../inventory/COMMANDS.md#c012) | The trailing digit selects table 0–9; detailed procedure uses CTn without EN. Summary footnote differs. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C013 `CT9`](../inventory/COMMANDS.md#c013) | The trailing digit selects table 0–9; detailed procedure uses CTn without EN. Summary footnote differs. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C014 `DA`](../inventory/COMMANDS.md#c014) | None. | L | Finite literal/fixture coverage; physical effects pending |
| [C015 `DC0`](../inventory/COMMANDS.md#c015) | 0 disables; 1 enables using last entered duty percentage. | L | Finite literal/fixture coverage; physical effects pending |
| [C016 `DC1`](../inventory/COMMANDS.md#c016) | 0 disables; 1 enables using last entered duty percentage. | L | Finite literal/fixture coverage; physical effects pending |
| [C017 `DD`](../inventory/COMMANDS.md#c017) | DD: firmware 1.5 or later according to summary; DF listed as disable alias. | L | Identified firmware 1.5+ required; alias DF guarded |
| [C018 `DF`](../inventory/COMMANDS.md#c018) | DD: firmware 1.5 or later according to summary; DF listed as disable alias. | Guard / G | A07: undocumented detailed firmware alias |
| [C019 `DE`](../inventory/COMMANDS.md#c019) | None. | L | Finite literal/fixture coverage; physical effects pending |
| [C020 `DN`](../inventory/COMMANDS.md#c020) | DN/UP change selected digit/value; LT/RT move selected digit. Context-sensitive. | L/H | Context required; no standalone driver operation |
| [C021 `LT`](../inventory/COMMANDS.md#c021) | DN/UP change selected digit/value; LT/RT move selected digit. Context-sensitive. | L/H | Context required; no standalone driver operation |
| [C022 `RT`](../inventory/COMMANDS.md#c022) | DN/UP change selected digit/value; LT/RT move selected digit. Context-sensitive. | L/H | Context required; no standalone driver operation |
| [C023 `UP`](../inventory/COMMANDS.md#c023) | DN/UP change selected digit/value; LT/RT move selected digit. Context-sensitive. | L/H | Context required; no standalone driver operation |
| [C024 `DU`](../inventory/COMMANDS.md#c024) | Up to 12 characters from 0–9, A–Z, and spaces; message-boundary parsing needs verification. | D | Finite literal/fixture coverage; physical effects pending |
| [C025 `DY`](../inventory/COMMANDS.md#c025) | 0.001–99.999%; EN, %, or PCT terminates. | N | Sampled numeric domain; cross-setting cases pending |
| [C026 `EN`](../inventory/COMMANDS.md#c026) | Commits the active numeric entry or advances a SPECIAL/table entry; bare EN reuses the current value where described. | L/H | Context required; no standalone driver operation |
| [C027 `ERR?`](../inventory/COMMANDS.md#c027) | None in summary. | L/Q | Finite literal/fixture coverage; physical effects pending |
| [C028 `*ESR?`](../inventory/COMMANDS.md#c028) | None. | L/Q | Finite literal/fixture coverage; physical effects pending |
| [C029 `*ESE`](../inventory/COMMANDS.md#c029) | ASCII weighted 8-bit mask; usable event bits 128,32,16,8. No EN is specified for this setter in summary. | N | Sampled numeric domain; cross-setting cases pending |
| [C030 `*ESE?`](../inventory/COMMANDS.md#c030) | None. | L/Q | Finite literal/fixture coverage; physical effects pending |
| [C031 `ET0`](../inventory/COMMANDS.md#c031) | n=0–9; 40 pairs for 0–7, 80 for 8–9. Frequencies use HZ/KZ/MZ/GZ; factors use %. Follow FR/KB domains pending confirmation of table-entry-specific limits. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C032 `ET1`](../inventory/COMMANDS.md#c032) | n=0–9; 40 pairs for 0–7, 80 for 8–9. Frequencies use HZ/KZ/MZ/GZ; factors use %. Follow FR/KB domains pending confirmation of table-entry-specific limits. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C033 `ET2`](../inventory/COMMANDS.md#c033) | n=0–9; 40 pairs for 0–7, 80 for 8–9. Frequencies use HZ/KZ/MZ/GZ; factors use %. Follow FR/KB domains pending confirmation of table-entry-specific limits. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C034 `ET3`](../inventory/COMMANDS.md#c034) | n=0–9; 40 pairs for 0–7, 80 for 8–9. Frequencies use HZ/KZ/MZ/GZ; factors use %. Follow FR/KB domains pending confirmation of table-entry-specific limits. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C035 `ET4`](../inventory/COMMANDS.md#c035) | n=0–9; 40 pairs for 0–7, 80 for 8–9. Frequencies use HZ/KZ/MZ/GZ; factors use %. Follow FR/KB domains pending confirmation of table-entry-specific limits. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C036 `ET5`](../inventory/COMMANDS.md#c036) | n=0–9; 40 pairs for 0–7, 80 for 8–9. Frequencies use HZ/KZ/MZ/GZ; factors use %. Follow FR/KB domains pending confirmation of table-entry-specific limits. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C037 `ET6`](../inventory/COMMANDS.md#c037) | n=0–9; 40 pairs for 0–7, 80 for 8–9. Frequencies use HZ/KZ/MZ/GZ; factors use %. Follow FR/KB domains pending confirmation of table-entry-specific limits. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C038 `ET7`](../inventory/COMMANDS.md#c038) | n=0–9; 40 pairs for 0–7, 80 for 8–9. Frequencies use HZ/KZ/MZ/GZ; factors use %. Follow FR/KB domains pending confirmation of table-entry-specific limits. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C039 `ET8`](../inventory/COMMANDS.md#c039) | n=0–9; 40 pairs for 0–7, 80 for 8–9. Frequencies use HZ/KZ/MZ/GZ; factors use %. Follow FR/KB domains pending confirmation of table-entry-specific limits. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C040 `ET9`](../inventory/COMMANDS.md#c040) | n=0–9; 40 pairs for 0–7, 80 for 8–9. Frequencies use HZ/KZ/MZ/GZ; factors use %. Follow FR/KB domains pending confirmation of table-entry-specific limits. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C041 `EX`](../inventory/COMMANDS.md#c041) | None. | L | Finite literal/fixture coverage; physical effects pending |
| [C042 `FA`](../inventory/COMMANDS.md#c042) | None. | L | Finite literal/fixture coverage; physical effects pending |
| [C043 `FH`](../inventory/COMMANDS.md#c043) | None. | L | Finite literal/fixture coverage; physical effects pending |
| [C044 `FM`](../inventory/COMMANDS.md#c044) | Binary progression 1,2,4,8,16,32,64,128,256,512; other entries rounded to nearest permitted count. Tie/out-of-domain handling unresolved. | N | Sampled numeric domain; cross-setting cases pending |
| [C045 `FR`](../inventory/COMMANDS.md#c045) | 0.0001–999.9999 GHz, 100 kHz resolution. Units HZ/KZ/MZ/GZ terminate frequency. | F | Sampled numeric domain; cross-setting cases pending |
| [C046 `GT0`](../inventory/COMMANDS.md#c046) | 0 ignore GET; 1 apply TR1 behavior; 2 apply TR2 behavior. | L | Finite literal/fixture coverage; physical effects pending |
| [C047 `GT1`](../inventory/COMMANDS.md#c047) | 0 ignore GET; 1 apply TR1 behavior; 2 apply TR2 behavior. | L | Finite literal/fixture coverage; physical effects pending |
| [C048 `GT2`](../inventory/COMMANDS.md#c048) | 0 ignore GET; 1 apply TR1 behavior; 2 apply TR2 behavior. | L | Finite literal/fixture coverage; physical effects pending |
| [C049 `GZ`](../inventory/COMMANDS.md#c049) | GHz, Hz, kHz, MHz respectively; suffix terminates FR frequency or ET frequency component. | F/H | Context required; no standalone driver operation |
| [C050 `HZ`](../inventory/COMMANDS.md#c050) | GHz, Hz, kHz, MHz respectively; suffix terminates FR frequency or ET frequency component. | F/H | Context required; no standalone driver operation |
| [C051 `KZ`](../inventory/COMMANDS.md#c051) | GHz, Hz, kHz, MHz respectively; suffix terminates FR frequency or ET frequency component. | F/H | Context required; no standalone driver operation |
| [C052 `MZ`](../inventory/COMMANDS.md#c052) | GHz, Hz, kHz, MHz respectively; suffix terminates FR frequency or ET frequency component. | F/H | Context required; no standalone driver operation |
| [C053 `ID`](../inventory/COMMANDS.md#c053) | ID and IDN? appear in Table 3-5; *IDN? appears in §3-21. | Guard / G | A01: identification alias awaits firmware evidence; use *IDN? candidate |
| [C054 `IDN?`](../inventory/COMMANDS.md#c054) | ID and IDN? appear in Table 3-5; *IDN? appears in §3-21. | Guard / G | A01: identification alias awaits firmware evidence; use *IDN? candidate |
| [C055 `*IDN?`](../inventory/COMMANDS.md#c055) | ID and IDN? appear in Table 3-5; *IDN? appears in §3-21. | L/Q | Finite literal/fixture coverage; physical effects pending |
| [C056 `KB`](../inventory/COMMANDS.md#c056) | 1.0–150.0%; 0.1% resolution, remote entry rounded; EN, %, or PCT terminates. | N | Sampled numeric domain; cross-setting cases pending |
| [C057 `LG`](../inventory/COMMANDS.md#c057) | LG log; LN linear. | L | Finite literal/fixture coverage; physical effects pending |
| [C058 `LN`](../inventory/COMMANDS.md#c058) | LG log; LN linear. | L | Finite literal/fixture coverage; physical effects pending |
| [C059 `LH`](../inventory/COMMANDS.md#c059) | −299.999 to +299.999 dBm. | N | Sampled numeric domain; cross-setting cases pending |
| [C060 `LL`](../inventory/COMMANDS.md#c060) | −299.999 to +299.999 dBm. | N | Sampled numeric domain; cross-setting cases pending |
| [C061 `LM0`](../inventory/COMMANDS.md#c061) | 0 disable; 1 enable with existing thresholds. | L | Finite literal/fixture coverage; physical effects pending |
| [C062 `LM1`](../inventory/COMMANDS.md#c062) | 0 disable; 1 enable with existing thresholds. | L | Finite literal/fixture coverage; physical effects pending |
| [C063 `LP`](../inventory/COMMANDS.md#c063) | LP summary; LP2 detailed invocation. Use LP2 as documented candidate while testing bare LP. | Guard / G | A02: ambiguous legacy framing/restore requires evidence |
| [C064 `LP2`](../inventory/COMMANDS.md#c064) | LP summary; LP2 detailed invocation. Use LP2 as documented candidate while testing bare LP. | L/Q | Finite literal/fixture coverage; physical effects pending |
| [C065 `OC0`](../inventory/COMMANDS.md#c065) | 0 off; 1 on. | L | Finite literal/fixture coverage; physical effects pending |
| [C066 `OC1`](../inventory/COMMANDS.md#c066) | 0 off; 1 on. | L | Finite literal/fixture coverage; physical effects pending |
| [C067 `OD`](../inventory/COMMANDS.md#c067) | None. | L/Q | Finite literal/fixture coverage; physical effects pending |
| [C068 `OF0`](../inventory/COMMANDS.md#c068) | 0 disable; 1 enable using last offset. | L | Finite literal/fixture coverage; physical effects pending |
| [C069 `OF1`](../inventory/COMMANDS.md#c069) | 0 disable; 1 enable using last offset. | L | Finite literal/fixture coverage; physical effects pending |
| [C070 `OS`](../inventory/COMMANDS.md#c070) | −99.99 to +99.99 dB, step0.01 dB. | N | Sampled numeric domain; cross-setting cases pending |
| [C071 `PCT`](../inventory/COMMANDS.md#c071) | Alternative to EN for CL, KB, DY; table RF and factor syntax described in Sensor Data. | L/H | Context required; no standalone driver operation |
| [C072 `%`](../inventory/COMMANDS.md#c072) | Alternative to EN for CL, KB, DY; table RF and factor syntax described in Sensor Data. | L/H | Context required; no standalone driver operation |
| [C073 `PR`](../inventory/COMMANDS.md#c073) | None. | L | Finite literal/fixture coverage; physical effects pending |
| [C074 `RA`](../inventory/COMMANDS.md#c074) | None. | L | Finite literal/fixture coverage; physical effects pending |
| [C075 `RC`](../inventory/COMMANDS.md#c075) | Integer register0–10; error54 for invalid register. | N | Sampled numeric domain; cross-setting cases pending |
| [C076 `RE`](../inventory/COMMANDS.md#c076) | n=1,2,3: log0.1/0.01/0.001 dB; linear1/0.1/0.01% full scale. | N | Sampled numeric domain; cross-setting cases pending |
| [C077 `RF0`](../inventory/COMMANDS.md#c077) | Table digit0–9 immediately followed by factor50.0–120.0%; % or EN in detailed procedure. RFnOD accesses displayed value in read example. | N | Sampled numeric domain; cross-setting cases pending |
| [C078 `RF1`](../inventory/COMMANDS.md#c078) | Table digit0–9 immediately followed by factor50.0–120.0%; % or EN in detailed procedure. RFnOD accesses displayed value in read example. | N | Sampled numeric domain; cross-setting cases pending |
| [C079 `RF2`](../inventory/COMMANDS.md#c079) | Table digit0–9 immediately followed by factor50.0–120.0%; % or EN in detailed procedure. RFnOD accesses displayed value in read example. | N | Sampled numeric domain; cross-setting cases pending |
| [C080 `RF3`](../inventory/COMMANDS.md#c080) | Table digit0–9 immediately followed by factor50.0–120.0%; % or EN in detailed procedure. RFnOD accesses displayed value in read example. | N | Sampled numeric domain; cross-setting cases pending |
| [C081 `RF4`](../inventory/COMMANDS.md#c081) | Table digit0–9 immediately followed by factor50.0–120.0%; % or EN in detailed procedure. RFnOD accesses displayed value in read example. | N | Sampled numeric domain; cross-setting cases pending |
| [C082 `RF5`](../inventory/COMMANDS.md#c082) | Table digit0–9 immediately followed by factor50.0–120.0%; % or EN in detailed procedure. RFnOD accesses displayed value in read example. | N | Sampled numeric domain; cross-setting cases pending |
| [C083 `RF6`](../inventory/COMMANDS.md#c083) | Table digit0–9 immediately followed by factor50.0–120.0%; % or EN in detailed procedure. RFnOD accesses displayed value in read example. | N | Sampled numeric domain; cross-setting cases pending |
| [C084 `RF7`](../inventory/COMMANDS.md#c084) | Table digit0–9 immediately followed by factor50.0–120.0%; % or EN in detailed procedure. RFnOD accesses displayed value in read example. | N | Sampled numeric domain; cross-setting cases pending |
| [C085 `RF8`](../inventory/COMMANDS.md#c085) | Table digit0–9 immediately followed by factor50.0–120.0%; % or EN in detailed procedure. RFnOD accesses displayed value in read example. | N | Sampled numeric domain; cross-setting cases pending |
| [C086 `RF9`](../inventory/COMMANDS.md#c086) | Table digit0–9 immediately followed by factor50.0–120.0%; % or EN in detailed procedure. RFnOD accesses displayed value in read example. | N | Sampled numeric domain; cross-setting cases pending |
| [C087 `RH`](../inventory/COMMANDS.md#c087) | None; captures current range. | L | Finite literal/fixture coverage; physical effects pending |
| [C088 `RL0`](../inventory/COMMANDS.md#c088) | 0 off; 1 use current displayed value as new reference; 2 reuse previous reference. | L | Finite literal/fixture coverage; physical effects pending |
| [C089 `RL1`](../inventory/COMMANDS.md#c089) | 0 off; 1 use current displayed value as new reference; 2 reuse previous reference. | L | Finite literal/fixture coverage; physical effects pending |
| [C090 `RL2`](../inventory/COMMANDS.md#c090) | 0 off; 1 use current displayed value as new reference; 2 reuse previous reference. | L | Finite literal/fixture coverage; physical effects pending |
| [C091 `RM`](../inventory/COMMANDS.md#c091) | n=0–5; 0 auto, 1 most sensitive through5 least. Sensor power limits govern actual input. | N | Sampled numeric domain; cross-setting cases pending |
| [C092 `*RST`](../inventory/COMMANDS.md#c092) | None listed. | Guard / G | A05: reset/self-test/menu effects require evidence |
| [C093 `RV`](../inventory/COMMANDS.md#c093) | None. | Guard / G | A02: ambiguous legacy framing/restore requires evidence |
| [C094 `SE`](../inventory/COMMANDS.md#c094) | n=0–9. | N | Sampled numeric domain; cross-setting cases pending |
| [C095 `SM`](../inventory/COMMANDS.md#c095) | None. | L/Q | Finite literal/fixture coverage; physical effects pending |
| [C096 `SN0`](../inventory/COMMANDS.md#c096) | Table 0–9 then label0–9/A–Z/underscore; detailed max7 characters, summary footnote6. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C097 `SN1`](../inventory/COMMANDS.md#c097) | Table 0–9 then label0–9/A–Z/underscore; detailed max7 characters, summary footnote6. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C098 `SN2`](../inventory/COMMANDS.md#c098) | Table 0–9 then label0–9/A–Z/underscore; detailed max7 characters, summary footnote6. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C099 `SN3`](../inventory/COMMANDS.md#c099) | Table 0–9 then label0–9/A–Z/underscore; detailed max7 characters, summary footnote6. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C100 `SN4`](../inventory/COMMANDS.md#c100) | Table 0–9 then label0–9/A–Z/underscore; detailed max7 characters, summary footnote6. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C101 `SN5`](../inventory/COMMANDS.md#c101) | Table 0–9 then label0–9/A–Z/underscore; detailed max7 characters, summary footnote6. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C102 `SN6`](../inventory/COMMANDS.md#c102) | Table 0–9 then label0–9/A–Z/underscore; detailed max7 characters, summary footnote6. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C103 `SN7`](../inventory/COMMANDS.md#c103) | Table 0–9 then label0–9/A–Z/underscore; detailed max7 characters, summary footnote6. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C104 `SN8`](../inventory/COMMANDS.md#c104) | Table 0–9 then label0–9/A–Z/underscore; detailed max7 characters, summary footnote6. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C105 `SN9`](../inventory/COMMANDS.md#c105) | Table 0–9 then label0–9/A–Z/underscore; detailed max7 characters, summary footnote6. | Guard / G | A03: table clear/edit/label framing awaits resolution |
| [C106 `SP`](../inventory/COMMANDS.md#c106) | SPECIAL function selection and necessary parameters; local menu0 status,1 sensor data,2 limits,3 filter,4 address,5 self-test,6 INIT. Remote domain is bounded by explicit exclusions. | Guard / G | A05: reset/self-test/menu effects require evidence |
| [C107 `*SRE`](../inventory/COMMANDS.md#c107) | ASCII integer0–255; explicit mask byte framing differs from @1 binary example. | N | Sampled numeric domain; cross-setting cases pending |
| [C108 `*SRE?`](../inventory/COMMANDS.md#c108) | None. | L/Q | Finite literal/fixture coverage; physical effects pending |
| [C109 `ST`](../inventory/COMMANDS.md#c109) | Integer register1–10; register0 reserved for previous configuration. | N | Sampled numeric domain; cross-setting cases pending |
| [C110 `*STB?`](../inventory/COMMANDS.md#c110) | None. | L/Q | Finite literal/fixture coverage; physical effects pending |
| [C111 `TR0`](../inventory/COMMANDS.md#c111) | 0 hold; 1 immediate; 2 delayed; 3 free-run. | L | Finite literal/fixture coverage; physical effects pending |
| [C112 `TR1`](../inventory/COMMANDS.md#c112) | 0 hold; 1 immediate; 2 delayed; 3 free-run. | L | Finite literal/fixture coverage; physical effects pending |
| [C113 `TR2`](../inventory/COMMANDS.md#c113) | 0 hold; 1 immediate; 2 delayed; 3 free-run. | L | Finite literal/fixture coverage; physical effects pending |
| [C114 `TR3`](../inventory/COMMANDS.md#c114) | 0 hold; 1 immediate; 2 delayed; 3 free-run. | L | Finite literal/fixture coverage; physical effects pending |
| [C115 `*TST?`](../inventory/COMMANDS.md#c115) | None listed. | Guard / G | A05: reset/self-test/menu effects require evidence |
| [C116 `ZE`](../inventory/COMMANDS.md#c116) | No RF power at sensor; zero all5 ranges; typically5–20s sensor-dependent. | L/P | Production polling unavailable; procedure fake-tested only |
| [C117 `@1`](../inventory/COMMANDS.md#c117) | One binary mask byte in HP BASIC USING "2A,B" example; prose calls subsequent value ASCII. | Guard / G | A02: ambiguous legacy framing/restore requires evidence |
| [C118 `@2`](../inventory/COMMANDS.md#c118) | Return captured 60-byte learn message uninterrupted, EOI on final byte; no text termination. | Guard / G | A02: ambiguous legacy framing/restore requires evidence |

## Bus entries

G002 is receive at the meter (host write); G003 is send at the meter (host read). Test names use the host direction. Raw addressing/poll semantics must not be inferred from Python method names.

| ID / primary source | Software route and evidence | Remaining limit |
| --- | --- | --- |
| [G001](../inventory/GPIB.md#g001) | Instrument.bus guard before I/O | A09: explicit address control is adapter-managed; deferred |
| [G002](../inventory/GPIB.md#g002) | Host write/read/EOM contract; T | ASCII/binary fixtures only; electrical EOI/handshake requires hardware |
| [G003](../inventory/GPIB.md#g003) | Host write/read/EOM contract; T | ASCII/binary fixtures only; electrical EOI/handshake requires hardware |
| [G004](../inventory/GPIB.md#g004) | Host write/read/EOM contract; T | ASCII/binary fixtures only; electrical EOI/handshake requires hardware |
| [G005](../inventory/GPIB.md#g005) | Instrument.bus guard before I/O | A09: raw UNL deferred |
| [G006](../inventory/GPIB.md#g006) | Instrument.bus guard before I/O | A09: raw UNT deferred |
| [G007](../inventory/GPIB.md#g007) | Instrument.bus guard before I/O | A09: explicit REN deferred (automatic initialization is separate) |
| [G008](../inventory/GPIB.md#g008) | Negotiated USB488 GTL; T and instrument cleanup fakes | Named adapter/profile only; no REN/lockout/poll inference |
| [G009](../inventory/GPIB.md#g009) | Instrument.bus guard before I/O | A09: lockout deferred |
| [G010](../inventory/GPIB.md#g010) | Instrument.bus guard before I/O | A09: clear lockout deferred |
| [G011](../inventory/GPIB.md#g011) | Instrument.bus guard before I/O; experimental clear fake handshake tests (T) | A09: device clear deferred |
| [G012](../inventory/GPIB.md#g012) | Instrument.bus guard before I/O | A09: universal clear deferred |
| [G013](../inventory/GPIB.md#g013) | Instrument.bus guard before I/O | A09: GET deferred |
| [G014](../inventory/GPIB.md#g014) | Instrument.bus guard before I/O | A09: SRQ events deferred |
| [G015](../inventory/GPIB.md#g015) | Instrument.bus guard before I/O | A09: serial poll deferred |
| [G016](../inventory/GPIB.md#g016) | Instrument.bus guard before I/O | A09: explicit SPD deferred |
| [G017](../inventory/GPIB.md#g017) | Instrument.bus guard before I/O | A09: parallel poll deferred |
| [G018](../inventory/GPIB.md#g018) | Instrument.bus guard before I/O | A09: parallel poll unconfigure deferred |
| [G019](../inventory/GPIB.md#g019) | Instrument.bus guard before I/O | A09: IFC deferred |
| [G020](../inventory/GPIB.md#g020) | Instrument.bus guard before I/O | C0: instrument controller-role exclusion |

## Residual scope and future cases

All 138 inventory IDs are accounted for. The new tests strengthen sampled software behavior; they do not close A01–A09. The inventory's per-ID future qualification cases remain the source-backed plan. In particular, legacy masks/restore, sensor-table editing/traversal, *RST/*TST?/SP, display alias DF, poll/SRQ/GET/IFC, clear recovery, settling, and exact opaque layouts require additional authoritative evidence and/or supervised hardware cases. No guarded operation was enabled. Identifications and values in new tests are fictional fixtures, never new equipment observations.

The 10,000-input parser campaign contains 2,500 generated valid measurement replies and 7,500 deliberately invalid replies with independent non-ASCII/truncation/oversize oracles. It is not arbitrary-fuzz grammar coverage. SM tests vary each documented finite field independently and test four unit/scale/REL combinations; they do not enumerate the Cartesian product. Snapshot tests preserve every repeated byte value without interpreting its payload. Identification retains existing fixtures; its firmware/terminator ambiguity is not resolved by invented acceptance rules.
