Sakala Mitra · plan of action · 25 Oct 2026

# A sovereign, native full-duplex Mitra

Can an all-open stack running on Karnataka's own H200 hardware reach Gemini Live's level for Mitra? Yes on turn-taking, function accuracy and reasoning. Kannada spoken natively by the duplex model is the one part that has to be trained, and it is the critical path.

Research and architecture only. Nothing has been implemented, changed or committed. Gemini stays in production until every gate below passes.

01 · The verdict

## Where Gemini level is reachable, and where it is not yet

Gemini Live is one native audio model. The open world now has the same kind of model, and on the public Full-Duplex-Bench the open models react to an interruption faster than Gemini, which is conservative and slow to yield. What no open model has is Kannada speech out of a duplex core. That is the gap we have to close ourselves.

**Turn-taking and barge-in**Reachable now. Moshi yields in 0.26 s, Gemini Live in 1.2 s. VoiceChat 11B takes over 100% of interruptions with 4.33/5 coherence.\
Gemini level or better

**Functions, ids, routing**Parity by construction. Every number already comes from our SQL and router. The duplex model only has to call and read back.\
Parity

**Reasoning and knowledge**A 7 to 11B duplex core is weaker than Gemini. A delegated 105B text brain behind a delegation token closes it.\
Parity via delegation

**English voice quality**PersonaPlex and VoiceChat are close. Emotion and persona control exist but are less polished.\
Near Gemini

**Kannada, spoken natively**No open duplex model has it. Qwen3.5-Omni hears Kannada but does not speak it. This needs our own training run.\
6 to 12 months, real risk

**Code-mixed Kannada English**Only Sarvam Bulbul shows it today, and that is a TTS behind an API. Learnable from our call-centre data.\
After Kannada training

02 · The architecture

## Native duplex core, delegated brain, our deterministic layer

This is not a cascade. One model hears and speaks at the same time on two audio streams, 12.5 frames a second each way, with a text monologue aligned to its own voice. The two extra output streams, a live user transcript and a delegation stream, are what make it usable for Sakala: they let a large text model and our existing router answer the hard parts while the voice keeps flowing. Everything inside the dashed boundary runs on the H200 in India. The browser, the relay contract and the whole POC stay as they are.

One voice turn: audio frames enter the duplex core through the relay; the core speaks, captions and transcribes at once; when it needs a fact or a decision it emits a delegation token, the dispatcher runs our router or asks the sovereign text brain, and the answer is prefilled into the core so it says it in its own voice. The factory below produces the Kannada weights the core needs.

### What makes it full duplex, and where the brain fits

The core never stops listening. The brain and the tools only ever see text, and they only speak through the core. This split is published: a 2026 paper puts a duplex speech model in front of Qwen3-235B behind a delegation token and keeps 92 to 97% tool recall with regular duplex turn-taking. NVIDIA's VoiceChat 11B goes further and emits tool calls on their own stream inside the model, at about 450 ms turn-taking. Either way the timing lives in the core, not in a pipeline of three services.

The behaviours the atlas will measure live on this timeline: how long after the question the voice starts, how fast it yields when the user cuts in, and whether the half-said answer is resumed or restarted.

03 · Model research

## What exists, and how sovereign each piece is

"Sovereign" is used loosely in this market, so the table scores four separate things. Weights: do we hold the model file. Hardware: can it run on Government of Karnataka machines in India. Data: does any audio leave our control. Licence: does it allow government production use.

**W** weights held by us

**H** runs on GoK hardware in India

**D** no audio leaves our control

**L** licence allows production use

### Native full-duplex cores

| Model | What it is | Languages | Sovereignty | Role for Mitra |
| --- | --- | --- | --- | --- |
| NVIDIA NemotronLabs VoiceChat 11B | Open full-duplex model with a native tool-call stream and streaming user transcript. Fast Conformer encoder + Nemotron Nano 9B. About 450 ms turn-taking. Weights on Hugging Face since Aug 2026. Needs an 80 GB GPU. | English | W H D yes. L: sources disagree, OpenMDW research-only vs commercial. Must be read before use. | Primary English core and the architectural template. Its tool stream is exactly what Mitra needs. |
| NVIDIA PersonaPlex 7B | Moshi-based, persona and voice prompts. Trained in 6 h on 8×A100 from under 5,000 h of guided data. NVIDIA Open Model License. | English | W H D yes. L: NVIDIA Open Model License, check government clause. | Fallback English core. Proof that a duplex model is cheap to re-tune once the base exists. |
| Kyutai Moshi 7B + Mimi codec | The open reference: two audio streams, inner monologue, 12.5 Hz codec. CC-BY-4.0. Official fine-tuning repo with LoRA. J-Moshi adapted it to Japanese with 69k h mono, 344 h stereo, 602 h synthetic. | English (Japanese by others) | W H D L all yes. | The base for the Kannada training run. Mimi generalised to Hindi well in one independent test, so the codec probably needs no retraining. |
| Qwen3.5-Omni | Thinker-Talker omni model, streaming speech. 74 speech-input languages including Kannada, 29 output languages without Kannada. Only a Light variant may be open; licence unconfirmed. | Hears Kannada, does not speak it | W: disputed. H D yes if weights exist. L: unconfirmed. | Not a duplex core. Useful as a Kannada hearing evaluator in the factory, if the licence allows. |
| Gnani Inya VoiceOS 5B | Indian voice-to-voice model under the IndiaAI Mission, Kannada among its languages, research preview, 14B coming. No weights published; on-prem only for its STT and TTS siblings. | 15+ Indian languages incl. Kannada | H D: on-prem promised. W L: not available. | The one Indian team already training what we need. Ask for an evaluation licence and a Kannada demo before we train our own. |
| BharatGen Param2 17B | Government-funded 22-language model with a speech family claimed. No speech specs or duplex capability published. | 22 Indian languages (text) | Government owned. W L unknown for speech. | Ask. Possibly a delegated brain, not a core. |
| Block Dessa | Full-duplex model announced 23 Oct 2026, waitlist only. | English | Closed. | Watch only. |

### Indian speech stack: the three you asked about

| Who | What they are | Models for Kannada | Sovereign? |
| --- | --- | --- | --- |
| AI4Bharat | IIT Madras research lab. Funded by MeitY's Bhashini programme and non-profits. Everything is published as downloadable weights. | IndicConformer 600M ASR (MIT, 22 languages). IndicF5 TTS (MIT, Kannada, voice prompt, 1,417 training hours). IndicParler-TTS (Apache 2.0, named Kannada speakers). IndicVoices 7,348 h corpus. | Fully, when self-hosted W H D L all yes. No API dependency at all. Quality is the question, not sovereignty: no public Kannada WER table exists, so we measure on our own clips. |
| Bhashini | MeitY's Digital India Bhashini Division. 350+ models reachable through the ULCA API. ULCA itself does not host models; each contributor's endpoint does. | Multilingual and Dravidian conformer ASR from IIT Madras, Kannada TTS. | Sovereign by ownership, not by control Government of India owns it, but the audio goes to a central hosted service, and no API data-retention terms are published. H and D depend on an agreement. For a GoK pilot it is acceptable. For production, run the same open models ourselves. |
| Sarvam | Indian company picked under the IndiaAI Mission. India-hosted inference, DPDP and data residency controls advertised. Sarvam-30B and 105B LLMs are Apache 2.0 and downloadable. Saaras v4 ASR and Bulbul v4 TTS are closed, API only. | Saaras v4 (22 languages, code-mixed, under 150 ms streaming). Bulbul v4 (Kannada, code-switching, under 250 ms). | Two different answers The LLMs: fully sovereign, W H D L yes, our best delegated brain. The speech APIs: India-hosted and DPDP-compliant, so data stays in India, but we hold no weights and depend on one vendor. That swaps a Google dependency for an Indian one. Good as a fallback and as the Kannada quality bar, not as the core. |

### Other components

| Role | Candidates | Note |
| --- | --- | --- |
| Delegated brain | Sarvam-105B (MoE, \~10B active, Apache 2.0), Qwen3-235B-A22B, Gemma 3 27B | The paper that pairs a duplex frontend with a text backend used Qwen3-235B. Sarvam-105B is the sovereign choice and is strong in Kannada text. |
| The gateway's Qwen3-ASR | Qwen3-ASR 0.6B / 1.7B open weights | Hindi is its only Indian language. It cannot be Mitra's Kannada ear. It remains useful for English transcription inside the factory. |
| Kannada ASR for the factory | IndicConformer, IndicWhisper, Saaras v4 as the bar | Used to filter synthetic dialogues and to score the core. WER inflates on Kannada because of agglutination, so report CER too. |
| Kannada voices for synthesis | IndicF5 with our own consented speakers, IndicParler named voices | Two distinct voices per dialogue, user and Mitra. IndicF5's licence forbids cloning a voice without permission, so the speakers sign. |
| Evaluation | Full-Duplex-Bench 1.0 / 1.5 / 3.0, VoiceBench, our atlas | FDB 3.0 scores tool selection, the closest public test to Mitra's job. |

04 · Kannada

## The critical path: teaching a duplex core to speak Kannada

The recipe exists. J-Moshi took the English Moshi to Japanese in three steps: continued pretraining on about 69,000 hours of monolingual speech turned into pseudo-stereo by speaker diarisation, fine-tuning on 344 hours of real two-channel dialogue, then 602 hours of synthetic dialogue written by a text model and voiced by a multi-stream TTS, filtered by word error rate. Its authors report natural turn-taking and backchannels, with speech quality still behind. That is the honest baseline for what Kannada will look like after round one.

| Kannada speech we can reach | Hours | Kind | Status |
| --- | --- | --- | --- |
| Call-centre recordings | 500 | Real conversation. Gold if the agent and caller are on separate channels. | Consent and masking review needed. Ours. |
| Vaani (IISc, 165 districts) | \~108 transcribed, far more raw | District speech across Karnataka, dialect-rich. | Open. Kannada total to be confirmed. |
| Kathbath | 166 clean + 65 noisy | Read speech. | Open (AIKosh). |
| IndicVoices, Shrutilipi | share of 7,348 and 6,457 | Extempore, conversational, radio. | Open. Kannada share to be extracted. |
| Synthetic duplex dialogues | 2,000 to 5,000 | Sakala conversations with overlaps, repairs and backchannels, two voices. | We generate these. Our LLM writes, IndicF5 speaks, IndicConformer filters. |

Two things are shorter than J-Moshi had. Real Kannada mono speech will be in the low thousands of hours, not 69,000, and real two-channel dialogue is the 500 hours. Three things help. The English duplex ability transfers, so we are teaching a language, not conversation. Mimi already encodes Hindi well, so the codec likely stays. And the factory can make synthetic hours at scale on the same node. The risk that remains is voice quality and code-mixing after round one, and the plan has a second training round for exactly that.

### Compute on the H200

- **Serving.** A 7B duplex core in bf16 is quoted at 3 to 4 concurrent sessions per 80 GB GPU. A 141 GB H200 with FP8 should carry 8 to 12. One 8-GPU node is a pilot, roughly 60 to 100 live conversations. 50,000 concurrent would be thousands of GPUs, which is the real cost of native duplex versus paying Gemini by the minute.
- **Fine-tuning.** PersonaPlex-scale supervised tuning is hours on one node. LoRA runs on a single GPU.
- **Continued pretraining.** A few thousand Kannada hours through a 7B core is days to two weeks on an 8-GPU node, by estimate. VoiceChat at 11B is heavier.
- **Factory.** Synthesising 5,000 hours of two-voice dialogue with IndicF5 and filtering it with IndicConformer is a multi-day batch job on the same node, run while the core is not training.

05 · Plan of action

## Phases and the gate each one must pass

Gemini stays in production through all of it. Each phase ends at a measured gate, and nothing is switched until the last one passes.

Now

**Phase 0 · Decisions**

Your calls: Gemini spend cap for the acceptance runs; which 500 hours and whether consent covers training; GPU hours on the H200; English-first prototype or Kannada-first data work in parallel (recommended: both). Send access requests to Gnani and BharatGen, and read the VoiceChat licence.

Weeks 1 to 2

**Phase 1 · Limit-test Mitra and build the atlas harness**

Virtual microphone at the WebSocket with millisecond traces, the 300-clip corpus, every test family from the earlier plan. Probe candidates on our own Kannada clips: Mimi reconstruction, IndicConformer and Saaras WER, IndicF5 and Bulbul listening test, Qwen3.5-Omni Kannada hearing. **Gate G0:** scorecard green, atlas requirement sheet signed, candidate probe table filled.

Weeks 2 to 5

**Phase 2 · English native duplex behind the relay**

VoiceChat 11B as the core if the licence allows, PersonaPlex otherwise. Delegation to Sarvam-105B on the H200. Same tools.execute, same guard, same read-back. The browser does not change. **Gate G1:** English atlas parity with Gemini on turn-taking, barge-in, first audio, id accuracy and the 24 Mitra turn tests.

Weeks 3 to 10

**Phase 3 · Kannada data factory**

Consent and DPDP review, privacy shield on audio, diarisation to pseudo-stereo, corpus extraction, synthetic dialogue generation and filtering. **Gate G2:** at least 3,000 h usable Kannada mono, 300 h conversational, 2,000 h synthetic duplex, privacy audit passed, zero Gemini-derived samples.

Months 3 to 6

**Phase 4 · Kannada duplex training, round one**

Stage A continued pretraining on Kannada mono. Stage B duplex dialogue fine-tune. Stage C persona and tool-stream SFT on Sakala flows. Stage D preference tuning for turn-taking. **Gate G3:** Kannada atlas parity, CER at or below Saaras on our clips, MOS of 4 or better from 20 Kannada listeners, the 18 Kannada live UI tests and the 55-question Kannada bank green.

Months 6 to 8

**Phase 5 · Round two and hardening**

Code-mixing and voice quality round with more call-centre hours. FP8 serving, concurrency and soak, failover to Gemini kept warm. **Gate G4:** two-week shadow run beside Gemini on the same traffic with an equal or better scorecard. Then the switch.

### Risks, in order

1. **Kannada voice quality after round one.** J-Moshi's own result. Mitigation: round two, more real hours, a consented professional Kannada voice for the synthetic side.
2. **VoiceChat licence.** If it is research-only, the English core is PersonaPlex or Moshi, which lack the native tool stream. Mitigation: the delegation-token design works on either.
3. **Consent on the 500 hours.** Without it, the real conversational set shrinks to what we record ourselves. Mitigation: start recording consented Sakala calls now.
4. **Scale economics.** Native duplex costs GPUs per live call. Mitigation: the H200 pilot proves quality; the 50,000-user plan is a separate budget decision.
5. **Reasoning latency through delegation.** Each brain call adds 0.3 to 1 s. Mitigation: the core speaks a lead phrase while the brain works, as the atlas will show Gemini does.

**The line we keep.** We measure how Gemini behaves and write our own requirements and tests from the measurements. We never store Gemini's audio or text as training data and never clone its voice. Every model in the factory is open-weight or ours, every corpus is public or consented.

06 · Two H200s

## How many live conversations the two H200s we have can carry

Two numbers matter and they are far apart. With the duplex server as it ships today, one process per session in bf16, two H200s carry 6 to 8 live conversations. That is enough to build and demo, not to pilot. After the serving work in Phase 2, batched FP8 inference with a 3-minute attention window, the same two GPUs carry 80 to 200 live conversations depending on how they are split. The planning number is 130.

| Layout | GPU 1 | GPU 2 | Day one, stock server | After serving work | Ceiling |
| --- | --- | --- | --- | --- | --- |
| A · brain lives elsewhere | duplex core | duplex core | 6 to 8 | 160 (100 to 240) | \~300 |
| B · self-contained pilot | duplex core | duplex core + Sarvam-30B brain, FP8 | 6 to 8 | 130 (80 to 200) | \~250 |
| C · serving while training | duplex core + small brain | factory: training, synthesis, eval | 3 to 4 | 70 (50 to 120) | \~150 |

Layout B is the one to plan around. One GPU is a pure duplex worker. The other runs a second duplex worker next to a Sarvam-30B brain in FP8, about 32 GB of weights, which serves the 30% of turns the deterministic layer does not answer. That is a complete sovereign Mitra on two cards, with nothing outside the boundary. If the two H200s are the existing gateway, its Qwen models make way for the core, and the gateway's text model can stay as the brain in place of Sarvam-30B.

### Where the numbers come from

- **Weights.** A 7B core in FP8 is about 7.5 GB. It is read once per 80 ms tick for every session together, so it costs almost nothing per session.
- **Attention cache.** About 0.26 MB per step per session at FP8. A 3-minute window is 2,250 steps, about 0.6 GB per session. 130 GB free on an H200 holds about 200 sessions.
- **Memory bandwidth.** Every tick reads every session's cache. 150 sessions is 90 GB, about 19 ms of the 80 ms budget at 4.8 TB/s. The rest of the budget goes to the depth transformer, the codec, and the network. The ceiling is the point where the 99th percentile tick no longer fits.
- **The brain's share.** Sarvam-30B at FP8 takes about 35 GB with its own cache and roughly a third of GPU 2's time at pilot load, which is why layout B loses about 30 sessions against layout A.
- **VoiceChat 11B instead of a 7B core** costs about a third of the density: plan 50 to 80 per GPU for the English prototype.

### What 130 live conversations means in people

A live session is someone speaking with Mitra right now. The client already drops to Standby after 20 seconds of silence and closes the live socket, so at any moment roughly one in four people with Mitra open is in a live session. 130 live sessions is therefore 400 to 600 people using Mitra at the same time, which covers the three pilot taluks and a Chief Secretary demo with room to spare. It is about 1% of the 10,000 stage. The two cards are a pilot and a factory, and the next section is what the state needs.

Two things raise the two-card number later without new hardware. The distilled 2 to 3B core at three times the density lifts layout B to 300 to 400 once it exists, around month 6. And the Phase 1 load run replaces every estimate above with a measured curve, which is the number we should quote to anyone after that.

07 · Scale

## From 1,000 to 50,000 live conversations at once, all native duplex

A native duplex core is a different kind of load from a chat model. Every live session needs a forward pass every 80 ms for as long as the call lasts, whether anyone is talking or not. So capacity is counted in sessions per GPU, and the whole budget hangs on that one number. The design below keeps every session fully duplex at every tier, and buys scale with batching, a sliding attention window, FP8 weights and a smaller core of our own for overflow, never with a cascade.

Why the scheduler matters: every session costs a fixed slice of a GPU for the whole call, so the pool must refuse the session it cannot serve well rather than slow down all the others. Overflow goes to a smaller duplex core we trained ourselves, never to a cascade.

### Why sessions per GPU is not three or four

The 3 to 4 sessions per 80 GB figure in vendor blogs is one process per session in bf16 with a long context. A 7B core at 12.5 Hz is a decode workload, and decode batches well, because every session ticks at the same instant. Weights are read once per tick for all sessions. What scales with sessions is the attention cache: about 0.26 MB per step at FP8, so a 3-minute window is roughly 0.6 GB per session, and 130 GB of free H200 memory holds about 150 of them. Reading all of them every tick takes about 20 ms of the 80 ms budget on an H200. That puts the engineering ceiling around 100 to 150 sessions per GPU and the safe planning number at 50 to 120. Kyutai's own Rust server already batches sessions; the work is making that production-grade, not inventing it.

### Capacity by stage

Assumptions: 7B core, FP8, 80 sessions per GPU, the deterministic layer answers 70% of turns, the brain the rest at one call per 10 s per session, 10% spare for failures and updates. Ranges show 50 and 120 sessions per GPU. All of it is an estimate until Phase 1 measures it.

| Concurrent live sessions | Duplex GPUs | Brain GPUs | Total H200s | 8-GPU nodes | Power | Rough cost |
| --- | --- | --- | --- | --- | --- | --- |
| 1,000 · the POC and pilot | 13 (8 to 20) | 2 | 17 to 25 | 2 to 3 | \~30 kW | About the H200 node you have plus one or two more. Rental: tens of lakh a month. |
| 10,000 · first production stage | 125 (85 to 200) | 15 to 20 | 160 to 240 | 20 to 30 | \~250 kW | Rental ₹3 to 5 crore a month at commercial Indian rates, far less on the IndiaAI pool. Purchase ₹50 to 75 crore. |
| 50,000 · the stated ceiling | 625 (420 to 1,000) | 60 to 100 | 750 to 1,200 | 95 to 150 | \~1.2 MW | Rental ₹12 to 20 crore a month. Purchase ₹250 to 375 crore, a dedicated hall, and a second site for failover. |

Two things to hold against those numbers. First, 50,000 concurrent live conversations is 50,000 people speaking to Mitra in the same minute. The 1902 helpline handles a small fraction of that, and 50,000 concurrent at 5 minutes a call is about 600,000 calls an hour. If 50,000 means registered or daily users, the GPU count drops by an order of magnitude, so the definition is worth settling. Second, the plan should still be built for the stated ceiling, because the architecture does not change between stages, only the count of identical workers does. Nothing in the 1,000-user POC has to be redone to reach 50,000.

### The levers that cut the bill, in order of return

1. **Sessions per GPU.** Every doubling halves every row above. FP8 weights and cache, a sliding window, CUDA graphs and a lean codec path are the first month of serving work.
2. **A smaller core of our own.** Distilling our 7B Kannada core to 2 to 3B is allowed, it is our model. At three times the density it serves overflow and the simplest flows.
3. **Keep the brain out of the loop.** The deterministic layer already answers the 113-question bank without a model. Every turn it takes is a brain call saved, and the brain pool is a tenth of the duplex pool only because of that.
4. **Peak shaping.** Office-hours load is the peak. Owned GPUs run the factory at night: training, synthetic data, evaluation. No idle capacity.
5. **Standby at the edge.** Today's client already drops to Standby after 20 s of silence and closes the live socket. At scale that is the difference between 50,000 sessions and 50,000 open tabs.

### What has to change in the POC for this scale

- SQLite becomes PostgreSQL with read replicas. The 8-stage pipeline, the router, the SLA engine and every endpoint stay as they are. Only the storage layer moves.
- Session state and the notification feed move to Redis and a queue, so any gateway pod can serve any session.
- The rate limits in the POC's protection layer become per-user instead of per-IP, because 50,000 users arrive through a handful of carrier addresses.
- A telephony bridge for 1902 callers: PCM over SIP into the same relay contract. The voice path is identical.

### What Phase 1 adds for scale

The virtual microphone harness gets a load mode: 200 synthetic callers on one GPU, each speaking from the corpus on a realistic talk-and-listen rhythm, while we measure per-tick latency, barge-in latency and first-audio latency as the session count rises. The session count where the 80 ms tick is still met at the 99th percentile is the planning number. That run costs a day and settles a ₹100 crore question before any order is placed.

08 · Sources

## What this page rests on

- [NemotronLabs VoiceChat 11B model card](https://huggingface.co/nvidia/NVIDIA-NemotronLabs-VoiceChat-11B) and [paper](https://arxiv.org/abs/2609.21967)
- [A frontend-backend architecture for tool calls in full-duplex speech models](https://arxiv.org/abs/2609.19334)
- [PersonaPlex code](https://github.com/NVIDIA/personaplex), [release coverage](https://the-decoder.com/nvidia-open-sources-personaplex-a-voice-ai-that-listens-and-talks-at-the-same-time/)
- [Moshi paper](https://arxiv.org/abs/2410.00037), [repo](https://github.com/kyutai-labs/moshi), [moshi-finetune](https://github.com/nu-dialogue/moshi-finetune)
- [J-Moshi: Towards a Japanese full-duplex spoken dialogue system](https://arxiv.org/html/2506.02979v1)
- [Full-Duplex-Bench](https://arxiv.org/html/2503.04721) and [v1.5](https://arxiv.org/html/2507.23159)
- [Qwen3.5-Omni technical report](https://arxiv.org/html/2604.15804v2), [Qwen3-Omni](https://github.com/QwenLM/Qwen3-Omni)
- [Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR), [model card](https://huggingface.co/Qwen/Qwen3-ASR-1.7B-hf)
- [IndicConformer](https://huggingface.co/ai4bharat/indic-conformer-600m-multilingual), [IndicF5](https://github.com/AI4Bharat/IndicF5), [Indic Parler-TTS](https://huggingface.co/ai4bharat/indic-parler-tts)
- [IndicVoices launch](https://inc42.com/buzz/iit-madras-ai4bharat-unveils-indicvoices-offers-access-to-7300-hours-of-speech-datasets/), [Vaani](https://arxiv.org/html/2603.28714v1), [Kathbath Kannada](https://aikosh.indiaai.gov.in/home/datasets/details/kathbath_kannada_valid_multilingual_asr_validation_dataset_for_kannada.html)
- [Bhashini ULCA](https://github.com/bhashini-dibd/ulca), [Bhashini models](https://dibd-bhashini.gitbook.io/bhashini-apis/available-models-for-usage), [MeitY note](https://www.meity.gov.in/static/uploads/2024/12/10fcadec462c330211502fed3d24ea83.pdf)
- [Sarvam](https://www.sarvam.ai/), [Bulbul docs](https://docs.sarvam.ai/api/getting-started/models/bulbul), [Sarvam 30B / 105B under Apache 2.0](https://www.opensourceforu.com/2026/03/sarvam-releases-30b-and-105b-llms-under-apache-2-0/)
- [Gnani Inya VoiceOS](https://www.etvbharat.com/en/technology/india-homegrown-voice-os-by-gnani-ai-promises-real-time-multilingual-ai-conversations-across-sectors-enn26021805142), [Vachana on-prem](https://www.business-standard.com/technology/tech-news/gnani-ai-expands-inya-voiceos-capabilities-with-two-new-speech-models-126021900332_1.html)
- [BharatGen Param2](https://bharatgen.com/param-2-launch-bharatgen-sovereign-ai-22-languages/)
- [Mimi on Hindi (Cohere Labs)](https://labscommunity.cohere.com/blog/2026/adapting-moshi-low-resource-speech-translation/)
- [Gemini Live API overview](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/live-api)
- [Moshi serving figures (vendor)](https://www.spheron.network/blog/speech-to-speech-gpu-cloud-moshi-sesame-csm-hertz-dev/)
- [Block Dessa](https://www.unite.ai/block-unveils-dessa-a-full-duplex-speech-model-trained-on-conversation/)