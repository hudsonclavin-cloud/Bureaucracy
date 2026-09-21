# Federal Register fixtures: signature blocks

Every rule and notice the federal government publishes ends with a signature
block naming the official who signed it and that official's own title:

    R.N. Macon,
    Captain, U.S. Coast Guard, Captain of the Port, Lake Michigan.
    [FR Doc. 2026-19270 Filed 9-18-26; 8:45 am]

`data_pipeline/verification/federal_register_signatures.py` reads the **title**
and never the name — the name line is located only so that the title can be
taken from below it, the rule `positions.py` sets for the PLUM archive's
incumbent columns and `whitehouse_pay.py` for its report's NAME column.

Everything here is **verbatim; refreshed only by re-fetching, never edited by
hand**. Each raw file has a sibling `<file>.meta.json` recording `fetched_at`,
`url`, `final_url`, HTTP `status`, `content_type`, `user_agent`, the robots
verdict, `bytes`, the `sha256` of the served body and any `error`; every loader
recomputes the digest from the bytes before reading.

## Permission

`www.federalregister.gov/robots.txt` answers **200** with rules that disallow
four search paths and `/my/`, `/auth/`, `/documents/current` and
`/documents/email-a-friend`. Neither path read here — `/api/v1/documents.json`
and `/documents/full_text/text/…` — is covered by any rule, so both are
allowed; the verdict on every `.meta.json` says so in the form
`allows <path>`. `robots.txt` was read **once** for the host at the start of
the run rather than once per file (`fetch_fixture.robots_verdict` takes a
per-host cache), because four hundred requests for one file is not politeness.
No crawl-delay is stated; the run kept one of its own, between 2 and 6 seconds
(it was varied while measuring the host's refusal rate, which turned out not to
track it — see "The responses that are not documents").

## How the sample was selected, and what that biases

A biased sample is a biased claim, so the rule is stated here in full and the
listings that implement it are committed beside the documents. There are two
tranches and they answer different questions.

**Tranche A — a per-agency census.** Every entry in the Federal Register's own
agency directory (`tests/fixtures/directories/federal_register_agencies.json`,
fetched 2026-09-08) whose listed name reduces, under
`directories.federal_register_name_keys`, to **exactly one** organisation in
the curated graph, and whose organisation carries at least one direct post
child whose name is two tokens or more: **143 of the directory's 472 entries**
(168 reach exactly one node; 25 of those carry no post a signature could ever
name). For each, ONE listing call — `conditions[agencies][]=<slug>`,
`conditions[type][]=RULE`, `conditions[type][]=NOTICE`, `order=newest`,
`per_page=2` — committed as `index/<slug>.json`, and every distinct document
those listings name was then fetched. An agency that could never produce a
record was not crawled at all.

**Tranche B — the newest documents government-wide.** Tranche A under-weights
the departments: a department's newest documents are filed under a bureau as
well, so the scoping rule refuses them, and the two that survive are whatever
that agency happened to publish. So the **300 most recent RULE and the 300 most
recent NOTICE** documents were listed with no agency condition, three pages of
100 each (`index/newest-rule.json`, `index/newest-rule-page2.json`,
`index/newest-rule-page3.json`, and the same for notices), and of those, the
documents whose WHOLE agency list reduces to exactly one organisation here were
fetched. The rest could never produce a record — the same reason an ineligible
agency is not crawled in tranche A — and because the listings are committed,
how many those were, and which, is reproducible offline with no network at all.
`read_documents` counts a listed document with no fetch record beside it as
`documents_not_fetched`, separately from one the host refused.

Nothing in either tranche was selected for what its signature says.

**What is here: 443 documents and 149 listings.** The listings name 756
distinct documents; 443 were fetched and committed, 1 the host never served
after twelve attempts, and 312 were not fetched because their agency list
reaches no single organisation here. Reading them yields 360 signature titles,
208 of them distinct, and three that reach a post
(`scripts/derive_fr_signature_evidence.py --dry-run` prints all of it).

What this biases: two documents per agency is a thin, recent slice, so an
agency that publishes rarely contributes documents that may be years old
(`05-22070` is from 2005) and a busy one contributes only its two newest, while
tranche B is a single moment's snapshot of the whole Register. Together they
say nothing about how often any title is signed in general — only that it was
signed on the documents in here.

## The responses that are not documents

`www.federalregister.gov` answers a document's `raw_text_url` with a
10,596-byte HTML page titled **"Federal Register :: Request Access"** at
random, under HTTP **200**; the same URL serves the document on the next
attempt. It is not a fact about this project's agent and not a simple rate
limit: measured against three header sets the rate did not move, and measured
across four stretches of the run paced at 2.5, 2.0, 6.0 and 2.5 seconds it came
back on 63%, 68%, 59% and 82% of requests — drifting between roughly three in
five and four in five without tracking the delay (`docs/NETWORK_ACCESS.md`
§13). What it costs is attempts rather than patience, so the run allows twelve.

Such a response is **not the document**, so it is refused outright rather than
having markup parsed out of it: it is deleted, the fetch waits and retries, and
if the host never serves the document, no `.txt` is written and the
`.meta.json` beside it records why. A `documents/<n>.txt.meta.json` with an
`error` and no `.txt` beside it is that case, and `read_documents` counts it as
`documents_refused_by_the_host` rather than dropping it silently.

The plain-text rendering the Government Publishing Office serves is wrapped in
a fixed `<html><head><title>…</title></head><body><pre>` envelope of its own,
and a few documents carry a Cloudflare e-mail-obfuscation `<span>` inside the
body. **Nothing here parses either.** The signature block is located by the
document's own `[FR Doc. <number> Filed …]` line, whose number must be the
number the API gives for that document, and a tag or an HTML entity inside the
block refuses it — a bare ampersand does not, since this graph names units
"Health & Human Services" and carries a post called
`AF/A1 (Manpower & Personnel)`.

## Layout

    index/<agency slug>.json        a tranche A listing, verbatim
    index/newest-rule.json          the tranche B listings, verbatim
    index/newest-rule-page2.json
    index/newest-rule-page3.json
    index/newest-notice.json
    index/newest-notice-page2.json
    index/newest-notice-page3.json
    index/<name>.json.meta.json
    documents/<document number>.txt          the raw text, verbatim
    documents/<document number>.txt.meta.json
