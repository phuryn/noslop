"""Measures for Tracks 2 and 3.

python scripts/track_measures.py t2 A-int B-int B2-int
  -> scores/track2_measures.json: asked, n_questions, hidden-fact recall (Opus checker),
     invented specifics vs draft+answers (Opus checker), share of output words inside
     5-word runs copied from the writer's answers.
verbatim_share() is also used by Track 3 (source = the human excerpt).
"""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor

from common import ROOT, parse_json, read, run_claude, write
from factcheck import check_pair

RECALL = """Below is a list of facts a writer knows, then a text. For each fact, say whether the text states it: "yes" (stated fully or substantially), "partial", or "no".

Facts:
{facts}

<text>
{text}
</text>

Return only JSON: {{"1": "yes|partial|no", ...}}"""


def words(t):
    return re.findall(r"[a-z0-9']+", t.lower().replace("’", "'"))


def verbatim_share(output, source, n=5):
    """Fraction of output words that sit inside some n-word run also present in source."""
    ow, sw = words(output), words(source)
    grams = {tuple(sw[i:i + n]) for i in range(len(sw) - n + 1)}
    covered = [False] * len(ow)
    for i in range(len(ow) - n + 1):
        if tuple(ow[i:i + n]) in grams:
            for j in range(i, i + n):
                covered[j] = True
    return round(sum(covered) / len(ow), 3) if ow else 0.0


def t2_one(arm, rec, brief):
    raw = json.loads(read(ROOT / "track2" / arm / "raw" / f"{rec['id']:02d}.json"))
    final = raw.get("final") or ""
    draft = read(ROOT / "inputs" / rec["file"])
    cache = ROOT / "scores" / "track2" / arm / f"{rec['id']:02d}.json"
    if cache.exists():
        return json.loads(read(cache))
    facts = "\n".join(f"{i + 1}. {f}" for i, f in enumerate(brief["hidden_facts"]))
    rec_out = {"id": rec["id"], "asked": raw["asked"]}
    if raw["asked"]:
        q = raw["questions"]
        rec_out["n_questions"] = len(re.findall(r"(?m)^\s*\d+[.)]", q)) or q.count("?")
        rec_out["answer_share"] = verbatim_share(final, raw["answers"])
    r = parse_json(run_claude(RECALL.format(facts=facts, text=final), model="opus", tag=f"recall-{arm}-{rec['id']}"))
    rec_out["recall_yes"] = sum(1 for v in r.values() if v == "yes")
    rec_out["recall_partial"] = sum(1 for v in r.values() if v == "partial")
    rec_out["hidden_total"] = len(brief["hidden_facts"])
    fc = check_pair(draft, final, tag=f"fc2-{arm}-{rec['id']}", allowed=raw.get("answers"))
    rec_out["invented_specifics"] = fc.get("invented_specifics", [])
    rec_out["meaning_preserved"] = fc.get("meaning_preserved")
    rec_out["major"] = [x for k in ("dropped", "changed", "added") for x in fc.get(k, [])
                        if isinstance(x, dict) and x.get("severity") == "major"]
    write(cache, json.dumps(rec_out, indent=2, ensure_ascii=False))
    return rec_out


def t2(arms):
    man = json.loads(read(ROOT / "inputs" / "manifest.json"))
    briefs = {b["id"]: b for b in json.loads(read(ROOT / "inputs" / "briefs.json"))}
    out = {}
    for arm in arms:
        with ThreadPoolExecutor(6) as ex:
            rs = list(ex.map(lambda r: t2_one(arm, r, briefs[r["id"]]), man))
        asked = [r for r in rs if r["asked"]]
        out[arm] = {
            "asked": len(asked), "texts": len(rs),
            "mean_questions_when_asked": round(sum(r["n_questions"] for r in asked) / len(asked), 1) if asked else 0,
            "hidden_facts_used_yes": sum(r["recall_yes"] for r in rs),
            "hidden_facts_used_partial": sum(r["recall_partial"] for r in rs),
            "hidden_facts_total": sum(r["hidden_total"] for r in rs),
            "texts_with_invented_specifics": sum(1 for r in rs if r["invented_specifics"]),
            "invented": {r["id"]: r["invented_specifics"] for r in rs if r["invented_specifics"]},
            "mean_answer_share_when_asked": round(sum(r["answer_share"] for r in asked) / len(asked), 3) if asked else None,
            "asked_ids": [r["id"] for r in asked],
        }
    write(ROOT / "scores" / "track2_measures.json", json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    if sys.argv[1] == "t2":
        t2(sys.argv[2:])
