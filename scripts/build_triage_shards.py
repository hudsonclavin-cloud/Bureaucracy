"""Build the per-organisation context shards for phase 1c (evidence triage).

    python scripts/build_triage_shards.py <out_dir> <shards> [<host_measurement.json>]

One JSON per shard, each organisation carrying everything the repository
knows about it: siblings with their evidence state and queued URLs (the
Court of Appeals defect was visible in one glance at that row), the evidence
record and why it failed, which queued hosts the measurement found walled,
any Federal Register listing, prior nominations from the ledger (later wins
by nominatedAt), the cost state, candidate Treasury lines whose name
overlaps the unit's, and OMB names that overlap it. Reads only committed
files; writes only the shard JSONs. docs/EVIDENCE_TRIAGE_RUNBOOK.md is the
brief the agents follow against these files.
"""
import json, sys, glob, re, collections
from pathlib import Path
from urllib.parse import urlparse
sys.path.insert(0, "/home/user/Bureaucracy")
from data_pipeline.verification.evidence import canonical_name_key as K
from data_pipeline.exporter.treasury_sections import SectionTree
from data_pipeline.verification import omb_budget
R = Path(__file__).resolve().parents[1]; S = Path(sys.argv[1]); N = int(sys.argv[2])
MEASUREMENT = Path(sys.argv[3]) if len(sys.argv) > 3 else R / "data/audit/host_measurement_2026-09-20.json"
g = json.load(open(R/"output/graph.json")); root = g.get("tree") or g.get("root") or g
base = json.load(open(R/"data/federal_gov_complete_1.json")); broot = base.get("tree") or base.get("root") or base
ev = json.load(open(R/"data/verification/evidence.json"))["nodes"]
sites = json.load(open(R/"data/verification/official_sites.json"))
prov = json.load(open(R/"data/verification/official_sites_provenance.json"))
dirv = json.load(open(R/"data/verification/directory_evidence.json")); dirv = dirv.get("nodes") or dirv
meas = {r["host"]: r for r in json.load(open(MEASUREMENT))}
DEAD = sorted(h for h, r in meas.items() if r.get("page_status") != 200)
# unapplied Treasury money lines, computed here rather than read from a file
_rows = json.load(open(R/"tests/fixtures/mts_table5_latest.json"))["rows"]
_g = json.load(open(R/"output/graph.json")); _root = _g.get("tree") or _g.get("root") or _g
_applied = set()
def _walk_applied(n):
    if n.get("treasury_classification_id"): _applied.add(str(n["treasury_classification_id"]))
    for r in n.get("treasury_component_rows") or []: _applied.add(str(r.get("classification_id")))
    for c in n.get("children", []) or []: _walk_applied(c)
_walk_applied(_root)
_comp = set(map(str, SectionTree.from_rows(_rows).receipts_component_ids()))
un = []
for r in _rows:
    d = r["classification_desc"]; amt = r["current_fytd_net_outly_amt"]; cid = str(r["classification_id"])
    if amt in (None, "null") or d.endswith(":") or d.startswith("Total") or cid in _comp or cid in _applied: continue
    un.append({"classification_id": cid, "desc": d, "fytd_net": float(amt), "parent_id": str(r.get("parent_id"))})
rows = json.load(open(R/"tests/fixtures/mts_table5_latest.json"))["rows"]
byid = {str(r["classification_id"]): r for r in rows}
def section_of(cid):
    seen = set(); cur = byid.get(cid); top = None
    while cur and cur.get("parent_id") not in (None, "null", "") and cid not in seen:
        seen.add(cid); cid = str(cur["parent_id"]); cur = byid.get(cid)
        if cur: top = cur["classification_desc"].rstrip(":")
    return top
# ledgers, later record wins by nominatedAt
def ledger(kind):
    best = {}
    for f in glob.glob(str(R/f"data/audit/nominations/{kind}-*.jsonl")):
        for ln in open(f):
            try: r = json.loads(ln)
            except Exception: continue
            if r.get("kind") != kind: continue
            k = r["id"]
            if k not in best or (r.get("nominatedAt","") > best[k].get("nominatedAt","")): best[k] = r
    return best
src_led = ledger("source"); cost_led = ledger("cost")
# base descriptions
bdesc = {}
def bwalk(n):
    bdesc[n["id"]] = (n.get("desc") or n.get("description"), n.get("descriptionSource"))
    for c in n.get("children", []) or []: bwalk(c)
bwalk(broot)
# OMB leads: bureau/agency names reaching no node
T = omb_budget.load_database()["tables"]; omb_names = set()
for t in T.values():
    hdr = t[0]; ia = hdr.index("Agency Name"); ib = hdr.index("Bureau Name")
    for r in t[1:]:
        if r[ia]: omb_names.add(str(r[ia]))
        if r[ib]: omb_names.add(str(r[ib]))
STOP = set("of the for and a an in on to department office bureau agency administration national united states us u s federal service services program programs commission board division branch center centre institute committee subcommittee".split())
def toks(s): return {t for t in K(s).split() if t not in STOP and len(t) > 1}
POST = ("position", "role", "office holder")
def ispost(n): return any(k in (n.get("type") or "").lower() for k in POST)
def isline(n): return "treasury accounting line" in (n.get("type") or "").lower()
allkeys = collections.Counter(K(n["name"]) for n in [x for x in [None] if False])
nodes = []
def walk(n, anc):
    nodes.append((n, anc))
    for c in n.get("children", []) or []: walk(c, anc + [n])
walk(root, [])
keycount = collections.Counter(K(n["name"]) for n, _ in nodes)
orgs = [(n, a) for n, a in nodes if not ispost(n) and not isline(n)]
un_tok = [(x, toks(x["desc"])) for x in un]
omb_tok = [(nm, toks(nm)) for nm in omb_names if K(nm) not in keycount]
def qurls(nid):
    v = sites.get(nid)
    if isinstance(v, dict): v = v.get("urls") or v.get("url")
    if isinstance(v, str): v = [v]
    return list(v or [])
def brief_ev(r):
    if not r: return None
    return {k: r.get(k) for k in ("status","reason","method","ownPage","siteFrom","pagesRead","checkedAt") if k in r} | \
           {"sources": [{"url": s.get("url"), "matchedText": s.get("matchedText"), "matchedIn": s.get("matchedIn")} for s in r.get("sources") or []],
            "failures": [{"url": f.get("url"), "reason": (f.get("reason") or "")[:160]} for f in r.get("failures") or []][:6],
            "placement": (r.get("placement") or {}).get("status")}
out = []
for n, anc in orgs:
    nid = n["id"]; T_ = toks(n["name"])
    parent = anc[-1] if anc else None
    sibs = [c for c in (parent.get("children") or [])] if parent else []
    tc = []
    if T_:
        for x, xt in un_tok:
            ov = len(T_ & xt) / len(T_)
            if ov >= 0.6: tc.append({"classification_id": x["classification_id"], "line": x["desc"], "fytd_net": x["fytd_net"], "section": section_of(x["classification_id"]), "overlap": round(ov, 2)})
        tc.sort(key=lambda z: -z["overlap"]); tc = tc[:6]
    ol = []
    if T_:
        for nm, nt in omb_tok:
            ov = len(T_ & nt) / len(T_)
            if ov >= 0.6: ol.append({"ombName": nm, "overlap": round(ov, 2)})
        ol.sort(key=lambda z: -z["overlap"]); ol = ol[:4]
    qu = qurls(nid)
    d = dirv.get(nid) if isinstance(dirv, dict) else None
    rec = {
        "id": nid, "name": n["name"], "type": n.get("type"),
        "ancestors": [a["name"] for a in anc], "parentId": parent["id"] if parent else None,
        "parentQueuedUrls": qurls(parent["id"]) if parent else [],
        "parentVerificationMethod": parent.get("verificationMethod") if parent else None,
        "siblings": [{"id": c["id"], "name": c["name"], "type": c.get("type"),
                      "verified": bool(c.get("verificationMethod")), "queuedUrls": qurls(c["id"])} for c in sibs if c["id"] != nid][:40],
        "childCount": len(n.get("children") or []),
        "childNames": [c["name"] for c in (n.get("children") or [])][:25],
        "description": (bdesc.get(nid) or (None, None))[0], "descriptionSource": (bdesc.get(nid) or (None, None))[1],
        "otherNodesWithThisName": keycount[K(n["name"])] - 1,
        "verification": {k: n.get(k) for k in ("verificationMethod","verificationMatchedText","verificationMatchedIn","verificationStatus","lastVerified","sourceUrls","placementVerified","placementMethod","verificationFailure") if n.get(k) is not None},
        "evidenceRecord": brief_ev(ev.get(nid)),
        "queuedUrls": qu,
        "queuedHostsWalled": sorted({urlparse(u).netloc for u in qu} & set(DEAD)),
        "directoryListing": ({"listedName": d.get("listedName"), "agencyUrl": d.get("agencyUrl"), "parentListedName": d.get("parentListedName")} if d else None),
        "priorSourceNomination": ({k: src_led[nid].get(k) for k in ("run","nominatedAt","noCandidate","reason","note","nominations")} if nid in src_led else None),
        "priorCostNomination": ({k: cost_led[nid].get(k) for k in ("run","nominatedAt","noCandidate","reason","metric","identifiers")} if nid in cost_led else None),
        "cost": {"status": n.get("cost_status"), "validation": n.get("cost_validation"), "amount": n.get("resolved_total_amount"),
                 "treasuryRowName": n.get("treasury_row_name"), "treasurySection": n.get("treasury_section"),
                 "hasUsaspending": bool(n.get("usaspendingOutlays")), "hasOmb": bool(n.get("ombBudget")), "hasNetCost": bool(n.get("auditedNetCost")),
                 "employees": n.get("employees"), "employeesOfficial": n.get("employeesOfficial")},
        "treasuryLineCandidates": tc, "ombNameLeads": ol,
    }
    out.append(rec)
out.sort(key=lambda r: r["id"])
S.mkdir(parents=True, exist_ok=True); (S/"shards").mkdir(exist_ok=True)
header = {"generatedFrom": "output/graph.json + data/verification/* + host_measurement.json on 2026-09-20",
          "walledHosts": DEAD, "walledHostsNote": "Measured 2026-09-20: these 67 hosts answer the PAGE with the same 401/403 they answer robots.txt. A URL on one of them is unreachable from this environment and cannot be fixed by nominating it again.",
          "runbook": "docs/EVIDENCE_TRIAGE_RUNBOOK.md"}
for k in range(N):
    shard = out[k::N]
    json.dump({"shard": f"{k+1}/{N}", **header, "nodes": shard}, open(S/"shards"/f"shard-{k+1:02d}.json","w"), indent=1)
print(f"{len(out)} organisations -> {N} shards; sizes {[len(out[k::N]) for k in range(N)]}")
print("walled hosts:", len(DEAD), "| omb leads present on", sum(1 for r in out if r['ombNameLeads']), "| treasury candidates on", sum(1 for r in out if r['treasuryLineCandidates']))
print("unverified in scope:", sum(1 for r in out if not r['verification'].get('verificationMethod')))
