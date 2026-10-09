"""Shared helpers for the work-humanizer evidence run. Stdlib only.

Every model call goes through run_claude / run_codex so the isolation flags are
identical for every arm. Calls run from an empty scratch directory (NEUTRAL) so
no CLAUDE.md / AGENTS.md from the repo reaches the model. Every call is logged to
scores/calls.jsonl with its cost (claude: list-price USD from --output-format
json; codex: tokens reported by the CLI).
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # evidence/
REPO = ROOT.parent                                      # repository root
# HUMANIZER_SET=holdout points inputs/outputs/scores at the held-out set (holdout/...)
DATA = ROOT / os.environ["HUMANIZER_SET"] if os.environ.get("HUMANIZER_SET") else ROOT
NEUTRAL = Path(os.environ.get("HUMANIZER_NEUTRAL_DIR",
               Path(tempfile.gettempdir()) / "humanizer-neutral"))
NEUTRAL.mkdir(parents=True, exist_ok=True)
CALL_LOG = ROOT / "scores" / "calls.jsonl"
CALL_LOG.parent.mkdir(parents=True, exist_ok=True)
_lock = threading.Lock()

CLAUDE = shutil.which("claude") or "claude"
CODEX = shutil.which("codex.cmd") or shutil.which("codex") or "codex"
SYSTEM = "You are a helpful writing assistant."


def _log(rec):
    with _lock:
        with open(CALL_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def run_claude(prompt, model="sonnet", tag="", system=SYSTEM, retries=3, timeout=900, effort=None):
    """One fresh, isolated Claude call. Returns the result text."""
    cmd = [CLAUDE, "-p", "--model", model, "--safe-mode", "--tools", "",
           "--system-prompt", system, "--no-session-persistence", "--output-format", "json"]
    if effort:
        cmd += ["--effort", effort]
    last_err = None
    for attempt in range(retries):
        t0 = time.time()
        try:
            p = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                               encoding="utf-8", cwd=str(NEUTRAL), timeout=timeout)
            d = json.loads(p.stdout)
            if d.get("is_error"):
                raise RuntimeError(str(d.get("result"))[:300])
            _log({"tool": "claude", "model": model, "tag": tag, "secs": round(time.time() - t0, 1),
                  "cost_usd": d.get("total_cost_usd"), "usage": d.get("modelUsage")})
            return d["result"]
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"claude call failed ({tag}): {last_err}")


def run_codex(prompt, tag="", effort="high", retries=3, timeout=1200):
    """One fresh, ephemeral Codex call (read-only sandbox). Returns the last message."""
    last_err = None
    for attempt in range(retries):
        t0 = time.time()
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "last.txt"
            cmd = [CODEX, "exec", "--skip-git-repo-check", "--ephemeral", "-s", "read-only",
                   "-c", f'model_reasoning_effort="{effort}"', "-o", str(out), "-"]
            try:
                p = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                                   encoding="utf-8", cwd=str(NEUTRAL), timeout=timeout)
                text = out.read_text(encoding="utf-8") if out.exists() else ""
                if not text.strip():
                    raise RuntimeError((p.stderr or p.stdout)[-400:])
                m = re.search(r"tokens used\s*\n\s*([\d,]+)", p.stdout + p.stderr)
                _log({"tool": "codex", "tag": tag, "secs": round(time.time() - t0, 1),
                      "effort": effort, "tokens": int(m.group(1).replace(",", "")) if m else None})
                return text
            except Exception as e:  # noqa: BLE001
                last_err = e
                time.sleep(15 * (attempt + 1))
    raise RuntimeError(f"codex call failed ({tag}): {last_err}")


def extract(tag, text):
    """Content of the LAST <tag>...</tag> block, or None."""
    blocks = re.findall(rf"<{tag}>(.*?)</{tag}>", text, re.S)
    return blocks[-1].strip() if blocks else None


def parse_json(text):
    """First JSON object or array in a model reply."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1)
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise ValueError("no JSON in reply")
    dec = json.JSONDecoder()
    obj, _ = dec.raw_decode(text[start:])
    return obj


def read(p):
    return Path(p).read_text(encoding="utf-8")


def write(p, s):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")


# ---- skill texts for the arms -------------------------------------------------

def skill_text(arm):
    if arm == "A":
        p = ROOT / "blader" / "SKILL.md"
        if not p.exists():
            raise SystemExit("Arm A needs blader/humanizer's SKILL.md: run python scripts/fetch_blader.py")
        return read(p)
    if arm in ("B", "B2", "B3", "B4a", "B4b", "B4", "B5", "B5I", "WORK_HUMANIZER"):
        # B = v1, B2 = v2, B3 = v3, B5 = v5 (the version scored on every set), B5I = v5i (reasoning-first
        # interview), all frozen in skill-versions/. WORK_HUMANIZER = the current published skill (skills/work-humanizer).
        # v4 (B4a/B4b/B4) was tried and not adopted; its text is described in evidence/README.md.
        if arm in ("B4a", "B4b", "B4"):
            raise SystemExit("v4 was not published; see evidence/README.md")
        d = {"B": ROOT / "skill-versions" / "v1", "B2": ROOT / "skill-versions" / "v2",
             "B3": ROOT / "skill-versions" / "v3", "B5": ROOT / "skill-versions" / "v5",
             "B5I": ROOT / "skill-versions" / "v5i", "WORK_HUMANIZER": REPO / "skills" / "work-humanizer"}[arm]
        return read(d / "SKILL.md") + "\n\n---\n\n# Supporting file: tells.md\n\n" + read(d / "tells.md")
    raise ValueError(arm)


def build_prompt(arm, text, mode="rewrite", qa=None, notes=None, user_says=None):
    """The ONE wrapper used for every arm. Only the skill text differs.

    mode="rewrite": user cannot answer questions (Track 1).
    mode="interactive": the writer can answer one round of questions (Tracks 2-3).
    qa: list of (questions_text, answers_text) already exchanged.
    notes: writer-supplied material given up front (Track 3 'notes' cell).
    user_says: overrides the user's one-line request (Track 3 'ask' cell: the user asks to be interviewed).
    """
    if arm == "V6A":   # the one-liner arm: the bare prompt plus one clause
        head = f'The user says: "{user_says or "Rewrite this to sound human, without changing the meaning."}"\n\n'
    elif arm == "C":
        head = f'The user says: "{user_says or "Rewrite this to sound human."}"\n\n'
    else:
        head = ("You have the following skill installed. Use it for this request.\n\n"
                f"<skill>\n{skill_text(arm)}\n</skill>\n\n"
                f'The user says: "{user_says or "Humanize this text."}"\n\n')
    body = f"<text>\n{text}\n</text>\n\n"
    if notes:
        body += ("The writer also sent these notes, in their own words:\n\n"
                 f"<writer_notes>\n{notes}\n</writer_notes>\n\n")
    if mode == "rewrite":
        tail = ("The user is not available to answer questions in this session, so do not ask any. "
                "Do the work however your instructions say, then end your reply with the final text only, "
                "between <final> and </final>.")
    else:
        if qa:
            convo = "".join(f"<your_questions>\n{q}\n</your_questions>\n\n<writer_answers>\n{a}\n</writer_answers>\n\n"
                            for q, a in qa)
            body += ("Earlier you asked the writer questions. Here is the exchange:\n\n" + convo)
            tail = ("No more questions are possible. Do the work however your instructions say, then end your "
                    "reply with the final text only, between <final> and </final>.")
        else:
            tail = ("The writer is available and will answer ONE round of questions if you ask. "
                    "Ask only if your instructions call for it. If you ask, end your reply with only the "
                    "questions, between <questions> and </questions>. Otherwise do the work however your "
                    "instructions say and end your reply with the final text only, between <final> and </final>.")
    return head + body + tail
