"""macOS: uses `system_profiler SPAirPortDataType -json`, which needs no admin rights.

Since macOS 14.4 the old `airport` tool is gone, and network names are hidden unless the
terminal app has Location Services permission. We don't need names to diagnose anything.
"""

from __future__ import annotations

import json
import re
from typing import List, Optional, Tuple

from fixmywifi.channels import band_for_channel
from fixmywifi.collectors import run
from fixmywifi.collectors.common import normalise_security, phy_from_text, to_float, to_int
from fixmywifi.models import Network, WifiLink

CHANNEL_RE = re.compile(r"(\d+)\s*(?:\((\d+(?:\.\d+)?)\s*GHz,\s*(\d+)\s*MHz\))?")
SIGNAL_RE = re.compile(r"(-?\d+)\s*dBm\s*/\s*(-?\d+)\s*dBm")


def _band(raw: Optional[str], channel: Optional[int]) -> Optional[str]:
    if raw:
        return {"2": "2.4", "2.4": "2.4", "5": "5", "6": "6"}.get(raw, raw)
    return band_for_channel(channel)


def parse_network(d: dict, cls=Network):
    n = cls()
    name = d.get("_name", "")
    n.ssid = "" if name == "<redacted>" else name
    ch = str(d.get("spairport_network_channel", ""))
    m = CHANNEL_RE.match(ch.strip())
    if m:
        n.channel = int(m.group(1))
        n.band = _band(m.group(2), n.channel)
        n.width_mhz = int(m.group(3)) if m.group(3) else None
    sig = SIGNAL_RE.search(str(d.get("spairport_signal_noise", "")))
    if sig:
        n.rssi_dbm, n.noise_dbm = int(sig.group(1)), int(sig.group(2))
    n.phy = phy_from_text(str(d.get("spairport_network_phymode", "")))
    sec = str(d.get("spairport_security_mode", "")).replace("spairport_security_mode_", "")
    n.security = normalise_security(sec)
    return n


def parse(data: dict) -> Tuple[Optional[WifiLink], List[Network], str]:
    """Parse system_profiler JSON. Returns (link, nearby, wifi interface name)."""
    link, nearby, iface = None, [], ""
    for block in data.get("SPAirPortDataType", []):
        for i in block.get("spairport_airport_interfaces", []):
            cur = i.get("spairport_current_network_information")
            if isinstance(cur, list):
                cur = cur[0] if cur else None
            others = i.get("spairport_airport_other_local_wireless_networks", []) or []
            if cur and not link:
                iface = i.get("_name", "")
                link = parse_network(cur, WifiLink)
                link.interface = iface
                link.tx_rate_mbps = to_float(cur.get("spairport_network_rate"))
                link.mcs = to_int(cur.get("spairport_network_mcs"))
                link.country = str(cur.get("spairport_network_country_code", ""))
            nearby.extend(parse_network(o) for o in others if isinstance(o, dict))
    return link, nearby, iface


def collect():
    notes = []
    raw = run(["system_profiler", "SPAirPortDataType", "-json"], timeout=40)
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        data = {}
    link, nearby, _ = parse(data)
    if link is None:
        notes.append("This Mac isn't connected to Wi-Fi (or system_profiler didn't answer).")
    if not nearby:
        notes.append("macOS didn't list nearby networks, so channel crowding couldn't be checked.")
    return link, nearby, notes
