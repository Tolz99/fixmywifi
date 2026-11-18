"""Network measurements: router reachability, internet latency, DNS speed, throughput, bufferbloat.

Everything is read-only. The only outside services contacted are Cloudflare's public speed-test
endpoints and the public DNS resolvers named below. No personal data is sent anywhere.
"""

from __future__ import annotations

import ipaddress
import os
import random
import re
import socket
import statistics
import struct
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import Callable, List, Optional
from urllib.parse import urlparse

from fixmywifi.collectors import current_platform, run
from fixmywifi.models import DnsResult, PingStats, Router, SpeedResult

INTERNET_HOST = "1.1.1.1"
PUBLIC_DNS = [("1.1.1.1", "Cloudflare"), ("8.8.8.8", "Google"), ("9.9.9.9", "Quad9")]
TEST_DOMAINS = ["wikipedia.org", "github.com", "netflix.com", "bbc.co.uk", "amazon.com", "reddit.com",
                "apple.com", "microsoft.com", "spotify.com", "zoom.us", "whatsapp.com", "openstreetmap.org"]
SPEED_DOWN = "https://speed.cloudflare.com/__down?bytes={n}"
SPEED_UP = "https://speed.cloudflare.com/__up"
UA = {"User-Agent": "fixmywifi (+https://github.com/Tolz99/fixmywifi)"}

# ---------------------------------------------------------------- gateway / interface


def parse_gateway(text: str, plat: str) -> tuple:
    """Return (gateway ip, interface) from the OS's routing output."""
    if plat == "macos":
        gw = re.search(r"gateway:\s*(\S+)", text)
        ifc = re.search(r"interface:\s*(\S+)", text)
        return (gw.group(1) if gw else "", ifc.group(1) if ifc else "")
    if plat == "linux":
        m = re.search(r"default via (\S+)(?:.*?dev (\S+))?", text)
        return (m.group(1), m.group(2) or "") if m else ("", "")
    if plat == "windows":
        m = re.search(r"^\s*0\.0\.0\.0\s+0\.0\.0\.0\s+(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)", text, re.M)
        return (m.group(1), m.group(2)) if m else ("", "")
    return "", ""


def default_gateway() -> tuple:
    plat = current_platform()
    if plat == "macos":
        return parse_gateway(run(["route", "-n", "get", "default"]), plat)
    if plat == "linux":
        return parse_gateway(run(["ip", "route", "show", "default"]), plat)
    if plat == "windows":
        return parse_gateway(run(["route", "print", "-4", "0.0.0.0"]), plat)
    return "", ""


# ---------------------------------------------------------------- ping

TIME_RE = re.compile(r"time\s*[=<]\s*([\d.]+)\s*ms", re.I)


def parse_ping(text: str, host: str, sent: int) -> PingStats:
    times = [float(t) for t in TIME_RE.findall(text)]
    st = PingStats(host=host, sent=sent, received=min(len(times), sent))
    if times:
        st.avg_ms = round(statistics.mean(times), 1)
        st.min_ms = round(min(times), 1)
        st.max_ms = round(max(times), 1)
        if len(times) > 1:
            st.jitter_ms = round(statistics.mean(abs(a - b) for a, b in zip(times, times[1:])), 1)
    return st


def ping(host: str, count: int = 20) -> Optional[PingStats]:
    if not host:
        return None
    plat = current_platform()
    if plat == "windows":
        cmd = ["ping", "-n", str(count), "-w", "1000", host]
    elif plat == "macos":
        cmd = ["ping", "-c", str(count), "-i", "0.2", "-W", "1000", host]
    else:
        cmd = ["ping", "-c", str(count), "-i", "0.2", "-W", "1", host]
    out = run(cmd, timeout=count * 1.5 + 5)
    if not out:
        return None
    return parse_ping(out, host, count)


# ---------------------------------------------------------------- DNS


def _dns_query(server: str, name: str, timeout: float = 2.0) -> Optional[float]:
    """Send one A-record query over UDP and return the round trip in ms (None on failure)."""
    qid = random.randint(0, 0xFFFF)
    header = struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0)
    qname = b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\x00"
    packet = header + qname + struct.pack(">HH", 1, 1)
    fam = socket.AF_INET6 if ":" in server else socket.AF_INET
    with socket.socket(fam, socket.SOCK_DGRAM) as s:
        start = time.perf_counter()
        deadline = start + timeout
        try:
            s.connect((server, 53))  # the OS then drops replies from any other address
            s.send(packet)
            while True:
                left = deadline - time.perf_counter()
                if left <= 0:
                    return None
                s.settimeout(left)
                data = s.recv(2048)
                if len(data) >= 2 and struct.unpack(">H", data[:2])[0] == qid:
                    return round((time.perf_counter() - start) * 1000, 1)
        except OSError:
            return None


def parse_dns_servers(text: str, plat: str) -> List[str]:
    if plat == "macos":
        found = re.findall(r"nameserver\[\d+\]\s*:\s*(\S+)", text)
    elif plat == "linux":
        found = re.findall(r"^\s*nameserver\s+(\S+)", text, re.M)
    else:
        found = re.findall(r"DNS Servers[ .]*:\s*([\d.]+)((?:\s+[\d.]+$)*)", text, re.M)
        flat = []
        for first, rest in found:
            flat.append(first)
            flat.extend(rest.split())
        found = flat
    out = []
    for s in found:
        s = s.split("%")[0]
        try:
            ipaddress.ip_address(s)
        except ValueError:
            continue
        if s not in out:
            out.append(s)
    return out


def system_dns_servers() -> List[str]:
    plat = current_platform()
    if plat == "macos":
        return parse_dns_servers(run(["scutil", "--dns"]), plat)
    if plat == "linux":
        servers = parse_dns_servers(run(["resolvectl", "dns"]).replace(":", "\nnameserver "), plat)
        if not servers:
            try:
                with open("/etc/resolv.conf") as fh:
                    servers = parse_dns_servers(fh.read(), plat)
            except OSError:
                servers = []
        return servers
    return parse_dns_servers(run(["ipconfig", "/all"]), plat)


def dns_benchmark(servers: Optional[List[str]] = None, rounds: int = 6) -> List[DnsResult]:
    """Compare how fast your current DNS answers versus well-known public resolvers."""
    yours = [s for s in (servers if servers is not None else system_dns_servers())
             if ":" not in s][:2]
    targets = [(s, "Your DNS" if i == 0 else "Your DNS (backup)") for i, s in enumerate(yours)]
    targets += [p for p in PUBLIC_DNS if p[0] not in yours]
    results = []
    domains = random.sample(TEST_DOMAINS, k=min(rounds, len(TEST_DOMAINS)))
    for server, label in targets:
        times, fails = [], 0
        for d in domains:
            t = _dns_query(server, d)
            if t is None:
                fails += 1
            else:
                times.append(t)
        results.append(DnsResult(server=server, label=label,
                                 median_ms=round(statistics.median(times), 1) if times else None,
                                 failures=fails))
    return results


# ---------------------------------------------------------------- speed + bufferbloat


def _tcp_latency(host: str = "speed.cloudflare.com", port: int = 443, timeout: float = 2.0) -> Optional[float]:
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return (time.perf_counter() - start) * 1000
    except OSError:
        return None


def _latency_sampler(stop: threading.Event, out: List[float]):
    while not stop.is_set():
        t = _tcp_latency()
        if t is not None:
            out.append(t)
        stop.wait(0.25)


def _download_worker(deadline: float, counter: List[int], lock: threading.Lock):
    while time.perf_counter() < deadline:
        try:
            req = urllib.request.Request(SPEED_DOWN.format(n=50_000_000), headers=UA)
            with urllib.request.urlopen(req, timeout=10) as r:
                while time.perf_counter() < deadline:
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    with lock:
                        counter[0] += len(chunk)
        except OSError:
            time.sleep(0.2)


def _upload_worker(deadline: float, counter: List[int], lock: threading.Lock):
    blob = os.urandom(2_000_000)
    while time.perf_counter() < deadline:
        try:
            req = urllib.request.Request(SPEED_UP, data=blob, headers={**UA, "Content-Type": "application/octet-stream"})
            with urllib.request.urlopen(req, timeout=10) as r:
                r.read()
            with lock:
                counter[0] += len(blob)
        except OSError:
            time.sleep(0.2)


def _measure(worker: Callable, seconds: float, streams: int, warmup: float = 1.5) -> Optional[float]:
    lock = threading.Lock()
    counter = [0]
    deadline = time.perf_counter() + seconds
    threads = [threading.Thread(target=worker, args=(deadline, counter, lock), daemon=True) for _ in range(streams)]
    for t in threads:
        t.start()
    time.sleep(warmup)  # ignore TCP slow-start
    with lock:
        start_bytes, start_t = counter[0], time.perf_counter()
    for t in threads:
        t.join(timeout=seconds + 15)
    elapsed = time.perf_counter() - start_t
    got = counter[0] - start_bytes
    if elapsed <= 0 or got <= 0:
        return None
    return round(got * 8 / elapsed / 1_000_000, 1)


def speed_test(seconds: float = 8, streams: int = 4, upload: bool = True) -> SpeedResult:
    res = SpeedResult()
    idle = [t for t in (_tcp_latency() for _ in range(5)) if t is not None]
    if not idle:
        res.error = "Couldn't reach the speed-test server (speed.cloudflare.com)."
        return res
    res.idle_latency_ms = round(statistics.median(idle), 1)
    stop, loaded = threading.Event(), []
    sampler = threading.Thread(target=_latency_sampler, args=(stop, loaded), daemon=True)
    sampler.start()
    try:
        res.download_mbps = _measure(_download_worker, seconds, streams)
        if upload:
            res.upload_mbps = _measure(_upload_worker, seconds * 0.75, streams)
    finally:
        stop.set()
        sampler.join(timeout=3)
    if loaded:
        res.loaded_latency_ms = round(statistics.median(loaded), 1)
    if res.download_mbps is None:
        res.error = "The speed test didn't complete."
    return res


# ---------------------------------------------------------------- router identity (UPnP)


def _is_private(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_private
    except ValueError:
        return False


def parse_device_xml(xml_text: str) -> Optional[Router]:
    # UPnP descriptions never need a DOCTYPE; refusing one blocks entity-expansion tricks.
    if "<!DOCTYPE" in xml_text.upper() or "<!ENTITY" in xml_text.upper():
        return None
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    def find(tag):
        for el in root.iter():
            if el.tag.split("}")[-1] == tag and el.text:
                return el.text.strip()
        return ""
    name, number = find("modelName"), find("modelNumber")
    model = name if (not number or number in name) else f"{name} {number}".strip()
    r = Router(manufacturer=_clean(find("manufacturer")), model=_clean(model),
               friendly_name=_clean(find("friendlyName")))
    return r if (r.manufacturer or r.model) else None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # the router must answer directly, never send us elsewhere
        return None


def safe_location(location: str, gateway: str) -> bool:
    """Only fetch the router's own description: same IP as the gateway, plain http, a sane port."""
    try:
        u = urlparse(location)
        port = u.port or 80
    except ValueError:
        return False
    return u.scheme == "http" and (u.hostname or "") == gateway and 1 <= port <= 65535


def _clean(text: str, limit: int = 80) -> str:
    """Router-supplied text is untrusted: drop control characters and cap the length."""
    return "".join(ch for ch in text if ch.isprintable())[:limit].strip()


def identify_router(gateway: str, timeout: float = 2.5) -> Optional[Router]:
    """Ask the router who it is via UPnP (the same discovery your games console uses). Read-only."""
    if not gateway or not _is_private(gateway):
        return None
    msg = (b"M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: \"ssdp:discover\"\r\nMX: 2\r\n"
           b"ST: urn:schemas-upnp-org:device:InternetGatewayDevice:1\r\n\r\n")
    location = ""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as s:
            s.settimeout(timeout)
            s.sendto(msg, ("239.255.255.250", 1900))
            end = time.time() + timeout
            while time.time() < end and not location:
                data, addr = s.recvfrom(4096)
                if addr[0] != gateway:
                    continue
                m = re.search(rb"(?im)^location:\s*(\S+)", data)
                if m:
                    location = m.group(1).decode(errors="ignore")
    except OSError:
        return None
    if not location:
        return None
    if not safe_location(location, gateway):
        return None
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(urllib.request.Request(location, headers=UA), timeout=timeout) as r:
            if not safe_location(r.geturl(), gateway):
                return None
            return parse_device_xml(r.read(200_000).decode(errors="ignore"))
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------- devices on the network


def count_lan_devices(text: str, gateway: str) -> Optional[int]:
    """Count distinct neighbours in the ARP table on the same /24 as the router."""
    if not gateway:
        return None
    prefix = ".".join(gateway.split(".")[:3]) + "."
    seen = set()
    for ip, mac in re.findall(r"(\d+\.\d+\.\d+\.\d+)\D+?([0-9a-fA-F]{1,2}(?:[:-][0-9a-fA-F]{1,2}){5})", text):
        if ip.startswith(prefix) and not ip.endswith(".255") and mac.lower() not in ("ff:ff:ff:ff:ff:ff", "ff-ff-ff-ff-ff-ff"):
            seen.add(ip)
    return len(seen) or None


def lan_devices(gateway: str) -> Optional[int]:
    plat = current_platform()
    text = run(["ip", "neigh"]) if plat == "linux" else run(["arp", "-a"])
    return count_lan_devices(text, gateway)
