# fixmywifi report: 48/100 (grade D)

_8 things are holding you back. Biggest one: You're only getting 25% of the speed you pay for._

| | |
|---|---|
| Band | 2.4 GHz, channel 6, 40 MHz wide |
| Signal | -63 dBm (ok) |
| Signal above noise | 29 dB |
| Wi-Fi type | Wi-Fi 6/6E (802.11ax) |
| Link speed to router | 144 Mbps |
| Security | WPA2 |
| Neighbouring networks | 9 |
| Router | ExampleCorp HomeHub 2 |
| Devices seen on network | ~19 |
| Delay to router | 4 ms avg, 3 ms jitter, 0% lost |
| Delay to internet | 21 ms avg, 3 ms jitter, 0% lost |
| Speed | 74 down / 18 up Mbps |
| Lag under load | +215 ms (grade D) |
| DNS lookup time | 64 ms |

## Do these first

1. Turn on 'Smart Queue', 'SQM' or 'QoS' in your router settings or app.
2. In the router settings, make sure the 5 GHz band is switched on.
3. Change your 2.4 GHz channel to 1 in the router settings (it's the least crowded right now).

## Fix this first

### ✖ You're only getting 25% of the speed you pay for.

You measured 74 Mbps on a 300 Mbps plan (25%). Your Wi-Fi link can't carry more, so the bottleneck is inside your home.

1. Fix the Wi-Fi issues listed in this report, then test again.
2. Plug a laptop into the router with a cable and run fixmywifi again: if it's fast on the cable, Wi-Fi is confirmed as the problem.

### ✖ Your connection lags badly when it's busy (bufferbloat grade D).

While we ran the speed test, delay jumped by 215 ms. That's why video calls freeze or games lag the moment someone starts a download, a backup or a Netflix stream. It's very common, and very fixable.

1. Turn on 'Smart Queue', 'SQM' or 'QoS' in your router settings or app.
2. It's called: eero 'Optimize for Conferencing and Gaming', Ubiquiti 'Smart Queues', ASUS 'Adaptive QoS', TP-Link 'QoS', OpenWrt 'SQM (cake)', Netgear 'Dynamic QoS'.
3. Set its speed limits to about 90% of your measured download and upload speed.
4. If your router has no such feature, this is a strong reason to upgrade it.

## Worth fixing

### ▲ You're on the slow 2.4 GHz band even though your signal is good.

2.4 GHz reaches further but is much slower and more crowded. With a signal this strong you could be on 5 GHz and get roughly 2-5x the speed.

1. In the router settings, make sure the 5 GHz band is switched on.
2. If the router has 'band steering' or 'smart connect', turn it on so devices move to 5 GHz.
3. Or give the 5 GHz band its own name (e.g. 'Home-5G') and connect laptops, phones and TVs to it.

### ▲ Your 2.4 GHz channel is shared with 6 nearby networks.

Wi-Fi networks on the same channel take turns to talk. Every neighbour on your channel eats into your airtime, and 2 of them are loud (close by).

1. Change your 2.4 GHz channel to 1 in the router settings (it's the least crowded right now).
2. If your router has an 'auto channel' option, make sure it's on and restart the router so it re-picks.
3. Move as many devices as possible to 5 GHz, where there's far more room.

### ▲ Your 2.4 GHz band is set to 40 MHz wide.

There's only room for three clean channels in 2.4 GHz. A 40 MHz channel takes up two of them, collides with neighbours and often ends up slower, not faster.

1. Set the 2.4 GHz channel width to 20 MHz in the router settings.

### ▲ Your Wi-Fi link is slower than your internet plan.

This device is talking to the router at 144 Mbps, which works out to about 86 Mbps of real speed. You pay for 300 Mbps, so Wi-Fi is the bottleneck, not your provider.

1. Get closer to the router or improve coverage (see signal tips).
2. Use 5 GHz with an 80 MHz channel.
3. For desks, TVs and consoles that never move, an Ethernet cable gets you the full speed.

### ▲ Your router is inside a cabinet, closet or box.

Doors, shelves and especially metal or TV cabinets block a lot of the signal before it even leaves the furniture.

1. Put the router out in the open, at least a metre off the floor, with antennas vertical.
2. If the cable is short, a longer Ethernet cable from the wall to the router is cheap.

### ▲ One router can't properly cover your home. You need about 2 access points.

With 150 m², 6 rooms, 2 floors, brick walls, a single router leaves weak spots: walls and floors absorb Wi-Fi (concrete and brick most of all).

1. Get a mesh system with 2 units (Wi-Fi 6 or newer). Brands like eero, Deco, Orbi, Nest Wifi or Ubiquiti all work.
2. Even better: run an Ethernet cable to the second unit if you can ('wired backhaul').
3. Can't run cables? Look at MoCA (uses TV coax) or powerline adapters to link the units.

## Tips

### ● Your DNS is slow (64 ms vs 12 ms for Cloudflare).

Every new website starts with a DNS lookup, so slow DNS makes browsing feel sluggish even when downloads are fast.

1. Set DNS to 1.1.1.1 (Cloudflare) in the router so every device benefits.
2. Prefer privacy-focused options like 1.1.1.1 or 9.9.9.9 over your provider's default.

### ● You're on WPA2. Fine, but WPA3 is better if your router has it.

WPA3 protects against password-guessing attacks. 'WPA2/WPA3 transition' mode keeps older devices working.

1. If the router offers WPA2/WPA3 (transition) mode, switch to it.

### ● For gaming and work calls, a cable beats any Wi-Fi.

Ethernet has near-zero jitter and never fights neighbours for airtime.

1. Plug consoles, desktop PCs and work laptops (via a cheap USB-Ethernet adapter) into the router or a mesh unit.

### ● You're using the router your provider gave you.

Provider routers are often basic: weak antennas, few settings and no traffic management. That's fine for small flats, but often the weak link in bigger or busier homes.

1. Ask your provider for their newest model.
2. Or put their box in 'bridge mode' (or 'modem only') and use your own router or mesh.

## What's working

- ✔ Your connection to the router is fast and steady (4 ms).
- ✔ You're using Wi-Fi 6/6E (802.11ax), the modern standard.

<sub>Generated by [fixmywifi](https://github.com/Tolz99/fixmywifi) v0.1.0 on 2026-11-18 17:17</sub>
