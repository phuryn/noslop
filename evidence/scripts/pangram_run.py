"""Primary detector: Pangram (pangram-4) via the REST API. Key: environment variable PANGRAM_API_KEY
(never printed or logged).

python scripts/pangram_run.py --estimate      # print the plan and estimated credits, spend nothing
python scripts/pangram_run.py --run [--pri N]  # score in priority order (up to priority N) until the hard cap

Budget rules used in the published run: hard cap 600 credits; one call per text,
no retries on scored texts; log credits per call. Billing per Pangram docs: one billable unit
per started 100-word block per text (Pangram 4), minimum one. The API exposes no balance
endpoint (checked docs + /models response headers), so spend is tracked here:
scores/pangram_log.csv (one row per call, cumulative credits) and scores/pangram/<key>.json.
"""
import csv
import json
import math
import re
import sys
import time
import urllib.error
import urllib.request

from common import REPO, ROOT, read, write

CAP = 600
BASE = "https://text.external-api.pangram.com"
OUT = ROOT / "scores" / "pangram"
LOG = ROOT / "scores" / "pangram_log.csv"
MODEL = "pangram-4"


def key():
    import os
    k = os.environ.get("PANGRAM_API_KEY")
    if not k:
        raise SystemExit("Set the PANGRAM_API_KEY environment variable")
    return k


def prep(text):
    """Light markdown strip, identical for every text: bold markers and heading hashes."""
    t = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text)
    t = re.sub(r"(?m)^#+\s*", "", t)
    return t.strip()


def units(text):
    return max(1, math.ceil(len(text.split()) / 100))


def plan():
    items = []
    t3m = ROOT / "track3" / "manifest.json"   # Track 3 texts are not shipped: build them with run_track3.py
    t3 = json.loads(read(t3m)) if t3m.exists() else []
    # priority 1: Track 3, every variant (the provenance test)
    for v in ["H", "D", "E", "A", "B2", "C", "A-notes", "B2-notes", "A-ask", "B2-ask", "B2-int", "A-int"]:
        for r in t3:
            items.append((1, f"track3/{v}", ROOT / "track3" / v / r["file"]))
    # priority 2: Track 1 originals + A / B2 / C
    man = json.loads(read(ROOT / "inputs" / "manifest.json"))
    for arm in ["O", "E", "A", "B2", "C"]:
        for r in man:
            p = ROOT / "inputs" / r["file"] if arm == "O" else ROOT / "outputs" / arm / r["file"]
            if p.exists():  # E has no output for the 30-word Slack text (API minimum is 40 words)
                items.append((2, f"t1/{arm}", p))
    for r in man:  # Emulate as a writer (/write), same requests as the AI drafts
        items.append((2, "gen/E-write", ROOT / "gen" / "E-write" / r["file"]))
    # priority 4: detector evaluation set (decision models vs Pangram): known-human excerpts not already
    # scored as Track 3 H, and the AI drafts of both held-out sets
    t3h = {read(p).strip() for p in (ROOT / "track3" / "H").glob("*.md")} if (ROOT / "track3" / "H").exists() else set()
    for p in sorted((ROOT / "human").glob("*.md")) if (ROOT / "human").exists() else []:
        if read(p).strip() not in t3h:
            items.append((4, "human", p))
    for sub in ("holdout", "holdout2"):
        for p in sorted((ROOT / sub / "inputs").glob("*.md")):
            items.append((4, f"{sub}/O", p))
    # priority 5: work-humanizer v5 on the 16 test texts (run only after v5 was adopted; cap 60 credits)
    for r in man:
        p = ROOT / "outputs" / "B5" / r["file"]
        if p.exists():
            items.append((5, "t1/B5", p))
    # priority 3 (only if budget remains): the final skill version and v1 on Track 1
    for arm in ["B3", "B"]:
        for r in man:
            items.append((3, f"t1/{arm}", ROOT / "outputs" / arm / r["file"]))
    return items


def done_keys(retry=()):
    """Scored texts, plus texts whose call failed after it may have been billed (never auto-retried;
    pass --retry KEY to try one again on purpose)."""
    keys = {p.stem for p in OUT.glob("*.json")}
    if LOG.exists():
        keys |= {r["key"] for r in csv.DictReader(open(LOG, encoding="utf-8"))
                 if r["stage"].startswith(("TIMEOUT", "ERROR")) and r["key"] not in retry}
    return keys


def k_of(group, path):
    return (group + "__" + path.name).replace("/", "_").replace(".md", "")


def spent():
    if not LOG.exists():
        return 0
    rows = list(csv.DictReader(open(LOG, encoding="utf-8")))
    return sum(int(r["units_billed_est"]) for r in rows)


def http(method, url, k, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"x-api-key": k, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def score_one(k, text):
    task = http("POST", f"{BASE}/task", k, {"text": text, "model": MODEL})
    tid = task["task_id"]
    for _ in range(90):
        time.sleep(2)
        res = http("GET", f"{BASE}/task/{tid}", k)
        if res.get("stage") in ("STAGE_SUCCESS", "STAGE_FAILED"):
            return res
    raise RuntimeError(f"task {tid} did not finish")


def main(run, max_pri=3, retry=()):
    items = [it for it in plan() if it[0] <= max_pri and (it[0] == max_pri or max_pri < 5)]
    done = done_keys(retry)
    already = spent()
    budget = CAP - already
    todo, est = [], 0
    for pri, group, path in items:
        kk = k_of(group, path)
        if kk in done:
            continue
        u = units(prep(read(path)))
        if est + u > budget:
            break
        todo.append((pri, group, path, kk, u))
        est += u
    by_pri = {}
    for pri, *_rest, u in todo:
        by_pri[pri] = by_pri.get(pri, 0) + u
    print(f"already spent (logged): {already}; cap {CAP}; this run: {len(todo)} texts, est {est} credits; by priority {by_pri}")
    skipped = [(g, p.name) for pri, g, p in items if k_of(g, p) not in done and k_of(g, p) not in {t[3] for t in todo}]
    if skipped:
        print(f"not scheduled (cap): {len(skipped)} texts, first: {skipped[:3]}")
    if not run:
        return
    k = key()
    new = not LOG.exists()
    with open(LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["key", "group", "file", "words", "units_billed_est", "cumulative_est", "stage",
                        "version", "prediction_short", "fraction_ai", "fraction_ai_assisted", "fraction_human",
                        "pangram_word_count"])
        cum = already
        for pri, group, path, kk, u in todo:
            text = prep(read(path))
            try:
                res = score_one(k, text)
            except urllib.error.HTTPError as e:
                print(f"HTTP {e.code} on {kk}; stopping (no retries)")
                break
            except Exception as e:  # timeout etc.: the POST may have been billed, so count it and move on
                cum += u
                w.writerow([kk, group, path.name, len(text.split()), u, cum, f"ERROR {type(e).__name__} (billing unknown, counted)",
                            "", "", "", "", "", ""])
                f.flush()
                print(f"{cum:4d} {group:16} {path.name:40} ERROR {type(e).__name__}; counted, not retried", flush=True)
                continue
            cum += u
            res.pop("text", None)
            for wdw in res.get("windows", []):
                wdw.pop("text", None)
            write(OUT / f"{kk}.json", json.dumps(res, indent=2))
            pwc = sum(x.get("word_count", 0) for x in res.get("windows", []))
            w.writerow([kk, group, path.name, len(text.split()), u, cum, res.get("stage"), res.get("version"),
                        res.get("prediction_short"), res.get("fraction_ai"), res.get("fraction_ai_assisted"),
                        res.get("fraction_human"), pwc])
            f.flush()
            print(f"{cum:4d} {group:16} {path.name:40} {res.get('prediction_short')} "
                  f"ai={res.get('fraction_ai')} assisted={res.get('fraction_ai_assisted')} human={res.get('fraction_human')}",
                  flush=True)


if __name__ == "__main__":
    mp = int(sys.argv[sys.argv.index("--pri") + 1]) if "--pri" in sys.argv else 3
    rt = (sys.argv[sys.argv.index("--retry") + 1],) if "--retry" in sys.argv else ()
    main("--run" in sys.argv, mp, rt)
