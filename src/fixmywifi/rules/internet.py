"""Rules about latency, packet loss, DNS and real-world speed. These separate 'my Wi-Fi' from 'my provider'."""

from __future__ import annotations

from fixmywifi.models import Finding
from fixmywifi.rules import Ctx, rule

SQM_FIX = [
    "Turn on 'Smart Queue', 'SQM' or 'QoS' in your router settings or app.",
    "It's called: eero 'Optimize for Conferencing and Gaming', Ubiquiti 'Smart Queues', ASUS 'Adaptive QoS', "
    "TP-Link 'QoS', OpenWrt 'SQM (cake)', Netgear 'Dynamic QoS'.",
    "Set its speed limits to about 90% of your measured download and upload speed.",
    "If your router has no such feature, this is a strong reason to upgrade it.",
]


def _gw_ok(ctx: Ctx) -> bool:
    g = ctx.scan.gateway_ping
    return bool(g and g.received and (g.loss_pct or 0) == 0 and (g.avg_ms or 0) < 10)


@rule
def router_latency(ctx: Ctx):
    g = ctx.scan.gateway_ping
    if not g or not g.sent:
        return None
    if g.received == 0:
        return Finding("router-no-ping", "tip", "Your router didn't answer our ping.",
                       "Many routers ignore pings on purpose, so this isn't necessarily a problem. It just means "
                       "we couldn't measure the delay between you and the router.")
    loss, avg, jit = g.loss_pct or 0, g.avg_ms or 0, g.jitter_ms or 0
    i = ctx.scan.internet_ping
    if loss == 0 and i and i.received and i.avg_ms is not None and i.avg_ms <= avg + 2:
        # The internet beyond the router answers as fast as the router itself, so the path is fine:
        # the router is just slow to reply to pings (very common, it treats them as low priority).
        return None
    medium = "the cable" if ctx.scan.wired else "Wi-Fi"
    if loss >= 3 or avg >= 25:
        sev = "critical"
    elif loss > 0 or avg >= 8 or jit >= 10:
        sev = "warning"
    else:
        return Finding("router-latency-good", "good", f"Your connection to the router is fast and steady ({avg:.0f} ms).",
                       "No lost packets between you and the router.")
    return Finding("router-latency", sev, "The connection between you and your router is unsteady.",
                   f"Talking to your own router should take under 5 ms with nothing lost. We measured {avg:.0f} ms on "
                   f"average, {jit:.0f} ms of jitter and {loss:.0f}% lost over {medium}. That causes stutter in calls "
                   "and games and slow page loads, and it's inside your home, not your provider's fault.",
                   ["Restart the router. If it's hot or more than 5 years old, consider replacing it.",
                    "Check for a device hogging the network (big downloads, backups, cloud photo sync).",
                    "If this report also lists signal or channel problems, fix those: they're the usual cause."])


@rule
def internet_quality(ctx: Ctx):
    i = ctx.scan.internet_ping
    if not i or not i.sent:
        return None
    if i.received == 0:
        return Finding("internet-down", "critical", "We couldn't reach the internet at all.",
                       "Pings to 1.1.1.1 got no answer. If your router answered fine, the problem is the line or your provider.",
                       ["Restart the modem/router (unplug for 30 seconds).", "Check your provider's status page or call them."],
                       category="internet")
    loss, avg = i.loss_pct or 0, i.avg_ms or 0
    gw_ok = _gw_ok(ctx)
    where = ("Your home network is fine, so this is happening on your provider's side." if gw_ok
             else "Part of this may be coming from inside your home (see the router checks).")
    if loss >= 2:
        return Finding("internet-loss", "critical", f"{loss:.0f}% of data is getting lost on the way to the internet.",
                       f"Even 1-2% loss makes video calls freeze and games rubber-band. {where}",
                       ["Restart the modem/router.",
                        "If it keeps happening, call your provider and tell them you see packet loss to 1.1.1.1 "
                        "(you can show them this report).", "Check the cable from the wall to the modem is tight and undamaged."],
                       category="internet")
    if avg >= 80:
        return Finding("internet-latency", "warning", f"Internet delay is high ({avg:.0f} ms).",
                       f"A good connection reaches big internet hubs in under 30-40 ms. {where}",
                       ["Run fixmywifi again at a different time: if it's only bad in the evening, your provider is congested.",
                        "Ask your provider about it, or compare with neighbours on other providers."],
                       category="internet")
    return None


@rule
def speed_vs_plan(ctx: Ctx):
    s = ctx.scan.speed
    if not s or s.download_mbps is None:
        return None
    dl = s.download_mbps
    if not ctx.plan:
        return Finding("speed-measured", "good" if dl >= 50 else "tip", f"Measured download speed: {dl:.0f} Mbps.",
                       "Tell fixmywifi your plan speed (it asks at the start) to find out whether you're getting what you pay for.",
                       category="internet")
    ratio = dl / ctx.plan
    if ratio >= 0.75:
        return Finding("speed-ok", "good", f"You're getting {dl:.0f} of your {ctx.plan} Mbps plan.",
                       "Your provider is delivering what you pay for.", category="internet")
    link = ctx.link
    wifi_limit = ctx.on_wifi and link.tx_rate_mbps and link.tx_rate_mbps * 0.6 < ctx.plan * 0.85
    if wifi_limit:
        why = (f"You measured {dl:.0f} Mbps on a {ctx.plan} Mbps plan ({ratio:.0%}). Your Wi-Fi link can't carry more, "
               "so the bottleneck is inside your home.")
        fix = ["Fix the Wi-Fi issues listed in this report, then test again.",
               "Plug a laptop into the router with a cable and run fixmywifi again: if it's fast on the cable, Wi-Fi is confirmed as the problem."]
        cat = "wifi"
    else:
        why = (f"You measured {dl:.0f} Mbps on a {ctx.plan} Mbps plan ({ratio:.0%}), and your Wi-Fi link looks fast "
               "enough to carry more. The router or your provider is likely the limit.")
        fix = ["Plug a laptop into the router with a cable and test again to rule out Wi-Fi completely.",
               "Restart the modem/router.", "If it's still slow on a cable, contact your provider with these numbers.",
               "Check nothing else on the network is downloading at the same time."]
        cat = "internet"
    return Finding("speed-low", "critical" if ratio < 0.35 else "warning",
                   f"You're only getting {ratio:.0%} of the speed you pay for.", why, fix, category=cat,
                   symptom=cat == "wifi")


@rule
def bufferbloat(ctx: Ctx):
    s = ctx.scan.speed
    if not s or s.bufferbloat_ms is None:
        return None
    b, g = s.bufferbloat_ms, s.bufferbloat_grade
    if g in ("A+", "A"):
        return Finding("bufferbloat-good", "good", f"No lag when the line is busy (bufferbloat grade {g}).",
                       f"Delay only rose by {b:.0f} ms during the speed test. Calls and games will stay smooth while others download.",
                       category="internet")
    sev = "warning" if g in ("B", "C") else "critical"
    return Finding("bufferbloat", sev, f"Your connection lags badly when it's busy (bufferbloat grade {g}).",
                   f"While we ran the speed test, delay jumped by {b:.0f} ms. That's why video calls freeze or games lag "
                   "the moment someone starts a download, a backup or a Netflix stream. It's very common, and very fixable.",
                   SQM_FIX if sev != "good" else [], category="internet")


@rule
def upload_for_calls(ctx: Ctx):
    s = ctx.scan.speed
    if not s or s.upload_mbps is None or not ctx.uses("calls", "wfh", "streaming_out"):
        return None
    if s.upload_mbps < 5:
        return Finding("upload-low", "warning", f"Upload speed is low for video calls ({s.upload_mbps:.1f} Mbps).",
                       "Your camera and microphone use upload. HD video calls need about 3-4 Mbps each, and anything "
                       "else uploading (photo backup, cloud sync) competes with it.",
                       ["Pause cloud backups during calls.", "Ask your provider about plans with more upload (fibre is usually symmetrical)."],
                       category="internet")


@rule
def dns_speed(ctx: Ctx):
    results = [r for r in ctx.scan.dns if r.median_ms is not None or r.failures]
    yours = next((r for r in results if r.label == "Your DNS"), None)
    public = [r for r in results if not r.label.startswith("Your") and r.median_ms is not None]
    if not yours or not public:
        return None
    best = min(public, key=lambda r: r.median_ms)
    if yours.median_ms is None or yours.failures >= 2:
        return Finding("dns-failing", "warning", "Your DNS (the internet's phone book) is failing to answer.",
                       "Every website visit starts with a DNS lookup. When it fails or times out, pages hang before they start loading.",
                       [f"Switch DNS to {best.label} ({best.server}) in your router or device network settings."],
                       category="internet")
    if yours.median_ms > best.median_ms * 2 and yours.median_ms - best.median_ms > 25:
        return Finding("dns-slow", "tip", f"Your DNS is slow ({yours.median_ms:.0f} ms vs {best.median_ms:.0f} ms for {best.label}).",
                       "Every new website starts with a DNS lookup, so slow DNS makes browsing feel sluggish even when "
                       "downloads are fast.",
                       [f"Set DNS to {best.server} ({best.label}) in the router so every device benefits.",
                        "Prefer privacy-focused options like 1.1.1.1 or 9.9.9.9 over your provider's default."],
                       category="internet")
    return None
