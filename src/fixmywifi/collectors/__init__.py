"""Read Wi-Fi details from the operating system. Read-only: nothing here changes any setting."""

from __future__ import annotations

import platform
import subprocess
from typing import List, Optional, Sequence, Tuple

from fixmywifi.models import Network, WifiLink


def run(cmd: Sequence[str], timeout: float = 20) -> str:
    """Run a command and return its output, or "" if it is missing or fails."""
    try:
        out = subprocess.run(list(cmd), capture_output=True, text=True, timeout=timeout,
                             errors="replace")
        return out.stdout or ""
    except (OSError, subprocess.SubprocessError):
        return ""


def current_platform() -> str:
    s = platform.system()
    return {"Darwin": "macos", "Linux": "linux", "Windows": "windows"}.get(s, s.lower())


def collect_wifi() -> Tuple[Optional[WifiLink], List[Network], List[str]]:
    """Return (your connection, nearby networks, notes about anything we couldn't read)."""
    p = current_platform()
    if p == "macos":
        from fixmywifi.collectors import macos as mod
    elif p == "linux":
        from fixmywifi.collectors import linux as mod
    elif p == "windows":
        from fixmywifi.collectors import windows as mod
    else:
        return None, [], [f"Wi-Fi scanning isn't supported on {platform.system()} yet. PRs welcome!"]
    try:
        return mod.collect()
    except Exception as e:  # never crash the whole run because one OS tool changed its output
        return None, [], [f"Couldn't read Wi-Fi details ({type(e).__name__}: {e}). Please open an issue."]
