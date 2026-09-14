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

## Regenerating this note

    python scripts/report_unreachable_hosts.py

The counts above are a snapshot; the causes are stable. A host that moves
from group 1 to "reached" is the only change that raises coverage.
