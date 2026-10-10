"""Brief to email: the common case, where a person types bullets and asks AI to write the email.

Same brief (brief-to-email/brief.txt) to five arms, 3 runs each: Claude with no skill, Claude + "Make it sound human.",
blader/humanizer, work-humanizer (all Claude Sonnet, same isolation flags as every other run), and Emulate-1 /v1/write
(130 words). Outputs go to brief-to-email/out/. Needs scripts/fetch_blader.py run first and EMULATE_API_KEY set.

  python scripts/run_brief_to_email.py
"""
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

import common
import run_emulate
from common import ROOT, read

HERE = ROOT / "brief-to-email"
BRIEF = read(HERE / "brief.txt").strip()
TAIL = ("\n\nThe user is not available to answer questions in this session, so do not ask any. Do the work however your "
        "instructions say, then end your reply with the final text only, between <final> and </final>.")


def with_skill(text):
    return f"You have the following skill installed. Use it for this request.\n\n<skill>\n{text}\n</skill>\n\nThe user says:\n\n"


ARMS = {
    "plain": lambda: BRIEF + TAIL,
    "human": lambda: BRIEF + "\nMake it sound human." + TAIL,
    "blader": lambda: with_skill(common.skill_text("A")) + BRIEF + TAIL,
    "wh": lambda: with_skill(common.skill_text("WORK_HUMANIZER")) + BRIEF + TAIL,
}


def run(job):
    arm, i = job
    path = HERE / "out" / f"{arm}-{i}.json"
    if path.exists():
        return arm, i, "cached"
    if arm == "emulate":
        res = run_emulate.call(run_emulate.key(), None, url=run_emulate.WRITE_URL, body={"prompt": BRIEF, "words": 130})
        out = {"arm": arm, "run": i, "final": (res.get("text") or "").strip(),
               "meta": {k: v for k, v in res.items() if k != "text"}}
    else:
        raw = common.run_claude(ARMS[arm](), model="sonnet", tag=f"brief-{arm}-{i}")
        m = re.search(r"<final>\s*(.*?)\s*</final>", raw, re.S)
        out = {"arm": arm, "run": i, "final": m.group(1).strip() if m else raw.strip(), "raw": raw}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return arm, i, len(out["final"].split())


if __name__ == "__main__":
    jobs = [(a, i) for a in ["plain", "human", "blader", "wh", "emulate"] for i in (1, 2, 3)]
    with ThreadPoolExecutor(6) as ex:
        for r in ex.map(run, jobs):
            print(r, flush=True)
