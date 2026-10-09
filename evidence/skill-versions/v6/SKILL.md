# v6c: v6a plus a narrow repair (experiment arm, two steps on Claude Sonnet)

1. **Rewrite.** v6a's one-liner, "Rewrite this to sound human, without changing the meaning." (v6a's own output for the same text is reused, so v6c differs from v6a only by step 2).
2. **Narrow repair** (one call, `REPAIR` in `scripts/run_v6c.py`): fix only meaning-bearing items (numbers, dates, names, commitments and who makes them, caveats and hedges, claim strength, tense and status, anything added) with as few word changes as possible, never reverting a sentence to the draft's wording just because it differs.
