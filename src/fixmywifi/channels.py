"""Wi-Fi channel maths: bands, overlap, and picking the quietest channel."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

from fixmywifi.models import Network

NON_OVERLAPPING_24 = (1, 6, 11)

# 5 GHz 80 MHz blocks (UNII-1, UNII-2, UNII-2e, UNII-3). DFS = radar-shared channels.
BLOCKS_80 = [(36, 40, 44, 48), (52, 56, 60, 64), (100, 104, 108, 112), (116, 120, 124, 128),
             (132, 136, 140, 144), (149, 153, 157, 161)]
DFS_CHANNELS = set(range(52, 65)) | set(range(100, 145))


def band_for_channel(channel: Optional[int], freq_mhz: Optional[float] = None) -> Optional[str]:
    if freq_mhz:
        if freq_mhz < 3000:
            return "2.4"
        if freq_mhz < 5925:
            return "5"
        return "6"
    if channel is None:
        return None
    if 1 <= channel <= 14:
        return "2.4"
    if 32 <= channel <= 177:
        return "5"
    return None


def channel_from_freq(freq_mhz: float) -> Optional[int]:
    f = int(round(freq_mhz))
    if f == 2484:
        return 14
    if 2412 <= f <= 2472:
        return (f - 2407) // 5
    if 5160 <= f <= 5885:
        return (f - 5000) // 5
    if 5955 <= f <= 7115:
        return (f - 5950) // 5
    return None


def occupied_24(channel: int, width: int = 20) -> Tuple[float, float]:
    """Frequency span (MHz) a 2.4 GHz network really uses. Each channel is 5 MHz apart but 20 MHz wide."""
    centre = 2407 + 5 * channel if channel != 14 else 2484
    half = 10 if width <= 20 else 20
    if width >= 40:
        # 40 MHz in 2.4 GHz extends up or down; assume up for low channels, down for high.
        centre = centre + 10 if channel <= 7 else centre - 10
    return centre - half, centre + half


def overlaps_24(a: int, b: int, width_a: int = 20, width_b: int = 20) -> bool:
    lo1, hi1 = occupied_24(a, width_a)
    lo2, hi2 = occupied_24(b, width_b)
    return lo1 < hi2 and lo2 < hi1


def span_5(channel: int, width: int = 20) -> List[int]:
    """All 20 MHz channels a 5 GHz network covers at the given width."""
    if width >= 160:
        for start in (36, 100):
            block = list(range(start, start + 32, 4))
            if channel in block:
                return block
    if width >= 80:
        for block in BLOCKS_80:
            if channel in block:
                return list(block)
    if width >= 40:
        base = channel - ((channel - 36) % 8) if channel < 149 else channel - ((channel - 149) % 8)
        return [base, base + 4]
    return [channel]


def strong(n: Network, floor_dbm: int = -82) -> bool:
    return n.rssi_dbm is None or n.rssi_dbm >= floor_dbm


def neighbours_on(channel: int, band: str, width: int, nearby: Iterable[Network]) -> List[Network]:
    """Neighbouring networks that share airtime with a network on `channel`."""
    out = []
    for n in nearby:
        if n.channel is None or n.band != band or not strong(n):
            continue
        if band == "2.4":
            if overlaps_24(channel, n.channel, width or 20, n.width_mhz or 20):
                out.append(n)
        elif band in ("5", "6"):
            mine = set(span_5(channel, width or 20)) if band == "5" else {channel}
            theirs = set(span_5(n.channel, n.width_mhz or 20)) if band == "5" else {n.channel}
            if mine & theirs:
                out.append(n)
    return out


def _weight(n: Network) -> float:
    """Closer (louder) neighbours hurt more than faint ones."""
    if n.rssi_dbm is None:
        return 1.0
    if n.rssi_dbm >= -60:
        return 3.0
    if n.rssi_dbm >= -70:
        return 2.0
    return 1.0


def congestion_24(nearby: Iterable[Network]) -> Dict[int, float]:
    nearby = list(nearby)
    return {ch: sum(_weight(n) for n in neighbours_on(ch, "2.4", 20, nearby)) for ch in NON_OVERLAPPING_24}


def congestion_5(nearby: Iterable[Network], width: int = 80) -> Dict[int, float]:
    nearby = list(nearby)
    scores = {}
    for block in BLOCKS_80:
        ch = block[0]
        scores[ch] = sum(_weight(n) for n in neighbours_on(ch, "5", width, nearby))
    return scores


def best_channel(band: str, nearby: Iterable[Network], width: int = 80) -> Optional[int]:
    if band == "2.4":
        scores = congestion_24(nearby)
    elif band == "5":
        scores = congestion_5(nearby, width)
        # Prefer non-DFS on ties: some devices drop off DFS channels when radar is detected.
        scores = {ch: s + (0.1 if ch in DFS_CHANNELS else 0) for ch, s in scores.items()}
    else:
        return None
    return min(scores, key=lambda c: (scores[c], c)) if scores else None
