"""Scenario tests: given a home, do we say the right thing?"""

from fixmywifi.channels import best_channel, neighbours_on, overlaps_24, span_5
from fixmywifi.demo import demo_profile, demo_scan
from fixmywifi.models import Network, PingStats, Profile, Scan, SpeedResult, WifiLink
from fixmywifi.rules import analyse


def ids(report):
    return {f.id: f.severity for f in report.findings}


def healthy_link(**kw):
    base = dict(channel=36, band="5", width_mhz=80, rssi_dbm=-50, noise_dbm=-95, phy="802.11ax",
                security="wpa3", tx_rate_mbps=1200, interface="en0")
    base.update(kw)
    return WifiLink(**base)


def test_healthy_network_scores_well():
    s = Scan(link=healthy_link(), gateway_ping=PingStats("r", 20, 20, 2, 1, 4, 0.5),
             internet_ping=PingStats("i", 20, 20, 12, 10, 15, 1),
             speed=SpeedResult(download_mbps=480, upload_mbps=200, idle_latency_ms=12, loaded_latency_ms=15))
    r = analyse(s, Profile(plan_mbps=500))
    assert r.grade == "A", r.findings
    assert not [f for f in r.findings if f.severity in ("critical", "warning")]


def test_empty_scan_never_crashes():
    r = analyse(Scan(), Profile())
    assert r.score == 100 and r.findings == []


def test_weak_signal():
    r = analyse(Scan(link=healthy_link(rssi_dbm=-79)), Profile())
    assert ids(r)["signal-weak"] == "critical"
    r = analyse(Scan(link=healthy_link(rssi_dbm=-70)), Profile(where_now="same_room"))
    f = next(f for f in r.findings if f.id == "signal-weak")
    assert f.severity == "warning" and "same room" in f.why


def test_24ghz_with_good_signal_suggests_5ghz():
    r = analyse(Scan(link=healthy_link(band="2.4", channel=6, width_mhz=20, rssi_dbm=-50)), Profile())
    assert ids(r)["band-24"] == "warning"


def test_24ghz_bad_channel_and_width():
    r = analyse(Scan(link=healthy_link(band="2.4", channel=4, width_mhz=40)), Profile())
    assert "channel-24-overlap" in ids(r) and "width-24-wide" in ids(r)


def test_congestion_recommends_quiet_channel():
    nearby = [Network(channel=6, band="2.4", rssi_dbm=-55) for _ in range(4)] + [Network(channel=11, band="2.4", rssi_dbm=-85)]
    r = analyse(Scan(link=healthy_link(band="2.4", channel=6, width_mhz=20), nearby=nearby), Profile())
    f = next(f for f in r.findings if f.id == "channel-crowded")
    assert "channel to 1" in f.fix[0]


def test_security_levels():
    for sec, fid, sev in (("open", "sec-open", "critical"), ("wep", "sec-broken", "critical"),
                          ("wpa/wpa2", "sec-mixed", "warning"), ("wpa2", "sec-wpa2", "tip"), ("wpa3", "sec-good", "good")):
        assert ids(analyse(Scan(link=healthy_link(security=sec)), Profile()))[fid] == sev


def test_speed_blames_wifi_when_link_is_slow():
    s = Scan(link=healthy_link(tx_rate_mbps=150), speed=SpeedResult(download_mbps=80))
    f = next(f for f in analyse(s, Profile(plan_mbps=500)).findings if f.id == "speed-low")
    assert f.category == "wifi" and f.symptom


def test_speed_blames_provider_when_link_is_fast():
    s = Scan(link=healthy_link(), speed=SpeedResult(download_mbps=80))
    f = next(f for f in analyse(s, Profile(plan_mbps=500)).findings if f.id == "speed-low")
    assert f.category == "internet" and not f.symptom


def test_bufferbloat_grades():
    assert SpeedResult(idle_latency_ms=20, loaded_latency_ms=22).bufferbloat_grade == "A+"
    assert SpeedResult(idle_latency_ms=20, loaded_latency_ms=520).bufferbloat_grade == "F"
    r = analyse(Scan(speed=SpeedResult(download_mbps=100, idle_latency_ms=20, loaded_latency_ms=400)), Profile())
    assert ids(r)["bufferbloat"] == "critical"


def test_router_ping_ignored_when_internet_is_just_as_fast():
    s = Scan(link=healthy_link(), gateway_ping=PingStats("r", 20, 20, 15, 2, 60, 21),
             internet_ping=PingStats("i", 20, 20, 15, 9, 40, 10))
    assert "router-latency" not in ids(analyse(s, Profile()))


def test_isp_loss_with_clean_home_network():
    s = Scan(link=healthy_link(), gateway_ping=PingStats("r", 20, 20, 2, 1, 3, 0.4),
             internet_ping=PingStats("i", 20, 18, 30, 20, 50, 4))
    f = next(f for f in analyse(s, Profile()).findings if f.id == "internet-loss")
    assert "provider" in f.why


def test_big_house_needs_mesh():
    r = analyse(Scan(link=healthy_link()), Profile(size_sqm=250, floors=2, walls="concrete", setup="own_router",
                                                    problem="some_rooms"))
    f = next(f for f in r.findings if f.id == "coverage-single")
    assert f.severity == "warning" and "5" in f.title


def test_extenders_and_enclosed_router():
    r = analyse(Scan(), Profile(setup="extenders", router_spot="enclosed"))
    assert ids(r)["extenders"] == "warning" and ids(r)["router-enclosed"] == "warning"


def test_wired_skips_wifi_checks():
    r = analyse(Scan(link=healthy_link(rssi_dbm=-85, band="2.4", channel=3), wired=True), Profile())
    assert "wired" in ids(r) and "signal-weak" not in ids(r) and "channel-24-overlap" not in ids(r)


def test_demo_is_a_believable_mid_score():
    r = analyse(demo_scan(), demo_profile())
    assert 30 <= r.score <= 70


def test_channel_maths():
    assert overlaps_24(1, 3) and not overlaps_24(1, 6) and not overlaps_24(6, 11)
    assert span_5(40, 80) == [36, 40, 44, 48] and span_5(149, 40) == [149, 153] and span_5(36, 20) == [36]
    near = [Network(channel=44, band="5", width_mhz=20, rssi_dbm=-60)]
    assert len(neighbours_on(36, "5", 80, near)) == 1 and not neighbours_on(149, "5", 80, near)
    assert best_channel("5", near) != 36


def test_rooms_walk_advice():
    from fixmywifi.models import PingStats as P
    from fixmywifi.rooms import RoomSample, advice, measure, verdict

    good = RoomSample("Living room", -48, "5", 866, 3, 0)
    bad = RoomSample("Bedroom", -80, "2.4", 26, 30, 10)
    assert verdict(good)[0] == "Great" and verdict(bad)[0] == "Dead zone"
    tips = advice([good, bad], "Living room")
    assert "halfway between the Living room and the Bedroom" in tips[1]
    assert any("2.4 GHz" in t for t in tips)
    s = measure("Office", lambda: (healthy_link(rssi_dbm=-66), [], []), lambda h, n: P(h, 10, 10, 4.0), "192.168.1.1")
    assert s.rssi_dbm == -66 and s.ping_ms == 4.0 and verdict(s)[0] == "OK"
