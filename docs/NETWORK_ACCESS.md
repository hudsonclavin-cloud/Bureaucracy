# What the verifier can reach, and what it cannot

The verification pipeline only ever makes claims about pages it actually
read. When a page cannot be read, the record says `fetch_failed` and applies
nothing — so an unreachable host does not weaken the site's honesty, it
just leaves the node unverified. This note says which hosts are unreachable
and why, because two of the three causes are fixable and one is deliberate.

Counted from `data/verification/official_sites.json` (149 candidate hosts)
against the failure reasons in `data/verification/evidence.json`, after the
live run of 2026-09-08.

## 1. Denied by the environment's network policy — 85 hosts, fixable

Every one of these answers a `CONNECT` with `403 Forbidden` at the egress
proxy before a byte reaches the host. They are not refusing us; the
environment is not letting us out. This is the entire set of hosts the
2026-09-08 seeding added (agency sites the Federal Register lists, and the
House's and Senate's own committee sites), which is why that run confirmed
nothing: the plan grew from 220 to 430 checks and every new one failed at
the proxy.

To fix, add these to the allowlist of the cloud environment the verifier
runs in (the one named "Bureaucracy (Treasury)"), then re-run
`python scripts/verify_base_graph.py`. Nothing in the repository needs to
change; the candidates are already committed.

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
