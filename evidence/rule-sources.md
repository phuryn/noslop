# Where the rules come from

work-humanizer was distilled from a working writing system built for publishing on LinkedIn, X and a newsletter, and from the studies run to calibrate it (2026). This maps each rule in `skills/work-humanizer/SKILL.md` to the evidence behind it. Studies are described, not linked: their raw data are not public.

| Rule | Evidence |
|---|---|
| Detectors read composition, not wording; interview mode; keep the writer's sentences | A five-cell Pangram test on a human-written article: AI formatting 99% human, AI copyedit 100%, full AI rephrase 100%, AI composition from the outline 68%, a style-targeted rewrite of that 69%. A human retyping AI prose stayed AI (25%). An earlier rewrite that turned the author's old sentences into clean house style kept 15 of 154 and lost the voice. This test's Track 3 replicates the pattern (Spearman 0.78 between surviving human words and Pangram's score). |
| Specifics carry the human signal; never invent them | Across 6 writers and 228 posts, density of numbers, names and dates was the only measured signal that tracked reader response (Spearman about +0.15; about +0.24 on 100 LinkedIn posts). Every other surface "AI tell" was flat. |
| Answer-first or evidence-first, not both | A 15-writer by 20-post voice study: no writer mixed the two in one post. |
| Deletion pass ("one word in six", "for the reader or to protect me from a doubt?") | Repeated cases where drafts passed every tell check and still shipped padding that the author cut by hand. |
| Contrast with a claim nobody made; pause-and-point, including the colon reveal | Validated against 60 top-performing posts from 6 writers: 0-1 occurrences. Also the most cited public tell. |
| Restating and engagement closers | Same study: absent from the top posts. |
| At most one crafted, quotable line per piece | A register study of the longest posts of five well-known technical writers: 0-1 quotable lines per post, stacked parallel aphorisms zero times. A long guide that allowed "one good line per section" shipped eight and read as AI. |
| Fragment stacks, invented metaphor labels | Repeated edits by the author in shipped posts. |
| Six ways of doing the reader's work | Catalog built from edits on shipped drafts; long-form carve-out for one signpost per section from the 60-post validation. |
| Hedge opinions, state facts flat, one marker; name the counter-case | 11 of 15 writers in the voice study; filler hedges 0 of 60 top posts. The "name the counter-case" form comes from an author's edit on a shipped post. |
| Keep the writer's qualifiers ("What you must not change") | This test: v1 lost on meaning (12-2-18 vs blader) by stripping them; v2 fixed it (27-2-3). |
| Sentence-length band in both directions; merge staccato | Reference writers keep 12-39% of sentences in one 10-word band; a guide that tripped AI readers had 78%, after tell fixes made it choppier. |
| Vary openers | Stylometry of an AI draft vs the same author's human edition: the AI version opened with "The", "It's" and "That's" far more often. |
| Shuffle test | A shipped post diagnosed as "stacked standalone facts" by an outside reviewer. |
| Filler transitions | Zero median density across 6 feed-native writers. |
| Synonym cycling on load-bearing nouns | Reader confusion on shipped drafts; scoped to referent doubt. |
| Em dashes, and not a semicolon | 2 of 93 top posts used em dashes. After a dash ban, AI-edited posts rerouted to semicolons: 2.9 per 1,000 words against 0.3-0.4 in the same writer's own prose. |
| Bold-label paragraph starts (reference-document exception) | Absent from top posts; allowed where a reader returns to find a section. |
| Sound like a person, not a costume; no fake noise | This test: judges flagged the bare prompt's added casual voice as "a deliberate humanizing pass". Pangram ignores planted typos (the retyping cell above). |
| Stock AI vocabulary list | Words from the public AI-tell literature with zero uses in one professional writer's 227-post newsletter archive, so a hit cannot be that writer's style. |
| Mechanical sweep as code (`check.py`) | Rules enforced by a script stuck (em-dash violations went from 7 of 26 posts to 0 of 26); the same rules as prose kept slipping. |

Overlap with blader/humanizer: about a third of the tell catalog (not-X-but-Y, closers, sayings, staged run-ups, triads, dashes, AI words, inflation, -ing riders, sales language, bold decoration, chat residue). Both descend from the same public observations. work-humanizer adds interview mode, the composition-vs-texture model, the two-direction rhythm rule with a number, the semicolon and colon-reveal traps, the crafted-line budget, the deletion quota, the shuffle test, hedge placement, synonym cycling and a code check.
