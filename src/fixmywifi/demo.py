"""A realistic made-up home, so anyone can see what a report looks like: `fixmywifi --demo`."""

from __future__ import annotations

from fixmywifi.models import DnsResult, Network, PingStats, Profile, Router, Scan, SpeedResult, WifiLink


def demo_scan() -> Scan:
    link = WifiLink(ssid="Smith-Family-WiFi", bssid="a4:2b:b0:11:22:33", channel=6, band="2.4", width_mhz=40, rssi_dbm=-63, noise_dbm=-92,
                    phy="802.11ax", security="wpa2", interface="en0", tx_rate_mbps=144)
    nearby = [Network(channel=c, band="2.4", width_mhz=20, rssi_dbm=r, security="wpa2")
              for c, r in ((6, -58), (6, -66), (5, -72), (7, -75), (1, -80), (11, -78), (6, -81))]
    nearby += [Network(channel=36, band="5", width_mhz=80, rssi_dbm=-74, security="wpa2"),
               Network(channel=149, band="5", width_mhz=80, rssi_dbm=-83, security="wpa3")]
    return Scan(
        platform="demo", link=link, nearby=nearby, gateway_ip="192.168.1.1",
        gateway_ping=PingStats("192.168.1.1", 20, 20, 4.1, 1.9, 14.0, 2.6),
        internet_ping=PingStats("1.1.1.1", 20, 20, 21.0, 16.0, 39.0, 3.4),
        dns=[DnsResult("192.168.1.1", "Your DNS", 64.0), DnsResult("1.1.1.1", "Cloudflare", 12.0),
             DnsResult("8.8.8.8", "Google", 18.0)],
        speed=SpeedResult(download_mbps=74.0, upload_mbps=18.0, idle_latency_ms=21.0, loaded_latency_ms=236.0),
        router=Router(manufacturer="ExampleCorp", model="HomeHub 2"), lan_devices=19,
    )


def demo_profile() -> Profile:
    return Profile(home_type="house", size_sqm=150, rooms=6, floors=2, walls="brick", router_spot="enclosed",
                   setup="isp_router", router_age_years=4, devices=22, plan_mbps=300,
                   uses=["streaming", "calls", "wfh"], problem="some_rooms", where_now="next_room")
