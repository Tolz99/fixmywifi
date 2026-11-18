"""Rules about how the network is locked. Weak security is also a speed issue: old modes slow everyone down."""

from __future__ import annotations

from fixmywifi.models import Finding
from fixmywifi.rules import Ctx, rule


@rule
def security(ctx: Ctx):
    link = ctx.link
    if not ctx.on_wifi or not link.security:
        return None
    s = link.security
    if s == "open":
        return Finding("sec-open", "critical", "Your Wi-Fi has no password.",
                       "Anyone nearby can use your connection (and your speed) and see unencrypted traffic.",
                       ["Set WPA2/WPA3 security with a long password in the router settings."], category="security")
    if s in ("wep", "wpa"):
        return Finding("sec-broken", "critical", f"Your Wi-Fi uses {s.upper()}, which can be cracked in minutes.",
                       "This security mode was broken years ago. It also forces the router into a slow legacy mode "
                       "(54 Mbps max for those connections).",
                       ["Switch to WPA2-Personal (AES), or WPA2/WPA3 if available, and choose a new password."],
                       category="security")
    if s == "wpa/wpa2":
        return Finding("sec-mixed", "warning", "Your router allows the old WPA/TKIP mode alongside WPA2.",
                       "Mixed mode keeps a broken cipher (TKIP) alive, and any device that uses it is capped at "
                       "54 Mbps. Some routers slow the whole network down to cope.",
                       ["Change security to 'WPA2-Personal (AES)' only, or 'WPA2/WPA3' if offered."], category="security")
    if s == "wpa2":
        return Finding("sec-wpa2", "tip", "You're on WPA2. Fine, but WPA3 is better if your router has it.",
                       "WPA3 protects against password-guessing attacks. 'WPA2/WPA3 transition' mode keeps older devices working.",
                       ["If the router offers WPA2/WPA3 (transition) mode, switch to it."], category="security")
    if s in ("wpa3", "wpa2/wpa3"):
        return Finding("sec-good", "good", "Your Wi-Fi security is up to date.", f"Using {s.upper()}.", category="security")
    return None
