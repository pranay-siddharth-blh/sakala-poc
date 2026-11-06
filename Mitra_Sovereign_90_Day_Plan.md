# Sovereign Mitra in ninety days

Written 26 Oct 2026 for Pranay and the Mitra team. Supersedes the six-month calendar in `Mitra_Sovereign_Plan_Report.md`; the architecture, the sovereignty guarantees and the scale costs there still apply. Nothing here is implemented.

## The three decisions, as taken

- Gemini stays in production and as the reference until Pranay is satisfied with our output. It is measured, compared against, and then retired. Its outputs are never used as training data.
- Moshi is the base model, starting from PersonaPlex weights if the NVIDIA licence allows government use, otherwise plain Moshi with the same recipe.
- All the Kannada training data is in hand.

## Why six months becomes three

1. **The bridge is no longer a product.** With Gemini serving citizens, the open-parts bridge does not have to be hardened for production. It shrinks to the factory that makes training data: about two weeks of work instead of six.
2. **Transcript-driven dispatch instead of a trained tool stream.** The core already emits a live text transcript of the citizen. The relay feeds that transcript to Mitra's existing brain (rules plus the Sarvam guided-JSON intent picker), the dispatcher runs the function, and the result text is prefilled into the core to be spoken. The core only has to listen and talk well; our existing code decides. Mitra already does this server-side for the auto picture and the Kannada submit. Teaching the core its own delegation stream becomes a later refinement, not a parity gate.
3. **Training is fast on our own cards.** One pass over ten thousand hours of Kannada through a 7B core is about a day on two H200s, so rounds are weekly and evaluated weekly by a standing listener panel.
4. **Adapter training for weekly rounds, one full pass at the end**, so one card trains while the other serves the demo.

## The ninety days

Four tracks from day one, a team of about ten.

| Weeks | Harness and atlas | Data factory | Training | Integration and serving |
|---|---|---|---|---|
| 1 to 2 | Virtual microphone at the WebSocket; Gemini atlas measured and signed; probes of Mimi, SraVaani, svara, IndicF5 on our Kannada clips; panel of five recruited | Recordings masked, split into caller and agent channels; open corpora gathered; synthetic Sakala dialogues generating in two voices | English core running from the open base on GPU 1 | Relay upstream swapped to the core; transcript-driven dispatch to the existing brain; prefill; captions from the monologue |
| 3 to 5 | Weekly atlas and English suites | Synthetic hours filtered by the tuned recogniser; 5,000 by week 5 | Kannada sound and language on mono data, then Kannada conversation on real plus synthetic; first Kannada checkpoint week 5 | English core serving the three desks as a demo on GPU 1; Sarvam-105B brain on GPU 2 |
| 6 to 8 | Weekly atlas, Kannada bank, panel | Sakala flow dialogues for all three desks, code-mixed turns | Persona, desks, read-back, language switching; round-one gate at week 8: Kannada bank 55, live UI 18, panel within 0.5 of Gemini | Kannada core replaces the English core; both languages on one model |
| 9 to 12 | Twenty-listener side-by-side against Gemini on scripted conversations, every atlas dimension | Hard cases: noise, phones, dialects, interruptions | Round two: code-mixing, voice, emotion; one full training pass overnight in week 11; parity attempt at week 12 | Load test on one card; delegation stream trained if time allows |

**"Satisfied", written down before week 1:** atlas within tolerance on every behaviour; Kannada bank and live UI tests green; every English suite green; panel within 0.3 of Gemini on naturalness and 0.2 on intelligibility; code-mix test passed; first word under 0.5 s; interruption cut under 0.25 s.

**The two GPUs during the ninety days:** GPU 1 serves the demo core, 30 to 50 sessions on the stock server with light batching. GPU 2 holds the brain and runs weekly adapter training. The full pass in week 11 uses both overnight. FP8 serving, compressed memory, the scheduler and the 3B distillation come after sign-off.

**Where it can slip:** a failed week-12 panel costs about two weeks per extra round, so month four is the fallback; mixed-channel recordings make diarisation harder and push weight onto synthetic data; a poor Mimi result on Kannada costs a week of codec adaptation; a PersonaPlex licence problem costs two weeks.

## After sign-off, and costs

- **Months 4 to 5:** distil to 3B, batched FP8 server with compressed memory and the session scheduler, real sessions-per-card measurement, 1,000-session pilot on three rented nodes.
- **Months 5 to 8:** 10,000 sessions on about a dozen nodes, PostgreSQL and Redis under the POC, the 1902 telephone bridge. GPU order placed in month 3.
- **Months 12 to 18:** 50,000 sessions, a dedicated hall of about a megawatt, a second site.

**Cost of the ninety days:** about ₹2 to 4 crore, nearly all people; no rented training cluster; a few lakh of Gemini spend for atlas measurement and side-by-side runs.

| Live sessions at once | GPUs | Rented per month | Bought |
|---|---|---|---|
| 1,000 | 9 to 11 | ₹20 to 30 lakh | ₹3 to 4 crore |
| 10,000 | 80 to 95 | ₹1.5 to 2.5 crore | ₹25 to 35 crore |
| 50,000 | 385 to 475 | ₹5 to 8 crore | ₹120 to 180 crore plus the hall |

**Sovereignty:** during the ninety days, Gemini via its Mumbai region with zero retention and the minimisation gateway. From sign-off, every model is ours on hardware in Karnataka with no outbound path, nothing from Gemini in its training, and the atlas as a permanent regression suite.

**Needed to start week 1:** the recordings, with a note on whether speakers are on separate channels; five Kannada speakers for an hour a week.
