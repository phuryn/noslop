"""HTTP helpers for the wider judge panel (OpenRouter chat) and the decision-model scorers.

Keys come from environment variables; if one is missing, a `.env` file at the repository root is read
as a fallback (never printed or logged): OPENROUTER_API_KEY, OPENAI_API_KEY, PERPLEXITY_API_KEY, SAGE_API_KEY.
"""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from common import ROOT

_ENV_FILES = [ROOT.parent / ".env"]   # optional fallback: a .env at the repository root (gitignored)
_lock = threading.Lock()
SPEND_LOG = ROOT / "scores" / "panel_spend.jsonl"


def key(name):
    v = os.environ.get(name)
    if v:
        return v
    for p in _ENV_FILES:
        if p.exists():
            for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                m = re.match(rf"\s*{name}\s*=\s*\"?([^\"\s]+)\"?", line)
                if m:
                    return m.group(1)
    raise SystemExit(f"Set {name}")


def post(url, body, headers, timeout=300):
    req = urllib.request.Request(url, method="POST", data=json.dumps(body).encode(), headers=headers)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"ok": True, "ms": int((time.time() - t0) * 1000), "d": json.load(r)}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "ms": int((time.time() - t0) * 1000),
                "error": f"HTTP {e.code} {e.read().decode('utf-8', 'replace')[:300]}"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "status": None, "ms": int((time.time() - t0) * 1000), "error": repr(exc)[:300]}


def log_spend(rec):
    with _lock:
        SPEND_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(SPEND_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")


def total_spend():
    if not SPEND_LOG.exists():
        return 0.0
    tot = 0.0
    for line in SPEND_LOG.read_text(encoding="utf-8").splitlines():
        try:
            tot += float(json.loads(line).get("cost") or 0)
        except Exception:  # noqa: BLE001
            pass
    return tot


OR_HDR = lambda: {"Authorization": "Bearer " + key("OPENROUTER_API_KEY"), "Content-Type": "application/json",
                  "X-Title": "work-humanizer judge panel"}
OR_CHAT = "https://openrouter.ai/api/v1/chat/completions"
OR_DEC = "https://openrouter.ai/api/v1/systemone"
