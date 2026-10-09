"""v6c: v6a plus a narrow repair. HUMANIZER_SET=holdout4 python scripts/run_v6c.py

Step 1 reuses v6a's output (outputs/V6A/). Step 2 is one Sonnet call that fixes only meaning-bearing items.
Writes outputs/V6C/<file> and outputs/V6C/raw/<id>.json.
"""
import json
from concurrent.futures import ThreadPoolExecutor

from common import DATA, extract, read, run_claude, write

REPAIR = """Below is an ORIGINAL text and a REWRITE of it. The rewrite is meant to say exactly what the original says, in a more natural voice.

<original>
{orig}
</original>

<rewrite>
{rewrite}
</rewrite>

Fix only meaning in the rewrite. Check these, and nothing else:
- numbers, prices, dates, times, names, and places
- commitments and who makes them ("we'll confirm" is not "I'll send")
- caveats, conditions, and hedges
- claim strength ("can help" is not "will", "about" is not exact)
- tense and status ("we're refunding" is not "I've refunded")
- anything the rewrite adds that the original does not say (a fact, reason, example, benefit, or timing): remove it

Change as few words as possible. Keep the rewrite's wording, voice, and structure everywhere else. Never change a sentence back to the original's wording just because it is worded differently; change it only if its meaning differs. If nothing needs fixing, return the rewrite unchanged.

End your reply with the final text only, between <final> and </final>."""


def job(rec):
    out = DATA / "outputs" / "V6C" / rec["file"]
    if out.exists():
        return f"skip {rec['id']}"
    orig = read(DATA / "inputs" / rec["file"])
    loose = read(DATA / "outputs" / "V6A" / rec["file"])
    reply = run_claude(REPAIR.format(orig=orig, rewrite=loose), model="sonnet", tag=f"v6c-repair-{rec['id']}")
    final = extract("final", reply)
    write(DATA / "outputs" / "V6C" / "raw" / f"{rec['id']:02d}.json",
          json.dumps({"v6a": loose, "reply": reply}, indent=2, ensure_ascii=False))
    write(out, (final or reply).strip() + "\n")
    return f"{'ok' if final else 'NO-FINAL'} {rec['id']}"


if __name__ == "__main__":
    man = json.loads(read(DATA / "inputs" / "manifest.json"))
    with ThreadPoolExecutor(6) as ex:
        for m in ex.map(job, man):
            print(m, flush=True)
