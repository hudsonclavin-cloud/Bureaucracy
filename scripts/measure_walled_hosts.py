"""For every host evidence.json records as refusing robots.txt with 401/403:
does the host serve the PAGE the verifier had queued there?

    python scripts/measure_walled_hosts.py data/audit/host_measurement_<date>.json

One request per host for robots.txt and one for a queued page, under the
project's User-Agent, with the readable-text count computed by the
verifier's own parse_page so the floor means what the verifier's would.
Read-only against the repository; writes one JSON file, the record of the
measurement. docs/NETWORK_ACCESS.md 11 is the 2026-09-20 run: 67 of 68
hosts refuse the page exactly as they refuse the robots file, and only
www.nga.mil was worth listing in politeness.STANDARD_4XX_HOSTS. Run it
again before listing any other host -- a refusal that changes nothing is
not worth withdrawing.
"""
import json, sys, time, urllib.request, urllib.error
from urllib.parse import urlparse
ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from data_pipeline.verification.evidence import parse_page
UA = "bureaucracy-data-pipeline/1.0 (+https://github.com/hudsonclavin-cloud/Bureaucracy)"
ev = json.load(open(ROOT / "data/verification/evidence.json"))["nodes"]
hosts = {}
for nid, r in ev.items():
    for f in r.get("failures") or []:
        reason = f.get("reason", "")
        if "refused by policy" in reason and "could not be read" in reason:
            h = urlparse(f["url"]).netloc
            hosts.setdefault(h, []).append(f["url"])
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            return resp.status, resp.headers.get("Content-Type", ""), body, None
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", "") if e.headers else "", b"", f"HTTPError {e.code}"
    except Exception as e:
        return None, "", b"", f"{type(e).__name__}: {e}"
out = []
for i, (h, urls) in enumerate(sorted(hosts.items(), key=lambda kv: -len(kv[1]))):
    rec = {"host": h, "refusals_recorded": len(urls)}
    rs, _, rb, rerr = get(f"https://{h}/robots.txt")
    rec["robots_status"] = rs; rec["robots_error"] = rerr
    time.sleep(2)
    page = urls[0]
    ps, ct, pb, perr = get(page)
    rec["page_url"] = page; rec["page_status"] = ps; rec["page_error"] = perr
    rec["content_type"] = ct.split(";")[0] if ct else ""
    if pb:
        try:
            pt = parse_page(pb.decode("utf-8", "replace"))
            rec["content_chars"] = pt.content_chars
            rec["readable"] = pt.readable
            rec["fragments"] = len(pt.fragments)
        except Exception as e:
            rec["parse_error"] = f"{type(e).__name__}: {e}"
    out.append(rec)
    print(f"[{i+1}/{len(hosts)}] {h:26s} robots={rs} page={ps} chars={rec.get('content_chars','-')}", flush=True)
    time.sleep(3)
json.dump(out, open(sys.argv[1], "w"), indent=1)
print("WROTE", sys.argv[1])
