"""Summarize scores/detectors.csv: calibration (human 2022 vs AI inputs) and P(AI) by arm / variant.

python scripts/detector_summary.py  -> scores/detector_summary.json + printed table
"""
import csv
import json
import statistics
from collections import defaultdict

from common import ROOT, write

DET = ("desklib", "fakespot", "radar")


def auroc(pos, neg):
    s = sum(1 if p > n else 0.5 if p == n else 0 for p in pos for n in neg)
    return s / (len(pos) * len(neg))


rows = list(csv.DictReader(open(ROOT / "scores" / "detectors.csv", encoding="utf-8")))
g = defaultdict(list)
for r in rows:
    g[r["group"]].append(r)
out = {"calibration": {}, "groups": {}}
ai = g["inputs"] + g.get("holdout/inputs", [])
hu = g["human"]
for d in DET:
    a = [float(r[d]) for r in ai]
    h = [float(r[d]) for r in hu]
    out["calibration"][d] = {"auroc_ai_inputs_vs_human_2022": round(auroc(a, h), 2),
                             "ai_inputs_flagged": f"{sum(x >= .5 for x in a)}/{len(a)}",
                             "human_flagged": f"{sum(x >= .5 for x in h)}/{len(h)}"}
for name, rs in sorted(g.items()):
    out["groups"][name] = {"n": len(rs), **{d: round(statistics.mean(float(r[d]) for r in rs), 3) for d in DET},
                           "desklib_flagged": f"{sum(float(r['desklib']) >= .5 for r in rs)}/{len(rs)}"}
write(ROOT / "scores" / "detector_summary.json", json.dumps(out, indent=2))
print(json.dumps(out["calibration"], indent=1))
for k, v in out["groups"].items():
    print(f"{k:24} n={v['n']:2}  desklib={v['desklib']:.2f} ({v['desklib_flagged']})  fakespot={v['fakespot']:.2f}  radar={v['radar']:.2f}")
