# Sakala Mitra

One voice agent for the three Sakala profiles: the Citizen, the Officer and the Chief Secretary. **Mitra is its own
input channel**: the citizen just says what is wrong (a photo of a petition is optional) and the request goes through the
full Sakala pipeline (privacy shield → AI understanding → completion → confirm → exact officer → clock → dashboards) and
straight to the officer. Everything the officer or the Chief Secretary does comes back to the citizen in real time, and the
other way round. It drives the Sakala POC through its API (the additive `/api/intake`, `/api/changes`, `/api/case/{id}`
endpoints); the WhatsApp engine is untouched. The pipeline now covers the whole state: 31 districts, 224 taluks, 3,433
officers, 4,757 live cases.

Say **"Hey Mitra"** (always listening after Start), hold the mic, or type. The red **Stop** button, `Esc` or saying "stop"
silences it at once.

**Start:** double-click `run.bat` (or from this folder: `python -m uvicorn server.main:app --port 8030`), then open
http://localhost:8030. If the Sakala POC (port 8020) is not running, Mitra starts it. Press **Start** on the splash
to enable the microphone.

## Talk to it

| Profile | Say |
|---|---|
| Citizen | "There is no drinking water in Gorahalli" (anywhere in Karnataka works: "no water in Holaluru", "street light in Sagar taluk") · "Piriyapatna" · "share my location" · "yes, file it" · "track my request" · "any update from the officer?" · reply to the officer's question in your own words · "apply for a caste certificate" · "appeal" · "yes it is solved" / "no, still not fixed" · "send a voice note to the officer: …" |
| Officer | "read my inbox" · "open the first one" / "open GR-504203" / "the overdue one" · "accept" · "ask the citizen which street" · "draft the report" · "resolve: inspected the site, pipeline repaired, supply restored" · "return it, not my jurisdiction" · "reject it as a duplicate" · "order compensation" · "next case" · "log in as Tahsildar Hunsur" · "tell the Chief Secretary …" |
| Chief Secretary | "give me the position" · "show the overdue cases" · "which officer has the most overdue cases" · "tell me about grievance 502706" (any G.Id from the Excel) · "list all pending cases from the Revenue department in Bagalkote" · "how many grievances came from Shivamogga by department" · "nudge the Tahsildar of Piriyapatna" · "read the Wednesday pack" · "Sakala 2025 district performance" · "E-4 defaulters" · "send the Tahsildar a note …" |
| Anywhere | "switch to officer mode" · "speak in Kannada" · "move time forward by 7 days" · "repeat" · "stop" · "help" |

Controls: say **"Hey Mitra"** (alone, or with the request in the same breath: "Hey Mitra, read my inbox"); **tap
the orb** to wake it without saying the name, or to silence it; **tap** the mic button to mute / unmute (or press `M`), **hold** it or **Space** to talk (works even while muted); the
**wake pill** (or `H`) turns hands-free on/off; `/` focuses the text box; **Esc** stops Mitra speaking. The orb can
be dragged to spin, pulled like jelly, and tapped. The profile switcher is bottom-left. Click any inbox row, KPI
tile or option chip: it is the same as saying it.

Talking over it: say "Hey Mitra …" while it is speaking and it lowers its voice, checks the clip and, if it was for
it, stops and acts; a cough, the speakers or people nearby do not stop it (press Stop for that). You may pause for
up to ~1.5 s mid-sentence ("uh…") without it cutting you off.

How the wake word works: the page keeps a 4 s microphone ring buffer. Whenever someone speaks while Mitra is
idle, the utterance is cut on silence and posted to `/api/turn` with `wake_only:true`; Gemini transcribes it and the
server acts only if it begins with the wake word (`main.wake_rx()` also accepts the ways speech models mishear
"Mitra"), otherwise it answers `intent:"ignored"` and nothing is logged. The browser's own recogniser is used as a
faster path when it can reach its cloud service; on corporate VPNs it usually cannot, and it is switched off.

## Full duplex (English)

Mitra talks like a person on a call: say **"Hey Mitra"** (or tap the orb, or type) and a live conversation opens on
Gemini Live (`gemini-3.8-live`). You can talk over it at any moment and it stops and listens; no wake word is needed
until the conversation goes quiet for ~20 s, when it returns to **Standby** (the mode pill above the orb shows
Standby · Live · full duplex · Voice · cascade · ಕನ್ನಡ, with the time to Mitra's first word). Every action is still done by
Sakala's own code (Live only chooses the function and speaks the result), so routing, permissions, notifications and the
8-stage pipeline are identical. **Kannada** uses the cascade (hear → understand → act → translate → speak); a reply's
first phrase is spoken while the rest is prepared. If Live is unavailable or over quota, Mitra falls back to the cascade
on its own. Use a headset for the demo: laptop speakers can echo (an echo guard limits this).

Ask anything about the data (officer and Chief Secretary): any case id or the 6-digit G.Id from the Excel ("what is the
status of 503063, who has it, where is it"), counts and rankings ("which district has the most pending cases", "how many
Revenue cases are open in Bagalkote"), officers ("tell me about PDO Attigodu"), places ("what is Bylakuppe"), the 9,999
iPGRS records ("how many Health grievances came through the mobile app"), Sakala 2025 performance. Every number comes
from SQL (`app/server/query.py`), never from the model.

## Stage mode (charts that build as Mitra speaks)

Ask the Chief Secretary screen anything that has a picture in it: "compare Piriyapatna, Hunsur and Mysore", "Revenue
versus RDPR on open and overdue", "which district has the most pending cases", "cases by department", "Sakala 2025 month
by month". The dashboard sinks into a dock at the bottom, the orb glides to the corner, and chart cards arc in from the
bottom-left. Each bar, slice or point appears the moment Mitra says its name (she is told to speak them in order), the
rest fill in at the end, and an insight chip sums it up. Say "close the chart", tap a dock chip or "Dashboard" to come
back. Up to five named things get one bar each; longer rankings become a ranked bar race where the named ones glow.
Every number comes from SQL (`app/server/compare.py`); the model only chooses what to compare.

## Engines (mitra/.env)

Nothing configured: brain = `qwen4-deploy` on the H200 gateway (from `app/.env`), hearing = the browser's recogniser
(or `qwen3-asr`), voice = `qwen3-tts` or the browser's voice. Add keys and it upgrades itself:

- `GEMINI_API_KEY`: brain `gemini-3.8-flash` (Interactions API, JSON schema), voice `gemini-3.8-flash-tts`, hearing via Gemini.
- `SARVAM_API_KEY`: hearing `saaras:v4` (Kannada + English), voice `bulbul:v4-flash` (Kannada voice `chaitra_kn_conversation`).
- `MITRA_BRAIN / MITRA_STT / MITRA_TTS` force a provider instead of `auto`.
- Every provider has a fallback; the last resort (rules + browser speech) needs no network at all.

## How it works

`web/` is the stage (orb, captions, three panel sets, live feed). `server/main.py` exposes `/api/turn`
(audio or text in → intent → action → words + audio out), `/api/events` (server-sent events from a 1.5 s poll of the
Sakala API), `/api/clip` (voice notes between roles) and `/api/session`. `brain.py` maps speech to one intent from a
closed list (Gemini → Qwen guided JSON → regex rules). `tools.py` executes it against the Sakala API and builds the UI
ops. `speech.py` holds the STT/TTS adapters. `store.py` is Mitra's own SQLite (sessions, turns, voice notes).

Tests: `python tests/test_turns.py` (24 text turns across the three profiles) and
`python tests/shot.py <profile> "<utterance> || <utterance>" out.png` (headless screenshot).
