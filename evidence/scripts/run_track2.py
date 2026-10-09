"""Track 2: interview mode with a simulated writer who holds the hidden brief.

python scripts/run_track2.py A B [B2]
-> track2/<arm>-int/<file> (final) and track2/<arm>-int/raw/<id>.json (questions, answers, replies)
Same interactive wrapper for every arm (common.build_prompt mode="interactive"). One round of questions max.
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor

from common import ROOT, build_prompt, extract, read, run_claude, write

MANIFEST = json.loads(read(ROOT / "inputs" / "manifest.json"))
BRIEFS = {b["id"]: b for b in json.loads(read(ROOT / "inputs" / "briefs.json"))}

WRITER = """You are {writer}. You asked an AI assistant for a {genre} with this request:

"{request}"

It wrote a draft, and a writing tool is now asking you some questions about it.

Everything you know beyond your request:
{facts}

The draft:
<draft>
{draft}
</draft>

The questions:
<questions>
{questions}
</questions>

Answer the way you would in a quick voice note to a colleague: first person, plain, a bit informal, one to three sentences per question, numbered in the order asked. Use ONLY what is in your request and your notes above. If your notes don't cover a question, say you don't know or that you'd rather skip it. Never make up a number, name, date, or story that is not in your notes. Output only the numbered answers."""


def job(arm, rec):
    name = f"{arm}-int"
    out = ROOT / "track2" / name / rec["file"]
    if out.exists():
        return f"skip {name} {rec['id']}"
    b = BRIEFS[rec["id"]]
    draft = read(ROOT / "inputs" / rec["file"])
    log = {"id": rec["id"], "arm": arm}
    r1 = run_claude(build_prompt(arm, draft, mode="interactive"), model="sonnet", tag=f"t2-{arm}-{rec['id']}-1")
    log["reply1"] = r1
    q = extract("questions", r1)
    final = extract("final", r1)
    if q and not final:
        ans = run_claude(WRITER.format(writer=b["writer"], genre=b["genre"], request=b["request"],
                                       facts="\n".join(f"- {f}" for f in b["hidden_facts"]),
                                       draft=draft, questions=q),
                         model="sonnet", tag=f"t2-writer-{arm}-{rec['id']}")
        log["questions"], log["answers"] = q, ans
        r2 = run_claude(build_prompt(arm, draft, mode="interactive", qa=[(q, ans)]), model="sonnet",
                        tag=f"t2-{arm}-{rec['id']}-2")
        log["reply2"] = r2
        final = extract("final", r2)
    log["asked"] = bool(q)
    log["final"] = final
    write(ROOT / "track2" / name / "raw" / f"{rec['id']:02d}.json", json.dumps(log, indent=2, ensure_ascii=False))
    write(out, (final or "").strip() + "\n")
    return f"{'asked' if q else 'no-q'} {name} {rec['id']} {'' if final else 'NO-FINAL'}"


if __name__ == "__main__":
    arms = sys.argv[1:] or ["A", "B"]
    jobs = [(a, r) for r in MANIFEST for a in arms]
    with ThreadPoolExecutor(6) as ex:
        for m in ex.map(lambda j: job(*j), jobs):
            print(m, flush=True)
