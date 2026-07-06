# Bureaucracy

A browsable, data-backed 3D organizational graph of the U.S. federal government.

## Commands

**Run pipeline once:**
```bash
python data_pipeline/run_once.py
```

**Run tests:**
```bash
python -m pytest tests/
```

**Run a single test file:**
```bash
python -m pytest tests/test_build_graph.py -v
```

**Serve frontend locally:**
```bash
python -m http.server 8080
# Open http://localhost:8080/index.html
```

**Expand corporate nodes:**
```bash
python data_expansion/expand_corporate_nodes.py
```

## Maintenance

### Audit repository file sizes

Run the audit script to inspect the largest files and repository size:
```bash
python scripts/scan_file_sizes.py
```

This writes `file_sizes.json` and prints the top files by size.

### Generate compressed viewer graph assets

Use this script to create a minimal viewer JSON and gzipped graph assets:
```bash
python scripts/prune_and_compress.py
```

It creates:
- `output/graph.min.json`
- `output/graph.json.gz`
- `output/graph.min.json.gz`

### Repository size policy

`.gitignore` excludes `output/`, `saved_pages/`, and compressed artifacts from new commits, but the
JSON files the site serves (`output/graph.json`, `output/expanded_nodes.json`,
`output/expanded_edges.json`, `output/node_validity_report.json`, and pipeline state/stats) stay
tracked — GitHub Pages serves them as static assets, so they must remain committed. Frozen
snapshots in `saved_pages/` are historical and can be removed from source control if repo size
becomes a problem.
