"""Download blader/humanizer's SKILL.md at the commit the published run used (arm A).

python scripts/fetch_blader.py   -> evidence/blader/SKILL.md (gitignored; MIT-licensed, not vendored here)
Source: https://github.com/blader/humanizer, v3.1.0, commit 225a6f39ac85f76ee48dbad772ea4abe4ed6c9d8
"""
import hashlib
import urllib.request

from common import ROOT, write

SHA = "225a6f39ac85f76ee48dbad772ea4abe4ed6c9d8"
URL = f"https://raw.githubusercontent.com/blader/humanizer/{SHA}/SKILL.md"

if __name__ == "__main__":
    with urllib.request.urlopen(URL, timeout=60) as r:
        text = r.read().decode("utf-8")
    write(ROOT / "blader" / "SKILL.md", text)
    print(f"saved {len(text.split())} words, sha1 {hashlib.sha1(text.encode()).hexdigest()[:12]}")
