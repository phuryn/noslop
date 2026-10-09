"""Track 1: pure rewrite. python scripts/run_track1.py A B C   (any subset of arms; B2 = current skill/)

Writes outputs/<arm>/<file> (final text) and outputs/<arm>/raw/<file> (full reply).
Skips work already done, so it is safe to rerun.
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor

from common import DATA, ROOT, build_prompt, extract, read, run_claude, write

MANIFEST = json.loads(read(DATA / "inputs" / "manifest.json"))


def job(arm, rec):
    out = DATA / "outputs" / arm / rec["file"]
    if out.exists():
        return f"skip {arm} {rec['file']}"
    text = read(DATA / "inputs" / rec["file"])
    prompt = build_prompt(arm, text, mode="rewrite")
    for attempt in range(2):
        reply = run_claude(prompt, model="sonnet", tag=f"t1-{arm}-{rec['id']}")
        final = extract("final", reply)
        if final:
            break
    write(DATA / "outputs" / arm / "raw" / rec["file"], reply)
    write(out, (final or reply).strip() + "\n")
    return f"{'ok' if final else 'NO-FINAL'} {arm} {rec['file']}"


if __name__ == "__main__":
    arms = sys.argv[1:] or ["A", "B", "C"]
    jobs = [(a, r) for r in MANIFEST for a in arms]
    with ThreadPoolExecutor(6) as ex:
        for msg in ex.map(lambda j: job(*j), jobs):
            print(msg, flush=True)
