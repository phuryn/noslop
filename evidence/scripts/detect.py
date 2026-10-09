"""Measure 4: three open-source AI-text detectors, run locally (no API key, no account).

Needs torch + transformers (pip install torch transformers sentencepiece protobuf). Run:
  python scripts/detect.py               (downloads the three models from Hugging Face on first run)
Calibration texts: put your own pre-2023 human excerpts in evidence/human/ (not shipped).
Scores every .md under human/, inputs/, outputs/*/, track2/*/, track3/*/ (raw/ folders skipped),
caching by content hash in scores/detectors_cache.json. Output: scores/detectors.csv.
--cached-only writes the CSV from the cache without scoring anything new.
Each score is P(AI) in [0,1]. Long texts are split into ~300-word windows; the score is the
word-weighted mean of the windows.
"""
import csv
import hashlib
import json
import re
from html import unescape
from pathlib import Path

import torch
import torch.nn as nn
from transformers import AutoConfig, AutoModel, AutoModelForSequenceClassification, AutoTokenizer, PreTrainedModel

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scores" / "detectors_cache.json"
torch.set_num_threads(8)


class DesklibAIDetectionModel(PreTrainedModel):  # from the desklib/ai-text-detector-v1.01 model card
    config_class = AutoConfig

    def __init__(self, config):
        super().__init__(config)
        self.model = AutoModel.from_config(config)
        self.classifier = nn.Linear(config.hidden_size, 1)
        self.post_init()

    def forward(self, input_ids, attention_mask=None):
        h = self.model(input_ids, attention_mask=attention_mask)[0]
        m = attention_mask.unsqueeze(-1).expand(h.size()).float()
        pooled = (h * m).sum(1) / m.sum(1).clamp(min=1e-9)
        return self.classifier(pooled)


def clean(t):  # fakespot's clean_text (utils.py on the model page), used for every detector
    t = re.sub(r"```.*?```", "", t, flags=re.S)
    t = re.sub(r"!\[.*?\]\(.*?\)", "", t)
    t = re.sub(r"\[([^\]]+)\]\(.*?\)", r"\1", t)
    t = re.sub(r"(\*\*|__)(.*?)\1", r"\2", t)
    t = re.sub(r"#+ ", "", t)
    t = re.sub(r"^(\s*[-*+]|\d+\.)\s+", "", t, flags=re.M)
    t = unescape(t).replace("\n", " ").replace("\r", " ")
    return re.sub(" +", " ", t).strip()


def windows(t, size=300):
    w = t.split()
    if len(w) <= size * 1.3:
        return [t]
    return [" ".join(w[i:i + size]) for i in range(0, len(w), size) if len(w[i:i + size]) >= 40]


class Detectors:
    def __init__(self):
        self.tok_d = AutoTokenizer.from_pretrained("desklib/ai-text-detector-v1.01")
        self.m_d = DesklibAIDetectionModel.from_pretrained("desklib/ai-text-detector-v1.01").eval()
        self.tok_f = AutoTokenizer.from_pretrained("fakespot-ai/roberta-base-ai-text-detection-v1")
        self.m_f = AutoModelForSequenceClassification.from_pretrained("fakespot-ai/roberta-base-ai-text-detection-v1").eval()
        self.tok_r = AutoTokenizer.from_pretrained("TrustSafeAI/RADAR-Vicuna-7B")
        self.m_r = AutoModelForSequenceClassification.from_pretrained("TrustSafeAI/RADAR-Vicuna-7B").eval()

    @torch.no_grad()
    def one(self, t):
        d = self.tok_d(t, truncation=True, max_length=512, return_tensors="pt")
        desk = torch.sigmoid(self.m_d(d["input_ids"], d["attention_mask"])).item()
        f = self.tok_f(t, truncation=True, max_length=512, return_tensors="pt")
        fake = torch.softmax(self.m_f(**f).logits, -1)[0, 1].item()          # id2label 1 = AI
        r = self.tok_r(t, truncation=True, max_length=512, return_tensors="pt")
        radar = torch.softmax(self.m_r(**r).logits, -1)[0, 0].item()         # RADAR README: index 0 = AI
        return {"desklib": desk, "fakespot": fake, "radar": radar}

    def score(self, text):
        t = clean(text)
        ws = windows(t)
        res = [(len(w.split()), self.one(w)) for w in ws]
        tot = sum(n for n, _ in res)
        return {k: round(sum(n * r[k] for n, r in res) / tot, 4) for k in ("desklib", "fakespot", "radar")}


def files():
    for sub in ["human", "inputs"]:
        for p in sorted((ROOT / sub).glob("*.md")):
            yield sub, p
    for p in sorted((ROOT / "holdout" / "inputs").glob("*.md")):
        yield "holdout/inputs", p
    for base in ["outputs", "track2", "track3", "gen", "holdout/outputs"]:
        d = ROOT / base
        if not d.exists():
            continue
        for p in sorted(d.rglob("*.md")):
            if "raw" in p.parts or "pangram-ready" in p.parts or p.name.lower() == "readme.md":
                continue
            yield str(p.parent.relative_to(ROOT)).replace("\\", "/"), p


def main(cached_only=False):
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    det = None
    rows = []
    for group, p in files():
        text = p.read_text(encoding="utf-8")
        h = hashlib.sha1(text.encode()).hexdigest()
        if h not in cache and cached_only:
            continue
        if h not in cache:
            det = det or Detectors()
            cache[h] = det.score(text)
            CACHE.write_text(json.dumps(cache))
        rows.append({"group": group, "file": p.name, "words": len(text.split()), **cache[h]})
    with open(ROOT / "scores" / "detectors.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("rows", len(rows))


if __name__ == "__main__":
    import sys
    main("--cached-only" in sys.argv)
