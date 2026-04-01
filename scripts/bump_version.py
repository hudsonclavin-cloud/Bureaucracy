#!/usr/bin/env python3
"""Auto-bump ?v= cache strings and APP_BUILD_INFO.version in index.html."""
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
today = date.today().strftime("%Y%m%d")

text = INDEX.read_text(encoding="utf-8")
new_text = re.sub(r"\?v=\d{8}[a-z]?", f"?v={today}", text)
new_text = re.sub(r'version: "[^"]*"', f'version: "{today}"', new_text)

if new_text != text:
    INDEX.write_text(new_text, encoding="utf-8")
    print(f"Bumped to {today}")
else:
    print(f"Already {today}")
