# Congressional salaries

**Fetched 2026-09-14.** Finding a citable, machine-readable primary source
for congressional pay took more than one attempt; every attempt is recorded
here rather than only the one that worked, because a `.meta.json` recording
an error is itself a fact about the network, and the next session should not
re-spend a fetch re-discovering what this one already found.

## What worked

    python scripts/fetch_fixture.py \
      https://www.senate.gov/senators/SenateSalariesSince1789.htm \
      congress/senate_salaries_since_1789.html

`senate_salaries_since_1789.html` (38,560 bytes, sha256
`6b67be0cc228b2b18f23b0842fad73351e015c4c0b8509f3919b44398f75d87a`, recorded
verbatim in its `.meta.json`) is the Senate's own year-by-year base-salary
table back to 1789 — 2026: $174,000 "per annum" — with one footnote beneath
it:

> Note: Since the early 1980s, Senate leaders–majority and minority
> leaders, and the president pro tempore–have received higher salaries than
> other members. Currently, leaders earn $193,400 per year.

**Read by `data_pipeline/verification/congressional_pay.py`, derived by
`scripts/derive_congressional_pay_evidence.py`.** It prices exactly the
three roles that footnote names — President Pro Tempore, Majority Leader,
Minority Leader — and nothing else. See the module's own docstring for the
full account of what it does not price and why (the party whips, the
House's own leadership, the Vice President's Senate-leadership node, and
any base "Member of Congress" seat, since none is curated as its own
position node).

Two parsing traps this fixture's own markup sets, both fixed and pinned in
`tests/test_congressional_pay.py`:

- every year cell hides a sort key ahead of the visible text —
  `<span style="display:none">2026</span>2026` — so a parser that does not
  suppress it reads the cell as "20262026" and matches no year at all;
- the page carries **two** `<footer>` elements: the one immediately after
  the table, with the leadership rate, and a second, site-wide one further
  down ("Contact | Content Responsibility | Usage Policy | ..."). A parser
  that captures the last `<footer><p>` on the page rather than the first one
  after the table silently replaces the leadership rate with boilerplate.

## What was fetched but is not read by anything

`clerk.house.gov/documents/Salary.pdf` (106,220 bytes, sha256
`646efcefc659f891f1014102c31d0c20bcf9924483cbb8063e31f8d060592ff8`) is the
House Clerk's own one-page statement: "As of January 21, 2026, the base
salary for all Members of Congress is $174,000," citing CRS report 97-1011.
It confirms the Senate page's base figure from a second, independent House
source, but states no House-side leadership premium, so nothing here reads
it. (Extracted with `pdfminer.six`, since this repository otherwise reads no
PDFs; not wired into the pipeline. `pip install pdfminer.six cffi
cryptography` — the environment's own apt-installed `cryptography` package
was missing its compiled `_cffi_backend` and had to be replaced with a pip
one, `pip install --ignore-installed cryptography cffi`, before
`pdfminer.high_level.extract_text` would import.)

`eo_pay_adjustments_2026.xml` (8,065 bytes) is Executive Order "Adjustments
of Certain Rates of Pay" (2025-23844, effective January 2026), fetched from
`federalregister.gov`'s own full-text XML endpoint because its Section 3
names the legal basis for both congressional pay (2 U.S.C. § 4501, "Schedule
6") and judicial pay (28 U.S.C. §§ 5, 44(d), 135, 252, 461(a), "Schedule
7") in one document. The fetched rendering (XML, HTML and plain text were
all checked) carries only the order's operative sections — the schedules
themselves, the actual dollar tables, are not present in any of
federalregister.gov's full-text renderings of this document, only in the
PDF exhibit at `govinfo.gov` (not fetched). Not read by anything; kept as
the record of where the legal basis is stated and why chasing this
particular document further would not have produced the tables.

## What failed

| Meta file | URL | Error |
|---|---|---|
| `crs_97-1011_salaries.html.meta.json` | `https://www.congress.gov/crs-product/97-1011` | `HTTP Error 403: Forbidden` — a Cloudflare interstitial ("Just a moment..."), confirmed from the response body; not this session's proxy. `crsreports.congress.gov`'s own product and PDF endpoints return the same 403. This is the CRS report the House Clerk's PDF itself cites for congressional pay, and would very likely also state the House's own leadership premiums if it could be read — the natural next fetch once this host is reachable. |
| `radiotv_house_salaries.html.meta.json` | `https://radiotv.house.gov/house-data/salaries` | `Tunnel connection failed: 403 Forbidden` — refused at this session's own egress proxy (a fact about the environment's allowlist, not the host), per `docs/NETWORK_ACCESS.md` §0/§1. |
