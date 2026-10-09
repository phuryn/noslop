"""Arm E: Emulate-1 (tryemulate.ai /v1/humanize), the model launched 2026-09-28 as "undetectable".

python scripts/run_emulate.py --estimate | --run            (/humanize arm E)
python scripts/run_emulate.py --write --estimate | --run    (/write generation track -> gen/E-write/)
Inputs: the 16 Track 1 drafts (-> outputs/E/) and the 4 Track 3 AI drafts D (-> track3/E/).
Key: environment variable EMULATE_API_KEY (never printed or logged).
Generation track: /write gets the same short request from inputs/briefs.json that produced each AI
draft, at the draft's word count (min 50). No `style` object on either endpoint: the other arms got
only the request / the text, so Emulate runs on its defaults too.
Budget used in the published run: hard cap 12,000 charged words; one call per text,
no retries on a text that was charged. words.charged is logged per call to scores/emulate_log.csv.
"""
import csv
import json
import os
import re
import sys
import urllib.error
import urllib.request

from common import REPO, ROOT, read, write

CAP = 12000
URL = "https://www.tryemulate.ai/v1/humanize"
LOG = ROOT / "scores" / "emulate_log.csv"


def key():
    k = os.environ.get("EMULATE_API_KEY")
    if not k:
        raise SystemExit("Set the EMULATE_API_KEY environment variable")
    return k


WRITE_URL = "https://www.tryemulate.ai/v1/write"


def write_items():
    """Generation track: Emulate /write gets the same short request that produced each AI draft."""
    briefs = {b["id"]: b for b in json.loads(read(ROOT / "inputs" / "briefs.json"))}
    for r in json.loads(read(ROOT / "inputs" / "manifest.json")):
        n = max(50, len(read(ROOT / "inputs" / r["file"]).split()))
        yield "gen", briefs[r["id"]]["request"], n, ROOT / "gen" / "E-write" / r["file"]


def items():
    if os.environ.get("HUMANIZER_SET"):   # a held-out set: inputs/ -> outputs/E/ only
        base = ROOT / os.environ["HUMANIZER_SET"]
        for r in json.loads(read(base / "inputs" / "manifest.json")):
            yield os.environ["HUMANIZER_SET"], base / "inputs" / r["file"], base / "outputs" / "E" / r["file"]
        return
    man = json.loads(read(ROOT / "inputs" / "manifest.json"))
    for r in man:
        yield "t1", ROOT / "inputs" / r["file"], ROOT / "outputs" / "E" / r["file"]
    t3m = ROOT / "track3" / "manifest.json"   # only if you built Track 3 with your own texts
    for r in (json.loads(read(t3m)) if t3m.exists() else []):
        yield "t3", ROOT / "track3" / "D" / r["file"], ROOT / "track3" / "E" / r["file"]


def spent():
    if not LOG.exists():
        return 0
    return sum(int(r["words_charged"] or 0) for r in csv.DictReader(open(LOG, encoding="utf-8")))


def call(k, text, url=URL, body=None):
    req = urllib.request.Request(url, data=json.dumps(body or {"text": text}).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {k}", "Content-Type": "application/json",
                                          "User-Agent": "curl/8.9.1", "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode())


def main_write(run):
    todo = [(g, req, n, dst) for g, req, n, dst in write_items() if not dst.exists()]
    used = spent()
    print(f"spent so far {used}; /write to do {len(todo)} texts, ~{sum(t[2] for t in todo)} words requested; cap {CAP}")
    if not run:
        return
    k = key()
    with open(LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for g, req, n, dst in todo:
            if used + n * 1.2 > CAP:
                print(f"cap reached before {dst.name}; stopping")
                break
            try:
                res = call(k, None, url=WRITE_URL, body={"prompt": req, "words": n})
            except urllib.error.HTTPError as e:
                body = e.read().decode()[:200]
                w.writerow([g, dst.name, n, 0, used, "", "", f"HTTP {e.code}: {body}"])
                f.flush()
                print(f"HTTP {e.code} on {dst.name}: {body}")
                continue
            charged = int((res.get("words") or {}).get("charged") or 0)
            used += charged
            write(dst, (res.get("text") or "").strip() + "\n")
            meta = {k2: v for k2, v in res.items() if k2 != "text"}
            write(dst.parent / "raw" / (dst.stem + ".json"), json.dumps(meta, indent=2))
            w.writerow([g, dst.name, n, charged, used, res.get("reads_human"), res.get("elapsed"), "ok"])
            f.flush()
            print(f"{used:5d} {g} {dst.name:40} requested={n} charged={charged}", flush=True)


def main(run):
    todo = [(g, src, dst) for g, src, dst in items() if not dst.exists()]
    est = sum(len(read(s).split()) for _, s, _ in todo)
    used = spent()
    print(f"spent so far {used}; to do {len(todo)} texts, ~{est} input words; cap {CAP}")
    if not run:
        return
    k = key()
    new = not LOG.exists()
    with open(LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["group", "file", "input_words", "words_charged", "cumulative", "reads_human", "elapsed", "status"])
        for g, src, dst in todo:
            text = read(src).strip()
            n = len(text.split())
            if used + n > CAP:
                print(f"cap reached before {src.name}; stopping")
                break
            try:
                res = call(k, text)
            except urllib.error.HTTPError as e:
                body = e.read().decode()[:200]
                w.writerow([g, src.name, n, 0, used, "", "", f"HTTP {e.code}: {body}"])
                f.flush()
                print(f"HTTP {e.code} on {g} {src.name}: {body}")
                continue
            charged = int((res.get("words") or {}).get("charged") or 0)
            used += charged
            write(dst, (res.get("text") or "").strip() + "\n")
            meta = {k2: v for k2, v in res.items() if k2 != "text"}
            write(dst.parent / "raw" / (dst.stem + ".json"), json.dumps(meta, indent=2))
            w.writerow([g, src.name, n, charged, used, res.get("reads_human"), res.get("elapsed"), "ok"])
            f.flush()
            print(f"{used:5d} {g} {src.name:40} charged={charged} reads_human={res.get('reads_human')}", flush=True)


if __name__ == "__main__":
    if "--write" in sys.argv:
        main_write("--run" in sys.argv)
    else:
        main("--run" in sys.argv)
