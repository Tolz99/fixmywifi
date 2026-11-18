"""Turn a Report into something people can read: terminal, Markdown, HTML or JSON."""

from __future__ import annotations

import copy
import html
import json
from datetime import datetime
from typing import List, Tuple

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from fixmywifi import __version__
from fixmywifi.models import Report

REPO = "https://github.com/Tolz99/fixmywifi"
ICON = {"critical": "✖", "warning": "▲", "tip": "●", "good": "✔"}
COLOR = {"critical": "red", "warning": "yellow", "tip": "cyan", "good": "green"}
GRADE_COLOR = {"A": "green", "B": "green", "C": "yellow", "D": "red", "F": "red"}
LABEL = {"critical": "Fix this first", "warning": "Worth fixing", "tip": "Tips", "good": "What's working"}


def redact(report: Report) -> Report:
    """Remove network names and hardware addresses so the report is safe to share."""
    r = copy.deepcopy(report)
    for n in ([r.scan.link] if r.scan.link else []) + r.scan.nearby:
        n.ssid = "(hidden)" if n.ssid else ""
        n.bssid = ""
    r.scan.gateway_ip = ""
    return r


def facts(report: Report) -> List[Tuple[str, str]]:
    s, link = report.scan, report.scan.link
    rows = []
    if s.wired:
        rows.append(("Connection", "Ethernet cable"))
    if link and not s.wired:
        band = f"{link.band} GHz" if link.band else "?"
        ch = f"channel {link.channel}" if link.channel else ""
        width = f"{link.width_mhz} MHz wide" if link.width_mhz else ""
        rows.append(("Band", ", ".join(x for x in (band, ch, width) if x)))
        if link.rssi_dbm is not None:
            q = "great" if link.rssi_dbm >= -60 else "ok" if link.rssi_dbm >= -67 else "weak" if link.rssi_dbm >= -75 else "very weak"
            rows.append(("Signal", f"{link.rssi_dbm} dBm ({q})"))
        if link.snr_db is not None:
            rows.append(("Signal above noise", f"{link.snr_db} dB"))
        if link.phy:
            from fixmywifi.rules.wifi import GEN
            rows.append(("Wi-Fi type", f"{GEN.get(link.phy, '')} ({link.phy})".strip()))
        if link.tx_rate_mbps:
            rows.append(("Link speed to router", f"{link.tx_rate_mbps:.0f} Mbps"))
        if link.security:
            rows.append(("Security", link.security.upper()))
    if s.nearby:
        rows.append(("Neighbouring networks", str(len(s.nearby))))
    if s.router and (s.router.manufacturer or s.router.model):
        rows.append(("Router", f"{s.router.manufacturer} {s.router.model}".strip()))
    if s.lan_devices:
        rows.append(("Devices seen on network", f"~{s.lan_devices}"))
    for label, p in (("Delay to router", s.gateway_ping), ("Delay to internet", s.internet_ping)):
        if p and p.received:
            rows.append((label, f"{p.avg_ms:.0f} ms avg, {p.jitter_ms or 0:.0f} ms jitter, {p.loss_pct:.0f}% lost"))
    if s.speed and s.speed.download_mbps is not None:
        up = f" / {s.speed.upload_mbps:.0f} up" if s.speed.upload_mbps is not None else ""
        rows.append(("Speed", f"{s.speed.download_mbps:.0f} down{up} Mbps"))
        if s.speed.bufferbloat_grade:
            rows.append(("Lag under load", f"+{s.speed.bufferbloat_ms:.0f} ms (grade {s.speed.bufferbloat_grade})"))
    yours = next((d for d in s.dns if d.label == "Your DNS" and d.median_ms is not None), None)
    if yours:
        rows.append(("DNS lookup time", f"{yours.median_ms:.0f} ms"))
    return rows


# ---------------------------------------------------------------- terminal

MAX_FULL = 6  # problems shown in full; the rest get one line each


def action_plan(report: Report, n: int = 3) -> List[str]:
    """The first fix step of the top problems: a short, concrete to-do list."""
    out = []
    for f in report.findings:
        if f.severity in ("critical", "warning") and f.fix and not f.symptom and f.fix[0] not in out:
            out.append(f.fix[0])
        if len(out) == n:
            break
    return out


def _steps(steps: List[str]) -> Table:
    g = Table.grid(padding=(0, 1))
    g.add_column(no_wrap=True, style="dim")
    g.add_column()
    for i, step in enumerate(steps, 1):
        g.add_row(f"  {i}.", step)
    return g


def render_terminal(report: Report, console: Console, brief: bool = False) -> None:
    gc = GRADE_COLOR.get(report.grade, "white")
    head = Text.assemble(("Wi-Fi health  ", "bold"), (f"{report.score}/100", f"bold {gc}"),
                         ("   grade ", "dim"), (report.grade, f"bold reverse {gc}"), "\n\n", (report.summary, "italic"))
    console.print(Panel(head, title="[bold]fixmywifi[/]", border_style=gc, padding=(1, 2)))

    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(style="dim", no_wrap=True)
    t.add_column()
    for k, v in facts(report):
        t.add_row(k, v)
    if t.row_count:
        console.print(Panel(t, title="What we measured", border_style="dim"))

    problems = [f for f in report.findings if f.severity in ("critical", "warning")]
    plan = action_plan(report)
    if plan:
        g = Table.grid(padding=(0, 1))
        g.add_column(style="bold", no_wrap=True)
        g.add_column()
        for i, step in enumerate(plan, 1):
            g.add_row(f"{i}.", step)
        console.print(Panel(g, title="[bold]Do these first[/]", border_style="magenta", padding=(0, 1)))

    if brief:
        for f in problems + [f for f in report.findings if f.severity == "good"]:
            console.print(f"[{COLOR[f.severity]}]{ICON[f.severity]}[/] {f.title}")
        console.print(f"\n[dim]Run without --brief for the reasons and step-by-step fixes. ⭐ {REPO}[/]\n")
        return

    for idx, f in enumerate(problems):
        sev = f.severity
        if idx == 0 or problems[idx - 1].severity != sev:
            console.print(f"\n[bold {COLOR[sev]}]{LABEL[sev]}[/]")
        if idx >= MAX_FULL:
            console.print(f"[{COLOR[sev]}]{ICON[sev]}[/] [bold]{f.title}[/] [dim]{f.fix[0] if f.fix else ''}[/]")
            continue
        console.print(Panel(Group(Text(f.why), *([Text(), Text("How to fix it:", style="bold"), _steps(f.fix)] if f.fix else [])),
                            title=f"[{COLOR[sev]}]{ICON[sev]}[/] [bold]{f.title}[/]",
                            title_align="left", border_style=COLOR[sev], padding=(0, 1)))
    if len(problems) > MAX_FULL:
        console.print("[dim]Run with --html report.html for the full details of every item.[/]")
    tips = [f for f in report.findings if f.severity == "tip"]
    if tips:
        console.print(f"\n[bold cyan]{LABEL['tip']}[/]")
        for f in tips:
            console.print(f"[cyan]{ICON['tip']}[/] [bold]{f.title}[/] [dim]{f.why}[/]")
            for step in f.fix[:2]:
                console.print(f"   [dim]→[/] {step}")
    goods = [f for f in report.findings if f.severity == "good"]
    if goods:
        console.print(f"\n[bold green]{LABEL['good']}[/]")
        for f in goods:
            console.print(f"[green]{ICON['good']}[/] {f.title}")
    for n in report.scan.notes:
        console.print(f"[dim]ⓘ {n}[/]")
    console.print("\n[dim]No network names or addresses are shown, so this is safe to screenshot and share.[/]")
    console.print(f"[dim]Helped? A ⭐ on GitHub helps others find it: {REPO}[/]\n")


# ---------------------------------------------------------------- markdown


def render_markdown(report: Report) -> str:
    out = [f"# fixmywifi report: {report.score}/100 (grade {report.grade})", "", f"_{report.summary}_", "",
           "| | |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in facts(report)]
    plan = action_plan(report)
    if plan:
        out += ["", "## Do these first", ""] + [f"{i}. {s}" for i, s in enumerate(plan, 1)]
    for sev in ("critical", "warning", "tip"):
        items = [f for f in report.findings if f.severity == sev]
        if items:
            out += ["", f"## {LABEL[sev]}"]
            for f in items:
                out += ["", f"### {ICON[sev]} {f.title}", "", f.why]
                out += [""] + [f"{i}. {s}" for i, s in enumerate(f.fix, 1)] if f.fix else []
    goods = [f for f in report.findings if f.severity == "good"]
    if goods:
        out += ["", f"## {LABEL['good']}", ""] + [f"- ✔ {f.title}" for f in goods]
    out += ["", f"<sub>Generated by [fixmywifi]({REPO}) v{__version__} on {datetime.now():%Y-%m-%d %H:%M}</sub>", ""]
    return "\n".join(out)


# ---------------------------------------------------------------- html


def render_html(report: Report) -> str:
    e = html.escape
    gc = {"A": "#16a34a", "B": "#65a30d", "C": "#ca8a04", "D": "#dc2626", "F": "#b91c1c"}.get(report.grade, "#666")
    rows = "".join(f"<tr><th>{e(k)}</th><td>{e(v)}</td></tr>" for k, v in facts(report))
    plan = action_plan(report)
    plan_html = ("<h2>Do these first</h2><ol class='plan'>" + "".join(f"<li>{e(p)}</li>" for p in plan) + "</ol>") if plan else ""
    cards = []
    for sev in ("critical", "warning", "tip", "good"):
        items = [f for f in report.findings if f.severity == sev]
        if not items:
            continue
        cards.append(f"<h2 class='{sev}'>{e(LABEL[sev])}</h2>")
        for f in items:
            steps = "".join(f"<li>{e(s)}</li>" for s in f.fix)
            cards.append(f"<article class='card {sev}'><h3><span>{ICON[sev]}</span> {e(f.title)}</h3>"
                         f"<p>{e(f.why)}</p>{f'<ol>{steps}</ol>' if steps else ''}</article>")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Wi-Fi report</title>
<style>
:root{{--bg:#f7f7f5;--fg:#1c1c1a;--muted:#6b6b66;--card:#fff;--line:#e5e5e0}}
@media (prefers-color-scheme:dark){{:root{{--bg:#141413;--fg:#ececea;--muted:#9a9a94;--card:#1e1e1c;--line:#2e2e2b}}}}
body{{background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,-apple-system,Segoe UI,sans-serif;margin:0;padding:24px 16px}}
main{{max-width:760px;margin:auto}} .score{{display:flex;gap:20px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px}}
.grade{{font-size:48px;font-weight:800;color:#fff;background:{gc};border-radius:12px;width:84px;height:84px;display:grid;place-items:center;flex:none}}
.num{{font-size:28px;font-weight:700}} .sum{{color:var(--muted)}} table{{width:100%;border-collapse:collapse;margin:20px 0;background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden}}
th,td{{text-align:left;padding:8px 14px;border-bottom:1px solid var(--line);font-weight:400}} th{{color:var(--muted);width:40%}}
.card{{background:var(--card);border:1px solid var(--line);border-left:4px solid;border-radius:10px;padding:4px 18px;margin:12px 0}}
.critical{{border-color:#dc2626}} .warning{{border-color:#ca8a04}} .tip{{border-color:#0891b2}} .good{{border-color:#16a34a}}
h2{{border:0;margin-top:32px}} h2.critical{{color:#dc2626}} h2.warning{{color:#ca8a04}} h2.tip{{color:#0891b2}} h2.good{{color:#16a34a}}
h3{{font-size:17px}} footer{{color:var(--muted);font-size:13px;margin:32px 0}} a{{color:inherit}}
</style></head><body><main>
<div class="score"><div class="grade">{e(report.grade)}</div><div><div class="num">Wi-Fi health {report.score}/100</div>
<div class="sum">{e(report.summary)}</div></div></div>
<table>{rows}</table>{plan_html}{''.join(cards)}
<footer>Generated by <a href="{REPO}">fixmywifi</a> v{__version__} on {datetime.now():%Y-%m-%d %H:%M}. No network names or addresses included.</footer>
</main></body></html>"""


def render_json(report: Report) -> str:
    return json.dumps(report.to_dict(), indent=2)
