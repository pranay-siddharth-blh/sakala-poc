# Sakala Mitra: R&D handoff

Written 26 Oct 2026 for anyone starting research or development on top of this project. It describes the system as it runs today: every model, its exact id and settings, the voice pipeline turn by turn, the shared grievance pipeline, the data, the code, the APIs, the requirements, the tests and the open items. Read `CLAUDE.md` section 0 for the day-by-day history behind it.

## 0. What already exists on paper, and why this document was needed

| File in the project root | Date | What it is | Current? |
|---|---|---|---|
| `Sakala_AI_POC_Technical_Architecture.png` / `.pdf` | 26 Oct | One picture of the five layers, every model, one voice turn, the real-time loop, tests and deploy. Rendered from `tools/arch_technical.html` by `tools/render_arch.py`; the 22 Oct edition is kept in `tools/backups/`. | Yes. Gemini only, Kannada on Live, current counts. Edit the HTML and run `python tools/render_arch.py` after any change. |
| `Sakala_Mitra_Models_and_Specs.pdf` | 26 Oct | Five pages on every model with exact ids, chains, settings, published specs and measured timings. Rebuilt from section 3 of this document by `tools/make_models_specs.py`; the 19 Oct edition is kept in `tools/backups/`. | Yes. Regenerate with `python tools/make_models_specs.py` after any model change. |
| `Sakala_AI_POC_Architecture.png` / `.pdf` | 14 Oct | The functional picture of the WhatsApp POC and the 8 stages. | Yes for the POC, but Mitra does not appear. |
| `Sakala_AI_POC_Mitra_Handoff.pdf`, `AI Grievance Assistant – POC Architecture.pdf` | 14 Oct | The first R&D handoff, written before the voice agent existed. The inner text still calls it Jarvis. | No. |
| `Sovereign Native Voice Architecture Infographic.png` | 26 Oct | The sovereign native full-duplex plan on one page: today, the proposed architecture, the 90-day Kannada factory, the 2-GPU pilot numbers, the scale path and costs. Rendered from `tools/sovereign_infographic.html` by `tools/render_infographic.py`; the 25 Oct version is in `tools/backups/`. | Plan, not the running system. Companion text: `Mitra_Sovereign_Plan_Report.md`, `Mitra_Sovereign_90_Day_Plan.md`, `Mitra Sovereign Duplex.md`. |
| `Mitra_Test_Questionnaire.md` / `.pdf` | 22 Oct | 85 English and 49 Kannada test questions with expected numbers. | Yes. |
| `Sakala_POC_Scope.pdf`, `Sakala_AI_POC_Final_Use_Cases.pdf`, `Sakala Use cases and Important Links.pdf`, the two client JPEGs | 13 Oct | The client's scope, the agreed 29 use cases, the client's own architecture drawings. | Yes, as requirements. |

So: the 22 Oct picture is the right thing to show for the shape of the system, and this document is the right thing to read for the models and the details. To refresh the picture, edit `tools/arch_technical.html` and re-render it the way `CLAUDE.md` describes.

## 1. What the system is

Two products share one pipeline and one database.

- **The Sakala WhatsApp POC** (`app/`, port 8020). A FastAPI service with a browser UI that shows a WhatsApp conversation inside an iPhone frame, the officer console and the Chief Secretary's dashboard. A citizen files a grievance or a Sakala service request in Kannada or English. The 8-stage pipeline understands it, completes it, routes it to the exact field officer for that village or Gram Panchayat, starts the clock, escalates, and shows it on the leadership screens.
- **Mitra** (`mitra/`, port 8030). A voice agent over the same POC for the same three profiles: Citizen, Officer, Chief Secretary. It is its own intake channel, not a wrapper on WhatsApp. It speaks English and Kannada in full duplex, calls functions, draws charts and the Karnataka map as it speaks, and keeps every screen in sync in real time. It drives the POC over HTTP and never writes to the database directly.

Both run on one laptop with no GPU, and a copy runs on a 1 GB AWS instance. Every AI call goes to Google Gemini through one API key kept on the server. No number on any screen ever comes from a model: counts, ids, officers and deadlines come from SQL in the POC.

Principles that hold everywhere: models choose from closed lists, data decides; only official masters; every action on the record; junk is never filed; low confidence goes to a human scrutiny desk; the grievance ladder and the Sakala appeal ladder never mix.

## 2. Architecture

```
                      BROWSER (vanilla JS, canvas; web desk and phone frame)
   WhatsApp citizen · Officer console · CS dashboard · AI mode        Mitra: orb, captions, stage, map, phone app
   app/web/index.html + app_wa_client.js + docupload.js               mitra/web/mitra.js stage.js orb.js app.js phone.js
            |  HTTP/JSON, 3.5 s polling                                   |  WebSocket /ws/live (16 kHz PCM up, 24 kHz down)
            |                                                             |  HTTP /api/turn · SSE /api/events
            v                                                             v
   +------------------------------+                           +-------------------------------+
   | SAKALA POC  :8020            |  <---- HTTP (sakala.py) --| MITRA  :8030                  |
   | app/server/api.py            |                           | mitra/server/main.py          |
   |  chat.py   WhatsApp engine   |                           |  live.py   relay to Gemini Live|
   |  pipeline  8 stages          |                           |  brain.py  intent (Gemini/rules)|
   |  routing   village->officer  |                           |  tools.py  55 intents -> POC   |
   |  sla.py    clock, escalation |                           |  query.py  10 data functions  |
   |  query.py  SQL for questions |                           |  board.py  CS dashboards      |
   |  ai.py     Gemini (POC jobs) |                           |  speech.py STT/TTS (cascade)  |
   |  docread   letter reader     |                           |  guard.py  masking, scrub     |
   |  transfer  return-with-hint  |                           |  knowledge.py 33 notes        |
   |  analytics insights, packs   |                           |  sync.py + notify.py real time|
   +--------------+---------------+                           +---------------+---------------+
                  |                                                           |
          app/data/sakala.db (SQLite, WAL)                           mitra/data/mitra.db
          cases, events, officers, gazetteer,                        sessions, turns, voice notes,
          ipgrs_records, masters, kv                                 feed, seen cursors, deviations
                  |
          Google Gemini API (one key, server side only):
            wss  BidiGenerateContent  gemini-3.8-live          Mitra full duplex, English and Kannada
            https generateContent      flash / lite / tts      Mitra cascade, STT, TTS, Kannada translation
            https openai/chat/completions  3.6-flash, 3.1-lite POC understanding, ATR, AI mode, document reading
```

Five layers, as drawn in the 22 Oct picture:

1. **Front end and channels.** Two single-page apps, no framework. Audio in the browser is Web Audio: a `ScriptProcessor` of 4,096 frames resampled to 16 kHz PCM, a playback queue at 24 kHz with instant cut, a 4 s ring buffer for the wake word, and an echo guard. No browser speech service is required.
2. **API layer.** Two FastAPI services on Python 3.11 and uvicorn. Cross-cutting middleware: per-IP rate limits, an 8 MB request cap, security headers, no-cache on pages, debug surfaces only with `MITRA_DEBUG=1`.
3. **AI layer.** The voice agent, the intent brain, the question router, understanding and routing, the document reader, the knowledge base and the guardrails. Models choose from closed lists; facts and numbers come from the data layer.
4. **Core services.** The 8-stage pipeline, the clock and escalation, the resolution loop, real-time sync and analytics. Both channels share these.
5. **Data layer.** SQLite in WAL mode, written the moment a case is filed, rebuilt from the real Excel by `ingest.py` in about two minutes.

## 3. Every model, with exact ids

All ids are Gemini model names as called by the code on 26 Oct 2026. Configuration lives in `mitra/.env` and `app/.env`; the code reads `mitra/.env` first, then the process environment, then `app/.env`. Only the key is secret; the model ids below are the configured or default values.

### 3.1 Mitra

| Job | Model chain, in order | Endpoint | Settings | When it is used |
|---|---|---|---|---|
| Full-duplex conversation, all three desks, English and Kannada | `gemini-3.8-live` | WebSocket `BidiGenerateContent`, relayed by `live.py` so the key never reaches the browser | Audio in 16 kHz 16-bit PCM, audio out 24 kHz. Voice `Kore`, temperature 0.6. Google's voice activity detection: 700 ms of silence ends a turn, 200 ms prefix padding. Input and output transcription on. `languageCode kn-IN` on a Kannada session. One system instruction per profile plus the screen context and the last 6 turns. Function declarations: every cascade intent for that profile except stop, repeat and smalltalk, plus the ten data functions. | Opened by the wake word, an orb tap or typing. Closed after 20 s of silence to save audio cost. On an upstream error the browser uses the cascade for 5 minutes and the server marks Live down for 120 s. |
| Cascade brain: one intent from a closed list | `gemini-3.8-flash` → `gemini-3.5-flash` (deprecated by Google, routed to 3.6) → `gemini-3.5-flash-lite` → `gemini-3.1-flash-lite` → rules | `models/{m}:generateContent` | Temperature 0, thinking level low, a response schema whose `intent` field is the enum of that profile's intents, so the model can only choose an action. A 429 parks a model for 30 minutes, a 503 for 2 minutes, a 404 for good. | Typed input, the fallback path, and the first turn after a language switch. A rules fast path answers navigation, chart switching, theme, identity, confirmations and most data questions before any model is asked. |
| Speech-to-text on the cascade, the "Hey Mitra" scanner, "Teach Mitra your voice" | `gemini-3.1-flash-lite` → `gemini-3.5-flash-lite` → `gemini-3.8-flash` → browser recogniser | `generateContent` with the 16 kHz WAV inline | "Transcribe exactly" prompt, temperature 0, thinking low. Fewer than 4 letters means no speech. | Every utterance while Mitra is idle is sent with `wake_only:true`; the server acts only if it begins with the wake word. |
| Kannada rendering of replies (`main.kn_say`, `translate_kn`) | the brain chain, so `gemini-3.8-flash` first | `generateContent` | `KN_PROMPT`: casual, warm, code-mixed spoken Kannada as used in Bengaluru and Mysuru; ids, names, numbers and dates kept as written; temperature 0.1. The first sentence is translated in parallel so speech starts sooner. | Every reply of a Kannada session that arrives over HTTP rather than from Live: document read, form submitted, photo, updates. |
| Cascade voice | `gemini-3.8-flash-tts` → `gemini-3.8-flash-lite-tts` → `gemini-3.1-flash-tts-preview` → browser `speechSynthesis` | `generateContent` with an audio response | Prebuilt voice `Kore`, up to 3,000 characters a call, 24 kHz WAV back. Only the words to be spoken are sent. | Only when Live cannot play the reply. A reply that arrives over HTTP while Live is open is read by the live voice instead (`lvRead`), so no TTS is spent. |
| Rules brain (`brain.rules`) | none | in process | Regular expressions for every intent, Kannada included; deterministic. | The last fallback, and the fast path listed above. The fake Live used by the tests runs on it. |

Dormant: the Sarvam adapters (`saaras:v4`, `bulbul:v4-flash`) are still in `speech.py` but are never chosen automatically; they run only if `MITRA_STT` or `MITRA_TTS` names them and a key exists. The H200 gateway Qwen path was removed on 23 Oct.

### 3.2 Inside the Sakala POC, called behind every filing

| Job | Model chain | Endpoint | Settings | Notes |
|---|---|---|---|---|
| Understand a complaint (`ai.understand`) | `POC_GEMINI_CHAIN`, default `gemini-3.6-flash` → `gemini-3.1-flash-lite` | Gemini's OpenAI-compatible `openai/chat/completions` | `reasoning_effort low`, temperature 0, `max_tokens 900`, `response_format json_schema` with `additionalProperties:false`. `service_id` is an enum of the 124 official service ids, so the model cannot name a service outside the masters. The schema also returns intent (GRIEVANCE, SERVICE_REQUEST, OUT_OF_SCOPE, WRONG_DOOR, UNCLEAR), grievance name, Sakala key, other department, confidence, reason, village, taluk, vulnerable flag and reason, English summary, language. The prompt carries the 5 most similar real grievances as reference. | A 429 or 5xx, a read timeout or a dropped connection moves to the next model. No network backs off for 60 s and the local model answers. Low reasoning effort took the call from 7.5 s to about 2.9 s. `gemini-3.8-flash` adds prose in JSON mode, which is why 3.6 is used. |
| Petition photo (`read_petition`) | same chain | same, vision through `image_url` | max 900 tokens, 60 s. Fewer than 8 letters read is refused. | WhatsApp photo path. |
| Officer ATR draft and ATR quality score (`draft_atr`, `check_atr`) | same chain | same | Draft temperature 0.2, 300 tokens. Check returns a JSON score; a case closes only at 4 or more. | `check_atr_local` is the heuristic fallback. |
| AI mode, ask the data (`ai.ask`) | same chain | same | A planner picks up to 3 of 5 typed tools (`query_cases`, `real_records`, `record`, `sakala_2025`, `insights`) with a fully declared argument schema; the tools run SQL; a writer turns the rows into HTML which is sanitised by `clean_html`. `guard_question` refuses prompt overrides and off-topic questions. | The chart is built from the tool rows by `api.build_chart`, never by the model. |
| Kannada for officer messages (`to_kannada`), briefs (`brief`) | same chain | same | temperature 0.1 | |
| Voice notes and the AI-mode mic (`ai.transcribe`) | `POC_GEMINI_STT_CHAIN`, default `gemini-3.1-flash-lite` → `gemini-3.6-flash` | `generateContent` with `inline_data audio/wav` | Kannada and English | |
| Written complaint reader (`docread.py`) | Orientation voters `gemini-3.1-flash-lite` and `gemini-3.6-flash`; the three reads on `gemini-3.6-flash`; fallback `GEMINI_MODEL` (`gemini-3.8-flash`) then `GEMINI_FALLBACK_MODEL` | `generateContent` with the page inline | Orientation: the four turns of the page on one labelled 2×2 sheet, "which panel reads upright", two voters in parallel, the stronger decides a tie, about 3 s. Then three independent reads in parallel: a faithful transcript, the form fields with English, and a differently worded second extraction. A field is confirmed only when both extractions agree. Thinking on except for lite models. A 6-digit iPGRS number in the letter is looked up in the 9,999 real records and used as evidence. | 12 to 17 s from upload to the filled form with the officer preview; a repeat upload is instant by file hash. 17/17 gold fields on the three real handwritten letters. |
| Offline classifier (`local_ai.py`) | scikit-learn, `app/data/local_models.joblib`, 46 MB | in process | TF-IDF on character n-grams 2 to 4, word-bounded, 60,000 features, sublinear tf, so it works on Kannada script. Two SGD classifiers (modified Huber, alpha 2e-5): 38 departments and 124 pilot services. Cosine nearest neighbours over 5,204 real pilot grievances return the 5 closest. Keyword rules for wrong door, out of scope, Sakala service requests and vulnerability. Kannada-to-Latin transliteration so Kannada village names match the gazetteer, with `KN_COMMON` so everyday nouns are never taken as places. Hold-out: department 71.4%, exact service 39.2%, top-3 43.4%. | Always on. Second opinion on every model decision; the whole job when no model is reachable. A grievance auto-routes only when the model's confidence clears the tuned threshold (0.55) and the offline model agrees. |
| Officer router (`routing.py`) | rules learned from the data, not a model | in process | service → officer role (RTC to the Tahsildar 99%, drinking water to the AE RDWS 100%, street light to the PDO 97%…), then taluk and GP → the named officer, with the escalation ladder from `up_id`. | Matches the real iPGRS officer in 97.6% of 673 Mysuru cases and 95.7% of 4,611 statewide. |

Measured accuracy of the whole understanding path on 40 real Mysuru complaints, text only, 24 Oct on Gemini 3.6 Flash: department 97.5%, service 72.5%, exact officer 77.5%. The 14 Oct run on the office gateway was 97.5 / 95 / 92.5, so service accuracy dropped with the model change and is an open item. The router alone is unchanged.

### 3.3 Published specs of the Gemini models, as opened on 19 Oct 2026

| Model | In → out | Input / output tokens | Notes |
|---|---|---|---|
| `gemini-3.8-live` | text, image, audio, video → text and audio | 131,072 / 65,536 | Function calling, Live API, native audio, interleaved thinking, search grounding. Structured output not supported. Text-only replies not supported on this model. |
| `gemini-3.8-flash` | text, image, video, audio, PDF → text | 1,048,576 / 65,536 | Stable Sep 2026, thinking low/medium/high, structured outputs and function calling. |
| `gemini-3.6-flash` | same | 1,048,576 / 65,536 | The model Google routes deprecated 3.5-flash calls to. |
| `gemini-3.5-flash-lite` | same | 1,048,576 / 65,536 | Stable Jul 2026. |
| `gemini-3.1-flash-lite` | same | 1,048,576 / 65,536 | Stable May 2026. |
| `gemini-3.8-flash-tts` | text → audio | 8,192 / 16,384 | 130+ languages, auto-detected. |
| `gemini-3.8-flash-lite-tts` | text → audio | 8,192 / 16,384 | Low latency, Kannada included. |
| `gemini-3.1-flash-tts-preview` | text → audio | 8,192 / 16,384 | Legacy preview; drop from the chain when convenient. |

Known API behaviours found on the way: the OpenAI-compatible endpoint supports `response_format json_schema` with enums and `additionalProperties:false`, integer enums, vision `image_url` and `reasoning_effort`; it rejects `chat_template_kwargs`; an open `{"type":"object"}` comes back as `{}`, so every argument schema must be declared in full.

## 4. The voice pipeline, turn by turn

### 4.1 One live turn (the normal path)

1. The page starts in **Standby**: the wake scanner listens locally (amplitude VAD, 160 ms onset, 650 ms silence cut, 1 s pre-roll, 4 s ring buffer). Nothing is streamed.
2. "Hey Mitra", an orb tap, or typing opens a Live session: the relay (`live.py`) connects to `gemini-3.8-live` with the profile's instruction, the screen context, the last 6 turns and the function declarations. Setup takes about 1.3 s. A command said in the same breath as the wake word becomes the first turn.
3. 16 kHz PCM streams up; 24 kHz PCM comes back on a playback queue. The input and output transcripts drive the captions word by word, the conversation strip, the chart reveal (`Stage.hear`: a bar or slice appears the moment its name is spoken) and the number checks.
4. When the model calls a function it closes the tool-call turn first and speaks in the next one; the relay holds the exchange open (`tool_wait`). The call runs `tools.execute` or `query.run`, the same code as the cascade, so routing, permissions, notifications and sync are identical. The result is sanitised, wrapped as data, and returned. Function call latency about 0.4 s; first audio about 0.45 s.
5. If the model says nothing 4 s after a result, `_speak_watch` nudges it once. If a live turn ends with no function call on a data question, the server runs the deterministic router itself and pushes the picture (`auto:true`).
6. Spoken numbers and ids are checked against the function results; deviations are logged to `mitra.db`. Vendor names are scrubbed from captions. Long Sakala numbers are spoken as "the application ending in 4811".
7. Barge-in: Gemini's `interrupted` flag cuts playback; locally, a voice clearly louder than Mitra's echo for two frames ducks her at once. Stop, Esc or an orb tap also cut.
8. 20 s of silence returns to Standby and closes the socket. A profile, officer or language change reconfigures and reopens the session, and the announcement after the change carries every reply of that turn.

### 4.2 Kannada

Kannada is full duplex on the same live session since 22 Oct. The Kannada persona block comes first in the instruction; function arguments stay in English; results are said in Kannada with ids and numbers exact; `speechConfig.languageCode` is `kn-IN`. The POC normalises Kannada arguments that slip through (ಹುಣಸೂರು → Hunsur). A language switch is understood in either language by `brain.lang_asked`, deterministically; at the end of a turn the server switches itself when the model did not, or when Kannada was simply spoken to an English session. Replies that come over HTTP are rendered by `kn_say`. Kannada submit words (ಸಲ್ಲಿಸಿ, ಸಬ್ಮಿಟ್, ಕಳಿಸಿ) file an open form even if the model called nothing (`SUBMIT_RX`). The wake word is also recognised in Kannada script (ಹೇ ಮಿತ್ರ).

### 4.3 The cascade (fallback and typed input)

hear → decide → act → speak. Speech-to-text on the lite chain, one intent from the brain chain as guided JSON, `tools.execute`, then the reply: read by the live voice if Live is open, else Gemini TTS, else the browser. An English cascade turn is 4 to 6 s end to end; a Kannada one 7 to 10 s to the first word. The cascade is used for the wake scanner, typed text when Live is closed, and for 5 minutes after any Live failure.

### 4.4 Intents and functions

`brain.INTENTS` holds 55 intents with the profiles that may use them: 27 on the citizen desk, 39 on the officer desk, 34 on the Chief Secretary's. Shared: switch_profile, set_language, set_theme, help, repeat, stop, tick, reset_demo, smalltalk, go_to, ask_knowledge, identity, forget_conversation, confirm_action, cancel_action, view_as_officer. Citizen: chat_text, chat_option, confirm, change, track, apply_service, feedback_yes, feedback_no, appeal, voice_note_officer, reply, later, updates, upload_document. Officer: login_as, inbox, open_case, next_case, read_case, accept, ask_info, draft_atr, resolve, return_case (with `to` and `place`), reject, comp_order, comp_hrms, voice_note_cs, voice_note_citizen. Chief Secretary: summary, ask_data, filter_cases, officers_attention, nudge (with her words), wednesday_pack, tracker, show_chart_as, voice_note_officer_cs.

The ten data functions declared to Live (`mitra/server/query.py`): case_info, find_cases, ipgrs_records, officer_profile, place_info, statewide_stats, sakala_2025, compare, ranking, dashboard. Each takes typed filters (district, taluk, department, status, officer, source, kind, escalated, days_left, dates, group_by, sort, limit, chart) and runs fixed parameterised SQL in the POC through `POST /api/query`. An officer's view is scoped to their own ladder in the SQL. The model never writes SQL.

Before any model is asked, `tools.route_question` maps most data questions deterministically, `board.py` turns the Chief Secretary's questions into dashboards (KPIs, the 7-day clock histogram, levels, departments, places), and a conversational scope keeps follow-ups such as "and Hunsur?" inside the last dashboard.

Consequential actions (reject, return, resolve, compensation, HRMS, nudge, reset) get a spoken read-back and wait 120 s for a yes.

## 5. The 8-stage pipeline and the deterministic layer

Shared by WhatsApp and Mitra. Mitra calls it through `POST /api/intake` with steps understand, place, create, scrutiny, document, apply, reply, feedback, appeal, messages, mine; `chat.py` is untouched by Mitra.

1. **Entry.** WhatsApp text, voice note, photo or letter; Mitra voice or typed text; a written complaint read into the official iPGRS form (`ipgrs_form.json`, the three portal steps).
2. **Privacy shield.** `privacy.mask`: email, 12-digit Aadhaar, Indian mobile, card ids. Masked before any model. Personal names inside Kannada text are still visible, an open item.
3. **Understanding.** Section 3.2. Master-only, with confidence and reason. The local wrong-door, out-of-scope and service-request checks override the model (engine label `llm+rules`).
4. **Completion.** Only what is missing is asked, usually the village or GP. `chat.place_reply` is the one resolver for both channels: a taluk named outright beats a look-alike village; a bare taluk gives its GP list or goes straight to confirm for a taluk-level officer; the demo GPS point is Gorahalli → Chapparadahalli GP.
5. **Validate and confirm.** Place valid, duplicate check, citizen confirms. Unclear requests are offered to the scrutiny desk and filed only on a yes.
6. **Exact-officer routing.** `routing.route`: learned role → taluk and GP → the named officer; the ladder from `up_id`. `transfer.resolve` handles a return with a suggestion: officer named, or role at a place, or place only, or the returning officer's own role there; anything unmatched goes to the scrutiny desk with the suggestion on record.
7. **Deadlines and reminders.** `sla.py`: L1 → L2 → L3 auto-escalation on 7 / 5 / 3 days (assumed), due-today reminders, the Sakala legal clock for applications (₹20 a day, ₹500 cap, Form C, mock HRMS), the resolution loop (a citizen's "not solved" re-opens the case one rung up with a fresh clock).
8. **Leadership view.** Officer inbox and Chief Secretary dashboard, the map, the Wednesday pack, E-4 defaulters; every change reaches every other screen within 0.7 s through `sync.py` and `notify.py` over SSE.

Every routing decision stores its evidence in `cases.audit`: engine, confidence, threshold, decision and reason, alternatives, 5 similar real cases, rules applied, how the place was found, the officer rule, and any human re-route. Every action taken by voice is appended to the event as "via Mitra (voice)" with the masked sentence.

The knowledge base (`mitra/knowledge.yaml`, 33 notes, re-read on change) answers general questions about Sakala, iPGRS, the Act, compensation, appeals, helplines, the people and the pilot through a deterministic matcher; an uncovered question gets "that is not in my notes yet", never an invented fact.

## 6. Data

`app/data/sakala.db` on 26 Oct: 4,763 cases (4,761 grievances, 2 Sakala applications; 3,038 pending), 6,394 case events, 3,433 officers, a gazetteer of 2,371 village → GP → taluk → district rows (31 districts, 224 taluks, 1,552 GPs), 9,999 masked iPGRS records, 38 departments, 26 line departments, 124 pilot services, 221 grievance types, 384 Sakala 2025 performance rows, notifications, citizen messages, chat sessions, the AI log and the `kv` store (demo clock, evaluations, threshold). `sakala_pristine.db` is the reset snapshot. `data/llm_eval.json` holds the accuracy run outside the database so a reset keeps it.

`mitra/data/mitra.db`: sessions, turns (7-day retention, "forget this conversation" deletes at once), voice notes, the notification feed with wall-clock arrival times, per-screen seen cursors, and the spoken-number deviations.

Source data: `Sample grievance cases.xlsx` (9,999 real iPGRS grievances, 3 to 9 Oct 2026, 17 columns, 38 departments), the three identical Sakala 2025 district performance workbooks, KGIS and OSM boundaries. `python -m server.ingest` rebuilds masters, learned officer rules, the gazetteer, the officer master, the live caseload, the synthetic demo cases, the local model and the routing evaluation in about two minutes. Pilot: Revenue, RDPR, Food; Mysuru district; Piriyapatna, Hunsur and Mysuru taluks; the data covers the whole state.

## 7. Code map

Line counts on 26 Oct. Python 3.11 throughout; the browser code is plain JavaScript.

**`mitra/server/`**: `main.py` 756 (FastAPI app, `/api/turn`, session, SSE, clips, TTS, document and photo doors, Kannada rendering, wake-word learning), `live.py` 462 (the Live relay and harness rules), `brain.py` 648 (intents, Gemini guided JSON, rules, `lang_asked`), `tools.py` 2,019 (every intent executed against the POC, speech templates, UI ops, the question router, read-back), `query.py` 454 (the data functions and their screen panels), `board.py` 382 (dashboards, scope, Kannada routing), `speech.py` 182 (STT and TTS adapters), `guard.py` 241 (masking, vendor scrub, injection stripping, spoken-id checks), `knowledge.py` 137, `notify.py` 333, `sync.py` 133, `store.py` 154, `sakala.py` 139 (HTTP client for the POC), `config.py` 114.

**`mitra/web/`**: `mitra.js` 1,597 (state machine, Live client `LV`, wake scanner, captions, panels, notifications, theme, view switching), `stage.js` 644 (canvas charts, the Karnataka map `KaMap`, speech-synced reveal), `orb.js` 221, `splash.js` 182, `phone.js` 132 and `app.js` 107 (the phone frame and the phone layout), `portal.js` 80, `mitra.css` 1,581, `assets/mapdata.js` (31 district and Mysuru taluk outlines).

**`app/server/`**: `api.py` 983 (every endpoint, permissions, rate limits, chart building), `chat.py` 821 (the WhatsApp state machine, EN and KN), `query.py` 509 and `query_board.py` 306 and `compare.py` 198 (SQL for questions, dashboards, comparisons), `docread.py` 431, `analytics.py` 393, `ai.py` 388, `ingest.py` 350, `local_ai.py` 260, `sla.py` 211, `transfer.py` 198, `pipeline.py` 195, `routing.py` 112, `db.py` 112, `privacy.py` 19, `config.py` 26.

**`app/web/`**: `index.html` generated from `wireframe/index.html` by `tools/make_app_ui.py` with `app_wa_client.js`, `app_charts.js`, `app_insights.js`; `docupload.js`; Chart.js 4.5.1 vendored.

**Elsewhere**: `tools/` patches and builders, `deploy/` (systemd units, Caddyfile, bundle builder, requirements), `launchers/` (desktop launchers), `mitra/tests/` and `tools/tests/`.

## 8. API surface

**POC, :8020.** `GET /api/bootstrap`, `GET /api/state?session=&scope=`, `GET /api/case/{id}`, `GET /api/changes?after_event&after_notif`, `POST /api/chat`, `POST /api/intake` (steps above), `POST /api/cases/{id}/action` (accept, info, return with `to` and `place`, reject, resolve, nudge with note, reroute, comp_order, comp_hrms; `via` and `heard` for the voice audit), `GET /api/cases/{id}/transfer_preview`, `POST /api/cases/{id}/draft_atr`, `POST /api/query` (the ten typed tools, with `viewer` for officer scope), `POST /api/ask`, `POST /api/transcribe`, `POST /api/photo`, `POST /api/upload`, `GET /api/insights/*`, `GET /api/sakala/{tracker,early_warning}`, `GET /api/review_pack`, `GET /api/e4`, `GET /api/ai_log`, `POST /api/clock/tick`, `POST /api/reset`, `GET /api/health`.

**Mitra, :8030.** `WS /ws/live`, `POST /api/turn` (text or audio, `wake_only`, `want_audio`), `POST /api/session`, `GET /api/events?session=` (SSE), `GET /api/notifs`, `POST /api/notifs/seen`, `POST /api/clip`, `POST /api/tts`, `POST /api/document`, `POST /api/document/submit`, `POST /api/photo`, `POST /api/wake_learn`, `POST /api/forget`, `GET /api/tracker`, `GET /api/boot`; with `MITRA_DEBUG=1` also `/api/live_stats`, `/api/deviations`, `/shot.html`, `/dbg.html`.

## 9. Guardrails

Masking before any model; official masters only; the confidence threshold with the offline second opinion; the scrutiny desk; routing evidence on every case; the grievance and Sakala ladders never mixed; only the owner acts, only the Competent Officer orders compensation, a reason to reject, an ATR scored 4 or more to resolve; an officer sees only their own ladder; session isolation for citizens; prompt-injection hardening (data delimited, instruction-like lines stripped, an injection battery); AI-mode question guard and HTML sanitising; rate limits and request caps; vendor names never on screen or in speech; a fixed identity answer; spoken numbers and ids checked against results; read-back before consequential actions; 7-day retention and "forget this conversation"; every voice action on the record.

## 10. Requirements and specs

**Runtime.** Python 3.11 (3.11.17 on the server). Packages pinned in `deploy/requirements.txt`: fastapi 0.136.3, starlette 1.2.1, uvicorn[standard] 0.48.0, httpx 0.28.1, websockets 16.1.1, pydantic 2.13.4, python-multipart 0.0.32, PyYAML 6.0.3, numpy 1.26.4, scipy 1.17.1, pandas 3.0.1, scikit-learn 1.9.0, joblib 1.5.3, openpyxl 3.1.5, pillow 12.0.0, pymupdf 1.28.2. The scikit-learn and numpy versions matter: the trained model file loads only on the versions it was saved with.

**Hardware.** No GPU anywhere. The laptop runs both services. The AWS copy runs both on a t3.micro: 2 vCPU, 908 MB RAM with a 2 GB swap, 8 GB disk. All model work is remote on Gemini, so the services are I/O bound. The database is about 60 MB plus the 46 MB model file.

**Browser.** Any Chromium browser with a microphone (Brave, Edge, Chrome). Web Audio and WebSocket. HTTPS is required for the microphone anywhere except localhost. The office VPN blocks the browser's own cloud speech recogniser, so Mitra does not depend on it.

**Network.** Outbound HTTPS and WSS to `generativelanguage.googleapis.com`. Nothing else. Inbound: 8020 and 8030 locally, or 443 through Caddy on the server.

**Configuration.** `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_FALLBACK_MODEL`, `GEMINI_TTS_MODEL`, `GEMINI_VOICE`, `GEMINI_LIVE_MODEL`; optional `POC_GEMINI_CHAIN`, `POC_GEMINI_STT_CHAIN`, `GEMINI_BRAIN_CHAIN`, `GEMINI_STT_CHAIN`, `GEMINI_TTS_CHAIN`; `MITRA_BRAIN`, `MITRA_STT`, `MITRA_TTS` (auto, gemini, rules or browser); `MITRA_NAME`, `MITRA_WAKE_WORDS`, `MITRA_DEBUG`, `MITRA_RETAIN_DAYS`, `MITRA_PORT`, `SAKALA_URL`, `MITRA_START_POC` (0 on a server where the POC is its own service), `MITRA_LIVE_URL` (points the relay at the fake Live for tests). The Gemini key is a prepaid AI Studio project; Live is billed on audio tokens, which is why sessions close after 20 s idle.

**Running.** `app\run.bat` or `python -m uvicorn server.api:app --port 8020` from `app/`; `mitra\run.bat` or `python -m uvicorn server.main:app --port 8030` from `mitra/`, which starts the POC if it is down. Desktop launchers in `launchers/` open a Brave tab on a splash that waits for the health endpoint. Test instances: `bash mitra/tests/restart_mitra.sh all` brings up 8030 on real Live, 8031 on a fake Live (8099) and 8032 on a failing fake (8098), with `MITRA_NO_SYNC=1` and `MITRA_DEBUG=1`.

**Deployment.** `deploy/make_bundle.py` stages `app/` and `mitra/` with a consistent database snapshot and nothing secret; `sakala-poc.service` and `mitra.service` bind to 127.0.0.1 under a `sakala` user; Caddy terminates TLS with Let's Encrypt on sslip.io names and gates access with a cookie set by `/__access?code=`. Keys live only in `/opt/sakala/app/.env`, mode 600.

**Measured on the running system.** Live setup 1.3 s, first word 0.45 s, function call 0.4 s, question to chart about 3 s, a change on any screen within 0.7 s, understanding call about 2.9 s, letter to form 12 to 17 s, Kannada first audio about 0.5 s on Live.

## 11. Tests

Mitra, `mitra/tests/`: `test_turns` 24, `battery` 101, `test_nav` 22, `test_guardrails` 59, `test_knowledge` 14, `test_notify` 21, `test_realtime` 35, `test_query` 32, `test_live` 15 offline and 13 online, `question_bank` via `run_bank` 113, `cs_bank` 94, `kn_bank` 55, `cs_live_bank` and `kn_bank --live` on real Live, `live_battery` 32, `live_battery2` 11, `live_doc` 8, `live_doc_ui` 10, `live_knowledge` 7, `live_return` 4, `lang_switch_probe` 8, `kn_live_ui` 18, and the browser suites over the DevTools protocol (`cdp.py`): `ui_live` 10, `ui_app` 17, `ui_stage` 19, `ui_map` 13, `ui_board` 13, `ui_portal` 16, `ui_theme` 11, `ui_splash` 9, `ui_view` 7, `ui_switch_matrix` 33, `ui_resolution` 18, `ui_docupload` 28, `ui_upload_phone` 17, `ui_officer_view` 6, `layout_sweep` 35 web and 35 phone, `phone_ui_sweep` 14. `fake_live.py` imitates Gemini Live on the rules brain so the structure is tested without cost.

POC, `tools/tests/`: `test_backend` 91, `test_twoway` 21, `test_guardrails` 27, `test_statewide` 40, `test_parity` 14, `test_docdoor` 17, `test_return_suggest` 31, `doc_letters` on the three gold letters, `ui_return_drawer` 7, plus the orientation and model probes.

Rules for running them: announce a regression run; tests never speak aloud; the POC backend suite resets the demo database, so do not run Mitra UI suites beside it; the live banks re-read the database before each question; snapshot `sakala.db` and `mitra.db` before a long run and restore after.

Last full Gemini-only run, 24 Oct: POC backend 90/91 then fixed, chat flows 34/34 twice, twoway 21/21, guardrails 27/27, statewide 40/40, parity 14/14, return_suggest 31/31, docdoor 16/17 (one model-variation check), gold letters every field right; Mitra turns 24/24, battery 101/101, nav 22/22. Still to re-run on the Gemini-only code: Mitra guardrails, knowledge, notify, realtime, test_live, cs_bank, kn_bank, run_bank and the live voice sample. They were stopped for a demo.

## 12. Known limits and open items

- Everything depends on one Gemini key and Google's quotas. A depleted prepaid balance or a 1011 from Live puts Mitra on the cascade; a depleted cascade puts it on rules and the browser voice. The sovereign plan in `Mitra Sovereign Duplex.md` is the answer to this, and it is a plan.
- Service accuracy on the understanding step fell from 95% to 72.5% with the move to Gemini 3.6 Flash; the router is unchanged. Worth a prompt and evaluation pass.
- SQLite is right for a laptop and a pilot. Thousands of concurrent users need PostgreSQL, Redis for sessions and a queue for notifications; the pipeline code does not change.
- Rate limits are per IP; real users arrive through carrier addresses.
- Personal names inside Kannada complaint text are not masked.
- SLA days per level are assumed (7 / 5 / 3); iPGRS does not publish them. Sakala service timelines are illustrative.
- A Kannada turn on the cascade is 7 to 10 s to the first word; on Live it is about 0.5 s, so keep Live healthy.
- The letter reader takes 12 to 17 s because of the independent second reading and the orientation check; accuracy was chosen over speed.
- Cascade fallback robustness: a single Live setup failure marks Live down for 120 s on the server and 5 minutes in the client. A retry before falling back and a shorter client fallback were proposed and not built.
- No RAG, no embeddings, no vector database anywhere. The only retrieval is the TF-IDF neighbour lookup and the knowledge notes.
- `CLAUDE.md` still says the launchers open an Edge app window; they open a Brave tab.

## 13. Where to start

Read `CLAUDE.md` sections 1, 2, 4 and 7 for the domain and the rules, then section 0 from the top for how each piece came to be. Run both services, press Start, say "Hey Mitra, read my inbox" on the officer desk, and watch `mitra/server/live.py` and `tools.py` with the test instance on 8031 and the fake Live, which costs nothing. To swap a model, change the chain variables in `mitra/server/config.py` or `app/server/ai.py`; everything that touches a model goes through `brain.gemini_generate`, `speech.py`, `ai.chat`, `ai.transcribe` and `docread._gemini`, and nothing else. To swap the voice engine entirely, keep the `/ws/live` contract and replace the upstream in `live.py`; the browser, the functions and the pipeline will not notice.
