#!/usr/bin/env python3
"""Regenerate the markdown-file manifest embedded in index.html.

Run from the repository root after adding or removing .md files:

    python3 docs/gen-manifest.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "index.html")

files = sorted(
    os.path.relpath(os.path.join(dirpath, name), ROOT)
    for dirpath, _, names in os.walk(ROOT)
    for name in names
    if name.endswith(".md") and not any(part.startswith(".") and part != "." for part in os.path.relpath(dirpath, ROOT).split(os.sep))
)

html = open(INDEX).read()
new, n = re.subn(
    r"/\*MANIFEST\*/.*?/\*END\*/",
    lambda _: "/*MANIFEST*/" + json.dumps(files) + "/*END*/",
    html,
    count=1,
    flags=re.S,
)
if n != 1:
    raise SystemExit("manifest markers not found in docs/index.html")
open(INDEX, "w").write(new)
print(f"{len(files)} files in manifest")
