"""Fact checks for the Emulate arms.

python scripts/emulate_measures.py t1    -> scores/factcheck/E/NN.json (E vs the original draft, same checker as Track 1)
python scripts/emulate_measures.py gen   -> scores/gen_check/<cand>/NN.json: every candidate in the generation track
                                            checked against the writer's REQUEST (what a writer actually supplied)
Generation candidates: O (the Sonnet/GPT draft), gen/E-write (Emulate /write), B3 and A (O humanized by
our skill v3 and by blader/humanizer).
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor

from common import ROOT, parse_json, read, run_claude, write
from factcheck import check_pair

GEN = """A writer typed this request into a writing tool:

<request>
{req}
</request>

The tool produced this {genre}:

<text>
{text}
</text>

Check the text against the request. Return only JSON:
{{
  "unsupported_specifics": ["..."],   // specific factual claims in the text that the request does not state or directly imply: numbers, names, dates, prices, quotes, customers, events or anecdotes, first-person experiences, product capabilities, results. Exact phrase from the text.
  "request_facts_missing_or_changed": ["..."],   // facts given in the request that are missing from the text or stated differently
  "language_errors": ["..."]           // spelling or grammar errors in the text (exact phrase), if any
}}
Generic connective statements, a greeting or sign-off, a placeholder like [Name], and reasonable framing are NOT unsupported specifics."""

MAN = json.loads(read(ROOT / "inputs" / "manifest.json"))
BRIEFS = {b["id"]: b for b in json.loads(read(ROOT / "inputs" / "briefs.json"))}


def t1_one(rec):
    out = ROOT / "scores" / "factcheck" / "E" / f"{rec['id']:02d}.json"
    src = ROOT / "outputs" / "E" / rec["file"]
    if out.exists() or not src.exists():
        return
    res = check_pair(read(ROOT / "inputs" / rec["file"]), read(src), tag=f"fc-E-{rec['id']}")
    write(out, json.dumps(res, indent=2, ensure_ascii=False))


def cand_path(c, rec):
    if c == "O":
        return ROOT / "inputs" / rec["file"]
    if "/" in c:
        return ROOT / c / rec["file"]
    return ROOT / "outputs" / c / rec["file"]


def gen_one(c, rec):
    out = ROOT / "scores" / "gen_check" / c.replace("/", "_") / f"{rec['id']:02d}.json"
    if out.exists():
        return
    b = BRIEFS[rec["id"]]
    reply = run_claude(GEN.format(req=b["request"], genre=b["genre"], text=read(cand_path(c, rec))),
                       model="opus", tag=f"gen-{c}-{rec['id']}")
    write(out, json.dumps(parse_json(reply), indent=2, ensure_ascii=False))


def summarize_gen(cands):
    s = {}
    for c in cands:
        rs = [json.loads(read(ROOT / "scores" / "gen_check" / c.replace("/", "_") / f"{r['id']:02d}.json")) for r in MAN]
        s[c] = {"texts": len(rs),
                "texts_with_unsupported_specifics": sum(1 for r in rs if r.get("unsupported_specifics")),
                "unsupported_specifics_total": sum(len(r.get("unsupported_specifics", [])) for r in rs),
                "request_facts_missing_or_changed": sum(len(r.get("request_facts_missing_or_changed", [])) for r in rs),
                "language_errors_total": sum(len(r.get("language_errors", [])) for r in rs),
                "texts_with_language_errors": sum(1 for r in rs if r.get("language_errors"))}
    write(ROOT / "scores" / "gen_check_summary.json", json.dumps(s, indent=2))
    for c, v in s.items():
        print(c, v)


if __name__ == "__main__":
    if sys.argv[1] == "t1":
        with ThreadPoolExecutor(6) as ex:
            list(ex.map(t1_one, MAN))
    else:
        cands = ["O", "gen/E-write", "B3", "A"]
        jobs = [(c, r) for r in MAN for c in cands]
        with ThreadPoolExecutor(6) as ex:
            list(ex.map(lambda j: gen_one(*j), jobs))
        summarize_gen(cands)
