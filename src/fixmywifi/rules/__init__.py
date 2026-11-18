"""The rule engine.

A rule is a function that looks at what we measured (`ctx.scan`) and what the person told us
(`ctx.profile`) and returns a Finding, a list of Findings, or None. Register it with @rule.

Adding a rule is the easiest way to contribute: see CONTRIBUTING.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

from fixmywifi.models import Finding, Profile, Report, Scan

RULES: List[Callable] = []
SEVERITY_ORDER = {"critical": 0, "warning": 1, "tip": 2, "good": 3}
CATEGORY_ORDER = {"wifi": 0, "internet": 1, "security": 2, "home": 3, "hardware": 4}
PENALTY = {"critical": 18, "warning": 8, "tip": 1.5, "good": 0}
DECAY = 0.8  # each extra problem costs a bit less, so one bad home doesn't hit zero


def rule(fn: Callable) -> Callable:
    RULES.append(fn)
    return fn


@dataclass
class Ctx:
    scan: Scan
    profile: Profile

    @property
    def link(self):
        return self.scan.link

    @property
    def on_wifi(self) -> bool:
        return self.scan.link is not None and not self.scan.wired

    @property
    def rssi(self) -> Optional[int]:
        return self.scan.link.rssi_dbm if self.scan.link else None

    @property
    def plan(self) -> Optional[int]:
        return self.profile.plan_mbps

    def uses(self, *names: str) -> bool:
        return any(n in self.profile.uses for n in names)


def _grade(score: int) -> str:
    for limit, g in ((90, "A"), (75, "B"), (60, "C"), (40, "D")):
        if score >= limit:
            return g
    return "F"


def analyse(scan: Scan, profile: Profile) -> Report:
    # Import the rule modules so their @rule decorators run.
    from fixmywifi.rules import home, internet, security, wifi  # noqa: F401

    ctx = Ctx(scan, profile)
    findings: List[Finding] = []
    seen = set()
    for fn in RULES:
        try:
            out = fn(ctx)
        except Exception as e:  # one broken rule must never hide the others
            out = Finding(id=f"rule-error-{fn.__name__}", severity="tip",
                          title=f"Internal check '{fn.__name__}' failed",
                          why=f"{type(e).__name__}: {e}. Please report this on GitHub.", category="hardware")
        for f in (out if isinstance(out, list) else [out]):
            if f and f.id not in seen:
                seen.add(f.id)
                findings.append(f)
    # Same severity: free settings changes (radio, internet, security) before buying or moving things.
    findings.sort(key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), CATEGORY_ORDER.get(f.category, 9)))
    penalties = sorted((PENALTY.get(f.severity, 0) for f in findings), reverse=True)
    score = max(5, round(100 - sum(p * DECAY ** i for i, p in enumerate(penalties))))
    problems = [f for f in findings if f.severity in ("critical", "warning")]
    if not problems:
        summary = "Your Wi-Fi looks healthy. Nothing big to fix."
    elif len(problems) == 1:
        summary = f"One thing is holding you back: {problems[0].title.rstrip('.')}."
    else:
        summary = f"{len(problems)} things are holding you back. Biggest one: {problems[0].title.rstrip('.')}."
    return Report(scan=scan, profile=profile, findings=findings, score=score, grade=_grade(score), summary=summary)
