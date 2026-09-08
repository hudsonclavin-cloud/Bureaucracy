# Directory fixtures

Official machine-readable organisational directories of the U.S. federal government,
committed exactly as served, so existence and placement evidence can be derived from
them offline and audited against these files. Nothing here is interpreted: each file is
**verbatim; refreshed only by re-fetching, never edited by hand**. Every fetch used the
project User-Agent (`bureaucracy-data-pipeline/1.0 (+https://github.com/hudsonclavin-cloud/Bureaucracy)`,
`BUREAUCRACY_PIPELINE_UA` was unset) and the verifier's `RobotsPolicy`
(`data_pipeline/verification/politeness.py`). TLS verification was on throughout.

Each raw file has a sibling `<file>.meta.json` recording `fetched_at` (UTC), `url`,
`final_url`, HTTP `status`, `content_type`, `bytes`, the `sha256` of the served body, the
robots.txt verdict, and any error. A failed fetch leaves only the meta file. Nothing was
substituted for a source that failed.

## Files

| File | URL | Fetched (UTC) | HTTP | Bytes served |
|---|---|---|---|---|
| `federal_register_agencies.json` | https://www.federalregister.gov/api/v1/agencies.json | 2026-09-08T19:19:15Z | 200 | 693552 |
| `house_gov_committees.html` | https://www.house.gov/committees | 2026-09-08T19:19:17Z | 200 | 23801 |
| `senate/senate_committees_page.html` | https://www.senate.gov/committees/ | 2026-09-08T19:19:19Z | 200 | 57666 |
| `senate/committee_membership_index.waf_response.html` | https://www.senate.gov/general/committee_membership/ | 2026-09-08T19:19:18Z | 200 | 33637 |
| `senate/committee_memberships_JSEC.xml` | https://www.senate.gov/general/committee_membership/committee_memberships_JSEC.xml | 2026-09-08T19:20:42Z | 200 | 1566 |
| `senate/committee_memberships_JSLC.xml` | https://www.senate.gov/general/committee_membership/committee_memberships_JSLC.xml | 2026-09-08T19:20:44Z | 200 | 934 |
| `senate/committee_memberships_JSPR.xml` | https://www.senate.gov/general/committee_membership/committee_memberships_JSPR.xml | 2026-09-08T19:20:45Z | 200 | 909 |
| `senate/committee_memberships_JSTX.xml` | https://www.senate.gov/general/committee_membership/committee_memberships_JSTX.xml | 2026-09-08T19:20:47Z | 200 | 905 |
| `senate/committee_memberships_SLET.xml` | https://www.senate.gov/general/committee_membership/committee_memberships_SLET.xml | 2026-09-08T19:20:48Z | 200 | 1056 |
| `senate/committee_memberships_SLIA.xml` | https://www.senate.gov/general/committee_membership/committee_memberships_SLIA.xml | 2026-09-08T19:20:49Z | 200 | 1700 |
| `senate/committee_memberships_SLIN.xml` | https://www.senate.gov/general/committee_membership/committee_memberships_SLIN.xml | 2026-09-08T19:20:51Z | 200 | 3014 |
| `senate/committee_memberships_SPAG.xml` | https://www.senate.gov/general/committee_membership/committee_memberships_SPAG.xml | 2026-09-08T19:20:52Z | 200 | 1966 |
| `senate/committee_memberships_SSAF.xml` | https://www.senate.gov/general/committee_membership/committee_memberships_SSAF.xml | 2026-09-08T19:20:53Z | 200 | 12778 |
| `senate/committee_memberships_SSAP.xml` | https://www.senate.gov/general/committee_membership/committee_memberships_SSAP.xml | 2026-09-08T19:20:55Z | 200 | 29993 |
| `senate/committee_memberships_SSAS.xml` | https://www.senate.gov/general/committee_membership/committee_memberships_SSAS.xml | 2026-09-08T19:20:56Z | 200 | 16978 |
| `senate/committee_memberships_SSBK.xml` | https://www.senate.gov/general/committee_membership/committee_memberships_SSBK.xml | 2026-09-08T19:20:57Z | 200 | 14731 |
| `senate/committee_memberships_SSBU.xml` | https://www.senate.gov/general/committee_membership/committee_memberships_SSBU.xml | 2026-09-08T19:20:59Z | 200 | 2976 |
| `senate/committee_memberships_SSCM.xml` | https://www.senate.gov/general/committee_membership/committee_memberships_SSCM.xml | 2026-09-08T19:21:00Z | 200 | 17984 |
| `senate/committee_memberships_SSEG.xml` | https://www.senate.gov/general/committee_membership/committee_memberships_SSEG.xml | 2026-09-08T19:21:01Z | 200 | 10630 |
| `senate/committee_memberships_SSEV.xml` | https://www.senate.gov/general/committee_membership/committee_memberships_SSEV.xml | 2026-09-08T19:21:02Z | 200 | 11222 |
| `senate/committee_memberships_SSFI.xml` | https://www.senate.gov/general/committee_membership/committee_memberships_SSFI.xml | 2026-09-08T19:21:04Z | 200 | 15858 |
| `senate/committee_memberships_SSFR.xml` | https://www.senate.gov/general/committee_membership/committee_memberships_SSFR.xml | 2026-09-08T19:21:05Z | 200 | 14737 |
| `senate/committee_memberships_SSGA.xml` | https://www.senate.gov/general/committee_membership/committee_memberships_SSGA.xml | 2026-09-08T19:21:06Z | 200 | 6852 |
| `senate/committee_memberships_SSHR.xml` | https://www.senate.gov/general/committee_membership/committee_memberships_SSHR.xml | 2026-09-08T19:21:07Z | 200 | 10253 |
| `senate/committee_memberships_SSJU.xml` | https://www.senate.gov/general/committee_membership/committee_memberships_SSJU.xml | 2026-09-08T19:21:09Z | 200 | 14942 |
| `senate/committee_memberships_SSRA.xml` | https://www.senate.gov/general/committee_membership/committee_memberships_SSRA.xml | 2026-09-08T19:21:10Z | 200 | 2494 |
| `senate/committee_memberships_SSSB.xml` | https://www.senate.gov/general/committee_membership/committee_memberships_SSSB.xml | 2026-09-08T19:21:11Z | 200 | 2758 |
| `senate/committee_memberships_SSVA.xml` | https://www.senate.gov/general/committee_membership/committee_memberships_SSVA.xml | 2026-09-08T19:21:13Z | 200 | 2745 |

Failed fetches (meta file only):

| Meta file | URL | Attempted (UTC) | Error (verbatim) |
|---|---|---|---|
| `house_clerk_memberdata.xml.meta.json` | https://clerk.house.gov/xml/lists/MemberData.xml | 2026-09-08T19:19:16Z | `URLError: <urlopen error Tunnel connection failed: 403 Forbidden>` |
| `house_clerk_lists_index.html.meta.json` | https://clerk.house.gov/xml/lists/ | 2026-09-08T19:19:17Z | `URLError: <urlopen error Tunnel connection failed: 403 Forbidden>` |
| `usagov_agency_index.html.meta.json` | https://www.usa.gov/agency-index | 2026-09-08T19:19:20Z | `URLError: <urlopen error Tunnel connection failed: 403 Forbidden>` |
| `sam_federal_hierarchy_orgs.json.meta.json` | https://api.sam.gov/prod/federalorganizations/v1/orgs?limit=1 | 2026-09-08T19:19:21Z | `URLError: <urlopen error Tunnel connection failed: 403 Forbidden>` |

## 1. Federal Register agency directory

`federal_register_agencies.json` wraps the API body as `{"fetched_at", "url", "status", ..., "data": <parsed body>}`.
`data` is the response array parsed and re-serialised (`indent=1`, key order as served,
`ensure_ascii=False`); `body_sha256` is the digest of the 693552-byte body exactly as
served, so a re-fetch can be checked against it. The endpoint returned the full array in one
response: 472 entries, no pagination envelope.

- Fields of one entry: `agency_url`, `child_ids`, `child_slugs`, `description`, `id`, `logo`, `name`, `parent_id`, `recent_articles_url`, `short_name`, `slug`, `url`, `json_url`.
- Entries with a non-null `parent_id`: 225 of 472.
- Department names are written `<Name> Department`, never `Department of <Name>`: "Agriculture Department", "Defense Department", "Health and Human Services Department", "Treasury Department", "Veterans Affairs Department".
- Sub-units qualify the parent after a comma: "Inspector General Office, Treasury Department", "Administration Office, Executive Office of the President".

## 2. House committees

`https://clerk.house.gov/xml/lists/MemberData.xml` and the `https://clerk.house.gov/xml/lists/`
index could not be fetched: the session's egress proxy refused the CONNECT to
`clerk.house.gov:443` with 403 ("gateway answered 403 to CONNECT (policy denial or upstream
failure)"). No byte from the Clerk was received, so nothing can be said here about whether
MemberData.xml carries committee or subcommittee names. The robots.txt of that host could not
be read for the same reason (the verifier's policy calls that "no readable robots.txt" and
fails open; the fetch itself was then refused by the proxy, not by the host).

`house_gov_committees.html` is `https://www.house.gov/committees` as served (the second page the
task named). It links the 20 standing committees, the Permanent Select Committee on
Intelligence, one select committee and four joint committees, each to its own `*.house.gov`
site. It contains no subcommittee names (the string "subcommittee" does not occur), so it
supports committee existence only, not committee→subcommittee structure. Which Clerk file is
the better source for that structure is not answered by this commit: the Clerk was unreachable.

## 3. Senate committees

`https://www.senate.gov/general/committee_membership/` (the directory) answered 200 but
redirected to `.../pagelayout/general/one_item_and_teasers/waf.htm`, a page titled "U.S.
Senate: Request not Accepted - Security Risk Detected". That response is saved verbatim as
`senate/committee_membership_index.waf_response.html` so the refusal is on record; it is not a
directory. The committee codes were enumerated instead from `senate/senate_committees_page.html`
(`https://www.senate.gov/committees/`), whose links are of the form
`committee_memberships_<CODE>.htm`. Every per-committee XML was then fetched directly, one
second apart; all 24 answered 200 `text/xml`.

Codes found (24): `JSEC`, `JSLC`, `JSPR`, `JSTX`, `SLET`, `SLIA`, `SLIN`, `SPAG`, `SSAF`, `SSAP`, `SSAS`, `SSBK`, `SSBU`, `SSCM`, `SSEG`, `SSEV`, `SSFI`, `SSFR`, `SSGA`, `SSHR`, `SSJU`, `SSRA`, `SSSB`, `SSVA`.

Committee names as the XML prints them:

- `JSEC` — Joint Economic Committee
- `JSLC` — Joint Committee of Congress on the Library
- `JSPR` — Joint Committee on Printing
- `JSTX` — Joint Committee on Taxation
- `SLET` — Select Committee on Ethics
- `SLIA` — Committee on Indian Affairs
- `SLIN` — Select Committee on Intelligence
- `SPAG` — Special Committee on Aging
- `SSAF` — Committee on Agriculture, Nutrition, and Forestry
- `SSAP` — Committee on Appropriations
- `SSAS` — Committee on Armed Services
- `SSBK` — Committee on Banking, Housing, and Urban Affairs
- `SSBU` — Committee on the Budget
- `SSCM` — Committee on Commerce, Science, and Transportation
- `SSEG` — Committee on Energy and Natural Resources
- `SSEV` — Committee on Environment and Public Works
- `SSFI` — Committee on Finance
- `SSFR` — Committee on Foreign Relations
- `SSGA` — Committee on Homeland Security and Governmental Affairs
- `SSHR` — Committee on Health, Education, Labor, and Pensions
- `SSJU` — Committee on the Judiciary
- `SSRA` — Committee on Rules and Administration
- `SSSB` — Committee on Small Business and Entrepreneurship
- `SSVA` — Committee on Veterans' Affairs

Each file is `<committee_membership><committees>` with `committee_name`, `committee_code`
(the four-letter code plus `00`), `members`, then zero or more `<subcommittee>` elements each
with `subcommittee_name`, `committee_code` (the four-letter code plus two digits) and its own
`members`. 70 subcommittees in total across 12 committees. Three, verbatim (each element continues with its `<members>`):

- `SSAF`: `<subcommittee><subcommittee_name>Subcommittee on Commodities, Derivatives, Risk Management, and Trade</subcommittee_name><committee_code>SSAF13</committee_code>`
- `SSAP`: `<subcommittee><subcommittee_name>Subcommittee on Agriculture, Rural Development, Food and Drug Administration, and Related Agencies</subcommittee_name><committee_code>SSAP01</committee_code>`
- `SSJU`: `<subcommittee><subcommittee_name>Subcommittee on Antitrust, Competition Policy, and Consumer Rights</subcommittee_name><committee_code>SSJU01</committee_code>`

A note on robots.txt: `www.senate.gov/robots.txt` answers 200 with `text/html` (an HTML page,
not a robots file). `RobotFileParser` parsed no rules from it and reported every path allowed;
that is what the verifier would do too, and it is recorded here rather than presented as a
published permission.

## 4. USA.gov agency index

`https://www.usa.gov/agency-index` could not be fetched: the egress proxy refused the CONNECT
to `www.usa.gov:443` with 403. Nothing was received, so the readable-text length and whether
entries carry a parent or a URL are not known from this environment.

## 5. SAM.gov Federal Hierarchy (optional)

`https://api.sam.gov/prod/federalorganizations/v1/orgs?limit=1` could not be fetched: the
egress proxy refused the CONNECT to `api.sam.gov:443` with 403. The documentation host
`open.gsa.gov` was refused the same way, so the key requirement could not be confirmed from
here. [Likely, from memory, unverified in this environment] The Federal Hierarchy Public API
is documented at `https://open.gsa.gov/api/fh-public-api/` and takes an `api_key` query
parameter on `GET https://api.sam.gov/prod/federalorganizations/v1/orgs`. No key was
registered for.

## Refreshing

Re-fetch with the same User-Agent and robots policy and overwrite the files; compare
`sha256` in the meta files to see what changed. Do not edit any file in this directory by hand.
