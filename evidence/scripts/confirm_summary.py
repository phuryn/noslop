"""Confirmation run summary (holdout5): informed-send picks, v6 vs each arm on reads-human, meaning-check counts.

HUMANIZER_SET=holdout5 python scripts/confirm_summary.py   -> holdout5/summary.json + stdout
Arm keys: v6 = outputs/V6C (v6c, renamed v6), v6a = outputs/V6A (the one-liner alone), v5 = B5, blader = A,
bare = C (the bare prompt), emulate = E (Emulate-1), draft = O (unedited AI draft, reads-human only).
"""
import json
from collections import Counter, defaultdict

from common import DATA, ROOT, write

RUN = "conf"
PANEL = ["grok", "deepseek", "qwen", "codex"]
NAME = {"V6C": "v6", "V6A": "v6a", "B5": "v5", "A": "blader", "C": "bare", "E": "emulate", "O": "draft", "none": "none"}
ARMS = ["V6C", "V6A", "B5", "A", "C", "E"]


def send_picks(judge):
    c = Counter()
    n = 0
    for p in (DATA / "scores" / "judges" / RUN / judge / "send").glob("*.json"):
        r = json.loads(p.read_text(encoding="utf-8"))
        c[NAME[r["picked_arm"]]] += 1
        n += 1
    return {k: c.get(k, 0) for k in [NAME[a] for a in ARMS] + ["none"]}, n


def human_pairs(judge):
    per = defaultdict(lambda: defaultdict(list))
    for p in (DATA / "scores" / "judges" / RUN / judge / "human").glob("*.json"):
        r = json.loads(p.read_text(encoding="utf-8"))
        for lab, v in r["human_rank"].items():
            per[p.name[:2]][r["label_to_arm"][str(lab)]].append(int(v))
    out = {}
    for y in ["V6A", "B5", "A", "C", "E", "O"]:
        w = t = l = 0
        for arms in per.values():
            if "V6C" in arms and y in arms:
                mx, my = sum(arms["V6C"]) / len(arms["V6C"]), sum(arms[y]) / len(arms[y])
                w += mx < my; l += mx > my; t += mx == my
        out[f"v6_vs_{NAME[y]}"] = {"better": w, "tie": t, "worse": l, "n": w + t + l}
    return out


def meaning():
    inv = json.loads((ROOT / "scores" / "invented_verified.json").read_text(encoding="utf-8")).get("holdout5", {})
    out = {}
    for a in ARMS:
        dr = ch = ad = 0
        files = list((DATA / "scores" / "factcheck" / a).glob("*.json"))
        for f in files:
            d = json.loads(f.read_text(encoding="utf-8"))
            dr += len(d.get("dropped", [])); ch += len(d.get("changed", [])); ad += len(d.get("added", []))
        out[NAME[a]] = {"texts": len(files), "invented_or_upgraded_texts_hand_verified": len(inv.get(a, {})),
                        "dropped_items_any_severity": dr, "changed_items_any_severity": ch,
                        "added_items_any_severity": ad}
    return out


def main():
    s = {"set": "holdout5", "texts": 12, "orders_per_text": 2,
         "judges": {"grok": "x-ai/grok-4.7", "deepseek": "deepseek/deepseek-v4-pro-0813",
                    "qwen": "qwen/qwen3.8-max-0902", "codex": "Codex CLI (OpenAI), effort high",
                    "opus": "Claude Opus (reported separately)"},
         "arms": {NAME[a]: a for a in ARMS},
         "informed_send": {"per_judge": {}, "panel4_pooled": {}},
         "reads_human": {"per_judge": {}, "panel4_pooled": {}},
         "meaning_check": meaning()}
    pooled = Counter(); pn = 0
    pooled_h = defaultdict(lambda: [0, 0, 0])
    for j in PANEL + ["opus"]:
        picks, n = send_picks(j)
        s["informed_send"]["per_judge"][j] = {"picks": picks, "n": n}
        hp = human_pairs(j)
        s["reads_human"]["per_judge"][j] = hp
        if j in PANEL:
            pooled.update(picks); pn += n
            for k, v in hp.items():
                pooled_h[k][0] += v["better"]; pooled_h[k][1] += v["tie"]; pooled_h[k][2] += v["worse"]
    s["informed_send"]["panel4_pooled"] = {"picks": dict(pooled), "n": pn}
    s["reads_human"]["panel4_pooled"] = {k: {"better": v[0], "tie": v[1], "worse": v[2], "n": sum(v)} for k, v in pooled_h.items()}
    spend = 0.0
    for line in (ROOT / "scores" / "panel_spend.jsonl").read_text(encoding="utf-8").splitlines():
        d = json.loads(line)
        if "-conf-" in (d.get("tag") or ""):
            spend += d.get("cost") or 0
    s["cost_usd_openrouter"] = round(spend, 2)
    write(DATA / "summary.json", json.dumps(s, indent=2))
    print(json.dumps(s, indent=1))


if __name__ == "__main__":
    main()
