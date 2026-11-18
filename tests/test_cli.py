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
