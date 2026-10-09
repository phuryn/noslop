"""Decision models (and Opus) as "written by a person?" scorers, compared with Pangram.

Known-human texts are user-supplied (evidence/human/, not shipped); the published run used 10 excerpts of the
author's pre-ChatGPT writing. Track 3 texts are built by run_track3.py from those excerpts.

python scripts/decision_detect.py phase1     # detector set x every model x every variant
python scripts/decision_detect.py select     # pick each model's variant on half A, report on half B
python scripts/decision_detect.py phase2     # every arm text, each model's selected variant
python scripts/decision_detect.py report     # tables -> scores/decisions/summary.json + stdout

Models: Jev 1.13, Cloudflare Clef and Clef-flash (OpenRouter /api/v1/systemone, yes/no "noul" questions),
OpenAI Decisions gpt-6-luna (2-option choice; its yes/no "predicate" returned 0.50 on a clearly human text),
Perplexity Decider, Levanto Sage (Jev's request format), and Claude Opus asked for a probability (comparison row).
P(human) is read from the returned probabilities, never from a confidence field.
Every call's usage and cost go to scores/panel_spend.jsonl (shared $25 cap with the judge panel).
"""
import concurrent.futures as cf
import hashlib
import json
import random
import statistics
import sys
import threading
import time

import apis
from common import ROOT, parse_json, read, run_claude, write

OUT = ROOT / "scores" / "decisions"
CACHE = OUT / "results.jsonl"
_lock = threading.Lock()
CAP = 25.0

Q_PLAIN = "Was this text written by a person, rather than generated or rewritten by an AI model?"
Q_TELLS = ("Was this text written by a person? Answer no if it shows the habits of AI-generated writing: contrasts against "
           "claims nobody made ('it's not X, it's Y'), neat groups of three, a tidy lesson or question tacked on at the end, "
           "generic benefits instead of specifics, evenly balanced sentences, stock phrases ('seamless', 'in today's world'), "
           "bold labels on every point, polished but impersonal tone. Answer yes if it reads like one particular person "
           "wrote it: uneven rhythm, specific detail, opinions, quirks, small imperfections.")
Q_COMPOSE = ("Was this text composed by a person, meaning the sentences are their own even if software later corrected or "
             "formatted them? Answer no if a language model generated the sentences, even if a person edited them afterwards.")
VARIANTS = {"plain": Q_PLAIN, "tells": Q_TELLS, "compose": Q_COMPOSE, "fewshot": Q_PLAIN}

PRICES = {  # USD per token where the API does not return cost (from each provider's published rates)
    "pplx": (0.04 / 1e6, 0.0), "sage": (0.05 / 1e6, 10 / 1e6), "oai": (0.10 / 1e6, 0.0),
}


def h(text):
    return hashlib.sha1(text.encode()).hexdigest()[:16]


# ---- texts -----------------------------------------------------------------------------------
def detector_set():
    """Known-human (pre-ChatGPT excerpts) and known-AI (the 32 unedited drafts). Split into halves A/B."""
    items = []
    for p in sorted((ROOT / "human").glob("*.md")):
        items.append({"set": "human", "group": "human", "file": p.name, "path": p, "truth": 1})
    for sub, base in (("main", ROOT), ("holdout", ROOT / "holdout"), ("holdout2", ROOT / "holdout2")):
        for p in sorted((base / "inputs").glob("[0-9][0-9]-*.md")):
            items.append({"set": sub, "group": f"{sub}/O", "file": p.name, "path": p, "truth": 0})
    # stratified alternate split, fixed: every other human text and every other AI draft per set
    k = {"human": 0, "main": 0, "holdout": 0, "holdout2": 0}
    for it in items:
        it["half"] = "A" if k[it["set"]] % 2 == 0 else "B"
        k[it["set"]] += 1
    return items


def arm_set():
    items = []
    for arm in ("A", "B3", "C", "E"):
        for p in sorted((ROOT / "outputs" / arm).glob("[0-9][0-9]-*.md")):
            items.append({"set": "main", "group": f"main/{arm}", "file": p.name, "path": p})
    for arm in ("A", "B3", "C"):
        for p in sorted((ROOT / "holdout" / "outputs" / arm).glob("[0-9][0-9]-*.md")):
            items.append({"set": "holdout", "group": f"holdout/{arm}", "file": p.name, "path": p})
    for arm in ("A", "B3"):
        for p in sorted((ROOT / "holdout2" / "outputs" / arm).glob("[0-9][0-9]-*.md")):
            items.append({"set": "holdout2", "group": f"holdout2/{arm}", "file": p.name, "path": p})
    for p in sorted((ROOT / "gen" / "E-write").glob("[0-9][0-9]-*.md")):
        items.append({"set": "main", "group": "main/E-write", "file": p.name, "path": p})
    for v in ("D", "A", "B2", "C", "E", "A-notes", "B2-notes", "A-ask", "B2-ask", "A-int", "B2-int"):
        for p in sorted((ROOT / "track3" / v).glob("[0-9][0-9].md")):
            items.append({"set": "track3", "group": f"track3/{v}", "file": p.name, "path": p})
    return items


def example_items():
    """Two human and two AI texts from half A, used as labelled examples (excluded from every score)."""
    ds = [d for d in detector_set() if d["half"] == "A"]
    return [d for d in ds if d["truth"] == 1][:2] + [d for d in ds if d["truth"] == 0 and d["set"] == "main"][:2]


def fewshot_examples():
    """The labelled examples, trimmed to 120 words."""
    trim = lambda p: " ".join(read(p).split()[:120])
    return [{"text": trim(d["path"]), "written_by_a_person": bool(d["truth"])} for d in example_items()]


# ---- model calls -------------------------------------------------------------------------------
def _state(text, variant):
    st = {"text": text}
    if variant == "fewshot":
        st["labelled_examples"] = fewshot_examples()
    return st


def call(model, text, variant):
    q = VARIANTS[variant]
    if apis.total_spend() > CAP - 0.5:
        raise RuntimeError("spend cap")
    if model in ("jev", "clef", "clef-flash", "pplx", "sage"):
        mid = {"jev": "typesafe/jev-1.13", "clef": "cloudflare/clef", "clef-flash": "cloudflare/clef-flash",
               "pplx": "pplx-decider-v1-27b", "sage": "levanto-sage-v1.3"}[model]
        url, hdr = apis.OR_DEC, apis.OR_HDR()
        if model == "pplx":
            url, hdr = "https://api.perplexity.ai/v1/decisions", {"Authorization": "Bearer " + apis.key("PERPLEXITY_API_KEY"),
                                                                  "Content-Type": "application/json"}
        if model == "sage":
            url, hdr = "https://sage.levanto.ai/v1/systemone", {"Authorization": "Bearer " + apis.key("SAGE_API_KEY"),
                                                               "Content-Type": "application/json", "User-Agent": "curl/8.7.1"}
        body = {"model": mid, "state": _state(text, variant), "questions": {"human": {"type": "noul", "instructions": q}}}
        r = None
        for attempt in range(3):
            r = apis.post(url, body, hdr, timeout=120)
            if r["ok"]:
                a = r["d"]["answers"]["human"]
                u = r["d"].get("usage") or {}
                tin, tout = u.get("input_tokens") or 0, u.get("output_tokens") or 0
                cost = u.get("cost")
                if cost is None:
                    pi, po = PRICES[model]
                    cost = tin * pi + tout * po
                return {"p": float(a["noul"]), "in": tin, "out": tout, "cost": cost, "ms": r["ms"]}
            time.sleep(3 * (attempt + 1))
        return {"error": r.get("error")}
    if model == "oai":
        st = _state(text, variant)
        body = {"model": "gpt-6-luna", "input": json.dumps(st, ensure_ascii=False),
                "questions": [{"type": "choice", "name": "human", "instructions": q,
                               "choices": [{"value": "person", "description": "Written by a person"},
                                           {"value": "ai", "description": "Generated or rewritten by an AI model"}]}]}
        hdr = {"Authorization": "Bearer " + apis.key("OPENAI_API_KEY"), "Content-Type": "application/json"}
        r = None
        for attempt in range(3):
            r = apis.post("https://api.openai.com/v1/decisions", body, hdr, timeout=120)
            if r["ok"]:
                a = r["d"]["answers"][0]
                tin = (r["d"].get("usage") or {}).get("input_tokens") or 0
                if a.get("type") == "refusal":
                    return {"error": "refusal", "in": tin, "cost": tin * PRICES["oai"][0]}
                probs = {x["value"]: x["probability"] for x in a.get("probabilities") or []}
                return {"p": float(probs.get("person", 0.0)), "in": tin, "out": 0, "cost": tin * PRICES["oai"][0], "ms": r["ms"]}
            time.sleep(3 * (attempt + 1))
        return {"error": r.get("error")}
    if model == "opus":
        ex = ""
        if variant == "fewshot":
            ex = "Labelled examples:\n" + json.dumps(fewshot_examples(), ensure_ascii=False) + "\n\n"
        prompt = (f"{ex}<text>\n{text}\n</text>\n\n{q}\n\nAnswer with JSON only: "
                  '{"p_human": <probability between 0 and 1 that a person wrote it>}')
        reply = run_claude(prompt, model="opus", tag=f"det-opus-{variant}", system="You are a careful, impartial reviewer.")
        return {"p": float(parse_json(reply)["p_human"]), "cost": 0.0}
    raise ValueError(model)


MODELS = ["jev", "oai", "clef", "clef-flash", "pplx", "sage", "opus"]


def load_cache():
    c = {}
    if CACHE.exists():
        for line in CACHE.read_text(encoding="utf-8").splitlines():
            d = json.loads(line)
            c[(d["model"], d["variant"], d["hash"])] = d
    return c


def job(model, variant, it, cache):
    text = read(it["path"]).strip()
    k = (model, variant, h(text))
    if k in cache:
        return
    res = call(model, text, variant)
    rec = {"model": model, "variant": variant, "hash": h(text), "group": it["group"], "file": it["file"],
           "words": len(text.split()), **res}
    with _lock:
        with open(CACHE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    if res.get("cost"):
        apis.log_spend({"api": "decision", "model": model, "variant": variant, "cost": res["cost"],
                        "in": res.get("in"), "out": res.get("out")})


def run_jobs(jobs, workers=8):
    cache = load_cache()
    OUT.mkdir(parents=True, exist_ok=True)
    with cf.ThreadPoolExecutor(workers) as ex:
        futs = [ex.submit(job, m, v, it, cache) for m, v, it in jobs]
        for f in futs:
            try:
                f.result()
            except Exception as e:  # noqa: BLE001
                print("ERR", repr(e)[:200])


# ---- analysis ----------------------------------------------------------------------------------
def auc(pos, neg):
    if not pos or not neg:
        return float("nan")
    return sum(1 if p > n else 0.5 if p == n else 0 for p in pos for n in neg) / (len(pos) * len(neg))


def scores_for(model, variant, items, cache):
    out = []
    for it in items:
        d = cache.get((model, variant, h(read(it["path"]).strip())))
        if d and "p" in d:
            out.append((it, d["p"]))
    return out


def metrics(pairs):
    hum = [p for it, p in pairs if it["truth"] == 1]
    ai = [p for it, p in pairs if it["truth"] == 0]
    return {"auc": round(auc(hum, ai), 3), "n_human": len(hum), "n_ai": len(ai),
            "acc_0.5": round((sum(p > 0.5 for p in hum) + sum(p <= 0.5 for p in ai)) / max(1, len(hum) + len(ai)), 3),
            "false_pos_human_called_ai": sum(p <= 0.5 for p in hum), "false_neg_ai_called_human": sum(p > 0.5 for p in ai),
            "mean_p_human_on_human": round(statistics.mean(hum), 3) if hum else None,
            "mean_p_human_on_ai": round(statistics.mean(ai), 3) if ai else None}


def pangram_by_hash():
    import csv
    out = {}
    rows = [r for r in csv.DictReader(open(ROOT / "scores" / "pangram_log.csv", encoding="utf-8")) if r["stage"] == "STAGE_SUCCESS"]
    paths = {}
    for p in list(ROOT.rglob("*.md")):
        if "raw" in p.parts or "scripts" in p.parts:
            continue
        paths.setdefault(p.name, []).append(p)
    for r in rows:
        g = r["group"]
        if g.startswith("t1/"):
            arm = g[3:]
            p = ROOT / "inputs" / r["file"] if arm == "O" else ROOT / "outputs" / arm / r["file"]
        elif g == "gen/E-write":
            p = ROOT / "gen" / "E-write" / r["file"]
        elif g.startswith("track3/"):
            p = ROOT / "track3" / g.split("/", 1)[1] / r["file"]
        elif g == "human":
            p = ROOT / "human" / r["file"]
        elif g in ("holdout/O", "holdout2/O"):
            p = ROOT / g.split("/")[0] / "inputs" / r["file"]
        else:
            continue
        if p.exists():
            out[h(read(p).strip())] = float(r["fraction_human"] or 0)
    return out


def select():
    cache = load_cache()
    ex = {d["file"] + d["set"] for d in example_items()}
    ds = [d for d in detector_set() if d["file"] + d["set"] not in ex]   # example texts never scored
    A = [d for d in ds if d["half"] == "A"]
    B = [d for d in ds if d["half"] == "B"]
    pg = pangram_by_hash()
    sel = {}
    table = {}
    for m in MODELS:
        best, best_auc = None, -1
        per = {}
        for v in VARIANTS:
            a_pairs = scores_for(m, v, A, cache)
            if len(a_pairs) < len(A) * 0.8:
                continue
            ma = metrics(a_pairs)
            per[v] = {"A": ma, "B": metrics(scores_for(m, v, B, cache)), "all": metrics(scores_for(m, v, ds, cache))}
            # select on half A: AUC first, then accuracy at 0.5
            key = (ma["auc"], ma["acc_0.5"])
            if best is None or key > best_auc:
                best, best_auc = v, key
        sel[m] = best
        table[m] = {"selected": best, "variants": per}
    # Pangram reference row
    pp = [(it, pg[h(read(it["path"]).strip())]) for it in ds if h(read(it["path"]).strip()) in pg]
    table["pangram"] = {"A": metrics([x for x in pp if x[0]["half"] == "A"]), "B": metrics([x for x in pp if x[0]["half"] == "B"]),
                        "all": metrics(pp)}
    # ensemble: mean of the 3 decision models (not Opus) with the best half-A AUC
    ranked = sorted([m for m in MODELS if m != "opus" and sel.get(m)],
                    key=lambda m: -table[m]["variants"][sel[m]]["A"]["auc"])[:3]
    def ens(items):
        out = []
        for it in items:
            ps = [d["p"] for m in ranked for d in [cache.get((m, sel[m], h(read(it["path"]).strip())))] if d and "p" in d]
            if len(ps) == len(ranked):
                out.append((it, statistics.mean(ps)))
        return out
    table["ensemble"] = {"members": ranked, "A": metrics(ens(A)), "B": metrics(ens(B)), "all": metrics(ens(ds))}
    write(OUT / "selection.json", json.dumps({"selected": sel, "ensemble": ranked, "table": table}, indent=2))
    print("selected:", sel, "ensemble:", ranked)
    for m, t in table.items():
        if m in ("pangram", "ensemble"):
            print(f"{m:11} half B {t['B']}")
        elif t["selected"]:
            print(f"{m:11} [{t['selected']}] half B {t['variants'][t['selected']]['B']}")


def report():
    cache = load_cache()
    sel = json.loads(read(OUT / "selection.json"))["selected"]
    pg = pangram_by_hash()
    groups = {}
    for it in arm_set() + detector_set():
        groups.setdefault(it["group"], []).append(it)
    out = {"by_group": {}, "pangram_agreement": {}}
    for g, its in sorted(groups.items()):
        row = {}
        for m in MODELS:
            v = sel.get(m)
            ps = [p for _, p in scores_for(m, v, its, load_cache())] if v else []
            if ps:
                row[m] = {"mean": round(statistics.mean(ps), 2), "share_gt_0.5": f"{sum(p > 0.5 for p in ps)}/{len(ps)}"}
        pgs = [pg[h(read(it['path']).strip())] for it in its if h(read(it['path']).strip()) in pg]
        if pgs:
            row["pangram"] = {"mean": round(statistics.mean(pgs), 2), "share_gt_0.5": f"{sum(p > 0.5 for p in pgs)}/{len(pgs)}"}
        out["by_group"][g] = row
    # agreement with Pangram on every text both scored
    allits = arm_set() + detector_set()
    for m in MODELS:
        v = sel.get(m)
        if not v:
            continue
        xs, ys = [], []
        for it in allits:
            hh = h(read(it["path"]).strip())
            d = cache.get((m, v, hh))
            if d and "p" in d and hh in pg:
                xs.append(d["p"]); ys.append(pg[hh])
        if len(xs) > 5:
            same = sum((x > 0.5) == (y > 0.5) for x, y in zip(xs, ys)) / len(xs)
            out["pangram_agreement"][m] = {"n": len(xs), "spearman": round(spearman(xs, ys), 2), "same_verdict": round(same, 2)}
    # cost per 1,000 texts of about 300 words, from real usage (cost per input word scaled to 300 words)
    cost = {}
    for m in MODELS:
        recs = [d for (mm, vv, _), d in cache.items() if mm == m and vv == "plain" and "p" in d and d.get("words")]
        if recs and m != "opus":
            per_word = sum(d.get("cost") or 0 for d in recs) / sum(d["words"] for d in recs)
            cost[m] = round(per_word * 300 * 1000, 4)
    out["cost_per_1000_texts_300w_usd"] = cost
    write(OUT / "summary.json", json.dumps(out, indent=2))
    print(json.dumps(out["pangram_agreement"], indent=1))
    print(json.dumps(cost, indent=1))
    for g, row in out["by_group"].items():
        print(f"{g:20}", "  ".join(f"{m}:{r['mean']:.2f}({r['share_gt_0.5']})" for m, r in row.items()))


def spearman(xs, ys):
    def rank(a):
        s = sorted(range(len(a)), key=lambda k: a[k]); r = [0.0] * len(a); i = 0
        while i < len(a):
            j = i
            while j + 1 < len(a) and a[s[j + 1]] == a[s[i]]:
                j += 1
            for k in range(i, j + 1):
                r[s[k]] = (i + j) / 2
            i = j + 1
        return r
    rx, ry = rank(xs), rank(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return cov / den if den else float("nan")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "phase1":
        ms = sys.argv[2].split(",") if len(sys.argv) > 2 else MODELS
        jobs = [(m, v, it) for it in detector_set() for m in ms for v in VARIANTS]
        run_jobs(jobs, workers=6 if "opus" in ms else 10)
    elif cmd == "select":
        select()
    elif cmd == "phase2":
        sel = json.loads(read(OUT / "selection.json"))["selected"]
        ms = sys.argv[2].split(",") if len(sys.argv) > 2 else MODELS
        jobs = [(m, sel[m], it) for it in arm_set() for m in ms if sel.get(m)]
        run_jobs(jobs, workers=6 if "opus" in ms else 10)
    elif cmd == "report":
        report()
