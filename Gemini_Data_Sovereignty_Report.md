# Keeping the data while using Gemini at scale

A report for the Sakala Mitra team, 26 Oct 2026. Brainstorm and research only; nothing here is implemented. The question: if Mitra stays on Gemini for 10,000 to 50,000 concurrent users, can Karnataka still retain its data? The short answer is yes, in layers, and the strongest layer puts Gemini itself inside an Indian perimeter.

## 1. What "retain our data" has to mean

Four kinds of data leave the server on every Mitra turn today. Each needs its own answer.

| Data | What leaves | Why it is sensitive |
|---|---|---|
| **Audio** | The citizen's or officer's voice, 16 kHz PCM, streamed live | A voice is a biometric. It identifies the speaker even when the words are masked. |
| **Text** | The masked complaint, the officer's words, the screen context, the last six turns | Complaint text names people, places and problems. Masking covers numbers today, not names. |
| **Function results** | Counts, case ids, officer names, places, the citizen's request as the POC filed it | This is the government's own record. Gemini reads it to speak it. |
| **Metadata and logs** | Session timing, which functions were called, the fact of a conversation at all | Google's abuse-monitoring logs keep prompts for a period unless switched off. |

Where it goes today: the Gemini Developer API from AI Studio. That endpoint gives no data residency, processes wherever Google chooses, and logs prompts for abuse monitoring even on the paid tier. For a pilot on a laptop that was fine. For a state service it is the first thing to change, and it is a contract change, not a code change.

What never leaves, already: the database, the routing decision, every number on screen, the audit trail, the citizen's phone number and ids. Mitra's design already keeps the facts at home and sends the model only what it needs to talk. That is the foundation every layer below builds on.

## 2. The ladder, from cheapest to strongest

Each rung keeps Gemini and keeps more data at home. They stack.

### Rung 1. Same models, different contract: Vertex AI in Mumbai with zero data retention

Gemini on Vertex AI is the same model family behind a Google Cloud contract, which the Developer API is not. Google commits to data residency at rest and during model processing for a list of countries that includes India, through the Mumbai region `asia-south1`. On top of that:

- **Zero data retention.** Prompt logging for abuse monitoring can be switched off by an approved exception, or is off by default under a Master Agreement or invoiced billing. Caching of inputs and outputs can be turned off per project. With both done, Google stores no prompt or response.
- **Customer-managed encryption keys** for anything Vertex does persist, held in a Karnataka-controlled key ring.
- **VPC Service Controls** so the project can only be reached from our relay's network, and **Access Transparency and Access Approval** so any Google staff access is logged and needs our yes.
- **No training on the data** is standard under Cloud terms.

What to verify before relying on it: whether the Live API, the native-audio model Mitra runs on, is served from `asia-south1`. Community reports show Live on Vertex in US and EU multi-regions and refusing the global endpoint, and Google's own note says Vertex Live defaults to `us-central1`. If Live is not in Mumbai, rung 1 covers every text and speech job in the POC and the cascade, and the live voice needs rung 4 or the sovereign plan. Also: grounding with Google Search keeps query logs regardless, so Mitra must not enable it, and it does not.

Cost to the product: none. Same models, same latency from Mumbai, likely better than today.

### Rung 2. Send less: minimisation engineering on our side

This rung is model-agnostic and cheap, because the pipeline already has the shape for it.

- **Pseudonymisation vault.** Extend the privacy shield from numbers to names. Before any text goes to the model, a local named-entity pass replaces person names with stable tokens (`PERSON_7`), and the relay swaps them back in captions and in the record. Gemini talks about `PERSON_7`; the citizen hears their own name because the relay re-inserts it in the transcript, and the live voice is told to say "you" and "the officer" instead of names. Kannada NER is the weak spot; AI4Bharat's IndicNER is the open candidate.
- **Handles instead of values.** Function results carry what the model must speak and nothing more. A case lookup returns the status, the officer's post and the days left, not the complaint text, the phone or the address, unless the turn asks for them. Today's `case_json` is fuller than the voice needs.
- **Aggregates with a floor.** Counts below a threshold (say five) in a small cell such as one GP and one service are reported as "fewer than five", the standard k-anonymity rule, so a dashboard answer never identifies a household.
- **Location generalisation.** The model sees the GP or taluk, never a house or a GPS point. The exact point stays in the POC for routing.
- **Memory held at home.** Mitra already rebuilds the session from the last six turns on every connect and never uses Google's stored state. Keep it that way: no uploaded files, no Interactions-API storage, no context caching on the Google side.
- **Allowlist, not blocklist.** The relay has a schema of what may leave per function and per profile, and rejects anything else. A DLP scan on the outgoing text is the second net.
- **Tamper-evident log of what left.** A hash chain of every payload sent, so an audit can prove what Google did and did not receive. Canary values seeded in the data show up if anything ever leaks through a model's output elsewhere.

Cost to the product: a little naturalness. Mitra says "the officer" more and names less. Nothing else changes.

### Rung 3. Anonymise the voice before it leaves

The content of speech can be masked; the identity of the speaker is in the timbre. Real-time speaker anonymisation replaces the speaker's voice with a pseudo-speaker while keeping the words and prosody, so Gemini hears an anonymous person say the same thing.

Where the research stands: DarkStream reports a speaker-verification equal error rate near 50%, meaning the speaker cannot be told apart from chance, with word error within about 9% and 203 ms end-to-end on a GPU. Stream-Voice-Anon runs in real time on an H200 at 151 to 399 ms. Zero-VC in 2026 targets zero lookahead. None of this is published on CPUs or phones, so it would run on the relay in India on a GPU, not in the browser.

Cost to the product: 150 to 400 ms added to Mitra's first word, some loss of Kannada recognition until it is tuned, and a weaker read of the caller's emotion, which Gemini's affective dialogue uses. Apply it to citizens by default and leave officers' voices as they are, or make it the citizen's choice. This rung is a research probe first, on our Kannada clips, before anything else.

### Rung 4. Gemini inside our perimeter: Google Distributed Cloud, air-gapped, in India

This is the rung that answers the question outright. Google Distributed Cloud air-gapped runs Gemini on Google-supplied hardware inside the customer's own data centre with no connection to the internet or to Google Cloud. Google announced the India offering for government and regulated sectors in July 2026 and states that prompts, model weights and outputs stay inside the customer's perimeter. Bharti Airtel sells and operates it in India as Airtel Air-Gapped Cloud, with on-site management and residency within India. On 20 Oct 2026 Google made Gemini 3.5 Flash generally available on air-gapped GDC and previewed managed RAG search inside the perimeter.

What this gives Mitra: every text and multimodal job, complaint understanding, the document reader, ATR drafting, AI mode, Kannada translation, runs on Gemini on racks in Bengaluru that Google cannot reach. The data question disappears for those jobs.

What to verify: whether the Live API, native audio in and out, is on the air-gapped catalogue. The October announcements name Gemini 3.5 Flash and search; nothing names Live. Until it does, the live voice stays on rung 1 or moves to the sovereign duplex plan. Also the model lag, 3.5 Flash on GDC against 3.8 on the cloud; who holds privileged access and encryption keys on the racks; how updates arrive without a network; and whether the Airtel offering includes Gemini itself or only Google's document and media services. Airtel's page lists document, audio and video analysis.

Cost: hardware and operations priced like infrastructure, not per token. For 10,000 to 50,000 users that is the same order as the sovereign GPU plan, with Google operating it.

### Rung 5, to watch: confidential inference with attestation

Google's Private AI Compute, launched November 2025, runs Gemini in Titanium Intelligence Enclaves on TPUs. The device verifies the enclave by remote attestation before sending anything, administrative access is cut off, and the data is visible only to the user, not to Google. Today it serves Google's own consumer features on Pixel phones. There is no developer API and no public timeline. If it becomes one, it is the answer for the live voice at cloud scale without any trust in Google's staff. Worth a standing request to Google India.

Confidential computing is available now for open models, H100 confidential VMs with attestation, but not for Gemini, whose weights Google does not release. Homomorphic encryption and secure multi-party computation cannot run a model of this size in real time and are not an option this decade.

## 3. The combined design: a sovereign gateway in India

```
  phones, browsers, 1902 bridge
          |
          v
  +-------------------------------------------------------------+
  |  SOVEREIGN GATEWAY  (our relay, in India, GoK control)       |
  |  1 wake word, session, memory          held here, never sent |
  |  2 privacy shield + pseudonym vault    numbers, names, ids   |
  |  3 voice anonymiser (citizens)         timbre replaced, GPU  |
  |  4 per-function allowlist + DLP scan   what may leave        |
  |  5 hash-chained send log, canaries     proof of what left    |
  |  6 router: which Gemini, by job                              |
  +------+-------------------------------+----------------------+
         |                               |
         v                               v
  Vertex AI, asia-south1 Mumbai     Google Distributed Cloud, air-gapped,
  zero data retention, CMEK,        Airtel-operated racks in Bengaluru
  VPC-SC, Access Approval           Gemini 3.5 Flash: understanding,
  Live API (if served there),       documents, ATR, AI mode, Kannada
  else the live voice until GDC     nothing leaves the perimeter
  carries native audio
         |                               |
         +---------------+---------------+
                         v
            Sakala POC + database, India   (facts, routing, audit: never sent)
```

Which rung protects which data:

| Data | Rung 1 Vertex ZDR | Rung 2 minimisation | Rung 3 voice anon | Rung 4 GDC |
|---|---|---|---|---|
| Audio content | processed in India, not stored | n/a | n/a | never leaves |
| Speaker identity | processed in India, not stored | n/a | removed before sending | never leaves |
| Names in text | not stored | replaced by tokens | n/a | never leaves |
| Numbers, ids, phones | not stored | already masked; handles | n/a | never leaves |
| Function results | not stored | trimmed to what is spoken; k-floor | n/a | never leaves |
| Logs and metadata | abuse logging off, caching off | our own hash log is the only log | n/a | our log only |

## 4. The legal frame, briefly

The Digital Personal Data Protection Act 2023 allows transfer of personal data to any country not on a Central Government restricted list, and Rule 15 of the 2025 Rules lets the government set conditions on data made available to foreign states. The United States is not restricted. So the Developer API is not unlawful; it is unaccountable, which is a different problem. For a government service the binding rules are MeitY's cloud guidance and Karnataka's own data policy, and both are satisfied more easily by an empanelled Indian region or by an air-gapped deployment than by an argument about Section 16.

The contract with Google should name: the Mumbai region for storage and processing, Live included or excluded in writing; the abuse-monitoring exception and caching off; no training; customer-managed keys; Access Approval; the sub-processor list; breach notice time; audit rights; deletion on exit; and for GDC, who holds root, who holds keys, and how updates are applied.

## 5. What each rung costs the product

| Rung | Latency | Naturalness | Features lost | Money |
|---|---|---|---|---|
| 1 Vertex Mumbai + ZDR | none, likely better | none | Google Search grounding, context caching | same per-token prices |
| 2 minimisation | none | Mitra names people less | none | engineering weeks |
| 3 voice anonymisation | +150 to 400 ms | emotion read weaker, Kannada WER to tune | affective dialogue partly | one GPU per ~50 streams on the relay |
| 4 GDC air-gapped | none | model one generation behind the cloud | Live until it ships on GDC | infrastructure pricing |
| 5 Private AI Compute | unknown | none | none | not available yet |

## 6. Verification before any decision

1. Ask Google India in writing whether `gemini-3.8-live` is served from `asia-south1` under residency commitments, and whether native audio is on the air-gapped catalogue or its roadmap.
2. Open a Vertex project in Mumbai, file the abuse-monitoring exception, turn caching off, and run the existing test suites against it. The code change is one base URL and an auth header; the suites tell us if anything moved.
3. Get an Airtel or Google quote for air-gapped GDC with Gemini 3.5 Flash at the 10,000-user stage, with the privileged-access and key-control answers in it.
4. Probe speaker anonymisation on the Kannada test clips: Stream-Voice-Anon on the H200, measure latency, Kannada WER through Gemini, and whether the function calls still land.
5. Red-team the minimisation: seed canary names and numbers, run the live banks, and search every outgoing payload for them.

## 7. Recommendation

Do rung 1 and rung 2 first. Together they move Mitra from an unaccountable endpoint to an Indian region with nothing stored at Google, and they cut what is sent to what the voice needs. That is weeks, not months, and it costs the product nothing visible.

Plan rung 4 for the 10,000-user stage: Gemini on air-gapped racks in India for every text and document job, which is most of the POC's model calls. Keep the live voice on Mumbai until native audio reaches the air-gapped catalogue.

Treat rung 3 as research with a go or no-go after the Kannada probe, and rung 5 as a standing request to Google.

And keep the sovereign duplex plan running in parallel. These rungs make Gemini accountable; they do not remove the dependency. The sovereign core does, and the minimisation and gateway work here is reused unchanged when it arrives.

## Sources

- [Google: data residency at rest and during ML processing](https://blog.google/intl/en-ca/company-news/technology/announcing-data-residency-at-rest-and-during-machine-learning-ml-processing/)
- [Vertex AI locations for ML services](https://docs.cloud.google.com/gemini-enterprise-agent-platform/machine-learning/general/locations)
- [Vertex AI multimodal FAQ on abuse monitoring and zero data retention](https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/multimodal-faqs)
- [Zero data retention for Gemini and Vertex AI, a deep dive](https://intuitionlabs.ai/insights/guides/zero-data-retention-gemini-vertex-ai-life-sciences)
- [Gemini Live API available on Vertex AI](https://cloud.google.com/blog/products/ai-machine-learning/gemini-live-api-available-on-vertex-ai) and [LiveKit community report on Live regions](https://community.livekit.io/t/gemini-3-8-live-rejected-with-vertexai-true-in-livekit-plugins-google-although-vertex-ai-serves-it-eu-multi-region/2179)
- [TechRepublic: Google brings air-gapped Gemini to India](https://www.techrepublic.com/fr/article/news-air-gapped-gemini-apac-india/)
- [Airtel Air-Gapped Cloud](https://www.airtel.in/b2b/airtel-air-gapped-cloud) and [coverage](https://telecomtalk.info/bharti-airtelair-gapped-cloud-organisations-internet-connectivity/1013099/)
- [Google: new innovations in Google Distributed Cloud](https://cloud.google.com/blog/topics/hybrid-cloud/new-innovations-in-google-distributed-cloud) and [Gemini search on air-gapped GDC](https://techbytes.app/posts/managed-rag-search-inside-the-sovereign-perimeter-gemini-on-gdc/)
- [Google: Private AI Compute](https://blog.google/innovation-and-ai/products/google-private-ai-compute/) and [The Hacker News coverage](https://thehackernews.com/2025/11/google-launches-private-ai-compute.html)
- [DarkStream real-time speech anonymisation](https://pith.science/paper/2509.04667), [Stream-Voice-Anon](https://www.researchgate.net/publication/399953322_Stream-Voice-Anon_Enhancing_Utility_of_Real-Time_Speaker_Anonymization_via_Neural_Audio_Codec_and_Language_Models), [Zero-VC](https://arxiv.org/pdf/2606.20218)
- [DPDP Act cross-border transfers](https://ksandk.com/data-protection-and-data-privacy/indias-new-cross-border-data-transfer-framework/) and [DPDP Rules 2025 guide](https://www.seclore.com/fundamentals/dpdp-rules-2025-compliance-guide/)
