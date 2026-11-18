"""Helpers shared by the platform scanners."""

from __future__ import annotations

import re
from typing import Optional


def normalise_security(text: str) -> str:
    """Map every OS's security wording to: open, wep, wpa, wpa/wpa2, wpa2, wpa2/wpa3, wpa3, enterprise."""
    t = (text or "").lower().replace("_", " ").replace("-", " ").strip()
    if not t or t in ("none", "open", "--") or t.startswith("none") or "open" == t.split()[0]:
        return "open"
    if "owe" in t.split() or "enhanced open" in t:
        return "wpa3"
    if "enterprise" in t or "802.1x" in t or re.search(r"\beap\b", t):
        return "enterprise"
    if "wep" in t:
        return "wep"
    has3 = "wpa3" in t or "sae" in t.split()
    has2 = "wpa2" in t or "rsn" in t.split()
    rest = t.replace("wpa3", "").replace("wpa2", "")
    has1 = "wpa1" in t or bool(re.search(r"\bwpa\b", rest)) or "mixed" in t or "tkip" in t
    if has3 and (has2 or "transition" in t):
        return "wpa2/wpa3"
    if has3:
        return "wpa3"
    if has2 and has1:
        return "wpa/wpa2"
    if has2:
        return "wpa2"
    if has1:
        return "wpa"
    return t


def percent_to_dbm(pct: Optional[float]) -> Optional[int]:
    """Windows and NetworkManager report signal as 0-100%. This is the usual approximation."""
    if pct is None:
        return None
    return int(round(pct / 2 - 100))


def phy_from_text(text: str) -> str:
    t = text.lower()
    for key, name in (("be", "802.11be"), ("ax", "802.11ax"), ("ac", "802.11ac"), ("n", "802.11n"),
                      ("g", "802.11g"), ("a", "802.11a"), ("b", "802.11b")):
        if re.search(rf"802\.11[a-z/]*{key}\b", t) or t.strip() == f"802.11{key}":
            return name
    return text.strip()


def to_int(s) -> Optional[int]:
    try:
        return int(float(str(s).strip().split()[0]))
    except (ValueError, IndexError, TypeError):
        return None


def to_float(s) -> Optional[float]:
    try:
        return float(str(s).strip().split()[0])
    except (ValueError, IndexError, TypeError):
        return None
