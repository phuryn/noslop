"""Measure 3: blind ranking by two model families (Codex/GPT and Claude Opus).

python scripts/judge.py <run> <arms,comma> [--meaning] [--ids 1,2] [--judges codex,opus]
  run   : output folder name under scores/judges/ (e.g. t1, t1v2, t2)
  arms  : candidates; 'O' = the unedited input. Texts come from outputs/<arm>/<file>,
          or from a custom resolver for tracks 2/3 (see candidates()).
Each text is judged in two independent random orders per judge. Labels are neutral numbers.
"""
import argparse
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor

from common import DATA, ROOT, parse_json, read, run_claude, run_codex, write

HUMAN_PROMPT = """You are an experienced editor. Below are {n} versions of the same {genre}. They cover the same content. Some may have been written or edited by AI.

{versions}

Answer as JSON only:
{{
  "human_rank": {{{rank_keys}}},     // rank ALL versions by how much each reads like a skilled human wrote it for this purpose (1 = most human). No ties.
  "send": "<label>",                 // if you were the writer, which ONE would you send or publish? Weigh quality, clarity, credibility and human feel.
  "tells": {{{tell_keys}}},          // the most noticeable AI-writing tell in each version, or "none"
  "reason": "<one or two sentences>"
}}"""

SEND_PROMPT = """Here is a {genre} that a writer drafted. It shows what the writer meant.

<original_what_the_writer_meant>
{orig}
</original_what_the_writer_meant>
{answers_block}
Below are {n} rewrites of it.

{versions}

You are the writer. Which ONE would you send? It must say what you meant (same facts, commitments, caveats) and read like you wrote it. If none keeps the meaning, say none.

Answer as JSON only:
{{"send": "<label, or none>", "reason": "<one or two sentences>"}}"""

MEANING_ANSWERS_PROMPT = """You are checking edits for faithfulness. Here is the ORIGINAL {genre}, and the writer's own answers to questions an editing tool asked them about it. An edit may use facts from the writer's answers; anything else new is an addition.

<original>
{orig}
</original>

<writer_answers>
{answers}
</writer_answers>

{versions}

Rank the edited versions by how faithfully each keeps the original's meaning, facts, numbers, commitments, and caveats AND adds only facts the writer supplied in their answers (1 = most faithful). Using the writer's answers is not a fault; adding anything found in neither the original nor the answers is. Ignore style and length except where a fact, nuance, or commitment is lost, changed, or added. No ties.

Answer as JSON only:
{{"meaning_rank": {{{rank_keys}}}, "reason": "<one or two sentences>"}}"""

MEANING_PROMPT = """You are checking edits for faithfulness. Here is the ORIGINAL {genre}, followed by {n} edited versions.

<original>
{orig}
</original>

{versions}

Rank the edited versions by how faithfully each keeps the original's meaning, facts, numbers, commitments, and caveats (1 = most faithful). Ignore style and length except where a fact, nuance, or commitment is lost, changed, or added. No ties.

Answer as JSON only:
{{"meaning_rank": {{{rank_keys}}}, "reason": "<one or two sentences>"}}"""


def load_manifest():
    return json.loads(read(DATA / "inputs" / "manifest.json"))


def text_for(arm, rec):
    if arm == "O":
        return read(DATA / "inputs" / rec["file"])
    if "/" in arm:                      # e.g. track2/A-int
        return read(ROOT / arm / rec["file"])
    return read(DATA / "outputs" / arm / rec["file"])


ANSWERS_FROM = None   # e.g. "track2/B3-int": show that arm's simulated-writer answers in the meaning question


def _answers(rec):
    if not ANSWERS_FROM:
        return None
    p = ROOT / ANSWERS_FROM / "raw" / f"{rec['id']:02d}.json"
    if not p.exists():
        return None
    d = json.loads(read(p))
    return d.get("answers") if d.get("asked") else None


def _exists(arm, rec):
    try:
        text_for(arm, rec)
        return True
    except FileNotFoundError:
        return False


def render(cands, order):
    return "\n\n".join(f"<version label=\"{i + 1}\">\n{cands[a].strip()}\n</version>" for i, a in enumerate(order))


OPENROUTER_JUDGES = {  # flagship of each family on OpenRouter, 2026-10-08; reasoning effort "high" (Codex also runs at high)
    "grok": "x-ai/grok-4.7",
    "deepseek": "deepseek/deepseek-v4-pro-0813",
    "qwen": "qwen/qwen3.8-max-0902",
}
SPEND_CAP = 63.4   # cumulative: $46.39 before informed-send + $17 for informed send and the interview comparison


def call_openrouter(model, prompt, tag):
    import apis
    if apis.total_spend() > SPEND_CAP - 0.5:
        raise RuntimeError(f"spend cap reached ({apis.total_spend():.2f} USD)")
    body = {"model": model, "reasoning": {"effort": "high"}, "max_tokens": 16000,
            "messages": [{"role": "system", "content": "You are a careful, impartial editor."},
                         {"role": "user", "content": prompt}]}
    for attempt in range(3):
        r = apis.post(apis.OR_CHAT, body, apis.OR_HDR())
        if r["ok"] and r["d"].get("choices"):
            u = r["d"].get("usage") or {}
            apis.log_spend({"api": "openrouter-chat", "model": model, "tag": tag, "cost": u.get("cost") or 0,
                            "in": u.get("prompt_tokens"), "out": u.get("completion_tokens"), "ms": r["ms"]})
            return r["d"]["choices"][0]["message"].get("content") or ""
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"openrouter {model} failed: {r.get('error')}")


def call(judge, prompt, tag):
    if judge == "codex":
        return run_codex(prompt, tag=tag, effort="high")
    if judge in OPENROUTER_JUDGES:
        return call_openrouter(OPENROUTER_JUDGES[judge], prompt, tag)
    return run_claude(prompt, model="opus", tag=tag, system="You are a careful, impartial editor.")


def one(run, judge, kind, rec, arms, k, genre_override=None):
    out = DATA / "scores" / "judges" / run / judge / kind / f"{rec['id']:02d}-p{k}.json"
    if out.exists():
        return
    arms = [a for a in arms if _exists(a, rec)]   # e.g. Emulate has no output for texts under its 40-word minimum
    cands = {a: text_for(a, rec) for a in arms}
    rng = random.Random(f"{run}|{judge}|{kind}|{rec['id']}|{k}")
    order = list(arms)
    rng.shuffle(order)
    n = len(order)
    keys = ", ".join(f'"{i + 1}": _' for i in range(n))
    genre = genre_override or rec["genre"]
    if kind == "send":
        ans = _answers(rec)
        ablock = ("\nThe writer also answered an editing tool's questions about it. These answers are also what the "
                  "writer meant, and a rewrite may use them:\n\n<writer_answers>\n" + ans + "\n</writer_answers>\n") if ans else ""
        prompt = SEND_PROMPT.format(genre=genre, orig=read(DATA / "inputs" / rec["file"]), n=n,
                                    versions=render(cands, order), answers_block=ablock)
        for attempt in range(3):
            reply = call(judge, prompt, tag=f"j-{run}-{judge}-send-{rec['id']}-{k}")
            try:
                res = parse_json(reply)
                pick = str(res["send"]).strip().strip('"').lower()
                if pick not in ("none",) and pick not in {str(i + 1) for i in range(n)}:
                    raise ValueError(f"bad pick {pick}")
                break
            except Exception as e:  # noqa: BLE001
                res, err = None, e
        if res is None:
            raise RuntimeError(f"send parse failed {judge} {rec['id']}: {err}")
        res["label_to_arm"] = {str(i + 1): a for i, a in enumerate(order)}
        res["picked_arm"] = "none" if pick == "none" else res["label_to_arm"][pick]
        write(out, json.dumps(res, indent=2, ensure_ascii=False))
        return
    if kind == "human":
        prompt = HUMAN_PROMPT.format(n=n, genre=genre, versions=render(cands, order),
                                     rank_keys=keys, tell_keys=keys.replace("_", '"..."'))
    else:
        orig = read(DATA / "inputs" / rec["file"]) if "orig" not in rec else rec["orig"]
        answers = _answers(rec)
        if answers:
            prompt = MEANING_ANSWERS_PROMPT.format(genre=genre, orig=orig, answers=answers,
                                                   versions=render(cands, order), rank_keys=keys)
        else:
            prompt = MEANING_PROMPT.format(n=n, genre=genre, orig=orig, versions=render(cands, order), rank_keys=keys)
    for attempt in range(3):
        reply = call(judge, prompt, tag=f"j-{run}-{judge}-{kind}-{rec['id']}-{k}")
        try:
            res = parse_json(reply)
            rk = res["human_rank" if kind == "human" else "meaning_rank"]
            ranks = sorted(int(v) for v in rk.values())
            if ranks != list(range(1, n + 1)):
                raise ValueError(f"bad ranks {rk}")
            break
        except Exception as e:  # noqa: BLE001
            res = None
            err = e
    if res is None:
        raise RuntimeError(f"judge parse failed {judge} {kind} {rec['id']}: {err}")
    res["label_to_arm"] = {str(i + 1): a for i, a in enumerate(order)}
    write(out, json.dumps(res, indent=2, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("arms")
    ap.add_argument("--meaning", action="store_true", help="also run the meaning call (excludes O)")
    ap.add_argument("--only-meaning", action="store_true")
    ap.add_argument("--ids", default="")
    ap.add_argument("--judges", default="codex,opus")
    ap.add_argument("--perms", type=int, default=2)
    ap.add_argument("--manifest", default="", help="alternative manifest (e.g. track3/manifest.json)")
    ap.add_argument("--answers-from", default="", help="interview arm whose writer answers the meaning judge sees")
    ap.add_argument("--send-only", action="store_true", help="pre-registered informed-send judgment (original shown)")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    global ANSWERS_FROM
    ANSWERS_FROM = a.answers_from or None
    arms = a.arms.split(",")
    man = json.loads(read(ROOT / a.manifest)) if a.manifest else load_manifest()
    if a.ids:
        keep = {int(x) for x in a.ids.split(",")}
        man = [r for r in man if r["id"] in keep]
    jobs = []
    for judge in a.judges.split(","):
        for rec in man:
            for k in range(a.perms):
                if a.send_only:
                    jobs.append((a.run, judge, "send", rec, [x for x in arms if x != "O"], k))
                    continue
                if not a.only_meaning:
                    jobs.append((a.run, judge, "human", rec, arms, k))
                if a.meaning or a.only_meaning:
                    jobs.append((a.run, judge, "meaning", rec, [x for x in arms if x != "O"], k))
    # interleave judges so codex and opus calls run side by side
    jobs.sort(key=lambda j: (j[3]["id"], j[5], j[1]))
    with ThreadPoolExecutor(a.workers) as ex:
        futs = [ex.submit(one, *j) for j in jobs]
        for f in futs:
            f.result()
    print("done", len(jobs))


if __name__ == "__main__":
    main()
