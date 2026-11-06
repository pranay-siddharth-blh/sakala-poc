# Sakala AI POC (live app)

**Start:** double-click `run.bat`. It opens http://localhost:8020.
The first run builds the database from `..\Sample grievance cases.xlsx` and trains the local model, which takes about 2 minutes.

**Claude:** put a valid Anthropic key (`sk-ant-…`) in `app\.env` (see `.env.example`) and restart. The header tag then reads
`LIVE · CLAUDE OPUS 5.5`. Without a key, every step runs on the local model trained on the real data, and the tag reads `LIVE · LOCAL AI MODEL`.

**Reset the demo:** use the ↺ button next to the demo clock. It restores the database to its state at go-live (14 Oct 2026, 10:00).

## What is real and what is synthetic
| Item | Source |
|---|---|
| 9,999 grievances, the category master (38 departments, 124 pilot services, 221 grievance types) | Real iPGRS sample, 3–9 Oct 2026 |
| Service → officer role rules (for example, Khata → Tahsildar 100%) | Learned from the real assignments |
| Village → Gram Panchayat → taluk gazetteer (198 villages, 61 GPs) and the field officers' designations | Real data, Mysuru district |
| Live caseload: 703 real Piriyapatna / Hunsur / Mysuru grievances, each with its real officer | Real |
| Supervisors (AC, DDLR, DD Food, EO, ZP CEO, DC) and the escalation ladder | Standard hierarchy; officers not seen in the sample are marked so in the data |
| 10 demo grievances and 2 Sakala applications | **Synthetic**, flagged `SYNTHETIC` in the UI |
| Grievance timelines L1 7 / L2 5 / L3 3 days; Sakala service timelines | **Assumed**, to be confirmed |

**Routing proof:** when the router is given the real service and location of 673 real Mysuru cases, it picks the same officer that iPGRS used in **97.6%** of them.

## Pipeline (`server/`)
1. Entry (`chat.py`). One engine serves WhatsApp and every other channel.
2. Privacy shield (`privacy.py`). Masks phone, Aadhaar, email and card numbers before any AI step.
3. AI understanding (`ai.py`, using Claude with enum-constrained JSON; or `local_ai.py`, the local fallback).
4. Completion agent. Asks only for missing details; reads Kannada village names through transliteration and the gazetteer.
5. Validate and confirm. Checks for duplicates and asks the citizen to confirm.
6. Exact-officer routing (`routing.py`). Maps role + taluk + GP to one named officer.
7. Deadlines, reminders and escalation; Sakala legal clock and compensation (`sla.py`).
8. Leadership view (`api.py`). Serves the officer inbox, the CS dashboard and AI mode.
