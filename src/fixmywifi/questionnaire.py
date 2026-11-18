"""The short interview about your home. Every question can be skipped with Enter."""

from __future__ import annotations

import json
from dataclasses import fields
from typing import List, Optional, Sequence, Tuple

from rich.console import Console
from rich.prompt import Prompt

from fixmywifi.models import Profile

Choice = Tuple[str, str]  # (value, label)


def _choose(console: Console, question: str, choices: Sequence[Choice]) -> str:
    console.print(f"\n[bold]{question}[/]")
    for i, (_, label) in enumerate(choices, 1):
        console.print(f"  [cyan]{i}[/]  {label}")
    while True:
        ans = Prompt.ask("  Pick a number [dim](Enter to skip)[/]", default="", show_default=False, console=console).strip()
        if not ans:
            return ""
        if ans.isdigit() and 1 <= int(ans) <= len(choices):
            return choices[int(ans) - 1][0]
        console.print("  [red]Please type one of the numbers above.[/]")


def _multi(console: Console, question: str, choices: Sequence[Choice]) -> List[str]:
    console.print(f"\n[bold]{question}[/] [dim](several allowed, e.g. 1 3)[/]")
    for i, (_, label) in enumerate(choices, 1):
        console.print(f"  [cyan]{i}[/]  {label}")
    ans = Prompt.ask("  Numbers [dim](Enter to skip)[/]", default="", show_default=False, console=console)
    out = []
    for tok in ans.replace(",", " ").split():
        if tok.isdigit() and 1 <= int(tok) <= len(choices):
            v = choices[int(tok) - 1][0]
            if v not in out:
                out.append(v)
    return out


def _number(console: Console, question: str, lo: int, hi: int) -> Optional[int]:
    while True:
        ans = Prompt.ask(f"\n[bold]{question}[/] [dim](Enter to skip)[/]", default="", show_default=False, console=console)
        ans = ans.strip().lower().replace("mbps", "").replace("m2", "").replace("m²", "").replace("sqm", "").strip()
        if not ans:
            return None
        try:
            v = int(float(ans))
        except ValueError:
            console.print("  [red]Just a number please.[/]")
            continue
        if lo <= v <= hi:
            return v
        console.print(f"  [red]Expected something between {lo} and {hi}.[/]")


def ask(console: Console) -> Profile:
    console.print("\n[bold magenta]A few quick questions about your home[/] [dim](about 1 minute, all optional)[/]")
    p = Profile()
    p.problem = _choose(console, "What's bothering you most?", [
        ("everywhere", "It's slow everywhere"), ("some_rooms", "Some rooms are slow or have no signal"),
        ("drops", "It keeps disconnecting"), ("evenings", "It's slow at certain times (e.g. evenings)"),
        ("lag", "Video calls / games lag or freeze"), ("none", "Nothing specific, just checking"),
    ])
    p.home_type = _choose(console, "What kind of place is it?", [
        ("apartment", "Apartment / flat"), ("house", "House"), ("office", "Office / shop"),
    ])
    p.size_sqm = _number(console, "Roughly how big is it, in square metres? (1 sq ft ≈ 0.09 m², so 1,000 sq ft ≈ 93 m²)", 10, 5000)
    p.rooms = _number(console, "How many rooms (bedrooms + living areas + office)?", 1, 100)
    p.floors = _number(console, "How many floors do you need Wi-Fi on?", 1, 20)
    p.walls = _choose(console, "What are most inside walls made of?", [
        ("light", "Plasterboard / drywall / wood"), ("brick", "Brick or block"), ("concrete", "Concrete or stone"),
    ])
    p.router_spot = _choose(console, "Where is the router?", [
        ("central", "Central and in the open"), ("edge", "At one end or corner of the home"),
        ("enclosed", "Inside a cabinet, closet or TV unit"), ("other_floor", "On a different floor from where I use it most"),
    ])
    p.setup = _choose(console, "What's your setup?", [
        ("isp_router", "Just the box my provider gave me"), ("own_router", "My own router"),
        ("mesh", "A mesh system (several matching units)"), ("extenders", "A router plus extender/repeater plugs"),
    ])
    p.router_age_years = _number(console, "About how old is the router, in years?", 0, 30)
    p.devices = _number(console, "Roughly how many devices use the Wi-Fi? (phones, laptops, TVs, speakers, smart plugs...)", 1, 500)
    p.plan_mbps = _number(console, "What download speed does your internet plan promise, in Mbps? (check your bill)", 1, 100000)
    p.uses = _multi(console, "What do you use the internet for?", [
        ("streaming", "Streaming TV/video"), ("gaming", "Online gaming"), ("calls", "Video calls"),
        ("wfh", "Working from home"), ("smart_home", "Smart home gadgets / cameras"), ("downloads", "Big downloads / backups"),
    ])
    p.where_now = _choose(console, "Where are you right now, compared to the router?", [
        ("same_room", "Same room"), ("next_room", "Next room"), ("far", "Far side of the home"),
        ("other_floor", "Different floor"),
    ])
    return p


def load(path: str) -> Profile:
    """Load answers from a JSON file (handy for scripting and repeat runs)."""
    with open(path) as fh:
        data = json.load(fh)
    known = {f.name for f in fields(Profile)}
    return Profile(**{k: v for k, v in data.items() if k in known})
