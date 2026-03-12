import json
import requests
import re
import time

SOURCE = "../data/federal_gov_complete_1.json"
OUTPUT = "corporate_expansion.json"

SEC_SEARCH = "https://efts.sec.gov/LATEST/search-index"
SEC_SUBMISSION = "https://data.sec.gov/submissions/CIK{}.json"

HEADERS = {"User-Agent": "bureaucracy-network-mapper"}

nodes = []
edges = []

def slug(text):
    return re.sub(r'[^a-z0-9]+','-',text.lower())

def walk(node, results):
    if isinstance(node, dict):
        if node.get("type") == "Independent Company":
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

def get_cik(company):
    r = requests.post(SEC_SEARCH, json={"keys": company}, headers=HEADERS)
    data = r.json()
    try:
        cik = data["hits"]["hits"][0]["_source"]["cik"]
        return str(cik).zfill(10)
    except:
        return None

def expand_company(name):
    company_id = "corp-" + slug(name)

    add_node(
        company_id,
        name,
        "Corporation",
        "Corporate entity discovered in government graph"
    )

    cik = get_cik(name)
    if not cik:
        return

    r = requests.get(SEC_SUBMISSION.format(cik), headers=HEADERS)
    if r.status_code != 200:
        return

    data = r.json()
    officers = data.get("officers", [])

    for officer in officers:
        exec_name = officer.get("name")
        title = officer.get("title")

        if not exec_name:
            continue

        exec_id = "exec-" + slug(exec_name)

        add_node(exec_id, exec_name, "Executive", title)
        add_edge(company_id, exec_id, "executive")

def main():

    with open(SOURCE) as f:
        data = json.load(f)

    companies = []
    walk(data, companies)

    print("Companies found:", len(companies))

    for c in companies:
        try:
            expand_company(c["name"])
            time.sleep(1)
        except Exception as e:
            print("Error expanding", c["name"], e)

    with open(OUTPUT, "w") as f:
        json.dump({
            "nodes": nodes,
            "edges": edges
        }, f, indent=2)

    print("Saved:", OUTPUT)

if __name__ == "__main__":
    main()