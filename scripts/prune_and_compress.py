#!/usr/bin/env python3
"""Create a minimal viewer JSON and gzipped copies of graph files."""
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data_pipeline.exporter.build_graph import prune_graph_for_viewer  # noqa: E402

IN = ROOT / "output" / "graph.json"
OUT_MIN = ROOT / "output" / "graph.min.json"
OUT_GZ = ROOT / "output" / "graph.json.gz"
OUT_MIN_GZ = ROOT / "output" / "graph.min.json.gz"


def main():
    if not IN.exists():
        print(f"Input graph not found: {IN}")
        return
    with IN.open("r", encoding="utf-8") as fh:
        graph = json.load(fh)

    pruned = prune_graph_for_viewer(graph)
    OUT_MIN.parent.mkdir(parents=True, exist_ok=True)
    with OUT_MIN.open("w", encoding="utf-8") as fh:
        json.dump(pruned, fh, separators=(",", ":"), ensure_ascii=False)
    # write gzipped originals
    with IN.open("rb") as src, gzip.open(OUT_GZ, "wb") as dst:
        dst.writelines(src)
    with OUT_MIN.open("rb") as src, gzip.open(OUT_MIN_GZ, "wb") as dst:
        dst.writelines(src)

    print(f"Wrote {OUT_MIN} and gzipped files.")


if __name__ == "__main__":
    main()
