# Examples

Five short excerpts from the test. Examples 1-5 show work-humanizer v3, the version first tested; v5 (published now) is in `evidence/outputs/B5/`. On example 3, v5 turns the repeated "Mitigation:" labels into plain "We'd..." sentences. Every person, company and number is fictional. Full texts: `evidence/inputs/`, `evidence/outputs/<arm>/`, `evidence/track2/`, `evidence/holdout/`.

## 1. Interview mode: what an edit cannot add

A LinkedIn post, written by an AI from a two-line request. The writer was available to answer questions.

**AI draft (excerpt)**

> We cut no-shows at Brightwell Dental Group from 18% to 7% in six months.
>
> The change was simple: we switched to text message reminders across all 9 of our clinics.
>
> [...] The lesson for me: sometimes the biggest operational wins come from meeting people where they already are.
>
> What's worked for you in reducing no-shows?

**blader/humanizer** (did not ask anything)

> We cut no-shows at Brightwell Dental Group from 18% to 7% in six months. All we did was switch to text message reminders across our 9 clinics. [...]
>
> My takeaway is that meeting patients where they already are can be a real operational win.
>
> If you run a multi-location practice and still rely on calls, try texts. What's worked for you in reducing no-shows?

**work-humanizer** (asked five questions; the writer answered in a few spoken sentences each)

> We switched to two-way text messages, so patients can reschedule just by replying. Confirmation calls had been eating about 11 hours a week of front desk time, and I think that's the bigger win.
>
> It hasn't all worked. Joanna at our Gdańsk clinic noticed that elderly patients would reply "OK" and still not show, so now we also phone every patient over 70. Sopot only got to 12%, and nobody's sure why. I'm also a bit wary of the 7%, because our six months included summer, when no-shows tend to drop anyway.

Every specific in the last version came from the writer's answers ("eating about 11 hours a week" is their phrase). The fact checker, given the answers as allowed material, found nothing invented. Across the 6 texts where work-humanizer asked, judges preferred its version 11 to 1.

## 2. Keeping the meaning

A talk bio. The original says the speaker *helped use* existing data.

| | Bio |
|---|---|
| AI draft | "A senior engineer at Mesa Valley Water Authority, the speaker helped use existing pressure data to identify leaks and reduce non-revenue water from 14% to 9%." |
| blader/humanizer | "The speaker is a senior engineer at Mesa Valley Water Authority and helped lead the effort to find leaks in existing pressure data, which brought non-revenue water down from 14% to 9%." |
| work-humanizer | "The speaker is a senior engineer at Mesa Valley Water Authority and helped use the Authority's existing pressure data to find leaks and reduce non-revenue water from 14% to 9%." |

"Helped lead the effort" is a promotion the writer never claimed. Most pairs look like this: the two skills make similar edits, and the differences are small fidelity slips, not style.

## 3. Where blader/humanizer did better

The risks section of a strategy memo.

**AI draft and work-humanizer** (work-humanizer kept the template labels)

> Lost sales and customers not transferring. Some mall-store revenue will not follow us. Mitigation: customer data capture and outreach starting at least six months before closing, plus tracking of retention by store.

**blader/humanizer**

> Lost sales and customers not transferring. Some mall-store revenue will not follow us. We will capture customer data and start outreach at least six months before closing, and track retention by store.

Both judges ranked blader's memo above work-humanizer's and named the repeated "Mitigation:" labels as the remaining tell. (The fact checker noted that "We will" turns proposals into commitments, a minor shift.)

## 4. Passing the detector vs keeping the content

A vet clinic's blog paragraph.

**AI draft** (Pangram: AI)

> [...] Bloodwork can help spot changes in kidney and liver function, blood sugar, and other health markers before noticeable symptoms appear. Annual testing also gives your veterinarian a baseline to track over time [...]

**work-humanizer** (Pangram: AI)

> Your dog's annual visit should include more than vaccines, especially after age 7. Bloodwork can catch changes in kidney and liver function, blood sugar, and other health markers before you'd notice symptoms. Testing every year also gives your veterinarian a baseline to track over time, which helps guide care as your dog ages. Our senior wellness panel is $129.

**Emulate-1** (Pangram: Human)

> You may be bringing your dog in annually for his vaccines, but have you considered having blood work done as well? After the age of 7, it is highly beneficial to have annual blood work done to check your dog's kidney function, liver function, blood sugar, and many other markers to monitor your dog's health as it ages. Our Senior Wellness Bloodwork Panel is available for $129.

Emulate-1's version is the one Pangram calls human. It no longer says that bloodwork finds changes before symptoms show, which was the paragraph's main reason to test. No assistant-model rewrite (work-humanizer, blader, the bare prompt) moved Pangram on any of the 16 texts.

## 5. The bare prompt invents

A recruiting email. The writer was guessing.

| | Opening line |
|---|---|
| AI draft | "I think you're currently a Second Engineer on a cargo line, so I wondered if you'd be interested in a Chief Engineer role with us." |
| "Rewrite this to sound human." | "I saw you're a Second Engineer on a cargo line at the moment, and I thought you might be a good fit for a Chief Engineer role we're hiring for." |
| work-humanizer | "I think you're currently a Second Engineer on a cargo line, and we have a Chief Engineer role you might want to hear about." |

"I think" became "I saw": a guess turned into an observation. The bare prompt changed or invented facts in 5 of 24 texts; work-humanizer in none.
