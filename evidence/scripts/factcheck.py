"""Measure 2: fact and meaning preservation, one Opus checker call per (original, edit) pair.

python scripts/factcheck.py A B C       -> scores/factcheck/<arm>/<id>.json + scores/factcheck_summary.json
Track 2/3 use check_pair() with an extra 'allowed sources' block (writer answers / notes).
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor

from common import DATA, ROOT, parse_json, read, run_claude, write

PROMPT = """You are checking an edit of a text for factual and meaning preservation. Be strict but fair.

<original>
{orig}
</original>
{extra}
<edit>
{edit}
</edit>

List, as JSON:
- "dropped": facts, claims, commitments, caveats, calls to action, or concrete details present in the ORIGINAL but missing from the EDIT. Each item: {{"item": "...", "severity": "major" | "minor"}}. Major = a reader would know or do something different, or a concrete fact (number, name, date, price, deadline, condition) is gone. Minor = a nuance is lost.
- "changed": facts or claims whose meaning, value, scope, certainty, or actor changed. Same item format.
- "added": claims or details in the EDIT that are not in the ORIGINAL{allowed_note}. Each item: {{"item": "...", "severity": "major" | "minor"}}.
- "invented_specifics": the subset of added content that is SPECIFIC FACTUAL content with no basis in the ORIGINAL{allowed_note}: a number, name, date, price, quote, customer, event or anecdote, or a first-person experience. List the exact phrase from the EDIT.
- "meaning_preserved": 1-5 (5 = everything a reader needs is there and nothing false was introduced).

NOT problems: rewording, merging, reordering, splitting, cutting pure filler or hype that carried no information (e.g. "in today's fast-paced world", "we're thrilled"), removing a vague flourish, a reasonable paraphrase, or a generic connective sentence. A template placeholder like [Your Name] kept or removed is not a problem.

Return only the JSON object."""


def check_pair(orig, edit, tag, allowed=None):
    extra = ""
    allowed_note = ""
    if allowed:
        extra = f"\nThe writer also supplied this material, which the edit MAY use:\n<writer_material>\n{allowed}\n</writer_material>\n"
        allowed_note = " or in the writer material"
    reply = run_claude(PROMPT.format(orig=orig, edit=edit, extra=extra, allowed_note=allowed_note),
                       model="opus", tag=tag)
    return parse_json(reply)


def job(arm, rec):
    out = DATA / "scores" / "factcheck" / arm / f"{rec['id']:02d}.json"
    if out.exists():
        return json.loads(read(out))
    orig = read(DATA / "inputs" / rec["file"])
    edit = read(DATA / "outputs" / arm / rec["file"])
    res = check_pair(orig, edit, tag=f"fc-{arm}-{rec['id']}")
    write(out, json.dumps(res, indent=2, ensure_ascii=False))
    return res


def summarize(arms):
    man = json.loads(read(DATA / "inputs" / "manifest.json"))
    summ = {}
    for arm in arms:
        rs = [json.loads(read(DATA / "scores" / "factcheck" / arm / f"{r['id']:02d}.json")) for r in man]
        major = lambda k: sum(1 for r in rs for x in r.get(k, []) if isinstance(x, dict) and x.get("severity") == "major")
        summ[arm] = {
            "texts": len(rs),
            "texts_with_invented_specifics": sum(1 for r in rs if r.get("invented_specifics")),
            "invented_specifics_total": sum(len(r.get("invented_specifics", [])) for r in rs),
            "major_dropped": major("dropped"), "major_changed": major("changed"), "major_added": major("added"),
            "texts_with_any_major": sum(1 for r in rs if any(isinstance(x, dict) and x.get("severity") == "major"
                                                           for k in ("dropped", "changed", "added") for x in r.get(k, []))),
            "mean_meaning_preserved": round(sum(r.get("meaning_preserved", 0) for r in rs) / len(rs), 2),
        }
    write(DATA / "scores" / "factcheck_summary.json", json.dumps(summ, indent=2))
    for arm, s in summ.items():
        print(arm, s)


if __name__ == "__main__":
    arms = sys.argv[1:] or ["A", "B", "C"]
    man = json.loads(read(DATA / "inputs" / "manifest.json"))
    jobs = [(a, r) for r in man for a in arms]
    with ThreadPoolExecutor(6) as ex:
        list(ex.map(lambda j: job(*j), jobs))
    summarize(arms)
