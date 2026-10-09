"""Five-judge panel: per judge, per set, per question; pooled over the four non-Anthropic judges; agreement.

python scripts/analyze_panel.py   -> scores/panel_summary.json + stdout
Judges: grok (x-ai/grok-4.7), deepseek (deepseek/deepseek-v4-pro-0813), qwen (qwen/qwen3.8-max-0902), codex (Codex CLI),
and opus (Claude Opus, reported separately). Per text, an arm's rank is averaged over the two random orders; X is
"better" than Y on a text when its mean rank is lower.
"""
import json
from collections import defaultdict
from itertools import combinations
from math import comb

from common import ROOT, write

SETS = {"main 16": ROOT / "scores", "fresh 8": ROOT / "holdout" / "scores", "new fresh 8": ROOT / "holdout2" / "scores"}
JUDGES = ["grok", "deepseek", "qwen", "codex", "opus"]
PANEL = ["grok", "deepseek", "qwen", "codex"]
PAIRS = [("B3", "A"), ("B3", "C"), ("B3", "E"), ("A", "C"), ("E", "A"), ("B3", "O"), ("A", "O")]
NAMES = {"A": "blader", "B3": "work-humanizer v3", "C": "bare prompt", "E": "Emulate-1", "O": "AI draft"}


def sign_p(w, l):
    n = w + l
    if not n:
        return 1.0
    return min(1.0, 2 * sum(comb(n, i) for i in range(min(w, l) + 1)) / 2 ** n)


def load(base, judge, kind):
    per = defaultdict(lambda: defaultdict(list))
    sends = defaultdict(int)
    d = base / "judges" / "panel" / judge / kind
    for p in sorted(d.glob("*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        rk = r["human_rank" if kind == "human" else "meaning_rank"]
        for lab, v in rk.items():
            per[p.name[:2]][r["label_to_arm"][str(lab)]].append(int(v))
        if kind == "human" and r.get("send"):
            a = r["label_to_arm"].get(str(r["send"]).strip())
            if a:
                sends[a] += 1
    return {t: {a: sum(v) / len(v) for a, v in arms.items()} for t, arms in per.items()}, dict(sends)


def cmp(mr, x, y):
    w = l = t = 0
    for arms in mr.values():
        if x in arms and y in arms:
            w += arms[x] < arms[y]
            l += arms[x] > arms[y]
            t += arms[x] == arms[y]
    return w, t, l


def main():
    out = {}
    signs = defaultdict(dict)  # (set, kind, text, pair) -> {judge: sign}
    for sname, base in SETS.items():
        for kind in ("human", "meaning"):
            for j in JUDGES:
                mr, sends = load(base, j, kind)
                if not mr:
                    continue
                row = {}
                for x, y in PAIRS:
                    if kind == "meaning" and "O" in (x, y):
                        continue
                    w, t, l = cmp(mr, x, y)
                    if w + t + l:
                        row[f"{x}>{y}"] = {"better": w, "tie": t, "worse": l, "n": w + t + l, "p": round(sign_p(w, l), 3)}
                    for tid, arms in mr.items():
                        if x in arms and y in arms:
                            signs[(sname, kind, tid, f"{x}>{y}")][j] = (arms[x] < arms[y]) - (arms[x] > arms[y])
                out.setdefault(sname, {}).setdefault(kind, {})[j] = {"pairs": row, "texts": len(mr)}
                if kind == "human":
                    out[sname][kind][j]["send"] = sends
            # pooled over the four non-Anthropic judges
            pooled = {}
            for x, y in PAIRS:
                acc = [0, 0, 0]
                for j in PANEL:
                    r = out.get(sname, {}).get(kind, {}).get(j, {}).get("pairs", {}).get(f"{x}>{y}")
                    if r:
                        acc[0] += r["better"]; acc[1] += r["tie"]; acc[2] += r["worse"]
                if sum(acc):
                    pooled[f"{x}>{y}"] = {"better": acc[0], "tie": acc[1], "worse": acc[2], "n": sum(acc),
                                          "p": round(sign_p(acc[0], acc[2]), 3)}
            out[sname][kind]["panel4_pooled"] = {"pairs": pooled}
    # agreement: share of (text, pair) decisions where a judge's direction matches the majority of the other judges
    agree = {}
    for kind in ("human", "meaning"):
        for j in JUDGES:
            hit = tot = 0
            for (s, k, t, pair), js in signs.items():
                if k != kind or j not in js:
                    continue
                others = [v for jj, v in js.items() if jj != j and jj in JUDGES]
                if len(others) < 3:
                    continue
                maj = (sum(others) > 0) - (sum(others) < 0)
                if maj == 0 or js[j] == 0:
                    continue
                tot += 1
                hit += js[j] == maj
            agree.setdefault(kind, {})[j] = {"agrees_with_majority_of_others": round(hit / tot, 2) if tot else None, "n": tot}
        # pairwise agreement between judges
        pw = {}
        for a, b in combinations(JUDGES, 2):
            hit = tot = 0
            for (s, k, t, pair), js in signs.items():
                if k == kind and a in js and b in js and js[a] and js[b]:
                    tot += 1
                    hit += js[a] == js[b]
            pw[f"{a}~{b}"] = round(hit / tot, 2) if tot else None
        agree[kind]["pairwise"] = pw
    out["agreement"] = agree
    write(ROOT / "scores" / "panel_summary.json", json.dumps(out, indent=2))
    for sname in SETS:
        for kind in ("human", "meaning"):
            print(f"== {sname} / {kind}")
            for j, v in out[sname][kind].items():
                cells = "  ".join(f"{k}: {r['better']}-{r['tie']}-{r['worse']}" for k, r in v["pairs"].items())
                print(f"  {j:13} {cells}  {v.get('send', '')}")
    print(json.dumps(agree, indent=1))


if __name__ == "__main__":
    main()
