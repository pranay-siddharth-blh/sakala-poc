# Sovereign Mitra: the complete plan

Written 26 Oct 2026 for Pranay and the Mitra team. This is the whole plan in one place: what we are building, how it works, how sovereign it is, how close it gets to the Gemini experience, what the two GPUs can do, how long it takes, and what it costs. Nothing in it is implemented yet.

## What we are building, in one paragraph

Today Mitra's voice is Gemini Live, a Google model that hears and speaks at the same time and calls our functions. Everything else in Mitra is ours: the router that finds the right officer, the SQL that answers every number, the guard, the read-back, the eight-stage pipeline, the screens. The plan replaces the one piece that is not ours, the voice model, with a voice model we train and own, running on government hardware in Karnataka, and leaves everything else exactly where it is. Gemini's role during the build is to be the reference we measure against, never a source of training data. When our model matches Gemini on the measured scorecard, Gemini is switched off and never used again.

The four conditions, all of which must hold: 100% data sovereignty, an experience as close to today's Gemini as possible, the shortest build on the two GPUs we have, and the lowest cost when it scales to 50,000 people at once.

## Part 1: How it works

**The conversation path, as a citizen would experience it.** A citizen taps Mitra on the phone or says "Hey Mitra" in the browser. Their voice streams to our relay, the same relay that exists today. The relay masks anything sensitive and passes the audio to the voice core. The core is one model that listens and speaks at the same time, twelve and a half times a second, so it can start answering while the citizen is still finishing a sentence, and it stops the moment the citizen cuts in. When the core needs a fact, an id, a count or an officer's name, it does not guess. It sends a short signal to our dispatcher, the same code that runs today, which answers from our own database and router. When it needs real thinking, wording a difficult reply or understanding a confused complaint, the dispatcher asks a large Indian text model that runs on our own GPU. The answer text comes back to the core, which says it in its own voice while still listening. Captions appear word by word, charts build as it speaks, and every number on screen comes from SQL, as now.

**Two engines, one after the other, behind the same relay.**

The first engine is the bridge, and it is what goes live first. It is built entirely from open models that already exist for Kannada: a streaming Kannada recogniser from IISc for hearing, the Sarvam open language model for thinking, and an open Kannada voice model for speaking, all tuned on your call recordings and wrapped in a controller that keeps listening while Mitra talks and cuts her off within a fifth of a second when a citizen interrupts. It is not one model; it is three models working at once. It is fully sovereign from the day it runs. It sounds a little more mechanical than Gemini and answers about half a second later. It is the working, sovereign Mitra while the real core trains, and it becomes the factory that produces the training data.

The second engine is the native core, and it is the real goal. It is one model, in the same family as Gemini Live and as the open English duplex models that exist today, trained by us to speak Kannada and English. It has four outputs at once: Mitra's voice, the text of what she is saying, the text of what the citizen is saying, and the signal to the dispatcher. We train a 7B version for quality, then shrink it to a 3B version for serving, which is three times cheaper to run and is what 50,000 citizens would talk to. The 7B stays on the Chief Secretary's and officers' desks, where users are few and quality matters most.

**The factory, which feeds both.** Your call-centre recordings, with consent and with phone numbers and ids masked, are split into the caller's channel and the agent's channel. Open Kannada speech corpora add a few thousand hours. Then the bridge's own models write and voice thousands of hours of synthetic Sakala conversations, with interruptions, pauses, repairs and code-mixed Kannada-English, in two voices, and the tuned recogniser filters out the bad ones. Real plus synthetic becomes the training set for the core. The factory runs on the two GPUs at night while the bridge serves by day.

**How sovereign it is.** Completely, and in a way that can be audited. Every model is a file we hold, under open licences or trained by us. Every model runs on hardware in Karnataka under government keys, with no outbound network path from the serving pool. No audio, text or embedding ever leaves that hardware. Training data is consented recordings, public corpora and our own synthetic dialogues. Gemini's audio and text are never stored and never used as a training target, because Google's terms forbid building a competing model from its outputs, and because the design was built from the start not to need it. The behaviour atlas we measure from Gemini holds timings and policies, not transcripts. A tamper-evident log records what every model received. The one date to understand: sovereignty is 100% from the day Gemini is switched off. If Gemini stays in production until the core reaches parity, that day is around month six. If the bridge replaces Gemini as soon as it is ready, that day is month two, at lower quality for the four months in between. Either way the interim should run Gemini through its Mumbai region with zero data retention and our minimisation gateway, which keeps nothing stored at Google and costs nothing.

**How close to Gemini.** The experience Mitra has today is a list of behaviours, and each has an equivalent in the design.

| What Mitra has today with Gemini | How the sovereign core gives it | When |
|---|---|---|
| First word about half a second after you stop | Same design: one model step every 80 ms; open cores of this class answer in 0.2 to 0.5 s | Core, month 4 |
| Interrupt any time | Learned in the core; open duplex models yield in a quarter of a second, Gemini takes over a second | Bridge partly, core fully |
| Captions word by word, charts that build as she speaks | The core's text stream of its own voice | Core |
| Functions with exact ids and numbers | The signal to our dispatcher; numbers from SQL as now | Bridge and core, parity from day one |
| Replies from the document reader read in the same voice | Text pushed into the core, which speaks it | Core |
| Kannada and English, switching mid-sentence | One bilingual core; the switch is a prefix, not a reconnect | Core |
| Casual code-mixed Kannada | Learned from your recordings and synthetic dialogues | Core, round two, month 6 |
| Emotion in the voice | Style control in the core | Core, round two |
| Standby after 20 s silence | Unchanged client | Day one |
| Reasoning on hard questions | Sarvam-105B behind the dispatcher | Bridge and core, parity |

The honest gaps, and when they close: the bridge hears Kannada worse than Gemini until the recogniser is tuned on your recordings, which is weeks; the bridge's voice is flatter than Gemini's until the core arrives, which is month four; code-mixing and emotion are a second training round, month six. After round two, the core is scored against Gemini on the same conversations by Kannada listeners, and parity is declared when the scores meet. That scorecard is what "replica" means. It is a replica of behaviour, measured, not a copy of anything.

## Part 2: What the two GPUs can do

**Serving.** Two H200 cards, each with 141 GB of memory. A duplex core costs one model step per session per 80 ms, whether or not anyone is talking, so capacity is a fixed number of live sessions per card. Weights are read once per step for every session together; what grows with sessions is each session's memory of the conversation, about 0.6 GB for the 7B core with a three-minute window, and about 0.15 GB for the 3B core with compressed memory. One card physically holds about 220 sessions of the 7B core and ticks 150 of them inside the time budget; the second card gives up a third of itself to the text brain. A card run at its limit stutters, so the number we promise is the one where the slowest 1% of ticks still land on time with room for bursts of interruptions.

| | Bridge, open parts tuned | Native core, 7B | Native core, 3B |
|---|---|---|---|
| Day one, stock software | about 20 | 6 to 8 | 6 to 8 |
| Smooth and stable, the number to promise | about 100 | about 130 | about 300 |
| Physical limit, not smooth | about 200 | about 250 | about 500 |
| Speaking at the same moment | all heard; about 50 spoken to at once | all, both ways | all, both ways |
| People with Mitra open, at one in four live | 300 to 450 | 400 to 600 | 900 to 1,200 |

"Smooth like Gemini today" means first word under half a second, interruption cut under a quarter of a second, no dropouts, no failed sessions over hours. The core meets that at its promised number. The bridge meets all of it except first word, which lands near one second. One measurement decides all of this: sessions per card, from a one-day load test with 200 synthetic Kannada callers on one GPU. It runs in month one and replaces every estimate above.

**Training.** The surprising finding is that the two cards are enough to train the core. A duplex model sees one token per audio frame, so 10,000 hours of Kannada is about 450 million training tokens, and one pass over that for a 7B model is roughly a day on two H200s. Making 10,000 synthetic hours with a 3B voice model is about a week on one card. Full training of 7B fits across the two cards; lighter adaptation fits on one. So the calendar is set by preparing the data and by how many rounds the listening tests demand, not by GPU hours, and no rented training cluster is needed.

**Day to day.** Month one, both cards run the harness and the probes. From month two, one card serves the bridge for the pilot and one runs the factory, with training jobs at night on both. From month four, the core serves beside the bridge for comparison. At the 1,000-session pilot, three rented nodes take over serving and the two cards go back to being the lab.

## Part 3: Time and cost

**Timeline.** Assumes the first 100 recording hours arrive in month one and the full 500 by month three.

| Month | What happens | Mitra in production | Sovereign |
|---|---|---|---|
| 1 | Load harness and the Gemini behaviour atlas measured and signed; probes of every open model on our Kannada clips; recogniser tuned on the first recordings; consent and masking pipeline | Gemini | not yet |
| 2 | Bridge live behind the relay, Kannada and English, about 100 smooth sessions on the two cards; English native core running from an open base | Gemini, or the bridge if you choose | yes if the bridge |
| 3 | Bridge hardened; factory producing synthetic hours; 1,000-session pilot capacity rented for a taluk-scale pilot; GPU order placed for the 10,000 stage | pilot on the bridge | yes |
| 4 | Kannada core round one trained and gated: the 55-question Kannada bank, the 18 live UI tests, a 20-listener test | pilot | yes |
| 5 | 7B distilled to 3B; batched FP8 serving; the load test gives the real sessions-per-card number | pilot | yes |
| 6 | Round two for code-mixing and voice; two-week side-by-side against Gemini; parity declared on the scorecard; Gemini retired | the core | 100%, permanently |
| 6 to 9 | 10,000-session capacity: about a dozen nodes, PostgreSQL and Redis under the POC, telephone bridge for 1902 | the core | yes |
| 12 to 18 | 50,000-session capacity: a dedicated hall, about a megawatt, a second site for failover | the core | yes |

Parity around month six. Capacity for 10,000 by month nine, gated by GPU delivery rather than software. Capacity for 50,000 at twelve to eighteen months, gated by a building and power. Two things can slip the parity date: a listening test failing round one, which costs about a month for another round, and recordings arriving late or without consent. Capacity dates do not depend on those.

**Cost to build.** The two GPUs we have, plus a team of about eight for six months, speech, backend, data and test, plus the recordings. As a rough placeholder, ₹6 to 10 crore for the whole programme to parity, most of it people. No training cluster is rented. The rented pilot nodes from month three are counted under running cost.

**Cost to run.** The design is built to be cheap at scale: a 3B core with compressed memory holds about 250 sessions per card, cheap cards do the audio codec and the hearing, the deterministic layer keeps the brain pool small, and Blackwell cards, if bought, roughly double sessions per card because this workload is limited by memory bandwidth. Estimates, at 250 sessions per core card and 10% spare, all to be replaced by the month-five load test:

| Live sessions at once | GPUs in total | Rented, per month | Bought, one time |
|---|---|---|---|
| 1,000 | 9 to 11 | ₹20 to 30 lakh | ₹3 to 4 crore |
| 10,000 | 80 to 95 | ₹1.5 to 2.5 crore | ₹25 to 35 crore |
| 50,000 | 385 to 475 | ₹5 to 8 crore | ₹120 to 180 crore, plus the hall and a second site |

For comparison, the first version of this plan needed 750 to 1,200 GPUs at 50,000 and ₹250 to 375 crore to buy. Paying Gemini by the minute at 50,000 concurrent speakers would be about ₹80 crore a month, so owning becomes cheaper than metering at around 1,000 concurrent sessions. And if 50,000 turns out to mean daily users rather than people speaking in the same minute, every row above divides by about ten.

**What keeps the cost down, in plain terms.** Most turns never touch a model, because our router and SQL answer them. Sessions only cost while someone is actually talking to Mitra. The model that 50,000 citizens talk to is the small one, shrunk from our own larger one. Memory per session is compressed so a card holds hundreds of callers. The audio plumbing runs on cheap cards so the expensive ones do only the thinking-and-talking. And the serving software is built so that growing to 50,000 means adding identical workers, with nothing redesigned.

**Three decisions needed to start.** Whether the bridge replaces Gemini at month two, or Gemini stays until parity at month six, which sets the sovereignty date. Moshi 7B as the base model, which is the recommendation for its licence, its proven language-adaptation recipe and its clean shrink to 3B. And the recordings: format, separate channels if they exist, and a consent line that covers training, with the first 100 hours as early as possible.
