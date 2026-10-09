"""Aggregate blind-judge verdicts into pairwise wins/ties/losses, mean ranks, and 'send' picks.

python scripts/analyze_judges.py <run> [pairs like B:A,B:C,A:C]
Per text and judge, an arm's rank is averaged over the random orders; arm X beats Y on a text if
its mean rank is lower. Sign test p-value (two-sided, ties dropped) is printed per pair.
"""
import json
import sys
from collections import defaultdict
from math import comb

from common import DATA, ROOT, write


def sign_p(w, l):
    n = w + l
    if n == 0:
        return 1.0
    k = min(w, l)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def load(run, judge, kind):
    d = DATA / "scores" / "judges" / run / judge / kind
    per_text = defaultdict(lambda: defaultdict(list))
    sends = defaultdict(int)
    n_files = 0
    for p in sorted(d.glob("*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        tid = p.name.split("-")[0]
        rk = r["human_rank" if kind == "human" else "meaning_rank"]
        for label, rank in rk.items():
            per_text[tid][r["label_to_arm"][str(label)]].append(int(rank))
        if kind == "human" and r.get("send"):
            sends[r["label_to_arm"][str(r["send"]).strip()]] += 1
        n_files += 1
    return per_text, sends, n_files


def analyze(run, pairs):
    report = {}
    for kind in ("human", "meaning"):
        for judge in ("codex", "opus"):
            per_text, sends, n = load(run, judge, kind)
            if not n:
                continue
            arms = sorted({a for t in per_text.values() for a in t})
            mean_rank = {a: round(sum(sum(t[a]) / len(t[a]) for t in per_text.values() if a in t) /
                                  sum(1 for t in per_text.values() if a in t), 2) for a in arms}
            pw = {}
            for x, y in pairs:
                if x not in arms or y not in arms:
                    continue
                w = l = t = 0
                for tr in per_text.values():
                    if x in tr and y in tr:
                        mx, my = sum(tr[x]) / len(tr[x]), sum(tr[y]) / len(tr[y])
                        w += mx < my
                        l += mx > my
                        t += mx == my
                pw[f"{x}>{y}"] = {"win": w, "tie": t, "loss": l, "p": round(sign_p(w, l), 3)}
            key = f"{kind}/{judge}"
            report[key] = {"texts": len(per_text), "verdicts": n, "mean_rank": mean_rank, "pairwise": pw}
            if kind == "human":
                report[key]["send_picks"] = dict(sends)
    # combined across both judges (each judge-text is one observation)
    for kind in ("human", "meaning"):
        comb_pw = {}
        for x, y in pairs:
            w = l = t = 0
            for judge in ("codex", "opus"):
                k = f"{kind}/{judge}"
                if k in report and f"{x}>{y}" in report[k]["pairwise"]:
                    s = report[k]["pairwise"][f"{x}>{y}"]
                    w, l, t = w + s["win"], l + s["loss"], t + s["tie"]
            if w + l + t:
                comb_pw[f"{x}>{y}"] = {"win": w, "tie": t, "loss": l}
        if comb_pw:
            report[f"{kind}/both"] = {"pairwise": comb_pw}
    write(DATA / "scores" / f"judges_{run}_summary.json", json.dumps(report, indent=2))
    for k, v in report.items():
        print(k, json.dumps(v))


if __name__ == "__main__":
    run = sys.argv[1]
    pairs = [tuple(p.split(":")) for p in (sys.argv[2] if len(sys.argv) > 2 else "B:A,B:C,A:C,B:O,A:O,C:O").split(",")]
    analyze(run, pairs)
