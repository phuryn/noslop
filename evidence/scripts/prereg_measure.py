"""Pre-registered measure (defined 2026-10-08 before v5 results): "Reads human, without inventing facts".

For each judged text and judge: an arm whose rewrite has a hand-verified invented or upgraded fact on that text
(scores/invented_verified.json) is disqualified on that text. A disqualified arm loses to every arm that kept the
facts; two disqualified arms tie. Otherwise the judge's reads-human verdict stands (per-text mean rank over orders).

python scripts/prereg_measure.py RUN judge1,judge2 X:Y,X:Y [--set main|holdout|holdout2|holdout3]
Prints raw and adjusted better-tie-worse per judge and pooled, and the texts where the adjustment changed a verdict.
"""
import argparse
import json
from collections import defaultdict

from common import ROOT

SETDIR = {"main": ROOT, "holdout": ROOT / "holdout", "holdout2": ROOT / "holdout2", "holdout3": ROOT / "holdout3"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run"); ap.add_argument("judges"); ap.add_argument("pairs")
    ap.add_argument("--set", default="main")
    a = ap.parse_args()
    inv = json.loads((ROOT / "scores" / "invented_verified.json").read_text(encoding="utf-8")).get(a.set, {})
    dq = lambda arm, tid: str(int(tid)) in inv.get(arm, {})
    pairs = [p.split(":") for p in a.pairs.split(",")]
    tot_raw = defaultdict(lambda: [0, 0, 0]); tot_adj = defaultdict(lambda: [0, 0, 0]); changed = []
    out = {}
    for j in a.judges.split(","):
        per = defaultdict(lambda: defaultdict(list))
        for p in (SETDIR[a.set] / "scores" / "judges" / a.run / j / "human").glob("*.json"):
            r = json.loads(p.read_text(encoding="utf-8"))
            for lab, v in r["human_rank"].items():
                per[p.name[:2]][r["label_to_arm"][str(lab)]].append(int(v))
        for x, y in pairs:
            raw = [0, 0, 0]; adj = [0, 0, 0]
            for tid, arms in per.items():
                if x not in arms or y not in arms:
                    continue
                mx, my = sum(arms[x]) / len(arms[x]), sum(arms[y]) / len(arms[y])
                r_ = 0 if mx < my else 2 if mx > my else 1
                raw[r_] += 1
                dx, dy = dq(x, tid), dq(y, tid)
                a_ = 1 if (dx and dy) else 2 if dx else 0 if dy else r_
                adj[a_] += 1
                if a_ != r_:
                    changed.append(f"{j} text {tid}: {x} vs {y} {['better','tie','worse'][r_]} -> {['better','tie','worse'][a_]}")
            out[f"{j} {x}>{y}"] = {"raw": raw, "adjusted": adj}
            for i in range(3):
                tot_raw[f"{x}>{y}"][i] += raw[i]; tot_adj[f"{x}>{y}"][i] += adj[i]
            print(f"{j:9} {x}>{y}  raw {raw[0]}-{raw[1]}-{raw[2]}  without-inventing {adj[0]}-{adj[1]}-{adj[2]}  (n={sum(raw)})")
    for k in tot_raw:
        r, d = tot_raw[k], tot_adj[k]
        print(f"pooled    {k}  raw {r[0]}-{r[1]}-{r[2]}  without-inventing {d[0]}-{d[1]}-{d[2]}  (n={sum(r)})")
    print("changed verdicts:", len(changed))
    for c in changed:
        print("  ", c)


if __name__ == "__main__":
    main()
