"""Step 1-2: writer briefs, then AI drafts from the short requests only.

python scripts/gen_inputs.py briefs   -> inputs/briefs.json   (one Opus call)
python scripts/gen_inputs.py drafts   -> inputs/NN-genre.md     (odd ids: Claude Sonnet, even ids: Codex/GPT)
HUMANIZER_SET=holdout python scripts/gen_inputs.py briefs-holdout   -> holdout/inputs/briefs.json (8 new briefs)
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor

from common import DATA, ROOT, run_claude, run_codex, parse_json, write

GENRES = [
    "LinkedIn post", "Cold sales email", "Release notes", "Newsletter intro",
    "PRD section (problem + goals)", "Landing page copy (hero + 3 sections)",
    "Slack status update to the team", "Blog post paragraph (opinion)",
    "Customer support reply", "Customer email announcing a pricing change",
    "Job post intro", "Conference talk abstract + speaker bio",
    "Internal strategy memo", "X/Twitter thread (5-7 posts)",
    "App store description", "Personal reflection (first-person essay paragraph)",
]

BRIEF_PROMPT = """I am building a test set for text-editing tools. Write 16 writer briefs as a JSON array, one per genre below, in this order.

Genres: {genres}

Each brief is an object with:
- "id": 1..16
- "genre": the genre
- "writer": who is writing (name, role, organization). Vary industries: not all software. Fictional but realistic.
- "request": exactly what this busy person would type into ChatGPT or Claude to get the draft. 1-4 sentences, casual, the way people actually type. It must contain 2-5 concrete facts the final text has to keep (names, numbers, dates, prices, product or feature names) and may include a light format hint. It must NOT contain the hidden facts.
- "hidden_facts": 6-10 short items the writer knows but did not type: the real numbers behind vague claims, one short true anecdote with a named person or customer, what went wrong or what they are unsure about, their honest opinion, one insider detail. Each item one sentence. Consistent with the request.

Return only the JSON array."""

DRAFT_SUFFIX = "\n\n(Reply with just the text, ready to paste.)"


HOLDOUT_GENRES = [
    "LinkedIn post", "Recruiting outreach email", "Product update email to users",
    "Newsletter intro", "Slack message asking a colleague for a decision", "How-to blog paragraph",
    "Customer support reply about a bug", "About page / founder bio",
]
HOLDOUT_NOTE = ("\n\nThis is a second, held-out set. Use 8 briefs (ids 1..8) for the 8 genres listed. Avoid these "
                "industries and situations, already used in set 1: dental clinics, refrigerated freight, accounting "
                "software, allotment gardening, home-care staffing, baking kits, auth migrations, veterinary care, "
                "e-bikes, gyms, restaurants, water utilities, retail leases, bookshops, physio apps, retiring teachers.")


HOLDOUT2_GENRES = [
    "Investor update email", "Outage apology email to customers", "Meeting recap email to a client",
    "Case study paragraph", "Event invitation post", "FAQ answer on a product help page",
    "Internal announcement of a new policy", "Personal blog post opening",
]
HOLDOUT2_NOTE = ("\n\nThis is a third, held-out set. Use 8 briefs (ids 1..8) for the 8 genres listed. Avoid these "
                 "industries and situations, already used: dental clinics, refrigerated freight, accounting software, "
                 "allotment gardening, home-care staffing, baking kits, auth migrations, veterinary care, e-bikes, gyms, "
                 "restaurants, water utilities, retail leases, bookshops, physio apps, retiring teachers, rooftop solar, "
                 "ferries, hearing aids, beekeeping, architecture practices, outdoor gear repair, parking apps, piano restoration.")


HOLDOUT3_GENRES = [
    "LinkedIn post", "Cold email to a potential partner", "Product launch email to customers",
    "Newsletter intro", "Slack update to the team", "Customer support reply",
    "Blog post paragraph (how-to or opinion)", "Landing page section", "Job post intro",
    "Speaker bio", "Personal essay paragraph", "Community event announcement",
]
HOLDOUT3_NOTE = ("\n\nThis is a fourth, final validation set. Use 12 briefs (ids 1..12) for the 12 genres listed. Avoid "
                 "every industry and situation already used: dental clinics, refrigerated freight, accounting software, "
                 "allotment gardening, home-care staffing, baking kits, auth migrations, veterinary care, e-bikes, gyms, "
                 "restaurants, water utilities, retail leases, bookshops, physio apps, retiring teachers, rooftop solar, "
                 "ferries, hearing aids, beekeeping, architecture practices, outdoor gear repair, parking apps, piano "
                 "restoration, and anything in investor updates, outage apologies, meeting recaps, case studies, event "
                 "invitations, FAQ pages, policy announcements or personal blogs from the third set. Every draft should "
                 "come out at least 60 words long.")


def briefs(holdout=False):
    genres = HOLDOUT_GENRES if holdout else GENRES
    if holdout == 2:
        genres = HOLDOUT2_GENRES
    if holdout == 3:
        genres = HOLDOUT3_GENRES
    prompt = BRIEF_PROMPT.format(genres="; ".join(genres)).replace("Write 16 writer briefs", f"Write {len(genres)} writer briefs")
    if holdout:
        prompt = prompt.replace('"id": 1..16', f'"id": 1..{len(genres)}') + ({2: HOLDOUT2_NOTE, 3: HOLDOUT3_NOTE}.get(holdout, HOLDOUT_NOTE))
    reply = run_claude(prompt, model="opus", tag=f"briefs-holdout{holdout}" if holdout else "briefs")
    data = parse_json(reply)
    assert len(data) == len(genres), len(data)
    write(DATA / "inputs" / "briefs.json", json.dumps(data, indent=2, ensure_ascii=False))
    print("briefs ok")


def slug(g):
    import re
    return re.sub(r"[^a-z0-9]+", "-", g.lower()).strip("-")[:30]


def one_draft(b):
    prompt = b["request"] + DRAFT_SUFFIX
    if b["id"] % 2 == 1:
        text, src = run_claude(prompt, model="sonnet", tag=f"draft{b['id']}"), "claude-sonnet-5-5"
    else:
        text, src = run_codex(prompt, tag=f"draft{b['id']}", effort="medium"), "codex gpt-6-astra (medium)"
    name = f"{b['id']:02d}-{slug(b['genre'])}"
    write(DATA / "inputs" / f"{name}.md", text.strip() + "\n")
    return {"id": b["id"], "file": f"{name}.md", "source_model": src, "genre": b["genre"]}


def drafts():
    bs = json.loads((DATA / "inputs" / "briefs.json").read_text(encoding="utf-8"))
    with ThreadPoolExecutor(6) as ex:
        manifest = list(ex.map(one_draft, bs))
    write(DATA / "inputs" / "manifest.json", json.dumps(sorted(manifest, key=lambda r: r["id"]), indent=2))
    print("drafts ok", len(manifest))


if __name__ == "__main__":
    {"briefs": briefs, "briefs-holdout": lambda: briefs(True), "briefs-holdout2": lambda: briefs(2), "briefs-holdout3": lambda: briefs(3), "drafts": drafts}[sys.argv[1]]()
