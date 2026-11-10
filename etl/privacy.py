"""
privacy.py - the PII fence the whole pipeline is built around.

Every record leaving Firestore passes through scrub() before it touches disk or
the Power BI model. Direct identifiers are replaced with a salted HMAC pseudonym
(stable across runs, not reversible without the salt); known PII keys are dropped
outright; and privacy_scan() is a hard gate that aborts the export if anything
that looks like PII survives.

The salt is loaded at runtime from the environment and is never committed,
logged, or shipped to the model. This file is illustrative of the production
module; the real allowlist/keys live in config.py (see config.example.py).
"""
from __future__ import annotations

import hmac
import hashlib
import os
import re

# Keys dropped from every document before anything is written.
PII_KEYS = {
    "email", "displayName", "gamerTag", "username", "phone", "phoneNumber",
    "ip", "ipAddress", "fcmToken", "pushToken", "avatarUrl", "bio",
}

# Fields that are identifiers and must be pseudonymized rather than dropped.
ID_SUFFIXES = ("Uid", "UserId", "OwnerId", "CreatorId")
ID_KEYS = {"id", "userId", "uid", "fromUid", "toUid", "winnerId"}

# Cheap signatures used by the final scan to catch anything that slipped through.
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_PHONE = re.compile(r"\b\+?\d[\d\-\s().]{7,}\d\b")


def _salt() -> bytes:
    salt = os.environ.get("PSEUDONYM_SALT")
    if not salt:
        raise RuntimeError("PSEUDONYM_SALT is not set; refusing to run without it.")
    return salt.encode("utf-8")


def pseudonymize(value: str, *, _salt_cache: dict = {}) -> str:
    """Stable, non-reversible pseudonym for a single identifier."""
    if not value:
        return value
    key = _salt_cache.get("k")
    if key is None:
        key = _salt_cache["k"] = _salt()
    digest = hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()
    return "p_" + digest[:16]


def _is_id_key(key: str) -> bool:
    return key in ID_KEYS or key.endswith(ID_SUFFIXES)


def scrub(doc: dict) -> dict:
    """Return a copy of doc with PII dropped and identifiers pseudonymized."""
    out: dict = {}
    for key, val in doc.items():
        if key in PII_KEYS:
            continue
        if _is_id_key(key) and isinstance(val, str):
            val = pseudonymize(val)
        elif isinstance(val, dict):
            val = scrub(val)
        elif isinstance(val, list):
            val = [scrub(v) if isinstance(v, dict) else v for v in val]
        out[key] = val
    return out


class ScanResult:
    def __init__(self, findings: list[str]):
        self.findings = findings

    def __bool__(self) -> bool:
        return not self.findings


def privacy_scan(rows: list[dict]) -> ScanResult:
    """Hard gate: look for raw emails, phones, or un-pseudonymized ids."""
    findings: list[str] = []
    for i, row in enumerate(rows):
        for key, val in _walk(row):
            if not isinstance(val, str):
                continue
            if _EMAIL.search(val):
                findings.append(f"row {i}: email-like value at {key}")
            elif _PHONE.search(val):
                findings.append(f"row {i}: phone-like value at {key}")
            elif _is_id_key(key) and not val.startswith("p_"):
                findings.append(f"row {i}: un-pseudonymized id at {key}")
    return ScanResult(findings)


def _walk(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{prefix}.{k}" if prefix else k)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v, prefix)
    else:
        yield prefix, obj
