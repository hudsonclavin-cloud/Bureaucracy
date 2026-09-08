# OPM fixtures: federal positions and headcounts

The U.S. Office of Personnel Management's own machine-readable data on federal
positions (PLUM Reporting, the successor to the printed Plum Book) and on federal
civilian employment by agency and sub-agency (FedScope), committed exactly as served
so the graph's 4,382 position nodes and its uncited `employees` fields — the counts the
cost cascade weights by — can be checked against official sources offline. Nothing here
is interpreted. Each file is **verbatim; refreshed only by re-fetching, never edited by
hand**.

Every fetch used the project User-Agent
(`bureaucracy-data-pipeline/1.0 (+https://github.com/hudsonclavin-cloud/Bureaucracy)`,
`BUREAUCRACY_PIPELINE_UA` unset) and the verifier's `RobotsPolicy`
(`data_pipeline/verification/politeness.py`): `www.opm.gov/robots.txt` was read and
allowed every path fetched. TLS verification was on throughout; `HTTPS_PROXY` was left as
the environment set it. Each raw file has a sibling `<file>.meta.json` recording
`fetched_at` (UTC), `url`, `final_url`, HTTP `status`, `content_type`, `user_agent`, the
robots.txt verdict, `bytes`, the `sha256` of the served body, and any `error`. A failed
fetch leaves only the meta file. Nothing was substituted for a source that failed; where a
weaker file from the same publisher was saved instead, this README says so.

## Files

| File | URL | Fetched (UTC) | HTTP | Bytes | sha256 |
|---|---|---|---|---|---|
| `fedscope/fedscope_employment_cube_2024-09.zip` | https://www.opm.gov/data/datasets/Files/721/550993be-94ba-476c-9d66-7f7e8871b07b.zip | 2026-09-08T19:51:10Z | 200 | 24176563 | `81c2056094fe776b7169f9e371041e2d1f5c930b13e5529732af7d3fe6b8133e` |
| `fedscope/fedscope_employment_cube_2024-09_data_dictionary.pdf` | https://www.opm.gov/data/datasets/Files/721/cf6137df-539e-4f18-8a91-21740000ce46.pdf | 2026-09-08T19:51:08Z | 200 | 539748 | `e4c6d5c4be8b9a32057c4f4aa4a51a371bdef5554f24c6f62c9f037e6a6b7a23` |
| `fedscope/fedscope_employment_file1_2025-03.zip` | https://www.opm.gov/data/datasets/Files/756/a1acc4f3-0c10-45e3-ac1f-0ee7f5769e1d.zip | 2026-09-08T19:50:56Z | 200 | 3759631 | `84f5b3d6234b5f4cbdd3fa1671fc6c422e6e91f1d84237827b7ad77fdf5366fc` |
| `fedscope/fedscope_employment_file1_2025-03_data_dictionary.pdf` | https://www.opm.gov/data/datasets/Files/756/d67e7d4a-55a6-4369-a8ee-e2ccf57d5229.pdf | 2026-09-08T19:50:53Z | 200 | 188669 | `55aa990f2a3e25788422414976b490bb1b98e60e52f1d6a59f207ca471f6817f` |
| `fedscope/fedscope_employment_file2_2025-03.zip` | https://www.opm.gov/data/datasets/Files/758/18693acd-e0d7-4cb5-b15b-bd455a3a432c.zip | 2026-09-08T19:51:00Z | 200 | 12914548 | `5b843f6174e51d56625ee77ccab7c5b15535ef2fb8abb183fecada1f0df42b84` |
| `fedscope/fedscope_employment_file2_2025-03_data_dictionary.pdf` | https://www.opm.gov/data/datasets/Files/758/6b1a51ba-e666-41f2-9224-e1284e4e054a.pdf | 2026-09-08T19:50:58Z | 200 | 188669 | `55aa990f2a3e25788422414976b490bb1b98e60e52f1d6a59f207ca471f6817f` |
| `fedscope/fedscope_employment_file3_2025-03.zip` | https://www.opm.gov/data/datasets/Files/759/3c93cbe4-ae79-4881-8562-5892df28744d.zip | 2026-09-08T19:51:05Z | 200 | 20909167 | `128e8d0a7006d246e4d2c47df252861361f783d1907ff89c8b718b28fc4286a7` |
| `fedscope/fedscope_employment_file3_2025-03_data_dictionary.pdf` | https://www.opm.gov/data/datasets/Files/759/949b3125-11c9-4ef5-b95e-498b96791574.pdf | 2026-09-08T19:51:03Z | 200 | 188669 | `55aa990f2a3e25788422414976b490bb1b98e60e52f1d6a59f207ca471f6817f` |
| `fedscope/fedscope_employment_summary_2025-03.zip` | https://www.opm.gov/data/datasets/Files/753/bc88ce69-1bbe-406f-9441-3c5153014616.zip | 2026-09-08T19:50:51Z | 200 | 1228412 | `d0d7ce6a6df4e43177c2d584624398af0f13818f2e193de9460e5db015329f74` |
| `fedscope/fedscope_employment_summary_2025-03_data_dictionary.pdf` | https://www.opm.gov/data/datasets/Files/753/19f81b5c-d287-4322-a1ac-a6a4c235674b.pdf | 2026-09-08T19:50:48Z | 200 | 188669 | `55aa990f2a3e25788422414976b490bb1b98e60e52f1d6a59f207ca471f6817f` |
| `fedscope/opm_datasets_index.html` | https://www.opm.gov/data/datasets/ | 2026-09-08T19:46:15Z | 200 | 294191 | `9be7b7c36d72cb45973a63c76f1413c6f625cb6a39681247eef8c23b0304fdcc` |
| `plum/opm_plum_archive_page.html` | https://www.opm.gov/about-us/open-government/plum-reporting/plum-archive/ | 2026-09-08T19:48:51Z | 200 | 91016 | `0ffa3e924d8a8c9bd584d8b6050b86c3da3e53defec32f2f06c2bb1fcb203a65` |
| `plum/opm_plum_data_page.html` | https://www.opm.gov/about-us/open-government/plum-reporting/plum-data/ | 2026-09-08T19:47:37Z | 200 | 211195 | `55e7dc41148112cd70fd16781369567d641bb9b3a031ddaadccf8b9113128c9e` |
| `plum/plum-archive-biden-administration.csv` | https://www.opm.gov/about-us/open-government/plum-reporting/plum-archive/plum-archive-biden-administration.csv | 2026-09-08T19:49:47Z | 200 | 3792279 | `2a77f8ca82e4e4077db4d923f77d5bc8812eecd9a8b86b9baf231e22a848fd3d` |

Failed fetches (meta file only). Every failure is the session's egress proxy refusing the
`CONNECT` with 403 before any byte reached the host — a fact about this environment's
network policy, not about the host. The robots.txt of each such host could not be read for
the same reason (the verifier's policy calls that "no readable robots.txt" and fails open;
the fetch itself was then refused by the proxy, not by the host).

| Meta file | URL | Attempted (UTC) | Error (verbatim) |
|---|---|---|---|
| `fedscope/data_opm_gov_data-downloads.html.meta.json` | https://data.opm.gov/explore-data/data/data-downloads | 2026-09-08T19:53:47Z | `URLError: <urlopen error Tunnel connection failed: 403 Forbidden>` |
| `fedscope/data_opm_gov_root.html.meta.json` | https://data.opm.gov/ | 2026-09-08T19:53:46Z | `URLError: <urlopen error Tunnel connection failed: 403 Forbidden>` |
| `fedscope/fedscope_opm_gov_root.html.meta.json` | https://www.fedscope.opm.gov/ | 2026-09-08T19:53:47Z | `URLError: <urlopen error Tunnel connection failed: 403 Forbidden>` |
| `plum/GPO-PLUMBOOK-2024.pdf.meta.json` | https://www.govinfo.gov/content/pkg/GPO-PLUMBOOK-2024/pdf/GPO-PLUMBOOK-2024.pdf | 2026-09-08T19:53:45Z | `URLError: <urlopen error Tunnel connection failed: 403 Forbidden>` |
| `plum/escs_pbpub_download-data.csv.meta.json` | https://escs.opm.gov/escs-net/api/pbpub/download-data | 2026-09-08T19:53:43Z | `URLError: <urlopen error Tunnel connection failed: 403 Forbidden>` |
| `plum/escs_pbpub_get-current-agencies.json.meta.json` | https://escs.opm.gov/escs-net/api/pbpub/get-current-agencies | 2026-09-08T19:53:44Z | `URLError: <urlopen error Tunnel connection failed: 403 Forbidden>` |
| `plum/govinfo_plum_book_collection.html.meta.json` | https://www.govinfo.gov/collection/plum-book | 2026-09-08T19:53:45Z | `URLError: <urlopen error Tunnel connection failed: 403 Forbidden>` |
| `plum/plumbook_opm_gov_root.html.meta.json` | https://plumbook.opm.gov/ | 2026-09-08T19:53:42Z | `URLError: <urlopen error Tunnel connection failed: 403 Forbidden>` |


## 1. Positions — PLUM Reporting (the Plum Book)

**What the current official data export is, and why it is not here.** OPM's PLUM Data
page, `https://www.opm.gov/about-us/open-government/plum-reporting/plum-data/` (saved as
`plum/opm_plum_data_page.html`), states that OPM "is publishing data reported by agencies as
of June 15, 2026" and offers "All Data (CSV)" / "All Data (XML)" buttons. Those buttons are
not links: the page's inline script (search the saved page for `baseApiUrl`) sets
`baseApiUrl = 'https://escs.opm.gov/escs-net/api/pbpub'` and the export is a `GET` to
`${baseApiUrl}/download-data` with the active filters as a JSON body; the filter lists come
from `get-current-agencies`, `get-current-organizations`, `get-current-positions` and
`get-current-appointment-types` on the same base. So the machine-readable file of current
positions with agency, title and appointment type is served by **`escs.opm.gov`**, and that
host is refused by the proxy (see the table above; `plum/escs_pbpub_download-data.csv.meta.json`
and `plum/escs_pbpub_get-current-agencies.json.meta.json` carry the exact error). Its record
count, field names and sample rows are therefore not known from this environment.
`https://plumbook.opm.gov/` (the address the task named) and GovInfo — both the collection
page and the 2024 printed Plum Book PDF that the OPM page links,
`https://www.govinfo.gov/content/pkg/GPO-PLUMBOOK-2024/pdf/GPO-PLUMBOOK-2024.pdf` — were
refused the same way. No Plum PDF was obtained.

**What www.opm.gov itself serves, saved with that caveat.** The Plum Archive page,
`https://www.opm.gov/about-us/open-government/plum-reporting/plum-archive/` (saved as
`plum/opm_plum_archive_page.html`), links one file hosted on www.opm.gov:
`plum-archive-biden-administration.csv`, labelled "Biden Administration". It is the same
publisher and the same reporting programme, but it is the **archive of the previous
administration's positions and incumbencies, not the current edition** dated June 15,
2026. It is committed as `plum/plum-archive-biden-administration.csv` because it is the only
machine-readable PLUM file reachable from here; anything derived from it must say
"positions as archived for the Biden administration", never "current positions".

- Encoding: UTF-8 with a byte-order mark; served as `application/octet-stream`.
- Records: **21,312** data rows after the header (21,313 lines), every row 14 fields.
- Fields, in order: `AgencyName`, `OrganizationName`, `PositionTitle`, `PositionStatus`,
  `AppointmentTypeDescription`, `ExpirationDate`, `LevelGradePay`, `Location`,
  `IncumbentFirstName`, `IncumbentLastName`, `PaymentPlanDescription`, `Tenure`,
  `IncumbentBeginDate`, `IncumbentVacateDate`.
- A row is an incumbency, not a position: the same (agency, organisation, title, location)
  recurs once per holder, with 13,809 rows carrying an `IncumbentVacateDate`. Distinct
  (agency, organisation, title, location) tuples: 10,708. Distinct `AgencyName`: 169;
  distinct `OrganizationName`: 1,259; distinct `PositionTitle`: 7,428.
- `AppointmentTypeDescription` values (count): CA 7,468; SC 5,612; NA 3,152; PAS 2,167;
  XS 1,807; PA 809; TA 229; CG 41; DA 15; EA 9; SS 3. `PositionStatus`: Filled 18,475;
  Vacant 2,837. The codes are the Plum Book's (PAS = Presidential appointment with
  Senate confirmation, PA = Presidential appointment, CA = career SES, NA = non-career
  SES, SC = Schedule C, XS = excepted, TA = limited term SES, and so on [likely, from the
  printed Plum Book's legend; the CSV carries no legend of its own]).
- Latest `IncumbentBeginDate` in the file: 1/20/2025. One `IncumbentVacateDate` reads
  `11/2/3024` — a typo in the source, kept as served.
- Ten rows (row number, `AgencyName` | `OrganizationName` | `PositionTitle` |
  `AppointmentTypeDescription` | `PositionStatus`), every 2,131st row:

```
     1 | ADMINISTRATIVE CONFERENCE OF THE UNITED STATES | ADMINISTRATIVE CONFERENCE OF THE UNITED STATES | CHAIRMAN | PAS | Filled
  2132 | DEPARTMENT OF COMMERCE | INTERNATIONAL TRADE ADMINISTRATION | DIRECTOR OF THE SUPPLY CHAIN CENTER | NA | Vacant
  4263 | DEPARTMENT OF ENERGY | UNDER SECRETARY FOR SCIENCE | CHIEF OF STAFF | NA | Filled
  6394 | DEPARTMENT OF HOMELAND SECURITY | PRIVACY OFFICE | CHIEF PRIVACY OFFICER AND CHIEF FREEDOM OF INFORMATION ACT OFFICER | NA | Filled
  8525 | DEPARTMENT OF JUSTICE | FEDERAL BUREAU OF PRISONS | Supervisory Industrial Specialist | NA | Filled
 10656 | DEPARTMENT OF STATE | OFFICE OF THE UNDER SECRETARY FOR POLITICAL AFFAIRS | AUSTRIA - Ambassador to the Republic of | PAS | Filled
 12787 | DEPARTMENT OF TRANSPORTATION | ASSISTANT SECRETARY FOR TRANSPORTATION POLICY | DEPUTY ASSISTANT SECRETARY FOR CLIMATE POLICY | NA | Vacant
 14918 | ENVIRONMENTAL PROTECTION AGENCY | OFFICE OF THE ASSISTANT ADMINISTRATOR FOR LAND AND EMERGENCY MANAGEMENT | DEPUTY DIRECTOR, OFFICE OF RESOURCE CONSERVATION AND RECOVERY | CG | Filled
 17049 | MORRIS K. UDALL AND STEWART L. UDALL FOUNDATION | MORRIS K UDALL SCHOLARSHIP AND EXCELLENCE IN NATIONAL ENVIRONMENTAL POLICY FOUNDATION | TRUSTEE | PAS | Vacant
 19180 | OFFICE OF THE SECRETARY OF DEFENSE | OFFICE OF THE SECRETARY OF DEFENSE | SPECIAL ASSISTANT | SC | Filled
```

## 2. Headcounts — FedScope employment data

**Where it lives now.** OPM's "Federal Workforce Data" page
(`/policy-data-oversight/data-analysis-documentation/fedscope/`) says FedScope was
succeeded by Federal Workforce Data (FWD) at `https://data.opm.gov/`, launched January
2026, with downloads at `https://data.opm.gov/explore-data/data/data-downloads`; both that
host and the old `www.fedscope.opm.gov` are refused by the proxy (meta files in
`fedscope/`). The raw files are still published on **www.opm.gov** at
`https://www.opm.gov/data/datasets/` — the full index (saved as
`fedscope/opm_datasets_index.html`, 160 datasets) — under the names "FedScope Employment
Cube (<month year>)" through September 2024 and, from the March 2025 release on, "FedScope
Employment Summary Data" plus "FedScope Employment Data File 1/2/3". The
`Index.aspx?tag=FedScope` view of the same index is stale (its newest employment cube is
June 2022) and was not used. The newest employment release on the index is March 2025
(posted 7/1/2025); nothing later was listed on 2026-09-08. The files are served under
opaque GUID paths; the index page is what ties each GUID to its dataset name.

**Period covered.** The March 2025 data dictionary (`fedscope_employment_*_2025-03_data_dictionary.pdf`,
the same 188,669-byte PDF served under four URLs, one per dataset — all four copies are
committed with their own meta files, sha256 identical) is headed "(Preliminary) March 2025
Employment Dataset" and says: the snapshot is "of the Federal workforce as of the last day
of the month"; it covers Federal civilian employees in the Executive Branch in an active
pay status, "excluding some agencies such as the U.S. Postal Service and intelligence
agencies"; "the March 2025 does not reflect expected Federal workforce reshaping
activities. Employees on administrative leave pending resignation, retirement, or release
are identified as current employees"; `REDACTED` values occur where data suppression is
required; "all aggregations of 10 or under will be categorized as 10_OR_LESS"; and "the
summary tables include both the March 2025 and September 2024 snapshots." The September
2024 cube's `DTdate.txt` reads `202409,SEP 2024`. All figures below are OPM's headcounts of
these records, not full-time equivalents, and not the whole federal workforce.

### `fedscope/fedscope_employment_summary_2025-03.zip` — the agency-level tables

Ten tab-separated `.txt` tables, each with a `DATECODE` column carrying both `202503` and
`202409`, plus the dictionary PDF. The one the graph needs is
`Status Employment by Agency and SubAgency_202503_and_202409.txt`: 1,016 rows, fields
`DATECODE, AGY, AGYT, AGYSUB, AGYSUBT, EMPCOUNT, AVGSAL, AVGLOS`.

| DATECODE | rows | distinct `AGY` | distinct `AGYSUB` | sum `EMPCOUNT` |
|---|---|---|---|---|
| 202503 | 499 | 116 | 499 | 2,289,472 |
| 202409 | 517 | 116 | 517 | 2,313,216 |

One row per period is `10_OR_LESS` in every code and name column — the suppressed
aggregate, `EMPCOUNT` 127 for 202503 and 109 for 202409; the distinct counts above include
it. There is no total row. Five rows for
202503, as served (tab-separated):

```
DATECODE	AGY	AGYT	AGYSUB	AGYSUBT	EMPCOUNT	AVGSAL	AVGLOS
202503	VA	DEPARTMENT OF VETERANS AFFAIRS	VATA	VETERANS HEALTH ADMINISTRATION	420521	111530	9.5
202503	TR	DEPARTMENT OF TREASURY	TR93	INTERNAL REVENUE SERVICE	101312	89541	11.8
202503	AF	DEPARTMENT OF THE AIR FORCE	AF1M	AIR FORCE MATERIEL COMMAND	71560	101790	11.7
202503	HS	DEPARTMENT OF HOMELAND SECURITY	HSBD	CUSTOMS AND BORDER PROTECTION	66839	110800	13.9
202503	HS	DEPARTMENT OF HOMELAND SECURITY	HSBC	TRANSPORTATION SECURITY ADMINISTRATION	66112	80363	10
```

The other tables in the zip: `Status Employment by Agency and Duty Location_…` (adds
`LOC, STATE, STATET`), `…by Agency_PayPlan_Grade_Series_…` (adds `OCC, OCCT, PAYPLAN, GRD`),
and government-wide tables by Age Level, Appointment Type, Duty Location, Education Level,
Occupation, and Pay Plan and Grade.

### `fedscope/fedscope_employment_file{1,2,3}_2025-03.zip` — the record-level release

Each zip holds one pipe-delimited, double-quoted `March_2025_Employment_<n>.txt` and the
dictionary. The dictionary says the three files "when combined … represent the full
Employment Raw dataset"; they were split by file size. Fields (31): `AGY, AGYT, AGYSUB,
AGYSUBT, DATECODE, AGELVLT, EDLVL, EDLVLT, LOS, OCC, OCCT, OCCFAM, OCCFAMT, PAYPLAN,
PAYPLANT, STEMAGGT, STEMTYPT, SUPERVIS, SUPERVIST, TOA, TOAT, WORKSCH, WORKSCHT, COUNT,
LOC, STATE, STATET, COUNTRY, COUNTRYT, SALARY, GRD`. Every row has `COUNT` 1, so rows are
employees:

| File | Uncompressed | Rows |
|---|---|---|
| `March_2025_Employment_1.txt` | 276,389,709 bytes | 771,384 |
| `March_2025_Employment_2.txt` | 311,600,617 bytes | 706,313 |
| `March_2025_Employment_3.txt` | 354,249,874 bytes | 811,775 |
| all three | | 2,289,472 |

The three-file total equals the summary table's 202503 total to the employee. 771,384 rows
— file 1 in its entirety — carry `REDACTED` in every field but agency, sub-agency, date
and count: the suppressed records, which the summary table still counts under their
agencies. Files 2 and 3 carry the full record and redact only the duty-location fields
(`LOC, STATE, STATET, COUNTRY, COUNTRYT`) and `SALARY` on some rows. 130 distinct
`AGY` codes across the three files (the summary's 116 plus codes that appear only in
suppressed rows or fall under `10_OR_LESS` there [likely; not reconciled code by code]).
Largest agencies by rows: VA 474,542; HS 231,771; AR 220,485; NV 220,459; AF 171,751.

### `fedscope/fedscope_employment_cube_2024-09.zip` — the last release in the cube format

The FACTDATA-plus-dimension layout the task named, for September 2024, the newest quarter
published in that format. Contents: `FACTDATA_SEP2024.TXT` (165,662,211 bytes,
comma-separated, fields `AGYSUB, LOC, AGELVL, EDLVL, GSEGRD, LOSLVL, OCC, PATCO, PP, PPGRD,
SALLVL, STEMOCC, SUPERVIS, TOA, WORKSCH, WORKSTAT, DATECODE, EMPLOYMENT, SALARY, LOS`;
2,313,216 rows, sum of `EMPLOYMENT` 2,313,216 — equal to the summary table's 202409
total), sixteen `DT*.txt` dimension files, `ReadRawData_CreateTempDatasets_DataGov.sas`,
and `FS_Employment_Sep2024_Documentation.pdf` (the same bytes as the committed
`fedscope_employment_cube_2024-09_data_dictionary.pdf`, sha256 identical).

The agency dimension, `DTagy.txt`: 542 rows, fields `AGYTYP, AGYTYPT, AGY, AGYT, AGYSUB,
AGYSUBT`; 132 distinct `AGY`, 542 distinct `AGYSUB`. `AGYTYP` groups agencies as
1 "Cabinet Level Agencies" (394 sub-agency rows), 2 "Large Independent Agencies (1000 or
more employees)" (52), 3 "Medium Independent Agencies (100-999 employees)" (35),
4 "Small Independent Agencies (less than 100 employees)" (61). Names in this file carry
their code as a prefix (`AF-DEPARTMENT OF THE AIR FORCE`); the March 2025 files do not.
Five rows as served:

```
AGYTYP,AGYTYPT,AGY,AGYT,AGYSUB,AGYSUBT
1,Cabinet Level Agencies,AF,AF-DEPARTMENT OF THE AIR FORCE,AF02,AF02-AIR FORCE INSPECTION AGENCY (FO)
1,Cabinet Level Agencies,AF,AF-DEPARTMENT OF THE AIR FORCE,AF03,AF03-AIR FORCE OPERATIONAL TEST AND EVALUATION CENTER
1,Cabinet Level Agencies,AF,AF-DEPARTMENT OF THE AIR FORCE,AF06,AF06-AIR FORCE AUDIT AGENCY
1,Cabinet Level Agencies,AF,AF-DEPARTMENT OF THE AIR FORCE,AF07,AF07-AIR FORCE OFFICE OF SPECIAL INVESTIGATIONS
1,Cabinet Level Agencies,AF,AF-DEPARTMENT OF THE AIR FORCE,AF09,AF09-AIR FORCE PERSONNEL CENTER
```

Largest agencies by `EMPLOYMENT` in the fact table: VA 482,831; HS 227,566; AR 221,222;
NV 220,772; AF 171,657.

**Size.** No committed file exceeds 50 MB (the largest is the September 2024 cube zip at
24,176,563 bytes), so every file is committed whole; the directory totals about 66 MB.
The uncompressed fact tables (166 MB and 942 MB) are read from the zips, not extracted.

## Refreshing

Re-fetch with the same User-Agent and robots policy and overwrite the files; compare
`sha256` in the meta files to see what changed. The March 2025 release is labelled
preliminary by OPM and may be replaced under the same or new GUIDs; re-read the index page
rather than the GUID URLs to find the current files. Do not edit any file in this directory
by hand.
