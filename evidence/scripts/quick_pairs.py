"""Pairwise better-tie-worse for any run and any judges. python scripts/quick_pairs.py RUN judge1,judge2 X:Y,X:Y"""
import json, sys
from collections import defaultdict
from common import DATA

run, judges, pairs = sys.argv[1], sys.argv[2].split(","), [p.split(":") for p in sys.argv[3].split(",")]
for kind in ("human", "meaning"):
    tot = defaultdict(lambda: [0, 0, 0])
    for j in judges:
        per = defaultdict(lambda: defaultdict(list)); sends = defaultdict(int)
        for p in (DATA / "scores" / "judges" / run / j / kind).glob("*.json"):
            r = json.loads(p.read_text(encoding="utf-8"))
            for lab, v in r["human_rank" if kind == "human" else "meaning_rank"].items():
                per[p.name[:2]][r["label_to_arm"][str(lab)]].append(int(v))
            if kind == "human" and r.get("send"):
                a = r["label_to_arm"].get(str(r["send"]).strip()); sends[a] += 1 if a else 0
        cells = []
        for x, y in pairs:
            w = t = l = 0
            for arms in per.values():
                if x in arms and y in arms:
                    mx, my = sum(arms[x]) / len(arms[x]), sum(arms[y]) / len(arms[y])
                    w += mx < my; l += mx > my; t += mx == my
            if w + t + l:
                cells.append(f"{x}>{y} {w}-{t}-{l}")
                tot[f"{x}>{y}"][0] += w; tot[f"{x}>{y}"][1] += t; tot[f"{x}>{y}"][2] += l
        print(f"{kind:8} {j:9} " + "  ".join(cells) + (f"  send {dict(sends)}" if sends else ""))
    print(f"{kind:8} {'pooled':9} " + "  ".join(f"{k} {v[0]}-{v[1]}-{v[2]}" for k, v in tot.items()))
