"""Command line entry point: `fixmywifi`."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from typing import List, Optional

from rich.console import Console

from fixmywifi import __version__
from fixmywifi.collectors import collect_wifi, current_platform
from fixmywifi.models import Profile, Scan
from fixmywifi.report import redact, render_html, render_json, render_markdown, render_terminal
from fixmywifi.rules import analyse

VPN_PREFIXES = ("utun", "tun", "tap", "wg", "ppp", "ipsec", "tailscale", "zt")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fixmywifi", description="Find out why your Wi-Fi is slow and exactly how to fix it.")
    p.add_argument("--rooms", action="store_true", help="walk test: measure Wi-Fi room by room and find dead zones")
    p.add_argument("-q", "--quick", action="store_true", help="skip the questions about your home")
    p.add_argument("--answers", metavar="FILE", help="read your answers from a JSON file instead of asking")
    p.add_argument("--no-speedtest", action="store_true", help="skip the download/upload/bufferbloat test (~20 s)")
    p.add_argument("--save", action="store_true", help="save HTML and JSON reports in the current folder")
    p.add_argument("--html", metavar="FILE", help="write a shareable HTML report")
    p.add_argument("--markdown", metavar="FILE", help="write a Markdown report (great for GitHub issues and Reddit)")
    p.add_argument("--brief", action="store_true", help="short report: score, to-do list and one line per problem")
    p.add_argument("--json", action="store_true", help="print the raw results as JSON instead of the report")
    p.add_argument("--show-names", action="store_true", help="include network names and addresses in exported files")
    p.add_argument("--demo", action="store_true", help="show an example report using made-up data")
    p.add_argument("--version", action="version", version=f"fixmywifi {__version__}")
    return p


def scan(console: Console, speedtest: bool = True) -> Scan:
    from fixmywifi import nettests as nt

    s = Scan(platform=current_platform())
    with console.status("[bold]Reading your Wi-Fi connection…[/]") as st:
        s.link, s.nearby, s.notes = collect_wifi()
        s.gateway_ip, route_iface = nt.default_gateway()
        if s.link is None and s.gateway_ip:
            s.wired = True
        elif s.link and route_iface and s.link.interface and route_iface != s.link.interface \
                and not route_iface.startswith(VPN_PREFIXES) and s.platform != "windows":
            s.wired = True
        if s.link is None and not s.gateway_ip:
            s.notes.append("No network connection found.")

        st.update("[bold]Asking your router who it is…[/]")
        s.router = nt.identify_router(s.gateway_ip)
        st.update("[bold]Checking the connection to your router…[/] (5 s)")
        s.gateway_ping = nt.ping(s.gateway_ip)
        st.update("[bold]Checking the connection to the internet…[/] (5 s)")
        s.internet_ping = nt.ping(nt.INTERNET_HOST)
        st.update("[bold]Timing DNS lookups…[/]")
        s.dns = nt.dns_benchmark()
        s.lan_devices = nt.lan_devices(s.gateway_ip)
        if speedtest:
            st.update("[bold]Running speed + lag test with Cloudflare…[/] (~15 s)")
            s.speed = nt.speed_test()
            if s.speed.error:
                s.notes.append(s.speed.error)
    return s


def _write(path: str, text: str, console: Console) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    console.print(f"[green]Saved[/] {path}")


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    console = Console(stderr=args.json, highlight=False)

    if args.rooms:
        from fixmywifi.rooms import walk
        try:
            return walk(console)
        except (KeyboardInterrupt, EOFError):
            return 130

    if args.demo:
        from fixmywifi.demo import demo_profile, demo_scan
        s, profile = demo_scan(), demo_profile()
        console.print("[dim]Demo mode: this is a made-up home, not your network.[/]")
    else:
        console.print(f"[bold]fixmywifi[/] {__version__}: let's find out what's up with your Wi-Fi.")
        if args.answers:
            from fixmywifi.questionnaire import load
            profile = load(args.answers)
        elif args.quick or args.json or not sys.stdin.isatty():
            profile = Profile()
        else:
            from fixmywifi.questionnaire import ask
            try:
                profile = ask(console)
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Skipping the rest of the questions.[/]")
                profile = Profile()
        console.print()
        try:
            s = scan(console, speedtest=not args.no_speedtest)
        except KeyboardInterrupt:
            console.print("\n[red]Stopped.[/]")
            return 130

    report = analyse(s, profile)
    shared = report if args.show_names else redact(report)

    if args.json:
        print(render_json(shared))
    else:
        render_terminal(redact(report), console, brief=args.brief)

    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    if args.save:
        args.html = args.html or f"fixmywifi-{stamp}.html"
        _write(f"fixmywifi-{stamp}.json", render_json(shared), console)
    if args.html:
        _write(args.html, render_html(shared), console)
    if args.markdown:
        _write(args.markdown, render_markdown(shared), console)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
