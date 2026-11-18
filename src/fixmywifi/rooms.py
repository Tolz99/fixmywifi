"""Walk test: carry your laptop room to room and find the dead zones.

Usage: fixmywifi --rooms
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table


@dataclass
class RoomSample:
    room: str
    rssi_dbm: Optional[int] = None
    band: Optional[str] = None
    tx_rate_mbps: Optional[float] = None
    ping_ms: Optional[float] = None
    loss_pct: Optional[float] = None


def verdict(s: RoomSample) -> tuple:
    if s.rssi_dbm is None:
        return "No Wi-Fi", "red"
    if s.rssi_dbm >= -60 and (s.loss_pct or 0) == 0:
        return "Great", "green"
    if s.rssi_dbm >= -67 and (s.loss_pct or 0) < 5:
        return "OK", "green"
    if s.rssi_dbm >= -75:
        return "Weak", "yellow"
    return "Dead zone", "red"


def advice(samples: List[RoomSample], router_room: str) -> List[str]:
    weak = [s for s in samples if verdict(s)[0] in ("Weak", "Dead zone", "No Wi-Fi")]
    if not weak:
        return ["Every room you tested has good Wi-Fi. If something still feels slow, run plain `fixmywifi` in that room."]
    worst = min(weak, key=lambda s: s.rssi_dbm if s.rssi_dbm is not None else -200)
    names = ", ".join(s.room for s in weak)
    tips = [f"Weak rooms: {names}."]
    on24 = [s.room for s in weak if s.band == "2.4"]
    if len(weak) >= 2 or verdict(worst)[0] != "Weak":
        tips.append(f"Add a mesh unit roughly halfway between the {router_room or 'router'} and the {worst.room}. "
                    "Halfway, not inside the dead zone: the unit needs a good signal itself to pass on.")
    else:
        tips.append(f"Try moving the router a few metres toward the {worst.room}, out in the open and off the floor, then test again.")
    if on24:
        tips.append(f"In {', '.join(on24)} you dropped to 2.4 GHz, a clear sign of too much distance or too many walls.")
    tips.append("After changing anything, run `fixmywifi --rooms` again and compare.")
    return tips


def measure(room: str, collect: Callable, ping: Callable, gateway: str) -> RoomSample:
    link, _, _ = collect()
    s = RoomSample(room=room)
    if link:
        s.rssi_dbm, s.band, s.tx_rate_mbps = link.rssi_dbm, link.band, link.tx_rate_mbps
    p = ping(gateway, 10) if gateway else None
    if p and p.sent:
        s.ping_ms, s.loss_pct = p.avg_ms, p.loss_pct
    return s


def render(samples: List[RoomSample], router_room: str, console: Console) -> None:
    t = Table(title="Wi-Fi by room", title_style="bold")
    for col in ("Room", "Signal", "Band", "Link speed", "Delay", "Verdict"):
        t.add_column(col)
    for s in samples:
        word, colour = verdict(s)
        t.add_row(s.room + (" (router)" if s.room == router_room else ""),
                  f"{s.rssi_dbm} dBm" if s.rssi_dbm is not None else "-",
                  f"{s.band} GHz" if s.band else "-",
                  f"{s.tx_rate_mbps:.0f} Mbps" if s.tx_rate_mbps else "-",
                  f"{s.ping_ms:.0f} ms" if s.ping_ms is not None else "-",
                  f"[{colour}]{word}[/]")
    console.print(t)
    console.print(Panel("\n".join(f"• {a}" for a in advice(samples, router_room)), title="What to do", border_style="magenta"))


def walk(console: Console) -> int:
    from fixmywifi.collectors import collect_wifi
    from fixmywifi.nettests import default_gateway, ping

    console.print(Panel("Carry this laptop to each room. In each one, type the room's name and press Enter.\n"
                        "We take a quick reading (about 5 seconds). Press Enter on an empty line when you're done.",
                        title="[bold]Room-by-room walk test[/]", border_style="cyan"))
    router_room = Prompt.ask("Which room is the router in?", default="", show_default=False, console=console).strip()
    gateway, _ = default_gateway()
    samples: List[RoomSample] = []
    while True:
        room = Prompt.ask("\n[bold]Room name[/] [dim](Enter to finish)[/]", default="", show_default=False, console=console).strip()
        if not room:
            break
        with console.status(f"Measuring {room}…"):
            s = measure(room, collect_wifi, ping, gateway)
        word, colour = verdict(s)
        console.print(f"  {room}: [{colour}]{word}[/]" + (f" ({s.rssi_dbm} dBm)" if s.rssi_dbm is not None else ""))
        samples.append(s)
    if not samples:
        console.print("No rooms measured.")
        return 0
    console.print()
    render(samples, router_room, console)
    return 0
