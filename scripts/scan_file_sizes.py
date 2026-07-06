#!/usr/bin/env python3
"""Scan repository files and write sorted sizes to file_sizes.json."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "file_sizes.json"

def should_skip(path: Path) -> bool:
    parts = [p.lower() for p in path.parts]
    if ".git" in parts:
        return True
    if parts.count('.tmp_chrome_profile'):
        return True
    if '.tmp_pytest' in parts:
        return True
    return False

items = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    # allow os.walk to continue on errors
    for fname in filenames:
        try:
            fpath = Path(dirpath) / fname
            if should_skip(fpath):
                continue
            stat = fpath.stat()
            items.append({"path": str(fpath.relative_to(ROOT)).replace('\\','/'), "size": stat.st_size})
        except Exception:
            continue

items.sort(key=lambda x: x["size"], reverse=True)
summary = {
    "total_files": len(items),
    "total_size_bytes": sum(item["size"] for item in items),
    "top_20": items[:20],
}
with OUT.open("w", encoding="utf-8") as fh:
    json.dump({"summary": summary, "files": items}, fh, indent=2)
print(f"Wrote {len(items)} entries to {OUT}")
print(f"Total files scanned: {summary['total_files']}")
print(f"Total repository size: {summary['total_size_bytes']} bytes")
for rank, item in enumerate(summary["top_20"], start=1):
    print(f"{rank:02d}. {item['path']} ({item['size']} bytes)")
