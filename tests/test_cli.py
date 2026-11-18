import json

from fixmywifi.cli import main


def test_demo_runs(capsys):
    assert main(["--demo"]) == 0
    out = capsys.readouterr().out
    assert "Wi-Fi health" in out and "Do these first" in out


def test_demo_exports(tmp_path, capsys):
    html, md = tmp_path / "r.html", tmp_path / "r.md"
    assert main(["--demo", "--html", str(html), "--markdown", str(md)]) == 0
    assert "<html" in html.read_text() and "Do these first" in md.read_text()
    assert "Smith-Family" not in html.read_text() and "a4:2b" not in html.read_text()  # redacted by default


def test_demo_json(capsys):
    assert main(["--demo", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["grade"] in "ABCDF" and data["scan"]["link"]["ssid"] == "(hidden)"
    assert data["scan"]["speed"]["bufferbloat_grade"]


def test_answers_file(tmp_path):
    from fixmywifi.questionnaire import load
    p = tmp_path / "a.json"
    p.write_text(json.dumps({"size_sqm": 120, "walls": "brick", "unknown_key": 1}))
    prof = load(str(p))
    assert prof.size_sqm == 120 and prof.walls == "brick"


def test_shared_reports_leak_no_local_addresses(capsys):
    import re

    from fixmywifi.demo import demo_profile, demo_scan
    from fixmywifi.models import Router
    from fixmywifi.report import redact, render_json, render_markdown
    from fixmywifi.rules import analyse

    scan = demo_scan()
    scan.router = Router(manufacturer="[bold]x[/] | y", model="M", friendly_name="Smith House Router")
    rep = redact(analyse(scan, demo_profile()))
    out = render_json(rep) + render_markdown(rep)
    assert not re.search(r"\b(192\.168|10\.\d+|172\.(1[6-9]|2\d|3[01]))\.\d+\.\d+\b", out)
    assert not re.search(r"([0-9a-f]{2}:){5}[0-9a-f]{2}", out, re.I)
    assert "Smith House" not in out and "\\| y" in render_markdown(rep)
