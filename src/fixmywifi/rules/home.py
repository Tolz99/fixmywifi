"""Rules that use what the person told us about their home and habits."""

from __future__ import annotations

import math

from fixmywifi.models import Finding
from fixmywifi.rules import Ctx, rule

# Rough area one modern router covers well, in square metres, by wall type.
COVER_SQM = {"light": 110, "brick": 80, "concrete": 55, "": 90}
ROOMS_PER_AP = {"light": 5, "brick": 4, "concrete": 3, "": 4}


def units_needed(p) -> int:
    walls = p.walls if p.walls in COVER_SQM else ""
    if p.size_sqm:
        n = math.ceil(p.size_sqm / COVER_SQM[walls])
    elif p.rooms:
        n = math.ceil(p.rooms / ROOMS_PER_AP[walls])
    else:
        n = 1
    if p.floors and p.floors > 1:
        n = max(n, p.floors)
    return max(1, n)


@rule
def coverage(ctx: Ctx):
    p = ctx.profile
    if not (p.size_sqm or p.rooms or p.floors):
        return None
    need = units_needed(p)
    have_mesh = p.setup == "mesh"
    if need <= 1:
        return None
    if have_mesh:
        return Finding("coverage-mesh", "tip", f"For your home, {need} mesh units is about right.",
                       "Mesh works best when units are no more than one or two rooms apart, with a clear line between them.",
                       ["If your mesh units can be connected with Ethernet cable ('wired backhaul'), do it: it doubles their speed.",
                        "Place each unit halfway between the router and the dead zone, not inside the dead zone."],
                       category="home")
    walls = {"concrete": "concrete walls", "brick": "brick walls"}.get(p.walls, "")
    detail = ", ".join(x for x in [f"{p.size_sqm} m²" if p.size_sqm else "", f"{p.rooms} rooms" if p.rooms else "",
                                    f"{p.floors} floors" if p.floors and p.floors > 1 else "", walls] if x)
    sev = "warning" if need >= 2 and (p.problem in ("some_rooms", "everywhere", "drops") or need >= 3) else "tip"
    return Finding("coverage-single", sev, f"One router can't properly cover your home. You need about {need} access points.",
                   f"With {detail}, a single router leaves weak spots: walls and floors absorb Wi-Fi "
                   "(concrete and brick most of all).",
                   [f"Get a mesh system with {need} units (Wi-Fi 6 or newer). Brands like eero, Deco, Orbi, Nest Wifi or "
                    "Ubiquiti all work.",
                    "Even better: run an Ethernet cable to the second unit if you can ('wired backhaul').",
                    "Can't run cables? Look at MoCA (uses TV coax) or powerline adapters to link the units."],
                   category="hardware")


@rule
def router_placement(ctx: Ctx):
    spot = ctx.profile.router_spot
    if spot == "enclosed":
        return Finding("router-enclosed", "warning", "Your router is inside a cabinet, closet or box.",
                       "Doors, shelves and especially metal or TV cabinets block a lot of the signal before it even leaves the furniture.",
                       ["Put the router out in the open, at least a metre off the floor, with antennas vertical.",
                        "If the cable is short, a longer Ethernet cable from the wall to the router is cheap."], category="home")
    if spot == "edge" and units_needed(ctx.profile) >= 1 and (ctx.profile.size_sqm or 0) >= 70:
        return Finding("router-edge", "warning", "Your router sits at the edge of the home.",
                       "Wi-Fi spreads out in a sphere. From a corner, half of it goes outside or to the neighbours, "
                       "and the far side of the home gets the weakest signal.",
                       ["Move the router as close to the middle of the home as the cabling allows.",
                        "If it has to stay put, add a mesh unit toward the far side."], category="home")
    if spot == "other_floor":
        return Finding("router-floor", "tip", "Your router is on a different floor from where you use the internet most.",
                       "Floors are thick and often contain metal and concrete. Signal drops a lot between floors.",
                       ["Put a mesh unit on each floor you use."], category="home")


@rule
def extenders(ctx: Ctx):
    if ctx.profile.setup == "extenders":
        return Finding("extenders", "warning", "You're using Wi-Fi extenders (repeaters).",
                       "A typical extender listens and repeats on the same radio, so anything connected through it gets "
                       "about half the speed, plus extra delay. Devices also cling to the wrong one.",
                       ["Replace extenders with a mesh system, ideally linked with Ethernet.",
                        "If you keep them: put them halfway between router and dead zone, not in the dead zone."],
                       category="hardware")


@rule
def router_age(ctx: Ctx):
    age = ctx.profile.router_age_years
    if age is None:
        return None
    if age >= 6:
        return Finding("router-old", "warning", f"Your router is about {age} years old.",
                       "Routers this old usually run Wi-Fi 5 or older, stop getting security updates, and struggle with "
                       "today's number of phones, TVs and smart-home gadgets.",
                       ["A Wi-Fi 6 (or newer) router is the single most effective upgrade for most homes.",
                        "If it's your provider's box, ask them for a newer model: it's often free."], category="hardware")


@rule
def many_devices(ctx: Ctx):
    n = ctx.profile.devices or ctx.scan.lan_devices
    if not n or n < 25:
        return None
    old = ctx.link and ctx.link.phy in ("802.11n", "802.11ac", "802.11g")
    if not old and (ctx.profile.router_age_years or 0) < 5:
        return None
    return Finding("many-devices", "warning" if old else "tip", f"You have about {n} devices on your network.",
                   "Older Wi-Fi serves devices one at a time. With dozens of phones, TVs, speakers and smart plugs, "
                   "everyone waits their turn. Wi-Fi 6 can serve several devices at once.",
                   ["Upgrade to a Wi-Fi 6 or newer router/mesh.",
                    "Put smart-home gadgets (plugs, bulbs, cameras) on a separate 2.4 GHz or guest network so they don't slow your main devices."],
                   category="hardware")


@rule
def isp_router(ctx: Ctx):
    p = ctx.profile
    if p.setup == "isp_router" and (p.problem not in ("", "none") or (p.plan_mbps or 0) >= 500):
        return Finding("isp-router", "tip", "You're using the router your provider gave you.",
                       "Provider routers are often basic: weak antennas, few settings and no traffic management. "
                       "That's fine for small flats, but often the weak link in bigger or busier homes.",
                       ["Ask your provider for their newest model.",
                        "Or put their box in 'bridge mode' (or 'modem only') and use your own router or mesh."],
                       category="hardware")


@rule
def plan_vs_router(ctx: Ctx):
    link, plan = ctx.link, ctx.plan
    if not plan or not ctx.on_wifi or not link.phy:
        return None
    if plan >= 300 and link.phy in ("802.11n", "802.11g"):
        return Finding("plan-outruns-wifi", "warning", f"Your {plan} Mbps plan is faster than your Wi-Fi can go.",
                       "Wi-Fi 4 (802.11n) rarely delivers more than 100-150 Mbps in a real home.",
                       ["Upgrade to a Wi-Fi 6 router to actually use the speed you pay for."], category="hardware")
    if plan >= 1000 and link.phy == "802.11ac":
        return Finding("plan-gigabit-ac", "tip", "On a gigabit plan, Wi-Fi 5 will hold you back.",
                       "Wi-Fi 5 tops out around 400-600 Mbps in practice. Wi-Fi 6/6E/7 can get close to gigabit.",
                       ["For full speed: Wi-Fi 6E/7 router, or Ethernet for your main computer/console."], category="hardware")


@rule
def wire_it(ctx: Ctx):
    if ctx.uses("gaming", "calls", "wfh") and ctx.on_wifi:
        return Finding("wire-it", "tip", "For gaming and work calls, a cable beats any Wi-Fi.",
                       "Ethernet has near-zero jitter and never fights neighbours for airtime.",
                       ["Plug consoles, desktop PCs and work laptops (via a cheap USB-Ethernet adapter) into the router or a mesh unit."],
                       category="home")


@rule
def evenings(ctx: Ctx):
    if ctx.profile.problem == "evenings":
        return Finding("evenings", "tip", "Slow mostly in the evenings? That points at your provider or neighbours.",
                       "From 7-11 pm everyone streams. If your provider's local network is overloaded, speed drops no "
                       "matter how good your Wi-Fi is. In apartments, neighbours' Wi-Fi also gets busier.",
                       ["Run `fixmywifi --save` now and again at a slow time, then compare the reports.",
                        "If speed drops on a cable too, the evidence is clear: take it to your provider.",
                        "Use 5 GHz or 6 GHz, which is much less affected by neighbours."], category="internet")


@rule
def drops(ctx: Ctx):
    if ctx.profile.problem == "drops":
        return Finding("drops-general", "tip", "Tips for random disconnects.",
                       "Drops are usually caused by weak signal at the edge of coverage, radar channels (DFS), "
                       "overheating or outdated router firmware, or devices bouncing between bands.",
                       ["Update the router's firmware (look for 'Firmware update' in its settings or app).",
                        "Make sure the router has airflow and isn't hot to the touch.",
                        "If your devices bounce between 2.4 and 5 GHz, give the bands separate names and pick one."],
                       category="home")
