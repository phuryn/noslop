# Hand verification of every invented-fact or major finding

The Opus checker's raw verdicts are in `factcheck/<arm>/NN.json` (main set), `../holdout/scores/factcheck/` (held-out) and `gen_check/` (writing from the request). Every hard finding below was checked by hand against both texts. All names are fictional test data.

## Skill and control arms

| Set | Arm | Text | Checker finding | Verdict |
|---|---|---|---|---|
| main | A (blader) | 12 talk bio | "helped lead the effort" (original: "helped use existing pressure data") | **Confirmed.** Role inflated to leadership; the abstract also turns "help reduce" into "cut". |
| main | C (bare prompt) | 01 LinkedIn | "The difference showed up quickly", "try texts for a month" | **Confirmed** for "showed up quickly" (new claim about timing). "For a month" is advice, minor. |
| main | C | 12 talk abstract | "Most water utilities already collect pressure readings", "what worked, what didn't" | **Confirmed.** New general claim; promises a "what didn't" section the original never mentions. |
| main | C | 14 X thread | "we started with what we loved", "My favorite thing...", "a friend borrowed it and never gave it back" | **Confirmed** for "we started with what we loved" (new fact about stocking). The borrowed-book line sits under "Maybe": hypothetical, not counted. |
| main | B, B2, B3 (work-humanizer) | 01 LinkedIn | dropped the closing question "What's worked for you in reducing no-shows?" (checker: major) | **Intended by the skill** (engagement-bait closer). Not a fact; not counted as a fact loss. |
| holdout | C | 02 recruiting email | "I saw you're a Second Engineer" (original: "I think you're") | **Confirmed.** A guess upgraded to an observation. |
| holdout | C | 06 how-to | temperature condition narrowed | **Confirmed** (changed instruction). |

Totals: invented or upgraded facts in **blader 1 of 24 texts, work-humanizer 0 of 24 (every version), bare prompt 5 of 24**.

## Emulate-1 rewrites (arm E), 15 texts

The 30-word Slack text is under the API's 40-word minimum. Checker: invented specifics in 5 of 15 texts, major meaning changes in 8 of 15, mean meaning score 3.47 (other arms 4.38-4.69). Spot-checked by hand:

| Text | Finding | Verdict |
|---|---|---|
| 12 talk bio | the unnamed speaker became "Mr. Matela ... he" | **Confirmed.** Name and gender not in the original. |
| 15 app store | "renews automatically unless canceled at least 24 hours before the end of the current period" became "will automatically renew within 24-hours prior to the end of the current period" | **Confirmed.** The cancellation condition is gone. |
| 16 reflection | the lab stools, the taps, the students whose questions changed his explanations for 20 years, replaced by "I had had good years and I had had bad years" and "whether with a bang or with a whimper" | **Confirmed.** Specific detail lost, general lines added. |
| 05 PRD | "Sunrise Home Care, our pilot partner, relies on coordinators" became "Sunrise Home Care has told us that..." | **Confirmed**, minor (new attribution). |

## Writing from the request (generation track), checked against the writer's request

| | Unsupported specifics (texts) | Request facts missing or changed | Language issues flagged (texts) |
|---|---|---|---|
| O: Claude Sonnet / OpenAI draft | 46 (9 of 16) | 1 | 0 |
| Emulate-1 `/v1/write` | 24 (8 of 16) | 11 | 35 (11 of 16) |
| O cleaned by work-humanizer v3 | 45 (8 of 16) | 1 | 0 |
| O cleaned by blader | 44 (11 of 16) | 4 | 0 |

The drafting models invent specifics from thin requests, and both skills carry them through: a rewrite cannot know which facts in a draft were invented. Emulate-1 invents fewer but drops or changes more of the facts the request gave.
