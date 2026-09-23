# What the verifier can reach, and what it cannot

The verification pipeline only ever makes claims about pages it actually
read. When a page cannot be read, the record says `fetch_failed` and applies
nothing — so an unreachable host does not weaken the site's honesty, it
just leaves the node unverified. This note says which hosts are unreachable
and why, because two of the three causes are fixable and one is deliberate.

Counted from `data/verification/official_sites.json` (149 candidate hosts)
against the failure reasons in `data/verification/evidence.json`, after the
live run of 2026-09-08.

## 0. The allowlist is per session, and it changed on 2026-09-09

The counts below describe the 2026-09-08 environment. On 2026-09-09 the
session's proxy refused, with the same `403 Forbidden` on the `CONNECT`,
four hosts that had been fetched successfully the day before:

| Host | 2026-09-08 | 2026-09-09 |
|---|---|---|
| `www.opm.gov` | 200; FedScope and the PLUM archive fetched (`tests/fixtures/opm/README.md` records the sizes and hashes) | 403 at the proxy, on `robots.txt` and on every path |
| `www.senate.gov` | 200; 24 committee-membership XML files fetched | 403 at the proxy |
| `fiscaldata.treasury.gov` | 200; the Monthly Treasury Statement | 403 at the proxy |
| `www.federalregister.gov`, `api.federalregister.gov` | 200; the agency directory | 403 at the proxy |

So an unreachable host is a fact about **this session**, not a standing
property of the project, and a fixture that exists is not evidence that its
source is reachable now. Two consequences, both already true of the code:

- every committed fixture is the only copy of its source the pipeline can
  count on, which is why they are committed at all;
- `scripts/fetch_fixture.py` writes a `.meta.json` for a refused fetch and no
  fixture, so a refusal is recorded with its date rather than looking like a
  source nobody thought to try. `tests/fixtures/opm/pay/` was the first entry
  made that way: OPM's Executive Schedule salary table, which would give 30
  matched positions an official rate of pay, refused on 2026-09-09. The table
  was fetched on 2026-09-11 and its `.meta.json` now records that fetch, so
  the refusal survives only in git history (commit 202a500).

Before concluding a host is blocked, try it — the list below is dated, not
permanent:

    python scripts/probe_network_access.py            # what is reachable now
    python scripts/probe_network_access.py --allowlist # the blocked hosts, paste-ready

That script reports *where* a 403 came from, which is the distinction that
matters: a refusal at the CONNECT, before a byte reaches the host, is the
sandbox; an HTTP status from the host is the host. Collapsing the two into
"failed" is what made the 2026-09-09 change look like the sites had changed
their minds.

## 0a. Which environment — the mistake this note used to invite

An allowlist belongs to a **cloud environment**, and this repository is
reachable from two of them:

| environment | id |
|---|---|
| `Default` | `env_018HP1sQhQm6Ff5TQZJcJ3XZ` |
| `Bureaucracy (Treasury)` | `env_01J86PgZpDPCZZFoX5fadMNY` |

An earlier version of this note told the reader to widen the allowlist of
"the one named Bureaucracy (Treasury)". That is the trap. The session that
produced every fixture and every verification run in this repository has run
in **`Default`** — confirmed on 2026-09-11 from the session's own
`environment_id`, not from the name. Editing the better-named environment
looks *exactly* like the setting not working: same 403, same CONNECT, no
error anywhere saying you changed the wrong thing.

So: ask the session which environment it is in before touching a setting.
The `claude-code-remote` `get_session` tool reports `environment_id`, and
`list_environments` maps ids to names. Widen that one.

## 1. Denied by the environment's network policy — 85 hosts, fixable

Every one of these answers a `CONNECT` with `403 Forbidden` at the egress
proxy before a byte reaches the host. They are not refusing us; the
environment is not letting us out. This is the entire set of hosts the
2026-09-08 seeding added (agency sites the Federal Register lists, and the
House's and Senate's own committee sites), which is why that run confirmed
nothing: the plan grew from 220 to 430 checks and every new one failed at
the proxy.

To fix, add these to the allowlist of the cloud environment the session
actually runs in — see §0a, and check the id rather than trusting a name —
then re-run `python scripts/verify_base_graph.py`. Nothing in the repository
needs to change; the candidates are already committed.

Three things to know before pasting:

- **`scripts/probe_network_access.py --allowlist` emits the list**, live, so
  it never goes stale the way a hand-maintained block does. On 2026-09-11 it
  printed 157 hosts.
- **That list includes the nineteen hosts of §2**, because they are
  proxy-blocked *as well as* robots-refused. Allowlisting them changes
  nothing: this project still declines them by its own conduct rule, and that
  rule is not to be relaxed to raise a coverage number. Widening the
  allowlist buys §1 and §3, not §2.
- A TLD wildcard is **not** a documented feature. The one documented form is
  a leading `*.` matching subdomains (`*.internal.example.com`), which would
  not match an apex domain in any case. Do not assume `*.gov` works; paste
  the hosts, or test a wildcard and verify with the probe before relying on
  it.

    agriculture.house.gov appropriations.house.gov armedservices.house.gov
    arts.gov budget.house.gov cha.house.gov disa.mil energycommerce.house.gov
    financialservices.house.gov foreignaffairs.house.gov homeland.house.gov
    intelligence.house.gov judiciary.house.gov naturalresources.house.gov
    rules.house.gov science.house.gov smallbusiness.house.gov trade.gov
    transportation.house.gov veterans.house.gov waysandmeans.house.gov
    www.abmc.gov www.aging.senate.gov www.agriculture.senate.gov www.ahrq.gov
    www.aphis.usda.gov www.appropriations.senate.gov www.arc.gov
    www.armed-services.senate.gov www.ars.usda.gov www.atf.gov
    www.banking.senate.gov www.bea.gov www.budget.senate.gov www.cbp.gov
    www.cdc.gov www.census.gov www.cms.gov www.commerce.senate.gov
    www.copyright.gov www.csb.gov www.dcaa.mil www.dia.mil www.dla.mil
    www.eac.gov www.eeoc.gov www.eere.energy.gov www.energy.senate.gov
    www.epw.senate.gov www.ethics.senate.gov www.faa.gov www.fbi.gov
    www.fca.gov www.fda.gov www.fec.gov www.fema.gov www.fhwa.dot.gov
    www.finance.senate.gov www.flra.gov www.foreign.senate.gov www.fra.dot.gov
    www.fs.usda.gov www.fsa.usda.gov www.fsis.usda.gov www.fta.dot.gov
    www.help.senate.gov www.hrsa.gov www.hsgac.senate.gov www.ice.gov
    www.ihs.gov www.indian.senate.gov www.intelligence.senate.gov
    www.judiciary.senate.gov www.marad.dot.gov www.mspb.gov www.ncua.gov
    www.neh.gov www.nga.mil www.osc.gov www.rules.senate.gov
    www.sbc.senate.gov www.secretservice.gov www.treasury.gov www.tsa.gov
    www.veterans.senate.gov

Four data hosts are denied the same way and would each unlock a whole line
of evidence:

| Host | What it serves | What it would unlock |
|---|---|---|
| `clerk.house.gov` | the House Clerk's committee XML | House subcommittee structure, the counterpart of the 43 Senate placements |
| `escs.opm.gov` | OPM's current PLUM export (positions as of 2026-06-15) | current positions; today only the previous administration's archive is available |
| `api.sam.gov` | SAM.gov Federal Hierarchy | the definitive executive-branch org structure — also needs an api.data.gov key, which only you can register for |
| `www.usa.gov`, `data.opm.gov`, `www.govinfo.gov` | agency index, OPM datasets, the printed Plum Book | secondary confirmations |

## 1a. Snapshot after the 2026-09-13 brute-force pass — 83 hosts still denied

`python scripts/probe_network_access.py --allowlist` on 2026-09-13, after
`nominate.py promote` queued the 159 pages the thirteen shard agents found:
every host below answered the CONNECT with 403 at the proxy. They are the
own-site domains of the units the pass could only nominate speculatively —
the national laboratories, the combatant commands, the circuit courts, NIST,
NIH, NOAA, CISA — so this is where the next coverage step is. The live
command is authoritative; this block is a dated paste-ready copy.

    ca3.uscourts.gov chaplain.house.gov crsreports.congress.gov department.va.gov diplomaticsecurity.state.gov
    ies.ed.gov legcounsel.house.gov ncses.nsf.gov srnl.doe.gov travel.state.gov
    www.af.mil www.americorps.gov www.ameslab.gov www.anl.gov www.armfor.uscourts.gov
    www.army.mil www.bop.gov www.ca1.uscourts.gov www.ca10.uscourts.gov www.ca6.uscourts.gov
    www.cem.va.gov www.centcom.mil www.chaplain.senate.gov www.cisa.gov www.cybercom.mil
    www.darpa.mil www.dcma.mil www.dfas.mil www.dfc.gov www.dtra.mil
    www.esd.whs.mil www.eucom.mil www.exim.gov www.fisc.uscourts.gov www.fletc.gov
    www.fmcsa.dot.gov www.fnal.gov www.fns.usda.gov www.ginniemae.gov www.health.mil
    www.inl.gov www.jcs.mil www.lbl.gov www.llnl.gov www.marines.mil
    www.navy.mil www.ncpc.gov www.nhtsa.gov www.nih.gov www.nist.gov
    www.nlrb.gov www.noaa.gov www.nps.gov www.nrcs.usda.gov www.nrel.gov
    www.nsa.gov www.ntia.gov www.ntsb.gov www.ornl.gov www.osha.gov
    www.pbgc.gov www.peacecorps.gov www.pfpa.mil www.phmsa.dot.gov www.pnnl.gov
    www.pppl.gov www.prc.gov www.socom.mil www.southcom.mil www.spacecom.mil
    www.spaceforce.mil www.sss.gov www.stratcom.mil www.usagm.gov www.usbr.gov
    www.uscg.mil www.uscis.gov www.uscourts.cavc.gov www.usmarshals.gov www.usmint.gov
    www.ustranscom.mil www.visitthecapitol.gov www.whitehouse.gov

## 1b. 2026-09-14, chasing salaries: one host opened, one newly denied

Probed while looking for official pay sources. Two findings worth keeping,
because each would otherwise be re-derived:

**`www.whitehouse.gov` is now reachable.** It is in §1a's denied list above,
dated 2026-09-13, and on 2026-09-14 it answered 200 — the allowlist widened
again between the two dates. That is what made
`tests/fixtures/whitehouse/staff_report_2026.pdf` fetchable, and with it the
only named-salary disclosure the federal government is required to publish.
Its `robots.txt` is `User-agent: * / Disallow:` — an empty disallow, which
permits everything. §1a's list is a dated paste, not a live fact; re-probe
before believing any line of it.

**`uscode.house.gov` answers the CONNECT with 403** — the egress proxy, not
the host, the same signature `clerk.house.gov` carried before it was
allowlisted. This is the one host that would unlock the rest of the
congressional pay work:

| Host | What it serves | What it would unlock |
|---|---|---|
| `uscode.house.gov` | the U.S. Code, 5 U.S.C. § 5332 Schedule 6 | the Speaker of the House ($223,500) and the House Majority and Minority Leaders ($193,400) — three curated position nodes that cannot be priced from the Senate's own salary page, whose footnote names only the three *Senate* leadership roles. Also 28 U.S.C. §§ 172(b) and 252, which give Court of Federal Claims and Court of International Trade judges the district-judge rate. (Corrected 2026-09-23, once both sections were read and committed under `tests/fixtures/uscode/`: § 172(b) does state that parity, but § 252 states none — it sets the rate by reference to section 225 of the Federal Salary Act of 1967 — so the Court of International Trade's judges stay unpriced; see `derived_pay.py`.) |

Two hosts here are refused **by the host, not by this session**, and no
allowlist change fixes them: `www.congress.gov` and `crsreports.congress.gov`
both serve a Cloudflare interstitial ("Just a moment…") with a 403,
confirmed from the response body. CRS report 97-1011 — the report the House
Clerk's own salary PDF cites for congressional pay, and the document most
likely to state the House's leadership premiums — is behind it.

Also probed and still denied at the proxy on this date: `www.dfas.mil` (403,
military basic pay tables) and `radiotv.house.gov` (403). `www.justice.gov`
answered 401.

## 2. Refused by this project's own robots policy — 19 hosts, deliberate

These hosts answer `robots.txt` itself with 401 or 403. Python's
`RobotFileParser` treats that as a blanket disallow, and this project keeps
the refusal as a matter of conduct even though RFC 9309 §2.3.1.3 would permit
the fetch — no longer a hedge: the standard is committed at
`tests/fixtures/standards/rfc9309.txt` and says "the crawler MAY access any
resources on the server" of a robots.txt in the 400-499 range. The record says "could not be
read (401/403); refused by policy" rather than quoting a rule nobody read.
**Do not change this to raise the coverage number.**

    www.aoc.gov www.cbo.gov www.commerce.gov www.defense.gov www.dhs.gov
    www.ed.gov www.fcc.gov www.federalreserve.gov www.ferc.gov www.ftc.gov
    www.gao.gov www.gpo.gov www.hhs.gov www.loc.gov www.sec.gov www.ssa.gov
    www.state.gov www.transportation.gov www.usda.gov

These nineteen include most of the cabinet departments, which is why the
Federal Register's directory and the Senate's committee list matter: they
are how those units get evidence at all.

## 3. Never attempted — 13 hosts

Candidates whose node the planner skipped because it was already confirmed
from another page; `--recheck` would fetch them.

    www.bia.gov www.blm.gov www.bls.gov www.boem.gov www.bsee.gov
    www.doleta.gov www.fincen.gov www.fws.gov www.irs.gov www.moneyfactory.gov
    www.msha.gov www.ttb.gov www.usgs.gov

## 4. 2026-09-15: the two causes have swapped places

The first position-verification pass re-measured all 238 candidate hosts,
and the picture above is now upside down:

    reached                                          131 hosts
    refused by THIS PROJECT's robots policy (401/403)  85 hosts
    denied by the environment's network policy         10 hosts
    other (host 403, TLS, reset, timeout, 404)         12 hosts

§1 was written when 85 hosts were denied at the proxy and 19 were refused
by the robots rule. **Those numbers have traded places.** The allowlist
widenings recorded in §1a and §1b worked: proxy denials fell 85 -> 10. What
they uncovered is that `robots.txt` answering 401/403 was underneath all
along, and it is now the binding constraint by a factor of eight.

Counted in fetches rather than hosts, over the 2026-09-15 run: **896
failures from the robots rule against 45 from the proxy.** The robots list
is every major department — `www.state.gov`, `www.ed.gov`, `www.hhs.gov`,
`www.dhs.gov`, `www.usda.gov`, `www.commerce.gov`,
`www.transportation.gov`, `www.defense.gov`, `www.fbi.gov`, `www.nih.gov`,
`www.federalreserve.gov`, `www.sec.gov`, `www.ssa.gov`, `www.army.mil`,
`www.navy.mil`, `www.af.mil` — 85 in all.

**So widening the allowlist further is now the small lever.** Ten hosts
remain denied at the proxy (`www.nrel.gov`, `www.treasury.gov`,
`www.fhwa.dot.gov`, `ca3.uscourts.gov`, `www.fns.usda.gov`, `trade.gov`,
`www.chaplain.senate.gov`, `www.anl.gov`, `www.lbl.gov`,
`www.armfor.uscourts.gov`), worth 45 fetches. The robots rule is worth
twenty times that and is **a policy decision in this repository**, not a
property of the sandbox: `data_pipeline/verification/politeness.py`, and
CLAUDE.md's note that RFC 9309 treats a 4xx on `robots.txt` as "Unavailable"
and permits access, while Python's `RobotFileParser` implements the older
401/403-means-disallow convention. **That hedge is no longer a hedge.**
`www.rfc-editor.org` answered 200 on 2026-09-15 and the RFC is committed
verbatim at `tests/fixtures/standards/rfc9309.txt`, with the digest its fetch
recorded; §2.3.1.3 and §2.3.1.4 are quoted in `politeness.py` and
`tests/test_politeness.py` asserts those sentences really are in the file. We
are deliberately stricter than the standard, and can now say so by quoting it
rather than by recalling it.

Nothing here is an argument for relaxing the rule, which stays until the
owner decides otherwise. It is an argument for not mistaking the allowlist
for the constraint.

## 5. 2026-09-15, later: the robots refusals were largely our own bug

Scoping the proposed relaxation of the 401/403 rule found the premise wrong
twice, and the second finding removed the need for the change.

**The relaxation was worth far less than §4 implies.** Probing all 86
refused hosts, **64 also answer 403 to the page itself**, so relaxing would
have moved those failures from "refused by policy" to "403 from the host"
and gained nothing. The ceiling was 245 fetches, not 896.

**The actual defect: we asked for robots.txt as somebody else.**
`RobotFileParser.read()` calls `urlopen` with no headers, so every
`robots.txt` went out as `Python-urllib/3.x` while every page went out as
this project's self-identifying agent. Federal hosts behind bot management
refuse the first and serve the second. Re-probed with our own agent, of the
86: **19 serve robots.txt (182 recorded failures), 3 answer 404 (78), and 64
still refuse (636)**.

So sending the right header recovers more than the relaxation would have,
and does it by making the verifier **more** obedient: those 19 hosts' rules
had never been read, and are now read and followed. nih.gov, fbi.gov,
loc.gov and census.gov went from "refused by policy" to "allowed by
robots.txt"; state.gov and defense.gov refuse our agent too and stay
refused. **The conservative 401/403 policy therefore stays unrelaxed**, and
now costs a handful of nodes instead of hundreds. No evasion was added: the
agent still names the project, and a host that refuses it is left alone.

**What the full re-run actually produced**, against the run before it:

    fetch_failed   1,209 -> 1,017   (-192: pages that are now read)
    inconclusive   1,560 -> 1,721   (+161: read, and simply not naming the unit)
    confirmed         20 ->     24
    not_found         69 ->     71

The honest reading is that the mechanical fix worked and the evidence yield
is modest: 192 more pages were read, and 161 of them do not label the unit
or post being checked. In the published graph: verified 191 -> 206, partial
304 -> 310, official source 563 -> 577, "no source recorded" 4,765 -> 4,750,
posts confirmed on their organisation's page 25 -> 28, placements 209 -> 212.

**No node lost anything.** Checked node-by-node against the previous
published graph: zero lost a `verificationMethod`, zero lost their
`sourceUrls`. The two counts that fell — the Federal Register directory
73 -> 62 and the Senate committee list 20 -> 18 — are 13 nodes *upgrading*
from a directory listing to their own official page, which is the
exporter's documented precedence working as intended.

## 6. 2026-09-16: the allowlist was widened, and it moved nothing — redirects

The owner widened the environment's allowlist. Proxy refusals fell **10 -> 4**
(`ca3.uscourts.gov`, `www.chaplain.senate.gov`, `www.nrel.gov` — all 502 —
and `www.fns.usda.gov`), and `probe_network_access.py` reported **233 of 245
hosts reachable**. The full re-verification that followed produced a
published graph **numerically identical** to the one before it: verified 206,
partial 310, official source 577, posts 28, placements 212. Not one number
moved.

**Why: the far end of a redirect is a different host, and nothing wrote it
down.** Only 7 curated nodes sit on the six hosts the widening opened, three
were already confirmed, and the remaining four still fail — because their
pages redirect off the allowlisted host:

    trade.gov/                     -> 301 -> www.trade.gov
    www.fhwa.dot.gov/              -> 307 -> highways.dot.gov
    www.treasury.gov/...OFAC.aspx  -> 302 -> ofac.treasury.gov
    www.fns.usda.gov/              -> 301 -> www.fna.usda.gov

The proxy's own `recentRelayFailures` names those targets, not the hosts we
asked for, which is what made it findable.

**And this probe was reporting them as reachable.** `probe()` asks for
`/robots.txt`, which usually does not redirect: `trade.gov/robots.txt`
answered 200 while `trade.gov/` answered `Tunnel connection failed: 403`. So
the "reachable: 233" line overstated the truth for every host whose pages
redirect somewhere unlisted. A host is only as reachable as the last hop of
its redirect chain, and the docstring now says so.

`REDIRECT_TARGETS` records the ten measured by requesting all 454 candidate
URLs with redirects disabled and reading the `Location` header; they are
included in `--all-hosts` (247 -> 257) and `--domains` (168 -> 171), and
`--redirect-targets` re-derives them live and reports drift in both
directions rather than leaving a hand-kept list to rot.

**These ten are what still needs allowlisting:**

    chinaselectcommittee.house.gov      ofac.treasury.gov
    financialresearch.gov               www.arts.gov
    highways.dot.gov                    www.bep.gov
    ncua.gov                            www.dea.gov
    www.fna.usda.gov                    www.trade.gov

Which is the argument for `*.gov` and `*.mil` made again, from a different
direction: a host-by-host allowlist cannot anticipate where a federal site
will redirect next, and the code already refuses every host outside those
two suffixes.

## 7. 2026-09-16, later: the wildcard landed, and the wall is not ours

The allowlist was widened to `*.gov` and `*.mil` on the **Default**
environment — `env_018HP1sQhQm6Ff5TQZJcJ3XZ`, read off the session with
`get_session` rather than picked by name, which is the mistake §0a exists to
prevent and the one the 2/245 session made. `probe_network_access.py` reports
**235 of 245**, against §6's 233.

The count is not the news, because §6's 233 moved nothing. What is new is that
the four redirect chains §6 named now complete **end to end**, tested by
requesting the pages themselves with redirects followed rather than
`/robots.txt` — the methodology §6 identified as the thing that overstated it:

    trade.gov/                     -> 301 -> www.trade.gov          200
    www.fns.usda.gov/              -> 301 -> www.fna.usda.gov       200
    www.treasury.gov/...OFAC.aspx  -> 302 -> ofac.treasury.gov      200
    www.fhwa.dot.gov/              -> 307 -> highways.dot.gov       403 from the host

All ten `REDIRECT_TARGETS` pass the CONNECT, and the wildcard covers the apex
as well as the subdomain: `trade.gov` and `www.trade.gov` both answer, as do
`arts.gov`, `ncua.gov` and `treasury.gov` beside their `www` forms. All ten
data hosts answer, including four this repository recorded as refused —
`escs.opm.gov`, `clerk.house.gov`, `api.sam.gov`, `www.govinfo.gov`. Three
hosts still fail (`ca3.uscourts.gov`, `www.chaplain.senate.gov`,
`www.nrel.gov`), all with 502 at CONNECT rather than 403; bare `navy.mil` also
answers 502 while `www.navy.mil` is reached under the same `*.mil` wildcard, so
these read as upstream failures rather than policy, and widening again would
not move them.

The full pass over all 2,809 checkable nodes then moved the published graph by
**two**: `exec-dept-treasury-ofac` unverified -> verified and `exec-dept-doc-ita`
partial -> verified, which are two of §6's own four. FHWA is now a 403 from the
host, and FNS's page is now *read* and simply does not label the curated name
"Food & Nutrition Service (FNS)" — a curation question about the ampersand, not
a network one.

**Of 1,042 remaining `fetch_failed`, zero were refused at the proxy.** 752 are
robots.txt, 148 are under the 400-character floor, 86 are a 403 from the host
and 56 a 404. The allowlist question is closed. §6's "the widened allowlist
moved nothing" has its sequel: the widening was necessary and was never
sufficient, because it was the binding constraint for a handful of nodes only.

### Are the robots refusals keyed to our User-Agent? Measured: no.

§5 fixed a real bug — robots.txt had been fetched as `Python-urllib/3.x` while
pages were fetched as this project's agent — and left 64 hosts refusing. The
obvious next hypothesis was that those 64 are keyed to the agent too. Probed
directly, all 64 hosts, robots.txt and the candidate page, under our own agent,
a browser agent, and urllib's default:

* **our agent and `Python-urllib` get identical statuses on every one of the
  64.** The §5 lever is fully spent; there is nothing further in that direction.
* a browser agent string recovers robots.txt on **7 hosts (75 nodes)** and the
  page on **7 hosts (74 nodes)**. Adopting one is refused here on its own
  merits: the agent exists so a site owner reading their logs can find out what
  this is and who to complain to, and a browser string is a lie told to a
  government server.
* **55 hosts (602 nodes) refuse the page to every agent tried**, including a
  full browser header set over HTTP/2 via curl, which is a different TLS stack
  from urllib's. That is consistent with egress-IP reputation, which no
  client-side change reaches.

**§5's parenthetical is falsified in two places, and only two.** It says every
one of the 64 "refuses the page itself to the same agent". `www.nga.mil` (8
nodes) and `www.army.mil` (12 nodes) serve the page 200 to our own agent while
refusing robots.txt. So relaxing the 401/403 refusal to what RFC 9309 §2.3.1.3
permits is worth **20 nodes**, not the 696 the refusal count suggests — §5's
judgement that it is worth nearly nothing stands, with that correction.

### One host is not blocking us at all, and it is the largest

`www.justice.gov` is **probabilistic**, not deterministic. Alternating
conditions to control for load, it served 4 of 12 to our own honest agent and 2
of 12 to a browser agent — the browser did no better. Its robots.txt behaves the
same way: refused, refused, then **HTTP 200, 2,651 bytes of `text/plain`**, a
standard Drupal robots.txt with 78 directive lines. Not a challenge page.

Parsed, it permits everything this project wants:

    can_fetch /about                                       -> True
    can_fetch /agencies                                    -> True
    can_fetch /doj/organization-mission-and-functions-manual -> True
    crawl_delay                                            -> None

Its 50 `Disallow` lines are Drupal internals — `/core/`, `/profiles/`, README
files. So **67 nodes are refused on the strength of a rule the Department of
Justice never published**, and its real rules allow the fetch.

The lever here is a bounded retry on robots.txt, not a policy change and not an
agent change. It is the same shape as the §5 fix: it makes the verifier *more*
obedient, because it reads and follows a published file instead of assuming a
blanket disallow nobody wrote.

### Implemented and measured, 2026-09-17 — and the number above was the wrong number

`RobotsPolicy` and the verifier's page fetch now ask again on 401, 403 and 5xx
— `--retries` (default 2) more times, waiting `--retry-backoff` (default 2)
seconds times the attempt number — and never on a 404 or a network error. The
verdict records how many knocks it took, so a third-try success is never
written up as a first-try one, and `tests/test_verification.py` pins it in
both directions: a refusal that clears yields the rules that were finally
read; a refusal that never clears is refused after exactly the bounded
attempts and says so; a 404 and a DNS failure get one knock; `--retries 0` is
the old behaviour to the call.

Then it was run against the 67 justice.gov nodes, twice, and the honest
result is this. **The "67 nodes" above was the count of refusals, not of
confirmations waiting behind them, and those are different quantities.**

*First run (default retries):* 10 distinct pages planned, **5 read** —
`/about`, `/enrd`, `/civil`, `/crt`, `/nsd` — where none had been before.
34 records moved from `fetch_failed` to `inconclusive` and 4 placement checks
were made. **Confirmations: 0.** 63 of the 67 are posts, checked only against
the department's About page, which names none of them; the Environment &
Natural Resources Division's own page names it in prose and not as a label
(`named_on_the_page_but_not_as_a_label`); the Tax Division reached only the
About page. A page read and found not to label the unit is real evidence —
it replaces "the network failed" with "we looked" — but it is not a source.

*Second run, 30 minutes later, the 33 still failing, `--retries 4
--retry-backoff 3`:* **0 of 6 pages.** Every one refused at robots.txt itself,
401 on each of five knocks across thirty seconds of backoff, where the first
run had read the same file. The success rate across this session went 4/12,
1/8, then 0/5: the host escalates against sustained probing, exactly as the
caution above said, and the retry must stay gentle for that reason.

So the retry is right and small: it converts a network non-answer into a
read where the host lets it, at the cost of a few seconds per refused host,
and it costs nothing where the host does not. It does not reach the 67 —
there is nothing on those pages for most of them to reach — and the sentence
above that read as if it did is corrected here rather than left standing.

## 8. 2026-09-18/19: three hosts this file recorded as denied now answer

Re-measured directly, because §7 says the wall is no longer the proxy and the
right response to that is to retry the things the proxy used to refuse rather
than carry the old list forward.

    uscode.house.gov     robots.txt 200   — recorded as CONNECT 403 in §1b
    www.govinfo.gov      robots.txt 200   — recorded as CONNECT 403 in CLAUDE.md
    clerk.house.gov      robots.txt 404   — i.e. nothing published to obey; crawled

`uscode.house.gov` is the one that paid. It serves the United States Code,
and 5 U.S.C. §§5312–5316 is the Executive Schedule itself — the list of which
positions Congress placed at which level. Until this session every Executive
Schedule rate in the graph took its level from OPM's PLUM archive of the
*previous* administration, reaching 29 positions; the statute took it to 99,
including the Secretary of State, the Attorney General and the Secretary of
Defense, none of which carried pay evidence of any kind. It also supplied the
citation that finished a curation gap this repository had recorded as
unfixable: thirteen cabinet heads were left spelled "Secretary of Department
of X" because "no source in hand names them", and §5312 names every one.

`www.govinfo.gov` answering 200 is recorded here but **not yet used**. It
serves the Budget Appendix and agency Financial Reports, which
`docs/EXACT_NODE_COSTS.md` names as the third step of the route to more
exact-node costs. Nobody has read one from here yet; this note exists so the
next session does not re-derive that it is blocked.

### What is still the wall, and it is not the proxy

The 2026-09-18 pass over all 304 organisations with no candidate page fetched
every candidate it could name and recorded a probe-backed reason for each.
The causes, which were previously all filed as "no page known":

    109  the page was read and does not carry the graph's NAME  — curation
     45  a real .gov/.mil site that refuses robots.txt          — policy
     37  an editorial grouping the government never names
     33  not on a .gov host (Smithsonian, USPS, Fed banks)
     28  genuinely no page anyone could name

So roughly half the remaining gap is a naming problem and a fifth is this
project's own robots policy, and neither is fixed by nominating more URLs.
The robots policy is deliberate and documented in
`data_pipeline/verification/politeness.py`; the naming problem is curation,
and `scripts/probe_candidate_pages.py --orphan-labels` prints what each page
calls the unit so a rename can be argued from the page's own words.

## Regenerating this note

    python scripts/report_unreachable_hosts.py            # why each host failed, from the last run
    python scripts/probe_network_access.py                # what this session can reach right now
    python scripts/probe_network_access.py --allowlist    # hosts the proxy refuses TODAY
    python scripts/probe_network_access.py --all-hosts    # every host this repo could ever need
    python scripts/probe_network_access.py --domains      # the same, as registrable domains

The counts above are a snapshot; the causes are stable. A host that moves
from group 1 to "reached" was the only change that raised coverage while §1
held; since §7 found no proxy refusal left, coverage has also moved through
renames and documents read offline (§8, §11), which need no host at all.

**Building an allowlist that does not go stale.** `--allowlist` is reactive:
it names what is broken now, and a promoted nomination or a new curated page
invalidates it. `--all-hosts` (247 on 2026-09-15, 342 on 2026-09-23) and
`--domains` (168 on 2026-09-15, 232 on 2026-09-23) are the superset,
read from `official_sites.json`, the provenance file, every nomination
ledger and every URL `evidence.json` has tried — so they already carry hosts
nobody has fetched yet. The whole-estate answer is `*.gov` and `*.mil`, and
it grants nothing the code does not already grant itself:
`classify_source_url` returns `official_site` for those two suffixes and
nothing else, `verify_node` and `verify_placement` refuse any URL that is
not `official_site`, `nominate.py` refuses a nomination on any other host,
and the gate refuses an `official_site` claim with no `.gov`/`.mil` URL
behind it. A narrower network allowlist adds no safety over that — only a
second list to keep in step, which is what §0 cost a day to.

## 9. 2026-09-19: govinfo is reachable and still refused, and escs.opm.gov moved

Two of §8's notes needed re-measuring after the §9 rename pass, and both
changed. Measured directly, not inferred.

### `www.govinfo.gov` answers 200 — and the project's own rules still refuse it

§8 recorded the host answering `robots.txt` 200 and left it "not yet used",
which reads like an opportunity waiting to be taken. It is not. Traced to the
end:

    www.govinfo.gov/robots.txt        200   — /content/ and /app/ allowed, /search/ Disallow
    api.govinfo.gov/robots.txt        500   — a complete disallow under RFC 9309 §2.3.1.4
    www.govinfo.gov/app/collection/budget   200, and 15 readable characters

The content paths are crawlable, but only if the package id is already known.
The two ways to *find* one are both refused: `/search/` is explicitly
disallowed in the site's own robots.txt, and `api.govinfo.gov` — which is
what the `/app/` pages call — answers `robots.txt` with 500, which RFC 9309
makes a complete disallow and which this project honours (the committed copy
is `tests/fixtures/standards/rfc9309.txt`). The collection browse page is an
Angular shell: 15 readable characters, far below this project's 400-character
floor, so nothing can be read off it either. A guessed package path
(`/content/pkg/BUDGET-2026-APP/html/BUDGET-2026-APP.htm`) redirects to
`/error`.

So the Budget Appendix is not available to this project today, and the
blocker is not the network — it is govinfo's own robots.txt on the endpoint
that indexes it. Recorded as a refusal rather than a to-do so the next
session does not spend the probe again. It would become available if the API
published a robots.txt, or if a package id were obtained from somewhere else.

### `escs.opm.gov`: the blocker moved from the proxy to the host

`CLAUDE.md` records OPM's current PLUM export as unavailable because "the
pipeline's egress proxy refuses (CONNECT 403)". That is no longer the reason.
The proxy now connects; the **host** answers:

    escs.opm.gov/robots.txt   403 Access Denied (Akamai edge)

This project refuses a host that answers `robots.txt` with 401 or 403 — by
its own choice, not by the standard, and the distinction matters for what the
record may say: "could not be read (403); refused by policy", never "disallows
/path", because no rule was read. So the outcome is unchanged and the reason
is different, and the difference is worth having written down: a proxy
refusal might be lifted by an allowlist change, an Akamai 403 will not be.

The practical consequence is unchanged too. Position evidence still rests on
the **previous** administration's archive (January 2021 – January 2025), every
record still names that archive and its period, and nothing in this graph
claims to say who holds a post now.

## 10. 2026-09-20: the refusal on `escs.opm.gov` was withdrawn, and the fetch still has not happened

Two separate things, and this note keeps them apart because conflating them
is how a repository ends up believing it holds a file it does not.

### What changed: a policy, for one host, recorded rather than made quietly

§9 above ends by saying the outcome for `escs.opm.gov` is unchanged and only
the reason moved — from the proxy to the host. The repository owner has since
instructed, explicitly, that the refusal be withdrawn for that host.

The refusal was never the standard's. RFC 9309 §2.3.1.3 calls a `robots.txt`
answered 4xx "Unavailable" and permits the crawler to access the server;
Python's `RobotFileParser` implements the older convention in which 401 and
403 alone mean disallow-all, and `politeness.py` has always kept that stricter
behaviour **on purpose**, saying so in its own docstring: "the one place we
are deliberately stricter than the rule we cite". Withdrawing it for a host is
therefore a policy change to be made in the open, not a bug fix.

`politeness.STANDARD_4XX_HOSTS` is that withdrawal. It is a per-host list, not
a switch:

- one entry, `escs.opm.gov`, carrying the reason and the date it was added;
- it applies **only** to 401/403. A listed host answering 5xx, or failing at
  the network, is refused exactly as any other host is — that is §2.3.1.4,
  where the standard itself requires a complete disallow, and nothing here
  touches it;
- it manufactures no rule. The verdict says in as many words that the file
  could not be read and that no rule was seen; what it adds is which
  permission the fetch rests on. No record may read as though `robots.txt`
  had been fetched and had allowed the path;
- it relaxes nothing else. The User-Agent still names the project and a
  published crawl delay still applies.

`scripts/fetch_fixture.py` was carrying its own second copy of the 401/403
rule and now imports the list instead. A per-host exception written in one
place and not the other is how a fetch gets refused by the fetcher while the
verifier allows it, or worse the other way round.
`tests/test_politeness.py::TheStandard4xxHostListTests` pins all of it in both
directions, including that a host merely *ending* with a listed one is not
listed — substring matching is how an allowlist becomes a wildcard.

### What did NOT change: nothing has been fetched from that host

The export is **not** in `tests/fixtures/`, no `plum_current` module exists,
and no published node carries a current-PLUM claim. Position evidence still
rests entirely on the **previous** administration's archive (January 2021 –
January 2025), every record still names that archive and its period, and
nothing in this graph claims to say who holds a post now.

The reason is this session's own sandbox rather than the host: the agent
harness declined the outbound request, so the policy above is correct and
tested offline and has never been exercised against the live server. A copy
of the export obtained earlier in the session is deliberately **not**
committed: it was fetched before the policy existed and therefore without any
robots check at all, so its `.meta.json` could not honestly say which
permission it rested on. A fixture whose provenance record is a guess is worse
than no fixture, and this repository's whole fixture convention — the
publisher's own bytes, a sibling `.meta.json`, a digest recomputed before
reading — exists to prevent exactly that.

So the standing entry for this host is now: **permitted by policy, unfetched
in fact.** The next session with outbound access should run

    python scripts/fetch_fixture.py \
        https://escs.opm.gov/escs-net/api/pbpub/download-data \
        opm/plum/escs_pbpub_download-data.csv

and let the recorded verdict be whatever the host actually answers.

## 11. 2026-09-20, later: the 715 robots refusals, measured host by host

§10 withdrew the 401/403 refusal for one host. This section is the
measurement that decides whether it should be withdrawn for any other, and
the answer is: for exactly one more.

**The question.** `evidence.json` records **715** fetch attempts refused with
`robots.txt could not be read (401/403); refused by policy, no rule was seen`,
across 68 hosts — `www.state.gov` 34, `www.uscg.mil` 26, `www.defense.gov`
19, `www.af.mil` 19, `www.jcs.mil` 18, and 17 each for `www.usda.gov`,
`www.commerce.gov`, `www.hhs.gov`, `www.transportation.gov`, `www.dhs.gov`,
`www.navy.mil` and `www.spaceforce.mil`; then the SEC, FCC, SSA, the DHS
components (CBP, TSA, USCIS, ICE, FEMA, CISA, Secret Service, FLETC), the
combatant commands, and the DOE laboratories. That is the largest single
mechanical cause of "no source recorded" on an organisation in this graph,
and it rests on a choice this project made — RFC 9309 §2.3.1.3 would permit
the fetch. So the choice was worth costing: if those hosts serve the *page*
while refusing the robots file, the refusal is withholding real evidence; if
they refuse both, the refusal changes nothing and the 715 are a fact about
the network.

**The measurement.** One request per host for `robots.txt` and one for a
page the verifier had actually queued there, under the project's User-Agent,
with the readable-text count computed by the verifier's own `parse_page` so
the floor means what the verifier's would. Read-only; nothing written outside
the scratchpad.

    (robots, page)   hosts
    (403, 403)         66
    (401, 401)          1     www.justice.gov
    (403, 200)          1     www.nga.mil  — 3,408 readable characters

**67 of 68 hosts refuse the page with exactly the status they refuse the
robots file.** `www.state.gov` answers from CloudFront with an S3 "Technical
Difficulties" body; the `.mil` hosts and the departments answer from Akamai.
That is bot protection against this egress address, and it is a fact about
the network, not about any rule this project follows: withdrawing the 401/403
refusal for those hosts would change no outcome at all, and so it is not
done. `www.nga.mil` is the one host where the refusal was actually
withholding a readable page, and it is now the second entry in
`politeness.STANDARD_4XX_HOSTS`, with this measurement as its reason. Its
eight refused nodes were re-run: the agency confirmed off its own homepage;
its seven posts came back `inconclusive`, which is what an organisation's
page not labelling a post means.

**What this settles, and what it moves.** The 715 refusals are, to within
one host, **unrecoverable from this environment**, and the site should say
that rather than present them as a policy choice. The route to evidence for
units on those hosts is therefore not a page at all: a directory the
government publishes elsewhere — the Federal Register's agency list, which
already reaches 158 of them, and the Government Manual, which names every
one of these agencies in a document this repository already holds verbatim
and currently reads only for posts. Extending `govman.py` to confirm an
organisation from its own Manual entry is the single largest lever left on
organisation coverage, and it needs no network.

## 12. 2026-09-21: the Plum Book export landed, and the pay tables with it

Two fetch sessions in one, both through `scripts/fetch_fixture.py`, both
recorded in the fixtures' `.meta.json` files and nowhere else by hand.

### `escs.opm.gov`: fetched, on a permission neither §9 nor §10 anticipated

§10 ends "permitted by policy, unfetched in fact" and prescribes the exact
command. It was run, and the export landed on the first attempt:
`tests/fixtures/opm/plum/escs_pbpub_download-data.csv`, 2,817,437 bytes,
`text/csv`, sha256 `14b39c477f66b0478298d7a49963bd3c99d22b39dd81ea43acb10c3151f070f6`.
The harness did not decline the request this time.

What the fetch rests on is worth stating exactly, because it is not the
`STANDARD_4XX_HOSTS` permission §10 withdrew the refusal for. On 2026-09-19 the
host answered `robots.txt` with an Akamai 403 (§9). On 2026-09-21 it answered
**200 with an HTML page** — 25,108 bytes, `text/html`, the site's own template
with a `<title>ESCS.OPM.GOV - OPM.gov</title>` — at `/robots.txt`. Python's
`RobotFileParser` reads such a body as a robots file with no parseable
directives, and RFC 9309 §2.3.1.2 says a successfully fetched file's
parseable rules must be followed; there are none, so the path is allowed by
the standard's ordinary rule. `fetch_fixture.robots_verdict` writes `allows
/escs-net/api/pbpub/download-data` in that case. That string should be read as
"no rule forbids it", not as "a rule permits it": no directive was read. The
`STANDARD_4XX_HOSTS` entry stays, with its dated reason, for the day the host
answers 403 again. `get-current-agencies` on the same base answers 404 to a
GET (the page's script POSTs a filter body to it); nothing depends on it.

**What the file is** is in `tests/fixtures/opm/README.md` §1: 15,777 rows, 15
columns, a `Pay Plan` column and a `Level, Grade, or Pay` column carrying a GS
grade, an Executive Schedule level or a rate — the same three things the
archive's `LevelGradePay` holds — with 3,761 GS rows carrying a grade. The two
name columns and the unique-ID column are never read. **`plum_current.py` reads
it since the same day** (CLAUDE.md, "The current Plum Book, read"): 170 positions
listed, 100 with the rate the export prints, as a second document beside the
archive and never over it.

### `www.opm.gov`: the 2026 GS, SES and SL/ST tables

`salary-tables/26Tables/html/GS.aspx` answered 200 directly. The two addresses
the task named for the SES and SL/ST tables (`26Tables/html/ES.aspx`,
`.../SLST.aspx`) answered 200 by **redirecting to the OPM homepage** — one
identical 63,890-byte digest for both — and those fetches were deleted rather
than committed: `fetch_fixture.py` records a redirect's `final_url`, and a
200 whose final URL is the site root is not the table. OPM's own 2026
executive-and-senior-level index links the tables under
`26Tables/exec/html/ES.aspx` and `.../SLST.aspx`, which answered 200 in place.
The GS PDF (`26Tables/pdf/GS.pdf`) redirected to
`salary-tables/pdf/2026/GS.pdf` and was re-fetched at that address, so the
committed record cites the URL that served the bytes;
`gs_pay._load_fixture` refuses any fixture whose `final_url` differs from its
`url`, which is the rule that caught the homepage case. Neither 2026 index page
links a pay-adjustment Executive Order or an OPM memo — the only related link
is the generic Compensation Policy Memoranda index — so nothing was fetched
for that item and nothing is recorded as refused.

## 13. 2026-09-21: www.federalregister.gov, and a host that refuses at random

`www.federalregister.gov` has been in this pipeline since the beginning — the
discovery crawler reads `api/v1/documents.json` and `directories.py` reads
`api/v1/agencies.json` — but nothing had ever fetched a document's own text.
`data_pipeline/verification/federal_register_signatures.py` does, for the
signature block every rule and notice ends with.

**The permission.** `robots.txt` answers **200** with real rules: five
`Disallow` lines for search paths, plus `/my/` and `/auth/`,
`/documents/current` and `/documents/email-a-friend`. Neither path read here is
covered by any of them, so both are allowed by rules that were actually read —
not by the "nothing published to obey" fallback most of this project's sources
rest on. Every `.meta.json` in `tests/fixtures/federal_register/signatures/`
records the verdict as `allows <path>`. No crawl-delay is stated; a 2.5-second
delay was kept anyway.

**One robots fetch, not four hundred.** This is the first source here that
needs several hundred files from one host, and `fetch_fixture.robots_verdict`
re-read `robots.txt` before every one of them. It now takes an optional
per-host cache — the caller owns the dict, the rules are still applied per
path, and omitting it keeps the old behaviour exactly — so the run read the
file once. A project whose deliverable is public trustworthiness should not
request one file four hundred times to prove it is being polite.

**The host refuses at random, and the refusal is not about us.** A document's
`raw_text_url` answers, perhaps one time in three, with a 10,596-byte
`text/html` page titled **"Federal Register :: Request Access"** — served with
HTTP **200**, so nothing in the status says anything is wrong. The same URL
serves the document on the next attempt. Measured against three header sets
(the project agent alone; with `Accept: text/plain`; with `Accept`,
`Accept-Language` and `Accept-Encoding: identity`) the rate did not move:
9, 6 and 8 documents of 12. It is not a rule, not a rate limit anybody stated,
and not a fact about this project's agent.

**Slowing down does not reliably help either**, which was worth measuring
rather than assuming. The run was paced at 2.5, 2.0, 6.0 and 2.5 seconds
between documents in four stretches, and the refusal page came back on
**63%, 68%, 59% and 82%** of requests. It drifts between roughly three in five
and four in five and does not track the delay in any clean way, so it is not a
simple rate limit and there is no pace that buys the document. What it costs is
attempts rather than patience, so the run allows twelve of them, after which
nothing is committed and the `.meta.json` records why.

What matters is what is done with such a response, and the answer is nothing.
It is **not the document**, so it is never parsed — the fetch deletes it,
waits, and retries, up to the twelve attempts above. Where the host never
served the document, no `.txt` is committed and the `.meta.json` beside it
carries the reason; the module counts those as
`documents_refused_by_the_host` rather than dropping them, so
the fixture set's own README and the derive step both state how many documents
the listings name that the host would not hand over.
