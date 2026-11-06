"""Builds Mitra_Sovereign_English_Sprint.pdf in the project root: the ten-day sprint (27 Oct -> 5 Nov 2026) that puts
Mitra's English voice on our own full-duplex core, as a complete sprint document (goal, definition of done, scope, team,
hardware, day-by-day plan, gates, test harness, risk register, working agreements, sign-off sheet).
HTML -> headless Edge over CDP -> Page.printToPDF (A4). Run: python tools/make_sprint_pdf.py"""
import asyncio
import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "mitra" / "tests"))

CSS = """
@page { size: A4; margin: 10mm 11mm 10mm; }
body { font-family:"Segoe UI","Nirmala UI",sans-serif; color:#15202e; font-size:9.6px; line-height:1.33; }
h1 { font-size:19px; color:#0d2547; margin:0 0 2px; }
h1 span { font-weight:500; color:#4c5a6b; font-size:12px; }
.sub { color:#4c5a6b; font-size:9.8px; margin:0 0 8px; }
h2 { font-size:13px; color:#0d2547; margin:11px 0 4px; border-bottom:1.5px solid #16c784; padding-bottom:2px; page-break-after:avoid; }
h3 { font-size:10.6px; color:#0d2547; margin:7px 0 3px; page-break-after:avoid; }
p { margin:0 0 5px; }
table { width:100%; border-collapse:collapse; margin:2px 0 6px; }
tr { page-break-inside:avoid; }
th { background:#0d2547; color:#fff; text-align:left; padding:3.5px 5px; font-size:8.8px; }
td { padding:3px 5px; border-bottom:1px solid #dfe5ec; vertical-align:top; }
tr:nth-child(even) td { background:#f5f7fa; }
td.k { font-weight:700; }
td.n, th.n { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
code { font-family:Consolas,"Cascadia Mono",monospace; font-size:8.8px; background:#eef2f6; padding:0 3px; border-radius:3px; white-space:nowrap; }
.callout { border-left:3px solid #16c784; background:#f0fbf5; padding:4px 8px; margin:4px 0 6px; page-break-inside:avoid; }
.warn { border-left:3px solid #f59e0b; background:#fff8ea; padding:4px 8px; margin:4px 0 6px; page-break-inside:avoid; }
.stop { border-left:3px solid #dc2626; background:#fff1f1; padding:4px 8px; margin:4px 0 6px; page-break-inside:avoid; }
.two { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
.three { display:grid; grid-template-columns:1fr 1fr 1fr; gap:7px; }
.box { border:1px solid #cfd8e3; border-radius:5px; padding:5px 8px; background:#fbfcfe; page-break-inside:avoid; }
.box b.t { display:block; color:#0d2547; margin-bottom:2px; }
.kpi { display:grid; grid-template-columns:repeat(6,1fr); gap:6px; margin:4px 0 8px; }
.kpi > div { border:1px solid #cfd8e3; border-radius:5px; padding:4px 7px; background:#fff; }
.kpi .n { font-size:16px; font-weight:800; color:#0d2547; line-height:1.1; }
.kpi .t { font-size:8.4px; color:#4c5a6b; }
ol, ul { margin:2px 0 5px 15px; padding:0; } li { margin:1.5px 0; }
.foot { font-size:8.4px; color:#6b7786; margin-top:6px; }
.pb { page-break-before:always; }
.day { border:1px solid #cfd8e3; border-radius:6px; margin:5px 0 7px; page-break-inside:avoid; overflow:hidden; }
.day .dh { background:#eef2f6; padding:4px 8px; display:flex; justify-content:space-between; align-items:baseline; }
.day .dh b { color:#0d2547; font-size:10.6px; }
.day .dh span { color:#4c5a6b; font-size:9px; }
.day table { margin:0; }
.day th { background:#2b4a75; }
.day td:first-child { font-weight:700; white-space:nowrap; width:16%; }
.day .done { padding:4px 8px; background:#f0fbf5; font-size:9.2px; border-top:1px solid #d6efe1; }
.day .done b { color:#0e7a4f; }
.gate { border:1.5px solid #f59e0b; border-radius:6px; padding:5px 8px; margin:5px 0 7px; background:#fffaf0; page-break-inside:avoid; }
.gate b.t { color:#9a4d00; font-size:10.6px; display:block; margin-bottom:2px; }
.tag { display:inline-block; font-size:8px; font-weight:700; border-radius:9px; padding:0 6px; margin-right:3px; color:#fff; background:#2b4a75; vertical-align:1px; }
.t-cs { background:#db2777; } .t-rc { background:#2563eb; } .t-fd { background:#ea580c; } .t-he { background:#7c3aed; } .t-io { background:#0d9488; }
.sig td { height:20px; }
"""

HEAD = """
<h1>Sovereign English Mitra · the ten-day sprint <span>· 27 Oct to 5 Nov 2026 · sprint document v1.0</span></h1>
<p class="sub">Sakala Mitra, Government of Karnataka · Prepared 27 Oct 2026 for the Mitra build team, AI ops and the sprint owner · Status key used throughout: <span class="tag t-cs">CS</span> core and serving · <span class="tag t-rc">RC</span> relay and client · <span class="tag t-fd">FD</span> factory and data · <span class="tag t-he">HE</span> harness and evaluation · <span class="tag t-io">IO</span> infra and ops</p>

<div class="kpi">
  <div><div class="n">10</div><div class="t">working days, Mon 27 Oct to Wed 5 Nov</div></div>
  <div><div class="n">6</div><div class="t">people on four tracks plus AI ops and legal</div></div>
  <div><div class="n">2</div><div class="t">H200 cards in the one office server</div></div>
  <div><div class="n">3</div><div class="t">gates: day 3, day 5, day 8</div></div>
  <div><div class="n">0</div><div class="t">Gemini calls on the English path by day 9</div></div>
  <div><div class="n">&lt; 0.5 s</div><div class="t">first word; barge-in cut under 0.25 s</div></div>
</div>

<h2>1 · The goal, in one sentence</h2>
<p>By Wednesday 5 November, every English behaviour Mitra has on Gemini Live today runs on our own native full-duplex core, on our own two H200s, with no Gemini key anywhere in the English path, and the demo rehearsal passes the sign-off sheet in section 10.</p>
<div class="callout"><b>What does not change.</b> The browser, the phone app, the relay contract at <code>/ws/live</code>, the intent router, the SQL query layer, the guard, the read-back bar, transfer, the knowledge notes, the 8-stage pipeline and every existing test suite. The sprint swaps the upstream behind the relay, from Gemini Live to our core, and trains the core to sound and behave like Mitra. Kannada stays on Gemini throughout and is out of scope (section 3).</div>

<h2>2 · Definition of done: what "perfect on day 10" means, written so it can be judged</h2>
<table>
<tr><th style="width:24%">Behaviour</th><th style="width:20%">Target</th><th style="width:30%">How it is measured</th><th>Evidence file</th></tr>
<tr><td class="k">First word after the citizen stops</td><td>under 0.5 s median, under 0.8 s at the 95th percentile</td><td>Virtual microphone at the WebSocket; timestamp of last user audio to first Mitra audio frame; 50 scripted turns</td><td><code>evidence/atlas_core.json</code></td></tr>
<tr><td class="k">Barge-in: Mitra stops when interrupted</td><td>audio cut under 0.25 s</td><td>Interruption injected at 20 points inside her answer; time to silence measured</td><td><code>evidence/atlas_core.json</code></td></tr>
<tr><td class="k">Functions called with exact ids and numbers</td><td>every id and number spoken equals the function result</td><td><code>guard.deviations</code> on every turn; zero deviations across the banks</td><td><code>evidence/deviations.json</code></td></tr>
<tr><td class="k">Captions and charts as she speaks</td><td>stage reveals follow the spoken names; one picture per turn</td><td><code>ui_stage</code> 19, <code>ui_viz_settle</code> 12, <code>ui_board</code> 13</td><td>suite logs</td></tr>
<tr><td class="k">Document reply in her own voice</td><td>letter read-back spoken by the core, no browser voice</td><td><code>live_doc_ui</code> 10, web and phone</td><td>suite logs</td></tr>
<tr><td class="k">Read-back bar, notifications, mute, stop</td><td>as on Gemini today</td><td><code>ui_mute_stage</code> 10, <code>test_notify</code> 21, <code>ui_live</code> 10</td><td>suite logs</td></tr>
<tr><td class="k">Existing English suites</td><td>all green on the sovereign core</td><td>turns 24, nav 22, bank 113, guardrails 59, relay 15, live-UI 10, settle 12, mute 10, stage 19, board 13, app 17, map 13, portal 16, theme 11, layout 35+35, phone sweep 14</td><td><code>evidence/suites_day9.md</code></td></tr>
<tr><td class="k">Full-Duplex-Bench v1 and v1.5</td><td>at PersonaPlex's published level or better: interruption takeover 0.95 at 0.24 s, smooth turn-taking 0.908 at 0.17 s</td><td>The public benchmark run on our tuned weights</td><td><code>evidence/fdb_v1.json</code>, <code>fdb_v15.json</code></td></tr>
<tr><td class="k">Listener panel against Gemini</td><td>within a third of a point (5-point scale) on naturalness, side by side</td><td>20 listeners, 12 scripted conversations each, blind A/B</td><td><code>evidence/panel_day8.xlsx</code></td></tr>
<tr><td class="k">Sovereignty</td><td>no outbound call from the English path; no Gemini key loaded</td><td>Egress log at the firewall during the rehearsal; <code>GEMINI_API_KEY</code> absent from the English process</td><td><code>evidence/egress_day9.log</code></td></tr>
<tr><td class="k">Stability</td><td>two hours of continuous sessions, no dropout, no failed session</td><td>Load test with 50 virtual callers for 2 hours</td><td><code>evidence/soak_day6.json</code></td></tr>
</table>
<div class="warn"><b>Stated now, not on day 10.</b> Out of scope: Kannada (stays on Gemini until its own programme), Gemini's depth of emotional tone (a training programme beyond ten days), and Gemini's exact voice (the voice will be Mitra's own, from a consented clip). If the panel on day 8 asks for either of the last two, the answer is a dated follow-on, not a slipped sprint.</div>
"""

SCOPE = """
<h2>3 · Scope</h2>
<div class="three">
  <div class="box"><b class="t">In</b><ul>
    <li>Sovereign English duplex core serving all three desks (Citizen, Officer, Chief Secretary), web and phone</li>
    <li>Live user transcript to the existing brain; function results spoken by the core</li>
    <li>"Hey Mitra" wake word on our own model, no Gemini transcription in Standby</li>
    <li>Two LoRA rounds: persona, Sakala wording, id reading, lead phrase while a function runs</li>
    <li>Behaviour atlas measured on Gemini and on the core; Full-Duplex-Bench; listener panel</li>
    <li>Load test and soak on the two cards; admission control</li></ul></div>
  <div class="box"><b class="t">Out</b><ul>
    <li>Kannada on the core (Gemini stays behind a switch for Kannada only)</li>
    <li>Emotional range and voice identity matching Gemini</li>
    <li>The 3B distillation and the 4-bit cache (post-sign-off serving work)</li>
    <li>Any change to routing, SQL, the POC on 8020, KPCL or RDPR (read-only, as always)</li>
    <li>Deployment to AWS or any cloud; the sprint ends on the office server</li></ul></div>
  <div class="box"><b class="t">Fixed constraints</b><ul>
    <li>Nothing from Gemini is stored or trained on; Gemini is probed for numbers only</li>
    <li>Every model is a file on the office server with a licence that allows government production use (the models list PDF)</li>
    <li>Ports 8000 and 8001 belong to other apps; Sakala POC 8020, Mitra 8030, test instances 8031 and 8032</li>
    <li>Backups of every patched file in <code>tools/backups/sprint27/</code> before the patch</li>
    <li>Tests never play audio aloud; regression runs are announced before they start</li></ul></div>
</div>

<h2>4 · Team, tracks and ownership</h2>
<table>
<tr><th style="width:9%">Code</th><th style="width:19%">Track</th><th style="width:8%">People</th><th style="width:36%">Owns</th><th>Hands to</th></tr>
<tr><td><span class="tag t-cs">CS</span></td><td class="k">Core and serving</td><td>2</td><td>PersonaPlex and Moshi on the Rust server, text forcing of results, voice prompt, LoRA rounds, batching, load test, weight freeze</td><td>RC the upstream adapter contract; HE the checkpoints to evaluate</td></tr>
<tr><td><span class="tag t-rc">RC</span></td><td class="k">Relay and client</td><td>1</td><td>The new upstream adapter behind <code>/ws/live</code>, transcript-driven dispatch, prefill, captions, stage, read-back, notifications, wake word, phone layout, Standby, mute and stop</td><td>HE a stable build each evening for the suites</td></tr>
<tr><td><span class="tag t-fd">FD</span></td><td class="k">Factory and data</td><td>1</td><td>Open Yap, DailyTalk, AMI, scripts by gpt-oss-120b, two voices, alignment, filtering by two recognisers, augmentation, moshi-finetune datasets</td><td>CS a dataset manifest per round</td></tr>
<tr><td><span class="tag t-he">HE</span></td><td class="k">Harness and evaluation</td><td>1</td><td>Virtual microphone, the Gemini atlas, suites against the core, Full-Duplex-Bench, listener panels, the scorecard, the sign-off sheet</td><td>Everyone the numbers, every evening</td></tr>
<tr><td><span class="tag t-io">IO</span></td><td class="k">Infra and ops (AI ops)</td><td>1</td><td>Model downloads and gated terms, vLLM, GPU allocation by day and night, disk, egress firewall rule, logs, backups, the Gemini key switch</td><td>CS working endpoints by day 1 evening</td></tr>
<tr><td></td><td class="k">Sprint owner</td><td>Pranay</td><td>Gates, scope decisions, the panel's definition of perfect, legal read of the NVIDIA Open Model License</td><td>The team a decision within the day it is asked</td></tr>
</table>

<h2>5 · Hardware and environment</h2>
<div class="two">
  <div class="box"><b class="t">GPU 1, 141 GB · the duplex worker, all day and all night</b>PersonaPlex 7B bf16 (16 GB), Mimi, Kyutai STT 1B (2 GB), Silero, Smart Turn: about 22 GB of models and 0.6 GB per live session. Serves 100 to 150 sessions in memory; the sprint promises 50. Never used for training.</div>
  <div class="box"><b class="t">GPU 2, 141 GB · brain by day, factory by night</b>Day: gpt-oss-120b on vLLM (65 GB plus 20 GB cache) and a second duplex worker (16 GB). Night, 20:00 to 07:00: the second worker is paused, moshi-finetune runs (40 GB peak), synthesis and scoring models take the rest. The brain stays up at night for script generation.</div>
</div>
<table>
<tr><th style="width:22%">Item</th><th>Value</th></tr>
<tr><td class="k">Disk</td><td>About 230 GB of model files plus 400 GB for datasets and checkpoints on the NVMe; one checkpoint per round is kept, the rest pruned</td></tr>
<tr><td class="k">Ports</td><td>Core Rust server 8040 (GPU 1) and 8041 (GPU 2); vLLM 8050; Kyutai STT 8042; Mitra 8030 unchanged; test instances 8031 and 8032 point at the core by <code>MITRA_LIVE_URL</code></td></tr>
<tr><td class="k">Egress</td><td>Firewall rule logs every outbound connection from the Mitra and core processes; the Gemini host is allowed only for the Kannada switch and the atlas probes</td></tr>
<tr><td class="k">Evidence</td><td><code>mitra/evidence/sprint27/</code>: one dated file per measurement; the sign-off sheet reads only from there</td></tr>
<tr><td class="k">Day-0 ops checklist</td><td>Hugging Face account with the gated terms accepted (PersonaPlex, pyannote, CSM, Orpheus) · every model in the models list pulled, hashes recorded · vLLM serving gpt-oss-120b · Rust server building · Open Yap 1K request sent · nightly cron for the factory · backup folder created · egress rule live</td></tr>
</table>
"""

PLAN = """
<h2 class="pb">6 · The plan, day by day</h2>
<p>Each day has a theme, the work on each track, and a "done when" line that the evening check reads out. A task that is not done moves to the next day and is written as such; nothing is silently dropped.</p>

<div class="day"><div class="dh"><b>Day 0 · Monday 27 October · Pull everything, measure Gemini</b><span>no code against the core yet</span></div>
<table>
<tr><td><span class="tag t-io">IO</span> infra</td><td>Every model in the models list downloaded, gated terms accepted, hashes recorded; vLLM up with gpt-oss-120b; Rust server built; egress rule live; backup folder created</td></tr>
<tr><td><span class="tag t-fd">FD</span> factory</td><td>Open Yap 1K access requested at 09:00; DailyTalk and AMI fetched; MUSAN and RIRS fetched; a consented Mitra voice clip recorded (two minutes, quiet room)</td></tr>
<tr><td><span class="tag t-he">HE</span> harness</td><td>Atlas probes written: pause inside a sentence, interruption at 20 points, id reading (case ids, Sakala numbers, phone digits), tool wait and lead phrase, language of numbers, noise; ten repeats each</td></tr>
<tr><td><span class="tag t-cs">CS</span> core</td><td>Read the PersonaPlex and moshi-finetune code; decide the text-forcing approach on paper; sprint owner and legal read the NVIDIA Open Model License</td></tr>
</table>
<div class="done"><b>Done when:</b> every model loads on the right card without error; the atlas probe list is signed by the sprint owner; the licence read has a written answer.</div></div>

<div class="day"><div class="dh"><b>Day 1 · Tuesday 28 October · The core speaks on our cards</b><span>first sovereign audio</span></div>
<table>
<tr><td><span class="tag t-cs">CS</span> core</td><td>PersonaPlex up on GPU 1 on the Rust server; Kyutai STT streaming on the user channel; gpt-oss-120b answering guided JSON from the existing brain prompt on GPU 2</td></tr>
<tr><td><span class="tag t-rc">RC</span> relay</td><td>New upstream adapter behind <code>/ws/live</code>: 16 kHz PCM in, 24 kHz PCM out, the core's text stream as captions, STT text as the user transcript; the Gemini adapter kept behind a switch</td></tr>
<tr><td><span class="tag t-fd">FD</span> factory</td><td>Factory pipeline skeleton: script → two voices (Kyutai TTS, Chatterbox) → stereo WAV, Mitra left, user right → aligner → moshi-finetune format; ten dialogues end to end</td></tr>
<tr><td><span class="tag t-he">HE</span> harness</td><td>Virtual microphone at the WebSocket with millisecond traces; the atlas measured on Gemini Live, ten repeats, and signed as the reference</td></tr>
</table>
<div class="done"><b>Done when:</b> a person talks to the core through the Mitra web desk and hears it answer; the Gemini atlas file exists with every probe filled.</div></div>

<div class="day"><div class="dh"><b>Day 2 · Wednesday 29 October · Results spoken in her voice</b><span>the sprint's one technical risk is attacked here</span></div>
<table>
<tr><td><span class="tag t-cs">CS</span> core</td><td>Text forcing prototyped: the function result's words forced into the core's text stream so it speaks them while still listening (the way Kyutai's TTS drives the same architecture); voice prompt from the consented clip</td></tr>
<tr><td><span class="tag t-rc">RC</span> relay</td><td>Transcript-driven dispatch wired: STT text → existing brain → <code>tools.execute</code> → prefill into the core; read-back question and the confirm bar on the new path</td></tr>
<tr><td><span class="tag t-fd">FD</span> factory</td><td>500 Sakala scripts generated by gpt-oss-120b (complaints, follow-ups, officer actions, CS questions, with interruptions, repairs and backchannels) and voiced</td></tr>
<tr><td><span class="tag t-he">HE</span> harness</td><td>Full-Duplex-Bench v1 run on stock PersonaPlex as the baseline; the suites' fake Live pointed at the core for a first dry run</td></tr>
</table>
<div class="done"><b>Done when:</b> "how many open cases in Hunsur" produces a function call and the number is spoken by the core; the FDB baseline file is in evidence.</div></div>

<div class="gate"><b class="t">Gate A · Thursday 30 October, 18:30 · a sovereign English turn end to end</b>Pass: a question through the web desk reaches the brain, the function runs, the result is spoken by the core in Mitra's voice while the mic stays open, first word under 0.6 s, and the id in the answer equals the result. Signed by the sprint owner on a recording in evidence. <b>If missed:</b> the same-voice fallback is switched on the same evening: Kyutai TTS 1.6B on the same voice embedding streams the result into the output channel while the core keeps listening; full duplex is kept, with a small voice mismatch on facts. The decision is written in the day's note, not deferred.</div>

<div class="day"><div class="dh"><b>Day 3 · Thursday 30 October · Go or no-go on text forcing; the desks come alive</b><span>Gate A</span></div>
<table>
<tr><td><span class="tag t-cs">CS</span> core</td><td>Text forcing made clean or the TTS fallback wired; latency traced per stage; the core's silence watchdog and echo gate tuned on the relay</td></tr>
<tr><td><span class="tag t-rc">RC</span> relay</td><td>Captions word by word, stage reveal from the spoken text, number checks (<code>guard.deviations</code>), notifications spoken in session, the three desks and the portal on the new path</td></tr>
<tr><td><span class="tag t-fd">FD</span> factory</td><td>2,000 scripts voiced and filtered by Canary and Whisper (word error under 10%, both recognisers agreeing); Open Yap subset converted when access arrives</td></tr>
<tr><td><span class="tag t-he">HE</span> harness</td><td>Relay 15, live-UI 10, turns 24 and navigation 22 run against the sovereign core; failures triaged into core / relay / harness buckets</td></tr>
</table>
<div class="done"><b>Done when:</b> Gate A signed; the four suites' failures are listed with an owner each.</div></div>

<div class="day"><div class="dh"><b>Day 4 · Friday 31 October · Round one trains overnight</b><span>first LoRA round</span></div>
<table>
<tr><td><span class="tag t-cs">CS</span> core</td><td>LoRA round one started at 20:00 on GPU 2: persona and desk register, Sakala wording, id reading digit by digit, the lead phrase while a function runs ("let me check that"), short answers</td></tr>
<tr><td><span class="tag t-rc">RC</span> relay</td><td>Phone layout on the new path, Standby and 20 s idle, mute as mic-only, Stop as the only cut, the document reply read by the core</td></tr>
<tr><td><span class="tag t-fd">FD</span> factory</td><td>Augmentation: MUSAN noise, RIRS room responses, phone-band filtering; the round-one manifest handed to CS (hours, sources, filter stats)</td></tr>
<tr><td><span class="tag t-he">HE</span> harness</td><td>Bank 113 and guardrails 59 on the sovereign core; deviations file reviewed line by line</td></tr>
</table>
<div class="done"><b>Done when:</b> the trainer is running with a manifest in evidence; bank and guardrails results are in evidence with failures owned.</div></div>

<div class="gate"><b class="t">Gate B · Saturday 1 November, 18:30 · the English suites green, FDB at PersonaPlex's level</b>Pass: relay 15, live-UI 10, turns 24, navigation 22, bank 113, guardrails 59 all green on the round-one weights; Full-Duplex-Bench v1 at or above the published PersonaPlex numbers; the 5-listener panel scores the core within 0.5 of Gemini. <b>If missed:</b> day 6's load test moves to day 7, and round two's data is cut to what the failures need.</div>

<div class="day"><div class="dh"><b>Day 5 · Saturday 1 November · Round one judged; the wake word is ours</b><span>Gate B</span></div>
<table>
<tr><td><span class="tag t-cs">CS</span> core</td><td>Round one evaluated against the base on the atlas; pacing and pause fixes; the better weights promoted to GPU 1</td></tr>
<tr><td><span class="tag t-rc">RC</span> relay</td><td>"Hey Mitra" on openWakeWord in Standby, trained from Piper clips; no Gemini transcription of room talk anywhere</td></tr>
<tr><td><span class="tag t-fd">FD</span> factory</td><td>3,000 more hours queued for round two; the panel's and the suites' failure cases turned into targeted scripts</td></tr>
<tr><td><span class="tag t-he">HE</span> harness</td><td>Atlas against the core; 5-listener English panel on six conversations; FDB v1 and v1.5 on the round-one weights</td></tr>
</table>
<div class="done"><b>Done when:</b> Gate B signed, or the miss written with its recovery plan.</div></div>

<div class="day"><div class="dh"><b>Day 6 · Sunday 2 November · Many callers at once</b><span>serving and scale</span></div>
<table>
<tr><td><span class="tag t-cs">CS</span> core</td><td>Batched sessions on the Rust server; load test with 200 virtual callers rising in steps of 25; sessions per card at which the 80 ms tick still holds at the 99th percentile; 2-hour soak at 50</td></tr>
<tr><td><span class="tag t-rc">RC</span> relay</td><td>Session scheduler lite: admission control on the two cards (refuse the session that cannot be served well), a per-card session count, drain before a weight swap</td></tr>
<tr><td><span class="tag t-fd">FD</span> factory</td><td>Round-two data from the panel's findings; hard cases: far-field, crosstalk, interruptions at every point, numbers under noise</td></tr>
<tr><td><span class="tag t-he">HE</span> harness</td><td>Noise, far-field, crosstalk and interruption-at-every-point families added to the atlas; the load-test traces plotted</td></tr>
</table>
<div class="done"><b>Done when:</b> the sessions-per-card number and the soak result are in evidence.</div></div>

<div class="day"><div class="dh"><b>Day 7 · Monday 3 November · Round two trains; full regression</b><span>second LoRA round</span></div>
<table>
<tr><td><span class="tag t-cs">CS</span> core</td><td>LoRA round two started at 20:00: the day-5 findings, interruptions and repairs, noisy numbers, officer and CS registers</td></tr>
<tr><td><span class="tag t-rc">RC</span> relay</td><td>Full regression on the new path: settle 12, mute 10, stage 19, board 13, map 13, app 17, portal 16, theme 11, layout sweeps 35+35, phone sweep 14, doc UI 10</td></tr>
<tr><td><span class="tag t-fd">FD</span> factory</td><td>Round-two manifest; the dataset frozen; the factory pipeline documented for the Kannada programme that follows</td></tr>
<tr><td><span class="tag t-he">HE</span> harness</td><td>Barge-in budget and pause tolerance tuned in the relay's safety controller from the atlas numbers; the 20-listener panel recruited and the 12 scripted conversations recorded on both systems</td></tr>
</table>
<div class="done"><b>Done when:</b> the regression results are in evidence; the trainer is running; the panel material is ready.</div></div>

<div class="gate"><b class="t">Gate C · Tuesday 4 November, 18:30 · atlas within tolerance, panel within a third of a point</b>Pass: every atlas behaviour inside its tolerance on the round-two weights; the 20-listener blind panel within 0.33 of Gemini on naturalness and not below it on correctness; FDB v1 and v1.5 held. <b>If missed:</b> the weights that scored best (round one or two) are frozen anyway, the gap is written on the scorecard, and day 9's rehearsal goes ahead with the gap stated; a third round is a follow-on, not a slip.</div>

<div class="day"><div class="dh"><b>Day 8 · Tuesday 4 November · Freeze</b><span>Gate C</span></div>
<table>
<tr><td><span class="tag t-cs">CS</span> core</td><td>Round two evaluated; the winning weights frozen and hashed; serving config frozen</td></tr>
<tr><td><span class="tag t-rc">RC</span> relay</td><td>Client frozen; the Gemini path kept behind a switch for Kannada only; the English process started without the Gemini key</td></tr>
<tr><td><span class="tag t-fd">FD</span> factory</td><td>Dataset and manifests archived; licence credits list compiled for the product notice</td></tr>
<tr><td><span class="tag t-he">HE</span> harness</td><td>20-listener side-by-side scored; the scorecard built: every definition-of-done row with its measured value</td></tr>
</table>
<div class="done"><b>Done when:</b> Gate C signed or its miss written; the scorecard exists with no empty cell.</div></div>

<div class="day"><div class="dh"><b>Day 9 · Wednesday 5 November · Rehearsal and sign-off</b><span>the only buffer day</span></div>
<table>
<tr><td><span class="tag t-cs">CS</span> core</td><td>Demo rehearsal on the two cards with the Gemini key removed from the English path; egress log captured for the whole rehearsal</td></tr>
<tr><td><span class="tag t-rc">RC</span> relay</td><td>Handoff notes; the model notice with the CC-BY credits; the switch procedure documented (English core, Kannada Gemini)</td></tr>
<tr><td><span class="tag t-he">HE</span> harness</td><td>Sign-off sheet filled from the evidence folder, every number against its target; demo script walked twice</td></tr>
<tr><td><span class="tag t-io">IO</span> infra</td><td>Backups of weights, datasets and config; the nightly factory cron left running for the Kannada programme</td></tr>
</table>
<div class="done"><b>Done when:</b> the sprint owner signs the sheet in section 10. Anything unsigned is listed on it with a date.</div></div>
"""

REST = """
<h2 class="pb">7 · Test harness and evidence</h2>
<p>Every claim on the sign-off sheet is backed by a file in <code>mitra/evidence/sprint27/</code>. The existing suites run unchanged against the core; three new instruments are built in the sprint.</p>
<table>
<tr><th style="width:24%">Instrument</th><th style="width:40%">What it measures</th><th>Built by · when</th></tr>
<tr><td class="k">Virtual microphone</td><td>Feeds recorded or synthesised speech into <code>/ws/live</code> as a browser would, timestamps every audio frame both ways, injects interruptions at chosen points, and records the core's audio and text streams</td><td>HE · day 1</td></tr>
<tr><td class="k">Behaviour atlas</td><td>Controlled probes, ten repeats each, on Gemini (reference) and on the core: first word, yield time on interruption, pause tolerance, lead phrase while a function runs, id and number reading, noise, crosstalk; each becomes a number with a tolerance</td><td>HE · days 0 to 1 (Gemini), 5 and 8 (core)</td></tr>
<tr><td class="k">Full-Duplex-Bench v1 and v1.5</td><td>The public benchmark: pause handling, backchannel, turn-taking, interruption, overlaps; the yardstick PersonaPlex and Gemini are scored on</td><td>HE · day 2 baseline, days 5 and 8</td></tr>
<tr><td class="k">Existing suites (unchanged)</td><td>turns 24 · nav 22 · bank 113 · guardrails 59 · relay 15 · live-UI 10 · settle 12 · mute 10 · stage 19 · board 13 · app 17 · map 13 · portal 16 · theme 11 · layout 35+35 · phone sweep 14 · notify 21 · realtime 35 · doc UI 10</td><td>HE and RC · days 3, 4, 7, 9</td></tr>
<tr><td class="k">Listener panels</td><td>Day 5: 5 listeners, 6 conversations. Day 8: 20 listeners, 12 scripted conversations recorded on both systems, blind A/B, 5-point naturalness and correctness</td><td>HE · days 5 and 8</td></tr>
<tr><td class="k">Load and soak</td><td>200 virtual callers in steps of 25; per-tick time at the 99th percentile, first word and barge-in at each step; 2-hour soak at 50</td><td>CS and HE · day 6</td></tr>
<tr><td class="k">Egress log</td><td>Every outbound connection from the Mitra and core processes during the rehearsal; must contain no Gemini host on the English path</td><td>IO · day 9</td></tr>
</table>

<h2>8 · Risk register</h2>
<table>
<tr><th style="width:4%">#</th><th style="width:22%">Risk</th><th style="width:7%">Likelihood</th><th style="width:7%">Impact</th><th style="width:20%">Trigger we watch</th><th>Mitigation and fallback</th><th style="width:7%">Owner</th></tr>
<tr><td>R1</td><td class="k">Text forcing of function results is not clean (garbled or slow speech of prefilled text)</td><td>Medium</td><td>High</td><td>Day 2 prototype; Gate A on day 3</td><td>Same-voice fallback ready on day 2: Kyutai TTS 1.6B on the same voice embedding streamed into the output while the core listens; full duplex kept, small voice mismatch on facts</td><td>CS</td></tr>
<tr><td>R2</td><td class="k">Open Yap 1K access arrives late</td><td>Low</td><td>Medium</td><td>No reply by day 2 noon</td><td>DailyTalk, AMI and synthetic data carry round one; Open Yap joins round two</td><td>FD</td></tr>
<tr><td>R3</td><td class="k">VRAM contention on GPU 2 between the brain, the second worker and the trainer</td><td>Medium</td><td>Medium</td><td>Out-of-memory in the nightly run</td><td>Train only at night with the second worker paused; brain cache capped at 20 GB; Qwen3-30B-A3B as the lighter brain on training nights</td><td>IO</td></tr>
<tr><td>R4</td><td class="k">NVIDIA Open Model License read differently by legal</td><td>Low</td><td>Medium</td><td>Legal answer on day 0</td><td>Moshiko (CC-BY-4.0) is the base either way; PersonaPlex's persona tuning is reproduced by our own round one on Moshiko if needed, costing one extra night</td><td>Owner</td></tr>
<tr><td>R5</td><td class="k">"Perfect" drifts to Gemini's exact voice or emotional range</td><td>Medium</td><td>High</td><td>Panel comments on day 5</td><td>Stated out of scope on day 0 in this document; a dated follow-on programme is the answer, not a slipped sprint</td><td>Owner</td></tr>
<tr><td>R6</td><td class="k">Core latency above target under load</td><td>Medium</td><td>Medium</td><td>Day 6 load test</td><td>Promise the count at which the 99th-percentile tick holds; admission control refuses beyond it; the 3B distillation is the post-sprint lever</td><td>CS</td></tr>
<tr><td>R7</td><td class="k">A suite fails for a harness reason, not a core reason</td><td>High</td><td>Low</td><td>Triage buckets on day 3</td><td>Failures are bucketed core / relay / harness with an owner each; harness fixes never change what is measured</td><td>HE</td></tr>
<tr><td>R8</td><td class="k">Person out for a day on a one-person track</td><td>Medium</td><td>Medium</td><td>Morning stand-up</td><td>Each track's work is in the plan by day; the sprint owner reassigns from CS (two people) for the day</td><td>Owner</td></tr>
<tr><td>R9</td><td class="k">Synthetic data sounds like the TTS, and the core learns that accent</td><td>Medium</td><td>Medium</td><td>Panel comments on day 5</td><td>Two voice families (Kyutai, Chatterbox), Open Yap and AMI real speech weighted up in round two</td><td>FD</td></tr>
<tr><td>R10</td><td class="k">Echo on laptop speakers trips the core's own barge-in</td><td>Medium</td><td>Low</td><td>Day 3 desk test</td><td>The relay's echo gate (Silero, ducking, the existing talk-over check) stays in front of the core; headset for the rehearsal if needed</td><td>RC</td></tr>
</table>

<h2>9 · Working agreements for the ten days</h2>
<div class="two">
  <div class="box"><b class="t">Rhythm</b><ul>
    <li>09:30 stand-up, 15 minutes: yesterday's "done when", today's, blockers</li>
    <li>18:30 evening check, 20 minutes: the day's evidence files read out; gates judged here</li>
    <li>20:00 to 07:00 the factory and the trainer own GPU 2; nobody starts a job on it by day without IO</li>
    <li>A daily note in <code>mitra/evidence/sprint27/notes/day-N.md</code>: done, not done and why, decisions</li></ul></div>
  <div class="box"><b class="t">Rules</b><ul>
    <li>Every patched file backed up to <code>tools/backups/sprint27/</code> first; every change applies to web and phone alike</li>
    <li>Regression runs announced before they start; tests never play audio aloud</li>
    <li>Nothing from Gemini is stored except the atlas numbers; no Gemini output enters a dataset</li>
    <li>KPCL and RDPR folders read-only; ports 8000 and 8001 untouched</li>
    <li>A missed gate is written the same evening with its fallback; the plan has no slack after day 8, so day 9 is the only buffer</li>
    <li>Scope changes go to the sprint owner and are answered the same day</li></ul></div>
</div>

<h2>10 · Sign-off sheet, Wednesday 5 November</h2>
<table class="sig">
<tr><th style="width:30%">Measure</th><th style="width:18%">Target</th><th style="width:16%">Measured</th><th style="width:8%">Pass</th><th>Evidence file · initials</th></tr>
<tr><td>First word, median / 95th</td><td>&lt; 0.5 s / &lt; 0.8 s</td><td></td><td></td><td></td></tr>
<tr><td>Barge-in cut</td><td>&lt; 0.25 s</td><td></td><td></td><td></td></tr>
<tr><td>Deviations across the banks</td><td>0</td><td></td><td></td><td></td></tr>
<tr><td>Existing English suites</td><td>all green</td><td></td><td></td><td></td></tr>
<tr><td>Full-Duplex-Bench v1 / v1.5</td><td>≥ PersonaPlex published</td><td></td><td></td><td></td></tr>
<tr><td>20-listener panel, naturalness gap to Gemini</td><td>≤ 0.33</td><td></td><td></td><td></td></tr>
<tr><td>20-listener panel, correctness</td><td>not below Gemini</td><td></td><td></td><td></td></tr>
<tr><td>Sessions per card at a held 99th-percentile tick</td><td>≥ 50 on GPU 1</td><td></td><td></td><td></td></tr>
<tr><td>2-hour soak at 50 sessions</td><td>0 dropouts, 0 failed</td><td></td><td></td><td></td></tr>
<tr><td>Egress during the rehearsal</td><td>no Gemini host on the English path</td><td></td><td></td><td></td></tr>
<tr><td>Gemini key in the English process</td><td>absent</td><td></td><td></td><td></td></tr>
<tr><td>Product notice with CC-BY credits</td><td>present</td><td></td><td></td><td></td></tr>
<tr><td class="k">Sprint owner signature · date</td><td></td><td></td><td></td><td></td></tr>
</table>

<h3>Glossary</h3>
<table>
<tr><td class="k" style="width:22%">Native full duplex</td><td>One model that listens and speaks at the same time, one step every 80 ms; no separate speech-to-text, text model and text-to-speech in the voice path</td></tr>
<tr><td class="k">Core</td><td>The duplex model we serve: PersonaPlex 7B (Moshi family) tuned by us</td></tr>
<tr><td class="k">Transcript-driven dispatch</td><td>The citizen's words, as text from the streaming recogniser, go to Mitra's existing brain, which picks the intent and runs the function</td></tr>
<tr><td class="k">Prefill / text forcing</td><td>Pushing the function result's words into the core so it speaks them in its own voice while still listening</td></tr>
<tr><td class="k">LoRA round</td><td>An overnight adapter-training run on a dataset manifest, evaluated the next day</td></tr>
<tr><td class="k">Atlas</td><td>The set of measured behaviours, each a number with a tolerance, taken from Gemini as the reference and from the core each round</td></tr>
<tr><td class="k">Gate</td><td>An evening check with written pass criteria and a written fallback; judged by the sprint owner</td></tr>
<tr><td class="k">Evidence</td><td>A dated file in <code>mitra/evidence/sprint27/</code> that a sign-off row points to</td></tr>
</table>
<p class="foot">Companion documents: the models list and Gemini costs (<code>Mitra_English_Sovereign_Models_and_Costs.pdf</code>), the 90-day sovereign plan (<code>Mitra_Sovereign_90_Day_Plan.md</code>), the two-page sovereign plan (<code>Mitra_Sovereign_Plan_2pager.pdf</code>), the sprint picture (<code>Mitra_Sovereign_English_Sprint.png</code>).</p>
"""


def build() -> str:
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>Sovereign English Mitra: the ten-day sprint</title>"
            f"<style>{CSS}</style></head><body>{HEAD}{SCOPE}{PLAN}{REST}</body></html>")


async def pdf(html_path: Path, out: Path):
    from cdp import Browser
    async with Browser(port=9496, size=(900, 1300)) as b:
        await b.goto(html_path.resolve().as_uri(), 2)
        r = await b.cmd("Page.printToPDF", printBackground=True, preferCSSPageSize=True,
                        displayHeaderFooter=True, headerTemplate="<span></span>",
                        footerTemplate="<div style='font-size:7px;color:#6b7786;width:100%;text-align:center;font-family:Segoe UI,sans-serif'>"
                                       "Sovereign English Mitra · ten-day sprint · 27 Oct to 5 Nov 2026 · page <span class='pageNumber'></span> of <span class='totalPages'></span></div>",
                        marginTop=0.39, marginBottom=0.45, marginLeft=0.43, marginRight=0.43)
        out.write_bytes(base64.b64decode(r["data"]))


def main():
    hp = ROOT / "tools" / "sprint_doc.html"
    hp.write_text(build(), encoding="utf-8")
    out = ROOT / "Mitra_Sovereign_English_Sprint.pdf"
    asyncio.run(pdf(hp, out))
    import pymupdf
    d = pymupdf.open(out)
    print("pages", len(d), "size", out.stat().st_size)
    for i, p in enumerate(d):
        print(f"page {i + 1}: {len(p.get_text())} chars")


if __name__ == "__main__":
    main()
