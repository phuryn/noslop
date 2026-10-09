"""Analyze Pangram results (scores/pangram_log.csv).

python scripts/pangram_analyze.py -> scores/pangram_summary.json + printed tables
Track 3: per variant mean fraction_human / fraction_ai / fraction_ai_assisted and labels, plus the
relationship with how much of the human original H survives (5-word-run share, scores/track3_verbatim.json).
Track 1 and generation: per arm means and label counts.
"""
import csv
import json
import statistics
from collections import defaultdict

from common import ROOT, write

rows = [r for r in csv.DictReader(open(ROOT / "scores" / "pangram_log.csv", encoding="utf-8"))
        if r["stage"] == "STAGE_SUCCESS" and not r["key"].startswith(("probe", "manual"))]
vb = json.loads((ROOT / "scores" / "track3_verbatim.json").read_text())
g = defaultdict(list)
for r in rows:
    g[r["group"]].append(r)


def f(x):
    return float(x) if x not in ("", None) else 0.0


out = {}
for name, rs in sorted(g.items()):
    labels = defaultdict(int)
    for r in rs:
        labels[r["prediction_short"]] += 1
    out[name] = {"n": len(rs),
                 "fraction_human": round(statistics.mean(f(r["fraction_human"]) for r in rs), 2),
                 "fraction_ai": round(statistics.mean(f(r["fraction_ai"]) for r in rs), 2),
                 "fraction_ai_assisted": round(statistics.mean(f(r["fraction_ai_assisted"]) for r in rs), 2),
                 "labels": dict(labels)}

# Track 3: human-share vs fraction_human, per text
pairs = []
per_text = defaultdict(dict)
for r in rows:
    if not r["group"].startswith("track3/"):
        continue
    v = r["group"].split("/", 1)[1]
    tid = str(int(r["file"][:2]))
    share = 1.0 if v == "H" else vb.get(v, {}).get(tid, {}).get("share_of_H_5grams")
    per_text[v][tid] = (round(f(r["fraction_human"]), 2), share)
    if share is not None and v not in ("H", "E"):
        pairs.append((share, f(r["fraction_human"])))


def spearman(xs, ys):
    def rank(a):
        s = sorted(range(len(a)), key=lambda k: a[k])
        rk = [0.0] * len(a)
        i = 0
        while i < len(a):
            j = i
            while j + 1 < len(a) and a[s[j + 1]] == a[s[i]]:
                j += 1
            for k in range(i, j + 1):
                rk[s[k]] = (i + j) / 2
            i = j + 1
        return rk
    rx, ry = rank(xs), rank(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    return cov / ((sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5)


summary = {"groups": out, "track3_per_text": per_text,
           "track3_spearman_human_share_vs_fraction_human": round(spearman([p[0] for p in pairs], [p[1] for p in pairs]), 2),
           "track3_n": len(pairs)}
write(ROOT / "scores" / "pangram_summary.json", json.dumps(summary, indent=2))
for k, v in out.items():
    print(f"{k:18} n={v['n']:2} human={v['fraction_human']:.2f} ai={v['fraction_ai']:.2f} "
          f"assisted={v['fraction_ai_assisted']:.2f} {v['labels']}")
print("Track 3 Spearman(share of H words, fraction_human), excluding H and E:",
      summary["track3_spearman_human_share_vs_fraction_human"], "n =", len(pairs))
for v, d in per_text.items():
    print(f"  {v:9}", "  ".join(f"{t}:{h:.2f}/{s if s is None else round(s, 2)}" for t, (h, s) in sorted(d.items())))
