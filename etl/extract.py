"""
extract.py - allowlisted Firestore -> CSV extract, PII-safe by construction.

For each collection in the allowlist, page through the Firestore REST API,
keep only the allowlisted fields, scrub every document, then refuse to write a
single row unless privacy_scan() comes back clean. The output CSVs are what the
Power BI model loads; they contain pseudonyms only.

A Windows scheduled task runs this every six hours (see docs/architecture.md).
This is a sanitized skeleton: auth, retry/backoff, and the real field allowlist
live in config.py (not committed). Nothing here is Konnect-specific beyond the
collection names.
"""
from __future__ import annotations

import csv
import os
import sys
import urllib.request
import urllib.parse
import json

from privacy import scrub, privacy_scan
import config  # see config.example.py

PROJECT = os.environ["FIRESTORE_PROJECT"]        # never hard-coded
BASE = f"https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents"


def _token() -> str:
    """Short-lived access token from the environment (set by the scheduler)."""
    tok = os.environ.get("GCP_ACCESS_TOKEN")
    if not tok:
        sys.exit("GCP_ACCESS_TOKEN not set; aborting.")
    return tok


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {_token()}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def _decode(fields: dict) -> dict:
    """Flatten Firestore's typed value wrappers into plain Python values."""
    out = {}
    for key, wrapper in (fields or {}).items():
        (kind, raw), = wrapper.items()
        if kind == "integerValue":
            out[key] = int(raw)
        elif kind == "doubleValue":
            out[key] = float(raw)
        elif kind == "booleanValue":
            out[key] = bool(raw)
        elif kind == "mapValue":
            out[key] = _decode(raw.get("fields", {}))
        elif kind == "nullValue":
            out[key] = None
        else:  # stringValue, timestampValue, referenceValue, ...
            out[key] = raw
    return out


def fetch(collection: str, fields: list[str]) -> list[dict]:
    """Page through one collection and return scrubbed, field-masked rows."""
    rows: list[dict] = []
    page_token = None
    mask = "&".join(f"mask.fieldPaths={urllib.parse.quote(f)}" for f in fields)
    while True:
        url = f"{BASE}/{collection}?pageSize=300&{mask}"
        if page_token:
            url += f"&pageToken={page_token}"
        page = _get(url)
        for doc in page.get("documents", []):
            raw = _decode(doc.get("fields", {}))
            raw["id"] = doc["name"].rsplit("/", 1)[-1]
            rows.append(scrub(raw))          # <-- PII fence, every document
        page_token = page.get("nextPageToken")
        if not page_token:
            break
    return rows


def export(collection: str, out_dir: str) -> int:
    rows = fetch(collection, config.ALLOWLIST[collection])

    scan = privacy_scan(rows)
    if not scan:                             # <-- hard gate: no clean scan, no file
        for f in scan.findings[:10]:
            print("PRIVACY:", f, file=sys.stderr)
        sys.exit(f"{collection}: {len(scan.findings)} privacy findings, aborting export.")

    path = os.path.join(out_dir, f"{collection}.csv")
    cols = sorted({k for r in rows for k in r})
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def main() -> None:
    out_dir = os.environ.get("EXPORT_DIR", "csv")
    os.makedirs(out_dir, exist_ok=True)
    for collection in config.ALLOWLIST:
        n = export(collection, out_dir)
        print(f"{collection}: {n} rows")


if __name__ == "__main__":
    main()
