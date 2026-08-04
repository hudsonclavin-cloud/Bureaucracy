import json
import re
import time
from pathlib import Path

import requests

from expand_corporate_nodes import is_expandable_company

BASE_DIR = Path(__file__).resolve().parent
SOURCE = BASE_DIR.parent / "data" / "federal_gov_complete_1.json"
OUTPUT = BASE_DIR / "corporate_expansion.json"

# EDGAR full-text search: GET with a "q" term; each hit's _source carries
# parallel "ciks" / "display_names" lists covering every entity on the filing.
SEC_SEARCH = "https://efts.sec.gov/LATEST/search-index"
SEC_SUBMISSION = "https://data.sec.gov/submissions/CIK{}.json"

# SEC requires the User-Agent to identify the tool and a contact address.
HEADERS = {"User-Agent": "bureaucracy-network-mapper (hudsonclavin@gmail.com)"}
REQUEST_TIMEOUT = 30

DISPLAY_NAME_CIK = re.compile(r"\s*\(CIK\s+(\d+)\)\s*$")
TRAILING_PARENTHETICAL = re.compile(r"\s*\([^)]*\)\s*$")

nodes = []
edges = []

def slug(text):
    return re.sub(r'[^a-z0-9]+','-',text.lower())

def walk(node, results):
    if isinstance(node, dict):
        if is_expandable_company(node):
            results.append(node)
        for child in node.get("children", []):
            walk(child, results)
    elif isinstance(node, list):
        for item in node:
            walk(item, results)

def add_node(node_id, name, node_type, desc):
    nodes.append({
        "id": node_id,
        "name": name,
        "type": node_type,
        "desc": desc,
        "employees": None,
        "budget": None,
        "color": "#4ac88a",
        "children": []
    })

def add_edge(source, target, rel):
    edges.append({
        "source": source,
        "target": target,
        "type": rel
    })

def search_filings(query, forms=None):
    params = {"q": '"{}"'.format(query)}
    if forms:
        params["forms"] = forms
    r = requests.get(SEC_SEARCH, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.json().get("hits", {}).get("hits", [])

def get_cik(company):
    try:
        hits = search_filings(company)
    except (requests.RequestException, ValueError):
        return None
    target = company.lower()
    for hit in hits:
        source = hit.get("_source", {})
        for cik, display_name in zip(source.get("ciks", []), source.get("display_names", [])):
            # Only accept a hit that actually names this company; full-text
            # search also returns filings that merely mention the phrase.
            if target in str(display_name).lower():
                return str(cik).zfill(10)
    return None

def get_insiders(company, company_cik):
    # The submissions JSON has no officer data; Form 4 filings name the
    # reporting insiders alongside the issuer, so harvest the display names
    # whose CIK differs from the company's.
    try:
        hits = search_filings(company, forms="4")
    except (requests.RequestException, ValueError):
        return []
    insiders = {}
    for hit in hits:
        source = hit.get("_source", {})
        ciks = [str(cik).zfill(10) for cik in source.get("ciks", [])]
        if company_cik not in ciks:
            continue
        for cik, display_name in zip(ciks, source.get("display_names", [])):
            if cik == company_cik:
                continue
            name = DISPLAY_NAME_CIK.sub("", str(display_name)).strip()
            if name:
                insiders.setdefault(cik, name)
    return sorted(insiders.values())

def expand_company(name):
    company_id = "corp-" + slug(name)

    add_node(
        company_id,
        name,
        "Corporation",
        "Corporate entity discovered in government graph"
    )
    company_node = nodes[-1]

    query_name = TRAILING_PARENTHETICAL.sub("", name).strip() or name
    cik = get_cik(query_name)
    if not cik:
        return

    r = requests.get(SEC_SUBMISSION.format(cik), headers=HEADERS, timeout=REQUEST_TIMEOUT)
    if r.status_code != 200:
        return

    data = r.json()
    sic_description = data.get("sicDescription")
    if sic_description:
        company_node["desc"] = "Corporate entity discovered in government graph. SEC industry: {}".format(sic_description)

    for exec_name in get_insiders(query_name, cik):
        exec_id = "exec-" + slug(exec_name)
        add_node(exec_id, exec_name, "Executive", "Form 4 insider filer for {}".format(name))
        add_edge(company_id, exec_id, "executive")

def main():

    with SOURCE.open() as f:
        data = json.load(f)

    companies = []
    walk(data, companies)

    print("Companies found:", len(companies))

    if not companies:
        print("No companies found; refusing to overwrite", OUTPUT)
        return

    for c in companies:
        try:
            expand_company(c["name"])
            time.sleep(1)
        except Exception as e:
            print("Error expanding", c["name"], e)

    with OUTPUT.open("w") as f:
        json.dump({
            "nodes": nodes,
            "edges": edges
        }, f, indent=2)

    print("Saved:", OUTPUT)

if __name__ == "__main__":
    main()
