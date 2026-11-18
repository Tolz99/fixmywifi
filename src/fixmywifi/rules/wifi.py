"""Rules about the radio link itself: signal, noise, band, channel, width, Wi-Fi generation."""

from __future__ import annotations

from fixmywifi.channels import DFS_CHANNELS, NON_OVERLAPPING_24, best_channel, neighbours_on
from fixmywifi.models import Finding
from fixmywifi.rules import Ctx, rule

GEN = {"802.11be": "Wi-Fi 7", "802.11ax": "Wi-Fi 6/6E", "802.11ac": "Wi-Fi 5", "802.11n": "Wi-Fi 4",
       "802.11g": "Wi-Fi 3", "802.11a": "Wi-Fi 2", "802.11b": "Wi-Fi 1"}


@rule
def wired(ctx: Ctx):
    if ctx.scan.wired:
        return Finding("wired", "good", "You're on a cable (Ethernet). That's the fastest, steadiest option.",
                       "Wi-Fi checks were skipped for this computer. Run fixmywifi on a phone-distance laptop "
                       "over Wi-Fi to check the wireless side.", category="wifi")


@rule
def signal_strength(ctx: Ctx):
    r = ctx.rssi
    if not ctx.on_wifi or r is None:
        return None
    near = ctx.profile.where_now in ("same_room",)
    if r >= -60:
        return Finding("signal-good", "good", f"Strong signal ({r} dBm).",
                       "Signal strength isn't your problem from where you're sitting.")
    if r >= -67:
        return None
    sev = "critical" if r < -75 else "warning"
    fix = ["Move the router to a central, open spot: off the floor, out of cabinets, away from the TV and microwave.",
           "If the house is big or has thick walls, one router can't cover it. A mesh system (2-3 units) is the real fix.",
           "Avoid cheap plug-in extenders: they usually halve your speed. Mesh with a cable between units is best."]
    why = (f"Your signal is {r} dBm. Above -60 is great, -67 is the minimum for smooth video calls, "
           f"and below -75 things get slow and drop. Weak signal forces devices to talk slowly and repeat themselves.")
    if near:
        why += " You said you're in the same room as the router, so something is wrong: check its antennas, " \
               "whether it's boxed in, or whether you're connected to a different access point."
        fix.insert(0, "Restart the router and check you're connected to the right network (not a neighbour's or an old extender).")
    return Finding("signal-weak", sev, "Your Wi-Fi signal is weak where you are.", why, fix)


@rule
def signal_noise(ctx: Ctx):
    link = ctx.link
    if not ctx.on_wifi or link.snr_db is None:
        return None
    snr = link.snr_db
    if snr >= 25:
        return None
    sev = "critical" if snr < 15 else "warning"
    return Finding("snr-low", sev, "There's a lot of radio noise around your connection.",
                   f"Your signal is only {snr} dB above the background noise (25+ is healthy, 40+ is excellent). "
                   "Noise comes from microwaves, cordless phones, baby monitors, Bluetooth, cheap USB 3 hubs and "
                   "neighbouring networks.",
                   ["Move the router away from microwaves, cordless phone bases, and big metal objects.",
                    "Use the 5 GHz (or 6 GHz) band: it's far less noisy than 2.4 GHz."])


@rule
def band(ctx: Ctx):
    link = ctx.link
    if not ctx.on_wifi or link.band != "2.4":
        return None
    r = ctx.rssi
    if r is not None and r >= -65:
        return Finding("band-24", "warning", "You're on the slow 2.4 GHz band even though your signal is good.",
                       "2.4 GHz reaches further but is much slower and more crowded. With a signal this strong you "
                       "could be on 5 GHz and get roughly 2-5x the speed.",
                       ["In the router settings, make sure the 5 GHz band is switched on.",
                        "If the router has 'band steering' or 'smart connect', turn it on so devices move to 5 GHz.",
                        "Or give the 5 GHz band its own name (e.g. 'Home-5G') and connect laptops, phones and TVs to it."])
    return Finding("band-24-far", "tip", "You're on 2.4 GHz, probably because you're far from the router.",
                   "2.4 GHz travels through walls better but is slow. Being stuck on it is a sign the router doesn't "
                   "cover this spot well.",
                   ["Better coverage (router placement or a mesh unit nearby) will let you use 5 GHz here."])


@rule
def channel_24_overlap(ctx: Ctx):
    link = ctx.link
    if not ctx.on_wifi or link.band != "2.4" or link.channel is None or link.channel in NON_OVERLAPPING_24:
        return None
    best = best_channel("2.4", ctx.scan.nearby)
    return Finding("channel-24-overlap", "warning", f"Your router uses 2.4 GHz channel {link.channel}, which overlaps its neighbours.",
                   "In 2.4 GHz only channels 1, 6 and 11 don't overlap each other. Anything in between gets interference "
                   "from networks on both sides.",
                   [f"In the router settings, set the 2.4 GHz channel to {best or '1, 6 or 11'}."])


@rule
def congestion(ctx: Ctx):
    link = ctx.link
    if not ctx.on_wifi or link.channel is None or link.band not in ("2.4", "5") or not ctx.scan.nearby:
        return None
    width = link.width_mhz or 20
    rivals = neighbours_on(link.channel, link.band, width, ctx.scan.nearby)
    loud = [n for n in rivals if n.rssi_dbm is not None and n.rssi_dbm >= -70]
    limit = 4 if link.band == "2.4" else 2
    if len(rivals) < limit and len(loud) < 2:
        return None
    best = best_channel(link.band, ctx.scan.nearby, width if link.band == "5" else 20)
    fix = []
    if best and best != link.channel and not (link.band == "5" and best in _block(link.channel)):
        fix.append(f"Change your {link.band} GHz channel to {best} in the router settings (it's the least crowded right now).")
    fix.append("If your router has an 'auto channel' option, make sure it's on and restart the router so it re-picks.")
    if link.band == "2.4":
        fix.append("Move as many devices as possible to 5 GHz, where there's far more room.")
    sev = "warning" if len(loud) >= 2 or len(rivals) >= limit * 2 else "tip"
    return Finding("channel-crowded", sev,
                   f"Your {link.band} GHz channel is shared with {len(rivals)} nearby network{'s' if len(rivals) != 1 else ''}.",
                   "Wi-Fi networks on the same channel take turns to talk. Every neighbour on your channel eats into "
                   f"your airtime{f', and {len(loud)} of them are loud (close by)' if loud else ''}.", fix)


def _block(ch):
    from fixmywifi.channels import span_5
    return span_5(ch, 80)


@rule
def width_24(ctx: Ctx):
    link = ctx.link
    if ctx.on_wifi and link.band == "2.4" and (link.width_mhz or 20) >= 40:
        return Finding("width-24-wide", "warning", "Your 2.4 GHz band is set to 40 MHz wide.",
                       "There's only room for three clean channels in 2.4 GHz. A 40 MHz channel takes up two of them, "
                       "collides with neighbours and often ends up slower, not faster.",
                       ["Set the 2.4 GHz channel width to 20 MHz in the router settings."])


@rule
def width_5(ctx: Ctx):
    link = ctx.link
    if not ctx.on_wifi or link.band != "5" or link.width_mhz is None or link.channel is None:
        return None
    rivals = neighbours_on(link.channel, "5", 80, ctx.scan.nearby)
    if link.width_mhz <= 40 and link.phy in ("802.11ac", "802.11ax", "802.11be") and len(rivals) < 3:
        return Finding("width-5-narrow", "tip", f"Your 5 GHz channel is only {link.width_mhz} MHz wide.",
                       "Wider channels carry more data at once. 80 MHz roughly doubles the top speed of 40 MHz, and "
                       "your area isn't crowded enough for that to cause trouble.",
                       ["Set the 5 GHz channel width to 80 MHz in the router settings."])
    if link.width_mhz >= 160 and len(rivals) >= 2:
        return Finding("width-5-160-crowded", "tip", "Your 5 GHz channel is 160 MHz wide in a crowded area.",
                       "160 MHz is fast in theory, but it overlaps more neighbours and drops back when any of them talk.",
                       ["Try 80 MHz in the router settings and compare with `fixmywifi` again."])


@rule
def dfs(ctx: Ctx):
    link = ctx.link
    if not ctx.on_wifi or link.band != "5" or link.channel not in DFS_CHANNELS:
        return None
    if ctx.profile.problem == "drops":
        return Finding("dfs-drops", "warning", f"Your router uses channel {link.channel}, a radar-shared (DFS) channel.",
                       "On DFS channels the router must go silent for about a minute whenever it detects weather or "
                       "airport radar. That shows up as random disconnects, which matches what you described.",
                       ["Pick a non-DFS 5 GHz channel: 36-48 or 149-161.",
                        "Some routers have a 'DFS' or 'Use radar channels' switch: turn it off."])
    return None


@rule
def wifi_generation(ctx: Ctx):
    link = ctx.link
    if not ctx.on_wifi or not link.phy:
        return None
    gen = GEN.get(link.phy)
    if link.phy in ("802.11ax", "802.11be"):
        return Finding("gen-modern", "good", f"You're using {gen} ({link.phy}), the modern standard.",
                       "Your router and this device both speak current Wi-Fi.")
    if link.phy in ("802.11n", "802.11g", "802.11b", "802.11a"):
        return Finding("gen-old", "warning", f"This connection is using old {gen or link.phy} ({link.phy}).",
                       "Older Wi-Fi tops out at a fraction of modern speeds and handles many devices badly. Either the "
                       "router is old, it's set to a compatibility mode, or this device is old.",
                       ["Check the router's 'wireless mode' setting: allow the newest mode (ax/ac) on 5 GHz.",
                        "If the router is more than ~5 years old, a Wi-Fi 6 router is the single biggest upgrade you can make."],
                       category="hardware")
    return None


@rule
def link_rate(ctx: Ctx):
    link = ctx.link
    if not ctx.on_wifi or not link.tx_rate_mbps:
        return None
    rate = link.tx_rate_mbps
    usable = rate * 0.6  # real-world throughput is ~50-70% of the link rate
    if ctx.plan and usable < ctx.plan * 0.85:
        return Finding("link-bottleneck", "warning" if usable < ctx.plan * 0.6 else "tip",
                       "Your Wi-Fi link is slower than your internet plan.",
                       f"This device is talking to the router at {rate:.0f} Mbps, which works out to about "
                       f"{usable:.0f} Mbps of real speed. You pay for {ctx.plan} Mbps, so Wi-Fi is the bottleneck, "
                       "not your provider.",
                       ["Get closer to the router or improve coverage (see signal tips).",
                        "Use 5 GHz with an 80 MHz channel.",
                        "For desks, TVs and consoles that never move, an Ethernet cable gets you the full speed."])
    if rate < 50:
        return Finding("link-slow", "warning", f"The link to your router is very slow ({rate:.0f} Mbps).",
                       "Even a basic modern connection should link at 150+ Mbps. Low rates come from weak signal, "
                       "interference, or old hardware.",
                       ["Work through the signal and channel tips above; this usually fixes itself with them."])
    return None
