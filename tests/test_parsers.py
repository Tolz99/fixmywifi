"""Parsers are tested against real-world command output, so they run on any OS."""

from fixmywifi.collectors import linux, macos, windows
from fixmywifi.collectors.common import normalise_security, percent_to_dbm
from fixmywifi.nettests import (
    count_lan_devices,
    parse_device_xml,
    parse_dns_servers,
    parse_gateway,
    parse_ping,
)

MAC_JSON = {
    "SPAirPortDataType": [{
        "spairport_airport_interfaces": [{
            "_name": "en0",
            "spairport_current_network_information": {
                "_name": "<redacted>", "spairport_network_channel": "36 (5GHz, 80MHz)",
                "spairport_network_country_code": "AE", "spairport_network_mcs": 11,
                "spairport_network_phymode": "802.11ax", "spairport_network_rate": 286,
                "spairport_security_mode": "spairport_security_mode_wpa2_personal",
                "spairport_signal_noise": "-40 dBm / -94 dBm",
            },
            "spairport_airport_other_local_wireless_networks": [
                {"_name": "Neighbour", "spairport_network_channel": "8 (2GHz, 20MHz)",
                 "spairport_network_phymode": "802.11b/g/n/ac",
                 "spairport_security_mode": "spairport_security_mode_wpa2_personal_mixed",
                 "spairport_signal_noise": "-80 dBm / -92 dBm"},
                {"_name": "<redacted>", "spairport_network_channel": "36 (5GHz, 160MHz)",
                 "spairport_network_phymode": "802.11a/n/ac/ax",
                 "spairport_security_mode": "spairport_security_mode_wpa3_transition",
                 "spairport_signal_noise": "-38 dBm / -91 dBm"},
                {"_name": "Six", "spairport_network_channel": "37 (6GHz, 320MHz)",
                 "spairport_security_mode": "spairport_security_mode_wpa3_personal"},
            ],
        }]
    }]
}


def test_macos_parse():
    link, nearby, iface = macos.parse(MAC_JSON)
    assert iface == "en0"
    assert (link.channel, link.band, link.width_mhz) == (36, "5", 80)
    assert (link.rssi_dbm, link.noise_dbm, link.snr_db) == (-40, -94, 54)
    assert link.phy == "802.11ax" and link.tx_rate_mbps == 286 and link.mcs == 11
    assert link.security == "wpa2" and link.ssid == ""
    assert [n.band for n in nearby] == ["2.4", "5", "6"]
    assert nearby[0].security == "wpa/wpa2" and nearby[1].security == "wpa2/wpa3"
    assert nearby[1].width_mhz == 160


def test_macos_not_connected():
    link, nearby, _ = macos.parse({"SPAirPortDataType": [{"spairport_airport_interfaces": [{"_name": "en0"}]}]})
    assert link is None and nearby == []


IW_LINK = """Connected to aa:bb:cc:dd:ee:ff (on wlp2s0)
\tSSID: MyHome
\tfreq: 5180.0
\tRX: 123456 bytes (789 packets)
\tTX: 23456 bytes (123 packets)
\tsignal: -58 dBm
\trx bitrate: 866.7 MBit/s VHT-MCS 9 80MHz short GI VHT-NSS 2
\ttx bitrate: 650.0 MBit/s VHT-MCS 7 80MHz short GI VHT-NSS 2
"""

NMCLI = (
    " :11\\:22\\:33\\:44\\:55\\:66:Neighbour:6:2437 MHz:70:WPA1 WPA2:20 MHz\n"
    "*:AA\\:BB\\:CC\\:DD\\:EE\\:FF:MyHome:36:5180 MHz:84:WPA2 WPA3:80 MHz\n"
    " :22\\:33\\:44\\:55\\:66\\:77:Cafe\\:Guest:11:2462 MHz:30::20 MHz\n"
)


def test_linux_iw_link():
    link = linux.parse_iw_link(IW_LINK)
    assert (link.channel, link.band, link.width_mhz) == (36, "5", 80)
    assert link.rssi_dbm == -58 and link.tx_rate_mbps == 650.0 and link.rx_rate_mbps == 866.7
    assert link.phy == "802.11ac" and link.ssid == "MyHome"
    assert linux.parse_iw_link("Not connected.") is None


def test_linux_nmcli():
    nets, current = linux.parse_nmcli(NMCLI)
    assert current.ssid == "MyHome" and current.security == "wpa2/wpa3" and current.width_mhz == 80
    assert len(nets) == 2
    assert nets[0].bssid == "11:22:33:44:55:66" and nets[0].band == "2.4" and nets[0].security == "wpa/wpa2"
    assert nets[1].ssid == "Cafe:Guest" and nets[1].security == "open" and nets[1].rssi_dbm == -85


def test_linux_noise_and_iface():
    assert linux.parse_proc_wireless("wlan0: 0000   54.  -56.  -95.  0 0 0 0 0 0", "wlan0") == -95
    assert linux.parse_proc_wireless("wlan0: 0000   54.  -56.  -256  0 0 0 0 0 0", "wlan0") is None
    assert linux.find_iface("phy#0\n\tInterface wlan0\n\t\tifindex 3") == "wlan0"


NETSH_IF = """
There is 1 interface on the system:

    Name                   : Wi-Fi
    Description            : Intel(R) Wi-Fi 6 AX201 160MHz
    State                  : connected
    SSID                   : MyHome
    BSSID                  : aa:bb:cc:dd:ee:ff
    Network type           : Infrastructure
    Radio type             : 802.11ax
    Authentication         : WPA2-Personal
    Cipher                 : CCMP
    Connection mode        : Auto Connect
    Band                   : 5 GHz
    Channel                : 44
    Receive rate (Mbps)    : 1201
    Transmit rate (Mbps)   : 960.8
    Signal                 : 88%
"""

NETSH_NETS = """
SSID 1 : MyHome
    Network type            : Infrastructure
    Authentication          : WPA2-Personal
    Encryption              : CCMP
    BSSID 1                 : aa:bb:cc:dd:ee:ff
         Signal             : 88%
         Radio type         : 802.11ax
         Band               : 5 GHz
         Channel            : 44
SSID 2 : Neighbour
    Network type            : Infrastructure
    Authentication          : WPA2-Personal
    Encryption              : TKIP
    BSSID 1                 : 11:22:33:44:55:66
         Signal             : 40%
         Radio type         : 802.11n
         Band               : 2.4 GHz
         Channel            : 6
    BSSID 2                 : 11:22:33:44:55:67
         Signal             : 52%
         Radio type         : 802.11ac
         Channel            : 149
"""


def test_windows_interfaces():
    link = windows.parse_interfaces(NETSH_IF)
    assert (link.channel, link.band) == (44, "5")
    assert link.rssi_dbm == percent_to_dbm(88) == -56
    assert link.tx_rate_mbps == 960.8 and link.phy == "802.11ax" and link.security == "wpa2"
    assert windows.parse_interfaces("    State : disconnected") is None


def test_windows_networks():
    nets = windows.parse_networks(NETSH_NETS)
    assert len(nets) == 3
    assert nets[1].ssid == "Neighbour" and nets[1].band == "2.4" and nets[1].rssi_dbm == -80
    assert nets[2].band == "5" and nets[2].channel == 149


def test_security_mapping():
    cases = {"wpa2_personal": "wpa2", "wpa2_personal_mixed": "wpa/wpa2", "wpa3_transition": "wpa2/wpa3",
             "WPA3-Personal": "wpa3", "none": "open", "": "open", "wep": "wep", "wpa_personal": "wpa",
             "WPA2-Enterprise": "enterprise", "WPA1 WPA2": "wpa/wpa2", "WPA2 WPA3": "wpa2/wpa3",
             "WPA2-Personal TKIP": "wpa/wpa2"}
    for raw, want in cases.items():
        assert normalise_security(raw) == want, raw


def test_ping_parsers():
    mac = """PING 192.168.1.1 (192.168.1.1): 56 data bytes
64 bytes from 192.168.1.1: icmp_seq=0 ttl=64 time=3.101 ms
64 bytes from 192.168.1.1: icmp_seq=1 ttl=64 time=5.002 ms
Request timeout for icmp_seq 2
64 bytes from 192.168.1.1: icmp_seq=3 ttl=64 time=4.100 ms"""
    st = parse_ping(mac, "192.168.1.1", 4)
    assert st.received == 3 and st.loss_pct == 25.0 and st.min_ms == 3.1 and st.max_ms == 5.0
    win = """Reply from 1.1.1.1: bytes=32 time=12ms TTL=57
Reply from 1.1.1.1: bytes=32 time<1ms TTL=57
Request timed out."""
    st = parse_ping(win, "1.1.1.1", 3)
    assert st.received == 2 and st.min_ms == 1.0


def test_gateway_parsers():
    assert parse_gateway("   route to: default\n    gateway: 192.168.1.1\n  interface: en0\n", "macos") == ("192.168.1.1", "en0")
    assert parse_gateway("default via 10.0.0.1 dev wlan0 proto dhcp metric 600", "linux") == ("10.0.0.1", "wlan0")
    win = "Network Destination        Netmask          Gateway       Interface  Metric\n          0.0.0.0          0.0.0.0      192.168.0.1    192.168.0.23     35"
    assert parse_gateway(win, "windows") == ("192.168.0.1", "192.168.0.23")


def test_dns_server_parsers():
    assert parse_dns_servers("nameserver[0] : 192.168.1.1\nnameserver[0] : 192.168.1.1\nnameserver[1] : fe80::1%en0", "macos") == ["192.168.1.1", "fe80::1"]
    assert parse_dns_servers("# x\nnameserver 127.0.0.53\noptions edns0", "linux") == ["127.0.0.53"]
    win = "   DNS Servers . . . . . . . . . . . : 192.168.0.1\n                                       8.8.8.8\n   NetBIOS"
    assert parse_dns_servers(win, "windows") == ["192.168.0.1", "8.8.8.8"]


def test_arp_count():
    mac = """? (192.168.1.1) at 0:11:22:33:44:55 on en0 ifscope [ethernet]
? (192.168.1.20) at a:b:c:d:e:f on en0 ifscope [ethernet]
? (192.168.1.255) at ff:ff:ff:ff:ff:ff on en0 ifscope [ethernet]
? (10.0.0.5) at 1:2:3:4:5:6 on en7"""
    assert count_lan_devices(mac, "192.168.1.1") == 2
    win = "  192.168.0.1           00-11-22-33-44-55     dynamic\n  192.168.0.255         ff-ff-ff-ff-ff-ff     static"
    assert count_lan_devices(win, "192.168.0.1") == 1


def test_router_xml():
    xml = """<?xml version="1.0"?><root xmlns="urn:schemas-upnp-org:device-1-0"><device>
    <friendlyName>Home Gateway</friendlyName><manufacturer>Sercomm</manufacturer>
    <modelName>HG6244B</modelName><modelNumber>HG6244B</modelNumber></device></root>"""
    r = parse_device_xml(xml)
    assert r.manufacturer == "Sercomm" and r.model == "HG6244B"
    assert parse_device_xml('<!DOCTYPE x [<!ENTITY a "b">]><root/>') is None
    assert parse_device_xml("not xml") is None
