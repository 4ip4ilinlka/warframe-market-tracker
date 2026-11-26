"""Static checks: the program talks only to the allowed hosts and loads nothing from CDNs."""
import re
from pathlib import Path

from wfmt.config import ALLOWED_HOSTS

PKG = Path(__file__).resolve().parent.parent / "wfmt"
SOURCES = [p for p in PKG.rglob("*") if p.suffix in {".py", ".html", ".js", ".css"}]
URL_RE = re.compile(r"""https?://([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*)""")
LOCAL = {"127.0.0.1", "localhost", "www.w3.org"}  # w3.org: SVG namespace string, never fetched


def test_sources_found():
    assert any(p.name == "app.js" for p in SOURCES)
    assert any(p.name == "http.py" for p in SOURCES)


def test_no_foreign_hosts_in_source():
    bad = []
    for p in SOURCES:
        for host in URL_RE.findall(p.read_text(encoding="utf-8")):
            host = host.lower()
            if host not in ALLOWED_HOSTS and host not in LOCAL:
                bad.append(f"{p.name}: {host}")
    assert bad == []


def test_no_cdn_in_static():
    for p in (PKG / "static").iterdir():
        text = p.read_text(encoding="utf-8")
        assert not re.search(r"<script[^>]+src=[\"']https?:", text), p.name
        assert not re.search(r"<link[^>]+href=[\"']https?:", text), p.name
        assert "@import" not in text, p.name


def test_no_telemetry_imports():
    banned = ("sentry", "analytics", "telemetry", "mixpanel", "segment", "requests", "urllib.request")
    for p in PKG.rglob("*.py"):
        for line in p.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith(("import ", "from ")):
                assert not any(b in s for b in banned), f"{p.name}: {s}"


def test_game_memory_never_writes():
    src = (PKG / "game_memory.py").read_text(encoding="utf-8")
    for forbidden in ("WriteProcessMemory", "VirtualAllocEx", "CreateRemoteThread", "PROCESS_ALL_ACCESS", "VirtualProtectEx"):
        assert forbidden not in src
