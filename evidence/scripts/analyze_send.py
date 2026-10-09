"""Pre-registered informed send: pick counts per arm per judge, pooled, and v5-vs-each pairwise from picks.

python scripts/analyze_send.py RUN [--set holdout3]   (env HUMANIZER_SET works too)
Per text and judge, an arm "beats" another if it got more picks across the random orders; equal = tie.
"""
import json
import sys
from collections import Counter, defaultdict

from common import DATA

PANEL = ["grok", "deepseek", "qwen", "codex"]
import os
V5 = os.environ.get("SEND_V5", "B5")          # e.g. track2/B5-int for the interview comparison
BL = os.environ.get("SEND_BLADER", "A")       # e.g. track2/A-int
ARMS = [V5, BL, "C", "E", "none"]
NAMES = {V5: "work-humanizer v5" + (" (interview)" if "int" in V5 else ""), BL: "blader", "C": "bare prompt", "E": "Emulate-1", "none": "none"}


seen = defaultdict(set)


def load(run, judge):
    per = defaultdict(list)
    for p in sorted((DATA / "scores" / "judges" / run / judge / "send").glob("*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        per[p.name[:2]].append(r["picked_arm"])
        seen[p.name[:2]].update(r["label_to_arm"].values())
    return per


def main(run):
    out = {}
    pooled_counts = Counter(); pooled_n = 0
    pooled_pw = defaultdict(lambda: [0, 0, 0])
    for j in PANEL + ["opus"]:
        per = load(run, j)
        picks = [a for v in per.values() for a in v]
        if not picks:
            continue
        c = Counter(picks)
        pw = {}
        for x in (BL, "C", "E"):
            w = t = l = 0
            for tid, v in per.items():
                if x == "E" and "E" not in seen.get(tid, set()):
                    continue   # no Emulate output for this text (under its 40-word minimum)
                cx, cy = v.count(V5), v.count(x)
                w += cx > cy; l += cx < cy; t += cx == cy
            key = f"v5>{NAMES[x]}"
            pw[key] = [w, t, l]
            if j in PANEL:
                for i in range(3):
                    pooled_pw[key][i] += pw[key][i]
        out[j] = {"n": len(picks), "texts": len(per), "picks": {a: c.get(a, 0) for a in ARMS}, "pairwise": pw}
        if j in PANEL:
            pooled_counts.update(c); pooled_n += len(picks)
        print(f"{j:9} n={len(picks):3}  " + "  ".join(f"{NAMES[a]} {c.get(a, 0)}" for a in ARMS) +
              "   |  " + "  ".join(f"{k} {v[0]}-{v[1]}-{v[2]}" for k, v in pw.items()))
    out["panel4_pooled"] = {"n": pooled_n, "picks": {a: pooled_counts.get(a, 0) for a in ARMS}, "pairwise": dict(pooled_pw)}
    print(f"{'pooled 4':9} n={pooled_n:3}  " + "  ".join(f"{NAMES[a]} {pooled_counts.get(a, 0)}" for a in ARMS) +
          "   |  " + "  ".join(f"{k} {v[0]}-{v[1]}-{v[2]}" for k, v in pooled_pw.items()))
    (DATA / "scores" / f"informed_send_{run}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1])
