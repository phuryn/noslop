"""Track 3: does human composition survive? Real human words as the writer.

BRING YOUR OWN TEXTS: put 250-350-word excerpts of prose you wrote yourself, published before
ChatGPT's release (Nov 30, 2022), in evidence/human/NN-anything.md. They are not shipped with this
repository (the published run used 4 excerpts of the author's own 2022 writing; only aggregate
numbers are included). evidence/human/ is gitignored.

python scripts/run_track3.py
For each human excerpt H (human/NN-*.md):
  outline  = model reduces H to paraphrased bullets (no wording kept)
  D        = fresh model call composes a newsletter section from the outline only (AI composition)
  A, B2, C = rewrite-only of D (Track 1 wrapper)
  A-notes, B2-notes = rewrite of D with H supplied up front as the writer's notes (same wrapper + notes)
  A-ask, B2-ask     = same, but the user's request says "Interview me first" (both skills get it)
  A-int, B2-int     = interactive wrapper; questions answered by an EXTRACTIVE writer who may only
                      copy whole sentences of H (every answer sentence verified as a substring of H)
Writes track3/<variant>/<NN>.md, track3/manifest.json, track3/raw/*.json.
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor

from common import ROOT, build_prompt, extract, read, run_claude, write

IDS = sorted(int(p.name[:2]) for p in (ROOT / "human").glob("[0-9][0-9]-*.md")) if (ROOT / "human").exists() else []
ASK = "Humanize this text. Interview me first: ask me what you need, then write it."
T3 = ROOT / "track3"

OUTLINE = """Reduce this text to a bullet outline of its points and facts: 5-9 bullets, each under 14 words, paraphrased in your own neutral words (do not reuse its phrasing). Keep numbers and names. Output only the bullets.

<text>
{h}
</text>"""

COMPOSE = """Write a ~300-word section for a product management newsletter, in first person, based on this outline:

{outline}

Reply with just the text, ready to paste."""

EXTRACT = """You are the writer of the ORIGINAL TEXT below. A writing tool asked you questions about an AI draft of your piece. Answer each question ONLY by copying whole sentences, word for word, from your original text. Copy 0-4 sentences per question. If nothing in your text answers a question, write "skip". Do not change, add, or join words. Number the answers in the order asked.

<original_text>
{h}
</original_text>

<questions>
{q}
</questions>"""


def norm(s):
    return re.sub(r"\s+", " ", s.replace("’", "'").replace("“", '"').replace("”", '"')).strip()


def verify_extractive(answers, h):
    """Keep only sentences that occur verbatim in H. Returns (clean_answers, dropped_sentences)."""
    hn = norm(h)
    out, dropped = [], []
    for line in answers.splitlines():
        m = re.match(r"\s*(\d+[.)])\s*(.*)", line)
        if not m:
            if line.strip():
                body, num = line.strip(), None
            else:
                continue
        else:
            num, body = m.group(1), m.group(2)
        if body.strip().lower().strip('"') == "skip":
            out.append(f"{num} skip" if num else "skip")
            continue
        sents = re.split(r"(?<=[.!?])\s+", body)
        keep = []
        for s in sents:
            s2 = norm(s).strip('"')
            if s2 and s2 in hn:
                keep.append(s.strip().strip('"'))
            elif s2:
                dropped.append(s)
        txt = " ".join(keep) if keep else "skip"
        out.append(f"{num} {txt}" if num else txt)
    return "\n".join(out), dropped


def prepare(i):
    hp = next((ROOT / "human").glob(f"{i:02d}-*.md"))
    h = read(hp)
    name = f"{i:02d}.md"
    write(T3 / "H" / name, h)
    if not (T3 / "D" / name).exists():
        outline = run_claude(OUTLINE.format(h=h), model="sonnet", tag=f"t3-outline-{i}")
        d = run_claude(COMPOSE.format(outline=outline), model="sonnet", tag=f"t3-compose-{i}")
        write(T3 / "raw" / f"{i:02d}-outline.md", outline)
        write(T3 / "D" / name, d.strip() + "\n")
    return {"id": i, "file": name, "genre": "newsletter section", "source": hp.name}


def variant(i, v):
    name = f"{i:02d}.md"
    out = T3 / v / name
    if out.exists():
        return f"skip {v} {i}"
    h, d = read(T3 / "H" / name), read(T3 / "D" / name)
    arm = v.split("-")[0]
    log = {"id": i, "variant": v}
    if v in ("A", "B2", "C"):
        r = run_claude(build_prompt(arm, d, mode="rewrite"), model="sonnet", tag=f"t3-{v}-{i}")
        final = extract("final", r)
    elif v.endswith("-notes"):
        r = run_claude(build_prompt(arm, d, mode="rewrite", notes=h), model="sonnet", tag=f"t3-{v}-{i}")
        final = extract("final", r)
    else:  # -int (skill decides whether to ask) or -ask (the user explicitly asks to be interviewed)
        us = ASK if v.endswith("-ask") else None
        r1 = run_claude(build_prompt(arm, d, mode="interactive", user_says=us), model="sonnet", tag=f"t3-{v}-{i}-1")
        q, final = extract("questions", r1), extract("final", r1)
        log["reply1"], log["asked"] = r1, bool(q)
        if q and not final:
            raw_ans = run_claude(EXTRACT.format(h=h, q=q), model="sonnet", tag=f"t3-extract-{v}-{i}")
            ans, dropped = verify_extractive(raw_ans, h)
            log.update(questions=q, raw_answers=raw_ans, answers=ans, dropped_non_verbatim=dropped)
            r2 = run_claude(build_prompt(arm, d, mode="interactive", qa=[(q, ans)], user_says=us), model="sonnet",
                            tag=f"t3-{v}-{i}-2")
            log["reply2"] = r2
            final = extract("final", r2)
        r = log.get("reply2", r1)
    log["reply"] = r
    log["final"] = final
    write(T3 / "raw" / f"{v}-{i:02d}.json", json.dumps(log, indent=2, ensure_ascii=False))
    write(out, (final or "").strip() + "\n")
    return f"{v} {i} {'ok' if final else 'NO-FINAL'}"


if __name__ == "__main__":
    if not IDS:
        raise SystemExit("Add your own pre-2023 human excerpts to evidence/human/NN-name.md first")
    with ThreadPoolExecutor(4) as ex:
        man = list(ex.map(prepare, IDS))
    write(T3 / "manifest.json", json.dumps(man, indent=2))
    jobs = [(i, v) for i in IDS for v in ("A", "B2", "C", "A-notes", "B2-notes", "A-int", "B2-int", "A-ask", "B2-ask")]
    with ThreadPoolExecutor(6) as ex:
        for m in ex.map(lambda j: variant(*j), jobs):
            print(m, flush=True)
