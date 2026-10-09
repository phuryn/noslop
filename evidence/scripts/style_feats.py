"""Style features of rewrites vs the draft: contractions, first person, new 4-grams (how much was recomposed), length.
python scripts/style_feats.py ARM [ARM...]   (env HUMANIZER_SET picks the set)"""
import json, re, statistics, sys
from common import DATA, read


def words(t):
    return [x.lower().replace("’", "'") for x in re.findall(r"[A-Za-z0-9'’]+", t)]


def feats(t, orig):
    w = words(t); n = max(1, len(w)); ow = words(orig)
    og = {tuple(ow[i:i + 4]) for i in range(len(ow) - 3)}
    g = [tuple(w[i:i + 4]) for i in range(len(w) - 3)]
    return {"contractions_per100": 100 * sum(1 for x in w if re.search(r"'(s|re|ve|ll|d|t|m)$", x)) / n,
            "first_person_per100": 100 * sum(1 for x in w if x in ("i", "we", "our", "my", "us", "me") or re.match(r"(i|we)'", x)) / n,
            "new_4grams": 1 - sum(1 for x in g if x in og) / max(1, len(g)),
            "len_ratio": len(w) / max(1, len(ow)), "exclam": t.count("!")}


if __name__ == "__main__":
    man = json.loads(read(DATA / "inputs" / "manifest.json"))
    for arm in sys.argv[1:]:
        fs = [feats(read(DATA / "outputs" / arm / m["file"]), read(DATA / "inputs" / m["file"])) for m in man
              if (DATA / "outputs" / arm / m["file"]).exists()]
        print(arm, {k: round(statistics.mean(f[k] for f in fs), 2) for k in fs[0]}, len(fs))
