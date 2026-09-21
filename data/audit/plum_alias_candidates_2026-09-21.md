# PLUM export agency names that denote a node the graph already has

Handoff from the 2026-09-21 pass over OPM's current PLUM export
(`tests/fixtures/opm/plum/escs_pbpub_download-data.csv`, fetched 2026-09-21).
`CURATION.md` §17 carries the full pass; `data/audit/plum_unmatched_agencies_2026-09-21.json`
carries all 96 dispositions with live-row counts.

**Nothing here has been acted on.** Each row is an identification with its basis,
for whoever owns the matcher's alias tables. No node was added for any of them:
adding one would duplicate a unit the graph already carries, which is the failure
`add_curated_nodes.py`'s docstring names ("adding one of those would create a
duplicate, which this repository has had to merge before").

`plum_current.py` has no alias table today, and `CLAUDE.md` records that as
deliberate ("**No alias table.**"). So the decision these rows need is first
whether such a table should exist at all, and only then what goes in it. Two of
the seven below could alternatively be settled by a **rename** of the graph's own
node rather than by an alias — that is
`scripts/rename_units_to_official_wording.py`'s job, not this file's, and the
page has to decide it either way.

## The graph carries the unit under a different name — 4

| Export agency (live rows) | Node | Basis |
|---|---|---|
| `CORPORATION FOR NATIONAL AND COMMUNITY SERVICE` (31) | `exec-ind-misc-americorps` — "AmeriCorps" | The statutory name against the current branding. `CURATION.md` §2 and `CLAUDE.md`'s "Known base-graph gaps" already own this pair for the Monthly Treasury Statement's line; **another agent owns the alias**, and this pass deliberately added nothing. |
| `EXPORT-IMPORT BANK` (18) | `exec-ind-misc-export-import-bank-of-the-u-s` — "Export-Import Bank of the U.S." | Keys `export import bank` against `export import bank of the united states`. The Government Manual prints "Export-Import Bank of the United States", so the graph's name is the full one and the export's is the short form. One unit. |
| `PRIVACY AND CIVIL LIBERTIES AND OVERSIGHT BOARD` (5) | `exec-ind-misc-privacy-civil-liberties-oversight-board-pclob` | The export's string carries an extra `AND` before `OVERSIGHT` that the board's own name does not. A transcription artefact on the export's side, not a different body. |
| `CONSUMER FINANCIAL PROTECTION BUREAU` (3) | `exec-regulatory-bureau-of-consumer-financial-protection` | 12 U.S.C. §5491 establishes the "Bureau of Consumer Financial Protection", which is the name the graph uses and the name the Monthly Treasury Statement prints; the export prints the bureau's own branding. One unit. |

## A node was added this pass, but under the name its own source gives — 3

These three units were genuinely missing and are now in the graph. Their rows
still do not reach them, because the node is named as an official source names
it and the export spells it otherwise. The node's name was **not** bent to the
export: the export is not a licence, and `CLAUDE.md` records for the templated
cabinet titles that a transform may recognise a name and never produce one.

| Export agency (live rows) | Node added | Basis |
|---|---|---|
| `OFFICE OF THE DIRECTOR FOR NATIONAL INTELLIGENCE` (6) | `exec-ind-misc-odni` — "Office of the Director of National Intelligence" | The export prints **for**; `dni.gov` and the Government Manual's 2025-12-31 entry both print **of**. Two official documents against one. |
| `COUNCIL OF INSPECTORS GENERAL ON INTEGRITY AND EFFICIENCY` (1) | `exec-ind-misc-cigie` — "Council of the Inspectors General on Integrity and Efficiency" | `ignet.gov` labels it "The Council of the Inspectors General on Integrity and Efficiency (CIGIE)"; the export omits "the". |
| `INTERAGENCY COUNCIL ON THE HOMELESS` (1) | `exec-ind-misc-interagency-council-on-homelessness` — "United States Interagency Council on Homelessness" | The export prints the council's pre-1994 name. `usich.gov` labels the current one, which is what the node carries. |

## Not an alias — recorded here so it is not mistaken for one

`OFFICE OF THE SECRETARY OF WAR` (506 rows) is **not** an alias of anything and
must not be treated as one. The export's bucket carries DARPA, the Defense
Finance and Accounting Service, the Defense Health Agency, the National Guard
Bureau, the Joint Chiefs of Staff and the U.S. Court of Appeals for the Armed
Forces alongside the Secretary's own offices — units the graph already carries
in three different places. An alias pointing it at any single node would file all
506 rows under that node. `CURATION.md` §17.1 has the evidence.
