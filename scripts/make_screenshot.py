"""Regenerate docs/demo.svg from the demo report: python scripts/make_screenshot.py"""

import os

from rich.console import Console

from fixmywifi.demo import demo_profile, demo_scan
from fixmywifi.report import redact, render_terminal
from fixmywifi.rules import analyse

console = Console(record=True, width=96, force_terminal=True, color_system="truecolor", highlight=False, file=open(os.devnull, "w"))
render_terminal(redact(analyse(demo_scan(), demo_profile())), console, brief=True)
console.save_svg("docs/demo.svg", title="fixmywifi --brief")

from fixmywifi.report import render_markdown  # noqa: E402

with open("docs/example-report.md", "w") as fh:
    fh.write(render_markdown(redact(analyse(demo_scan(), demo_profile()))))
