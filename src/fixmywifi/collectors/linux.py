"""Linux: uses `iw` for the link and NetworkManager's `nmcli` for nearby networks. No root needed."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from fixmywifi.channels import band_for_channel, channel_from_freq
from fixmywifi.collectors import run
from fixmywifi.collectors.common import normalise_security, percent_to_dbm, to_float, to_int
from fixmywifi.models import Network, WifiLink


def split_terse(line: str) -> List[str]:
    """Split `nmcli -t` output on colons that aren't escaped with a backslash."""
    parts, cur, esc = [], "", False
    for ch in line:
        if esc:
            cur += ch
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == ":":
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return parts


NMCLI_FIELDS = ["IN-USE", "BSSID", "SSID", "CHAN", "FREQ", "SIGNAL", "SECURITY", "BANDWIDTH"]


def parse_nmcli(text: str, fields=NMCLI_FIELDS) -> Tuple[List[Network], Optional[Network]]:
    nets, current = [], None
    for line in text.splitlines():
        if not line.strip():
            continue
        p = split_terse(line)
        if len(p) < len(fields):
            continue
        row = dict(zip(fields, p))
        n = Network(ssid=row.get("SSID", ""), bssid=row.get("BSSID", ""))
        n.channel = to_int(row.get("CHAN"))
        freq = to_float(row.get("FREQ"))
        n.band = band_for_channel(n.channel, freq)
        n.rssi_dbm = percent_to_dbm(to_float(row.get("SIGNAL")))
        n.security = normalise_security(row.get("SECURITY", ""))
        n.width_mhz = to_int(row.get("BANDWIDTH")) if row.get("BANDWIDTH") else None
        if row.get("IN-USE", "").strip() == "*":
            current = n
        else:
            nets.append(n)
    return nets, current


def parse_iw_link(text: str) -> Optional[WifiLink]:
    if "Not connected" in text or "Connected to" not in text:
        return None
    link = WifiLink()
    m = re.search(r"Connected to ([0-9a-fA-F:]{17})", text)
    link.bssid = m.group(1) if m else ""
    m = re.search(r"SSID: (.*)", text)
    link.ssid = m.group(1).strip() if m else ""
    m = re.search(r"freq: ([\d.]+)", text)
    if m:
        f = float(m.group(1))
        link.channel = channel_from_freq(f)
        link.band = band_for_channel(link.channel, f)
    m = re.search(r"signal: (-?\d+) dBm", text)
    link.rssi_dbm = int(m.group(1)) if m else None
    for key, attr in (("tx bitrate", "tx_rate_mbps"), ("rx bitrate", "rx_rate_mbps")):
        m = re.search(rf"{key}: ([\d.]+) MBit/s(.*)", text)
        if m:
            setattr(link, attr, float(m.group(1)))
            rest = m.group(2)
            w = re.search(r"(\d+)MHz", rest)
            if w and not link.width_mhz:
                link.width_mhz = int(w.group(1))
            if not link.phy:
                for tag, phy in (("EHT", "802.11be"), ("HE", "802.11ax"), ("VHT", "802.11ac"), ("MCS", "802.11n")):
                    if tag in rest:
                        link.phy = phy
                        break
            mcs = re.search(r"MCS (\d+)", rest)
            if mcs and link.mcs is None:
                link.mcs = int(mcs.group(1))
    if link.width_mhz is None and link.tx_rate_mbps is not None:
        link.width_mhz = 20  # iw omits the width for plain 20 MHz links
    return link


def parse_iw_info_width(text: str) -> Optional[int]:
    m = re.search(r"width: (\d+) MHz", text)
    return int(m.group(1)) if m else None


def parse_proc_wireless(text: str, iface: str) -> Optional[int]:
    """Noise floor from /proc/net/wireless. -256 / 0 mean the driver doesn't report it."""
    for line in text.splitlines():
        if line.strip().startswith(iface + ":"):
            parts = line.split()
            noise = to_float(parts[4]) if len(parts) > 4 else None
            if noise is not None and -120 < noise < -10:
                return int(noise)
    return None


def find_iface(iw_dev: str) -> str:
    m = re.search(r"Interface (\S+)", iw_dev)
    return m.group(1) if m else ""


def collect():
    notes = []
    iface = find_iface(run(["iw", "dev"]))
    link = None
    if iface:
        link = parse_iw_link(run(["iw", "dev", iface, "link"]))
        if link:
            link.interface = iface
            link.width_mhz = parse_iw_info_width(run(["iw", "dev", iface, "info"])) or link.width_mhz
            try:
                with open("/proc/net/wireless") as fh:
                    link.noise_dbm = parse_proc_wireless(fh.read(), iface)
            except OSError:
                pass
    raw = run(["nmcli", "-t", "-f", ",".join(NMCLI_FIELDS), "dev", "wifi", "list", "--rescan", "auto"])
    fields = NMCLI_FIELDS
    if not raw.strip():  # older nmcli has no BANDWIDTH column
        fields = NMCLI_FIELDS[:-1]
        raw = run(["nmcli", "-t", "-f", ",".join(fields), "dev", "wifi", "list"])
    nearby, current = parse_nmcli(raw, fields)
    if link is None and current is not None:
        link = WifiLink(**current.__dict__)
    elif link is not None and current is not None:
        link.security = current.security
        link.width_mhz = link.width_mhz or current.width_mhz
    if not iface:
        notes.append("Couldn't find a Wi-Fi adapter with `iw` (install the `iw` package for full details).")
    if not raw.strip():
        notes.append("`nmcli` isn't available, so nearby networks and channel crowding weren't checked.")
    return link, nearby, notes
