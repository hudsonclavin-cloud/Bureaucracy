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
  source nobody thought to try. `tests/fixtures/opm/pay/` is the first entry
  made that way: OPM's Executive Schedule salary table, which would give 30
  matched positions an official rate of pay, refused on 2026-09-09.

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

Two things to know before pasting:

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
| `uscode.house.gov` | the U.S. Code, 5 U.S.C. § 5332 Schedule 6 | the Speaker of the House ($223,500) and the House Majority and Minority Leaders ($193,400) — three curated position nodes that cannot be priced from the Senate's own salary page, whose footnote names only the three *Senate* leadership roles. Also 28 U.S.C. §§ 172(b) and 252, which give Court of Federal Claims and Court of International Trade judges the district-judge rate. |

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
the refusal as a matter of conduct even though RFC 9309 [likely; unverified
from this environment] would permit the fetch. The record says "could not be
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
CLAUDE.md's note that RFC 9309 [likely; unverified from this environment]
treats a 4xx on `robots.txt` as "Unavailable" and permits access, while
Python's `RobotFileParser` implements the older 401/403-means-disallow
convention. That hedge is still a hedge: `www.rfc-editor.org` and
`datatracker.ietf.org` are themselves refused at the proxy, so the standard
cannot be read from here to settle it. Both are in `--all-hosts` for that
reason.

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
blanket disallow nobody wrote. It is not implemented here — that is a
deliberate change to `politeness.py` with tests in both directions, and this
section only records the measurement that justifies it.

Two cautions for whoever implements it. The success rate fell across the
session — 4/12 early, 1/8 later — which is consistent with the host escalating
against sustained probing, so the retry must be gentle and backed off, not
aggressive. And a 200 must still be checked for being a real robots.txt rather
than a challenge page served with the wrong status; on this host it was real,
and that is a fact about this host on this day, not a guarantee.

## Regenerating this note

    python scripts/report_unreachable_hosts.py            # why each host failed, from the last run
    python scripts/probe_network_access.py                # what this session can reach right now
    python scripts/probe_network_access.py --allowlist    # hosts the proxy refuses TODAY
    python scripts/probe_network_access.py --all-hosts    # every host this repo could ever need
    python scripts/probe_network_access.py --domains      # the same, as registrable domains

The counts above are a snapshot; the causes are stable. A host that moves
from group 1 to "reached" is the only change that raises coverage.

**Building an allowlist that does not go stale.** `--allowlist` is reactive:
it names what is broken now, and a promoted nomination or a new curated page
invalidates it. `--all-hosts` (247) and `--domains` (168) are the superset,
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
