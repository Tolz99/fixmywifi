"""Plain data objects shared by the scanners, the rules and the report."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import List, Optional


@dataclass
class Network:
    """One Wi-Fi network (yours or a neighbour's) as seen by this computer."""

    ssid: str = ""
    bssid: str = ""
    channel: Optional[int] = None
    band: Optional[str] = None  # "2.4", "5" or "6" (GHz)
    width_mhz: Optional[int] = None
    rssi_dbm: Optional[int] = None  # signal strength, e.g. -55
    noise_dbm: Optional[int] = None
    phy: str = ""  # e.g. "802.11ax"
    security: str = ""  # normalised: open, wep, wpa, wpa2, wpa2/wpa3, wpa3, enterprise

    @property
    def snr_db(self) -> Optional[int]:
        if self.rssi_dbm is None or self.noise_dbm is None:
            return None
        return self.rssi_dbm - self.noise_dbm


@dataclass
class WifiLink(Network):
    """Your current connection: a Network plus the link details."""

    interface: str = ""
    tx_rate_mbps: Optional[float] = None
    rx_rate_mbps: Optional[float] = None
    mcs: Optional[int] = None
    country: str = ""


@dataclass
class PingStats:
    host: str
    sent: int = 0
    received: int = 0
    avg_ms: Optional[float] = None
    min_ms: Optional[float] = None
    max_ms: Optional[float] = None
    jitter_ms: Optional[float] = None

    @property
    def loss_pct(self) -> Optional[float]:
        if not self.sent:
            return None
        return round(100.0 * (self.sent - self.received) / self.sent, 1)


@dataclass
class DnsResult:
    server: str
    label: str
    median_ms: Optional[float] = None
    failures: int = 0


@dataclass
class SpeedResult:
    download_mbps: Optional[float] = None
    upload_mbps: Optional[float] = None
    idle_latency_ms: Optional[float] = None
    loaded_latency_ms: Optional[float] = None  # latency while the line is busy (bufferbloat)
    error: str = ""

    @property
    def bufferbloat_ms(self) -> Optional[float]:
        if self.idle_latency_ms is None or self.loaded_latency_ms is None:
            return None
        return max(0.0, round(self.loaded_latency_ms - self.idle_latency_ms, 1))

    @property
    def bufferbloat_grade(self) -> Optional[str]:
        b = self.bufferbloat_ms
        if b is None:
            return None
        for limit, grade in ((5, "A+"), (30, "A"), (60, "B"), (200, "C"), (400, "D")):
            if b < limit:
                return grade
        return "F"


@dataclass
class Router:
    manufacturer: str = ""
    model: str = ""
    friendly_name: str = ""


@dataclass
class Scan:
    """Everything we measured. Every field may be missing: rules must cope."""

    platform: str = ""
    link: Optional[WifiLink] = None
    nearby: List[Network] = field(default_factory=list)
    gateway_ip: str = ""
    gateway_ping: Optional[PingStats] = None
    internet_ping: Optional[PingStats] = None
    dns: List[DnsResult] = field(default_factory=list)
    speed: Optional[SpeedResult] = None
    router: Optional[Router] = None
    lan_devices: Optional[int] = None
    wired: bool = False
    notes: List[str] = field(default_factory=list)  # things we could not measure, and why


@dataclass
class Profile:
    """What the person told us about their home. Empty means "didn't say"."""

    home_type: str = ""  # apartment, house, office
    size_sqm: Optional[int] = None
    rooms: Optional[int] = None
    floors: Optional[int] = None
    walls: str = ""  # light, brick, concrete
    router_spot: str = ""  # central, edge, enclosed, other_floor
    setup: str = ""  # isp_router, own_router, mesh, extenders
    router_age_years: Optional[int] = None
    devices: Optional[int] = None
    plan_mbps: Optional[int] = None
    uses: List[str] = field(default_factory=list)  # streaming, gaming, calls, wfh, smart_home, downloads
    problem: str = ""  # everywhere, some_rooms, drops, evenings, lag, none
    where_now: str = ""  # same_room, next_room, far, other_floor


@dataclass
class Finding:
    id: str
    severity: str  # "critical", "warning", "tip", "good"
    title: str
    why: str
    fix: List[str] = field(default_factory=list)
    category: str = "wifi"  # wifi, internet, home, security, hardware
    symptom: bool = False  # True when this is a result of other problems, not something to act on directly


@dataclass
class Report:
    scan: Scan
    profile: Profile
    findings: List[Finding]
    score: int
    grade: str
    summary: str

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.scan.speed:
            d["scan"]["speed"]["bufferbloat_ms"] = self.scan.speed.bufferbloat_ms
            d["scan"]["speed"]["bufferbloat_grade"] = self.scan.speed.bufferbloat_grade
        return d
