"""Windows: uses `netsh wlan`. No admin needed.

Windows 11 24H2+ only shows Wi-Fi details when Location services are on
(Settings > Privacy & security > Location). netsh output is localised; the parser
understands English labels, and contributions for other languages are welcome.
"""

from __future__ import annotations

import re
from typing import List, Optional

from fixmywifi.channels import band_for_channel
from fixmywifi.collectors import run
from fixmywifi.collectors.common import normalise_security, percent_to_dbm, phy_from_text, to_float, to_int
from fixmywifi.models import Network, WifiLink

KV = re.compile(r"^\s*([^:]+?)\s*:\s*(.*)$")


def _kv(line: str):
    m = KV.match(line)
    return (m.group(1).strip().lower(), m.group(2).strip()) if m else (None, None)


def _band(value: str, channel: Optional[int]) -> Optional[str]:
    v = value.lower()
    if "2.4" in v:
        return "2.4"
    if v.startswith("5"):
        return "5"
    if v.startswith("6"):
        return "6"
    return band_for_channel(channel)


def parse_interfaces(text: str) -> Optional[WifiLink]:
    d = {}
    for line in text.splitlines():
        k, v = _kv(line)
        if k and k not in d:
            d[k] = v
    if d.get("state", "").lower() != "connected":
        return None
    link = WifiLink(interface=d.get("name", ""), ssid=d.get("ssid", ""),
                    bssid=d.get("bssid", ""))
    link.channel = to_int(d.get("channel"))
    link.band = _band(d.get("band", ""), link.channel)
    link.rssi_dbm = percent_to_dbm(to_float(d.get("signal", "").rstrip("%")))
    if d.get("rssi"):
        link.rssi_dbm = to_int(d["rssi"]) or link.rssi_dbm
    link.phy = phy_from_text(d.get("radio type", ""))
    link.security = normalise_security(d.get("authentication", "") + " " + d.get("cipher", ""))
    link.rx_rate_mbps = to_float(d.get("receive rate (mbps)"))
    link.tx_rate_mbps = to_float(d.get("transmit rate (mbps)"))
    return link


def parse_networks(text: str) -> List[Network]:
    nets: List[Network] = []
    ssid, auth = "", ""
    cur: Optional[Network] = None
    for line in text.splitlines():
        k, v = _kv(line)
        if not k:
            continue
        if re.match(r"ssid \d+", k):
            ssid, auth = v, ""
        elif k == "authentication":
            auth = v
        elif re.match(r"bssid \d+", k):
            cur = Network(ssid=ssid, bssid=v, security=normalise_security(auth))
            nets.append(cur)
        elif cur is not None:
            if k == "signal":
                cur.rssi_dbm = percent_to_dbm(to_float(v.rstrip("%")))
            elif k == "radio type":
                cur.phy = phy_from_text(v)
            elif k == "channel":
                cur.channel = to_int(v)
                cur.band = cur.band or band_for_channel(cur.channel)
            elif k == "band":
                cur.band = _band(v, cur.channel)
    return nets


def collect():
    notes = []
    link = parse_interfaces(run(["netsh", "wlan", "show", "interfaces"]))
    nearby = parse_networks(run(["netsh", "wlan", "show", "networks", "mode=bssid"]))
    if link is not None:
        nearby = [n for n in nearby if n.bssid.lower() != link.bssid.lower()]
    else:
        notes.append("Windows didn't report a Wi-Fi connection. On Windows 11, turn on Location services "
                     "(Settings > Privacy & security > Location) so apps can read Wi-Fi details.")
    return link, nearby, notes
