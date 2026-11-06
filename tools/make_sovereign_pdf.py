"""Builds Mitra_Sovereign_Plan_2pager.pdf (exactly two A4 pages) in the project root:
page 1 = how we achieve it technically (architecture, models, specs, engineering techniques, 90 days);
page 2 = scale (the two H200s, then 1,000 / 10,000 / 50,000 live sessions, and why it holds).
HTML -> headless Edge over CDP -> Page.printToPDF. Run: python tools/make_sovereign_pdf.py"""
import asyncio
import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "mitra" / "tests"))

CSS = """
@page { size: A4; margin: 8mm 10mm 7mm; }
body { font-family:"Segoe UI","Nirmala UI","Noto Sans Kannada",sans-serif; color:#15202e; font-size:9.3px; line-height:1.3; }
.pg { page-break-after:always; }
.pg:last-child { page-break-after:auto; }
h1 { font-size:17px; color:#0d2547; margin:0 0 1px; }
.sub { color:#4c5a6b; font-size:9.5px; margin:0 0 6px; }
h2 { font-size:11.5px; color:#0d2547; margin:7px 0 3px; border-bottom:1.5px solid #16c784; padding-bottom:1px; }
h3 { font-size:9.8px; color:#0d2547; margin:5px 0 2px; }
p { margin:0 0 4px; }
table { width:100%; border-collapse:collapse; margin:2px 0 4px; }
th { background:#0d2547; color:#fff; text-align:left; padding:3px 5px; font-size:8.6px; }
td { padding:2.5px 5px; border-bottom:1px solid #dfe5ec; vertical-align:top; }
tr:nth-child(even) td { background:#f5f7fa; }
td.k { font-weight:700; white-space:nowrap; }
td.n, th.n { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
.two { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
.three { display:grid; grid-template-columns:1fr 1fr 1fr; gap:6px; }
.box { border:1px solid #cfd8e3; border-radius:5px; padding:4px 7px; background:#fbfcfe; }
.box b.t { display:block; color:#0d2547; margin-bottom:1px; }
.flow { display:grid; grid-template-columns:repeat(7,1fr); gap:4px; margin:3px 0 4px; }
.flow div { border:1px solid #9fdcb6; background:#f0fbf5; border-radius:5px; padding:3px 5px; font-size:8.6px; }
.flow div b { display:block; color:#0e7a4f; font-size:8.8px; }
.g { color:#0e7a4f; font-weight:700; } .a { color:#b45309; font-weight:700; }
ul { margin:1px 0 3px 13px; padding:0; } li { margin:1px 0; }
.kpi { display:grid; grid-template-columns:repeat(6,1fr); gap:5px; margin:3px 0 5px; }
.kpi div { border:1px solid #cfd8e3; border-radius:5px; padding:3px 6px; background:#fff; }
.kpi .n { font-size:15px; font-weight:800; color:#0d2547; line-height:1.1; }
.kpi .t { font-size:8.3px; color:#4c5a6b; }
.foot { font-size:8.2px; color:#6b7786; margin-top:4px; }
.callout { border-left:3px solid #16c784; background:#f0fbf5; padding:3px 7px; margin:3px 0 4px; }
.warn { border-left:3px solid #f59e0b; background:#fff8ea; padding:3px 7px; margin:3px 0 4px; }
"""

PAGE1 = """
<div class="pg">
<h1>Sovereign Mitra · how we build it <span style="font-weight:500;color:#4c5a6b">· page 1 of 2 · technical</span></h1>
<p class="sub">26 Oct 2026 · Sakala Mitra, Government of Karnataka · Replace the one piece of Mitra that is not ours, the Gemini Live voice model, with a native full-duplex core we train and own, running on government GPUs in Karnataka. Everything else in Mitra stays. Gemini remains in production as the measured reference until the core matches it; it is never a training source and is retired at sign-off.</p>

<h2>A · The architecture, one turn</h2>
<div class="flow">
  <div><b>1 · audio in</b>16 kHz PCM from browser, phone or 1902 bridge through the existing relay; masked, echo-gated</div>
  <div><b>2 · core listens + speaks</b>one native duplex model, one step every 80 ms; answers while the citizen is still finishing</div>
  <div><b>3 · live transcript</b>the core's text stream of the citizen's words goes to the dispatcher as it arrives</div>
  <div><b>4 · decide</b>Mitra's existing brain (rules + Sarvam guided JSON) picks the intent; tools.execute; SQL for every number</div>
  <div><b>5 · brain if needed</b>Sarvam-105B for wording, reasoning, Kannada text; ~30% of turns; text only</div>
  <div><b>6 · prefill</b>result text pushed into the core, spoken in its own voice while still listening</div>
  <div><b>7 · voice out</b>24 kHz audio + captions from the inner monologue; first word 0.3–0.5 s; barge-in cut ≤0.25 s</div>
</div>
<div class="callout"><b>Not a cascade.</b> There is no separate speech-to-text, text model and text-to-speech in the voice path. One model hears and speaks at the same time; tools and the brain only speak through it. <b>What stays the same:</b> browser, relay contract, router, SQL, guard, read-back, transfer, knowledge, the 8-stage pipeline, every test suite. <b>Sovereign boundary:</b> every model is a file we hold, runs on GoK GPUs in Karnataka, no outbound network path, nothing from Gemini in training, a hash-chained log of every payload a model receives.</div>

<h2>B · Models and specs</h2>
<table>
<tr><th>Role</th><th>Model</th><th>Spec</th><th>Licence</th><th>Why this one</th></tr>
<tr><td class="k">Duplex core</td><td>Moshi 7B (Kyutai) trained with the PersonaPlex recipe, by us, for Kannada + English; distilled to a 3B serving core</td><td>Temporal transformer 7B + small depth transformer; Mimi codec, 12.5 frames/s, 24 kHz; two audio streams + inner-monologue text; served in FP8 with a 4-bit attention cache and a 2-minute audio window plus a text summary</td><td>CC-BY-4.0 (NVIDIA Open Model License if PersonaPlex weights are the start)</td><td>Open reference architecture; official fine-tuning code; J-Moshi proved language adaptation; Mimi already encodes Hindi well; shrinks cleanly to 3B</td></tr>
<tr><td class="k">Text brain</td><td>Sarvam-105B MoE (fallback Sarvam-30B)</td><td>~10B active parameters, FP8 on vLLM, profile instruction prefix-cached, 128k context</td><td>Apache 2.0</td><td>Strong Kannada text; sovereign; bursty load, one call per ~10 s per session</td></tr>
<tr><td class="k">Deterministic layer</td><td>Mitra's existing router, SQL, transfer, knowledge, guard, read-back</td><td>Answers ~70% of turns with no model; every id and number from SQL</td><td>ours</td><td>Already passes the 113-question bank; parity by construction</td></tr>
<tr><td class="k">Factory: hearing</td><td>SraVaani-0.5-live (IISc), fine-tuned on our recordings</td><td>430M FastConformer, streaming chunks 80 ms–1.1 s; Kannada WER 16.6 Kathbath / 21.4 Fleurs offline, 31–34 streaming before tuning</td><td>MIT</td><td>Filters synthetic dialogues; transcribes recordings; Kannada bridge fallback</td></tr>
<tr><td class="k">Factory: voices</td><td>svara-TTS (3B Orpheus-class, Kannada ~120 h) · IndicF5 (AI4Bharat)</td><td>Token-based voice model and flow-matching TTS; two consented voices per dialogue</td><td>not stated / MIT</td><td>Voice the synthetic Sakala conversations; IndicF5 forbids cloning without permission, so speakers sign</td></tr>
<tr><td class="k">Reference only</td><td>Gemini Live (gemini-3.8-live)</td><td>Probed by the atlas: first word, yield time, pause handling, id reading, language switch; compared by listeners</td><td>Google terms</td><td>Defines the bar; its outputs are never stored or trained from</td></tr>
</table>

<h2>C · Engineering techniques that make it work, and fast</h2>
<div class="three">
  <div class="box"><b class="t">Transcript-driven dispatch</b>The core already emits the citizen's words as text. The relay feeds that to the existing cascade brain and executes the function, then prefills the answer. The core only has to listen and talk; our code decides. No tool-stream training is needed for parity; the delegation stream is a round-two refinement.</div>
  <div class="box"><b class="t">Kannada training factory</b>Recordings masked and diarised into caller/agent channels (pseudo-stereo). Thousands of synthetic Sakala dialogues written by Sarvam, voiced in two voices, filtered by the tuned recogniser (the J-Moshi recipe). Stages: A sound + language on mono data, B dialogue, C persona + three desks + language switching, D turn-taking preference.</div>
  <div class="box"><b class="t">Weekly rounds, one full pass</b>Adapter (LoRA) training on one GPU every week, evaluated every week by the atlas and a 5-person Kannada panel; one full training pass overnight in week 11. 10,000 h of Kannada ≈ 450 M frames ≈ one day per pass on two H200s, so rounds cost days, not months.</div>
  <div class="box"><b class="t">The behaviour atlas</b>Gemini probed with controlled inputs, ten repeats each; every behaviour becomes a number with a tolerance. The same probes run against our core every week. Parity = every tolerance met + Kannada bank 55/55 + live UI 18/18 + English suites + panel within 0.3 of Gemini.</div>
  <div class="box"><b class="t">Safety and sovereignty controls</b>Echo gate, barge-in budget, silence watchdog in the relay; privacy shield on audio and text; hash-chained send log; interim Gemini through Vertex Mumbai with zero retention and the minimisation gateway, so nothing is stored at Google while it is still the reference in production.</div>
  <div class="box"><b class="t">Serving tricks for the 2-GPU demo</b>Batched decode so all sessions tick together; FP8 weights; light batching on the stock server reaches 30–50 sessions for the demo; the full serving work (4-bit cache, scheduler, 3B distillation) comes after sign-off.</div>
</div>

<h2>D · Ninety days to the parity attempt</h2>
<table>
<tr><th>Weeks</th><th>Harness and atlas</th><th>Data factory</th><th>Training</th><th>Integration</th></tr>
<tr><td class="k">1–2</td><td>Virtual microphone at the WebSocket; Gemini atlas measured and signed; Mimi, SraVaani, svara, IndicF5 probed on our clips; panel recruited</td><td>Recordings masked, split; open corpora gathered; synthetic generation starts</td><td>English core running from the open base on GPU 1</td><td>Relay upstream swapped to the core; transcript dispatch; prefill; captions</td></tr>
<tr><td class="k">3–5</td><td>Weekly atlas + English suites</td><td>5,000 synthetic hours filtered by the tuned recogniser</td><td>Kannada sound + language, then dialogue; first Kannada checkpoint week 5</td><td>English core serves the three desks as a demo; Sarvam brain on GPU 2</td></tr>
<tr><td class="k">6–8</td><td>Weekly atlas, Kannada bank, panel</td><td>Sakala flow dialogues for all desks; code-mixed turns</td><td>Persona, desks, language switching; <span class="a">Gate 1 at week 8</span>: bank 55, live UI 18, panel within 0.5</td><td>Kannada core replaces the English core; one bilingual model</td></tr>
<tr><td class="k">9–12</td><td>20-listener side-by-side with Gemini on every atlas dimension</td><td>Hard cases: noise, phones, dialects, interruptions</td><td>Round two: code-mixing, voice, emotion; full pass week 11; <span class="a">parity attempt day 90</span></td><td>Load test on one card; delegation stream if time allows</td></tr>
</table>
<p class="foot"><b>Build cost:</b> the two H200s we have, a team of about ten for three months, panels and data work: roughly ₹2–4 crore, almost all people; no rented cluster. <b>Slip risks:</b> a failed week-12 panel costs about two weeks per extra round; mixed-channel recordings push weight onto synthetic data; a poor Mimi result on Kannada costs a week. <b>Sign-off:</b> Gemini retired that day; the atlas becomes the regression suite; 100% sovereign from then on.</p>
</div>
"""

PAGE2 = """
<div class="pg">
<h1>Sovereign Mitra · how it scales <span style="font-weight:500;color:#4c5a6b">· page 2 of 2 · the two H200s to 50,000 live sessions</span></h1>
<p class="sub">A live session is a person in a conversation with Mitra right now. The client drops to Standby after 20 s of silence, so about one person in four with Mitra open is live at any moment. All numbers are hardware arithmetic until the load test in week 12 replaces them with measurements.</p>

<h2>A · Why a duplex core's capacity is a fixed number of sessions per card</h2>
<div class="two">
  <div><p>A native duplex model takes one step per session every 80 ms whether or not anyone is talking, so the cost of a session does not depend on how much is said, and every session can be speaking at once. All sessions on a card tick at the same instant, so they are processed as one batch: the model weights are read once per tick for everyone. What grows with each session is its memory of the conversation, the attention cache. A card is therefore limited by how many caches fit in memory and by how fast it can read them all inside one tick.</p>
  <p>A card run at its limit stutters, because the slowest 1% of ticks start missing the 80 ms deadline. The number we promise is where the 99th-percentile tick still lands with headroom for bursts of interruptions, roughly 50–60% of the physical limit.</p></div>
  <table>
  <tr><th>Quantity</th><th class="n">Value</th><th>Source</th></tr>
  <tr><td>H200 memory · bandwidth</td><td class="n">141 GB · 4.8 TB/s</td><td>NVIDIA spec</td></tr>
  <tr><td>Core weights, 7B FP8 / 3B FP8</td><td class="n">7.5 GB / 3 GB</td><td>read once per tick</td></tr>
  <tr><td>Cache per session, 7B, 3-min window, FP8</td><td class="n">0.6 GB</td><td>32 layers × 4,096 × 2 bytes-ish × 2,250 steps</td></tr>
  <tr><td>Cache per session, 3B, 2-min window, 4-bit</td><td class="n">0.15 GB</td><td>smaller model, compressed cache</td></tr>
  <tr><td>Sessions that fit in memory, 7B / 3B</td><td class="n">~220 / ~850</td><td>130 GB free ÷ cache</td></tr>
  <tr><td>Time to read 150 caches of the 7B per tick</td><td class="n">~19 ms of 80</td><td>90 GB ÷ 4.8 TB/s</td></tr>
  <tr><td>Rest of the tick: codec, depth transformer, overhead</td><td class="n">15–25 ms</td><td>engineering estimate</td></tr>
  </table>
</div>

<h2>B · The two H200s we have (layout B: GPU 1 pure duplex worker · GPU 2 duplex worker + Sarvam brain in FP8)</h2>
<div class="kpi">
  <div><div class="n">6–8</div><div class="t">day one, stock server, one process per session in bf16</div></div>
  <div><div class="n">30–50</div><div class="t">the 90-day demo, light batching</div></div>
  <div><div class="n">~130</div><div class="t">7B core after the serving work; range 80–200; <b>the number to promise</b></div></div>
  <div><div class="n">~250</div><div class="t">physical ceiling of the pair on the 7B core; not smooth</div></div>
  <div><div class="n">~300</div><div class="t">3B distilled core, smooth; ceiling ~500</div></div>
  <div><div class="n">400–600</div><div class="t">people with Mitra open at once at one in four live (900–1,200 on the 3B)</div></div>
</div>
<div class="two">
  <div class="box"><b class="t">How 130 comes out of two cards</b>GPU 1 holds about 220 sessions of the 7B core in memory and ticks 150 of them inside about 40 ms. GPU 2 gives about 35 GB and a third of its time to the Sarvam brain, so it carries roughly half as many. Together about 250 at the physical limit; 130 is where the 99th-percentile tick is still met with headroom. All 130 can be speaking at the same moment, in both directions, because the cost is per tick, not per word. "Smooth like Gemini today" = first word under 0.5 s, barge-in cut under 0.25 s, no dropouts, no failed sessions over hours.</div>
  <div class="box"><b class="t">Training fits on the same two cards</b>A duplex model sees one token per audio frame, so 10,000 hours of Kannada is about 450 million training tokens. At six operations per parameter per token and 40% utilisation, one pass of the 7B core is about a day on two H200s, including the per-frame depth transformer. Full training of 7B with optimiser state fits across the two 141 GB cards with sharding; adapter rounds fit on one. Synthesising 10,000 hours with a 3B voice model is about a week on one card. No rented training cluster is needed.</div>
</div>

<h2>C · From the pilot to 50,000 live sessions: identical workers behind a scheduler</h2>
<p>Scaling adds workers; it does not change the design. Stateless WebSocket gateways run the relay. A session scheduler does admission control (a card is never oversubscribed), bin-packs sessions onto duplex workers, checkpoints each session's state every 10 s so a worker failure resumes the call, and drains a worker before a weight update. Pools are heterogeneous: the core on bandwidth cards (H200, or Blackwell when bought, which roughly doubles sessions per card because this workload is bandwidth-bound), the Mimi codec and the transcript branch on cheap cards (L40S class), the brain on a small vLLM pool, the deterministic layer and the POC on CPU with PostgreSQL and Redis replacing SQLite. Overflow goes to the same 3B core, never to a cascade.</p>
<table>
<tr><th>Live sessions at once</th><th class="n">Core cards</th><th class="n">Brain cards</th><th class="n">Codec + hearing</th><th class="n">Total GPUs</th><th class="n">Nodes</th><th>Rented / month</th><th>Bought, one time</th><th>When</th></tr>
<tr><td class="k">1,000 · taluk-scale pilot</td><td class="n">4–6</td><td class="n">2</td><td class="n">3</td><td class="n">9–11</td><td class="n">2</td><td>₹20–30 lakh</td><td>₹3–4 crore</td><td>month 4–5</td></tr>
<tr><td class="k">10,000 · first production stage</td><td class="n">40–50</td><td class="n">15–20</td><td class="n">25</td><td class="n">80–95</td><td class="n">~12</td><td>₹1.5–2.5 crore</td><td>₹25–35 crore</td><td>month 8–9 (GPU order in month 3)</td></tr>
<tr><td class="k">50,000 · the stated ceiling</td><td class="n">200–250</td><td class="n">60–100</td><td class="n">125</td><td class="n">385–475</td><td class="n">50–60</td><td>₹5–8 crore</td><td>₹120–180 crore + a hall (~1 MW) + a second site</td><td>month 12–18, gated by building and power</td></tr>
</table>
<p class="foot">Assumptions: 250 sessions per core card on the 3B core, 70% of turns answered by the deterministic layer, one brain call per 10 s per session, one codec card per 400 sessions, 10% spare. The first version of this plan needed 750–1,200 GPUs at 50,000; the levers below cut it by about three times. Metered Gemini at 50,000 simultaneous speakers would be about ₹80 crore a month, so owning wins from roughly 1,000 concurrent sessions. If "50,000" means daily users rather than people speaking in the same minute, divide every row by about ten.</p>

<h2>D · Why 50,000 concurrent live sessions holds up</h2>
<div class="three">
  <div class="box"><b class="t">Per-session cost is small and fixed</b>0.15 GB of cache and one batched step per tick on the 3B core. 250 sessions on one card read 38 GB per tick, about 8 ms of 80. Memory holds 850. The limit becomes software overhead, which CUDA graphs and a lean codec path address, which is why the planning number is 250 and not 850.</div>
  <div class="box"><b class="t">Most turns never touch a model</b>Counts, ids, routing, status, inbox, open, accept, resolve: the deterministic layer answers them from SQL. The brain pool stays a tenth of the core pool. The brain's calls are short, bursty and prefix-cached, so 50,000 sessions produce about 1,700 brain calls a second, well inside 60–100 cards.</div>
  <div class="box"><b class="t">Only live sessions cost anything</b>Standby closes the session after 20 s of silence. At one in four live, 50,000 live sessions is roughly 200,000 people with Mitra open. Capacity is provisioned for the office-hours peak, and the GPUs run the training factory at night, so nothing sits idle.</div>
  <div class="box"><b class="t">Failure is contained</b>Admission control refuses the session it cannot serve well instead of slowing everyone. A worker failure resumes calls from the 10 s checkpoint. Rolling weight updates drain one worker at a time. A second Indian site mirrors the primary for failover.</div>
  <div class="box"><b class="t">The levers, with their multipliers</b>3B distilled core ÷3 · FP8 weights + 4-bit cache included · codec and hearing on cheap cards −30% of spend · Blackwell core pool ÷2 on the core at ~1.5× price per card · codec encoder in the browser, later, −10% · 7B kept only for the CS and officer desks, a few hundred users.</div>
  <div class="box"><b class="t">What is measured before anything is bought</b>Week 12: 200 synthetic Kannada callers on one card, with per-tick, barge-in and first-word latency recorded as the count rises. The count at which the 80 ms tick still holds at the 99th percentile is the planning number. That one-day run settles the GPU order for the 10,000 stage before it is placed.</div>
</div>
<p class="foot"><b>Sovereignty at scale is unchanged:</b> every pool runs on GoK hardware in Karnataka under GoK keys, with no outbound path; the audio, the text and the weights never leave; Gemini has no role after sign-off.</p>
</div>
"""


def build() -> str:
    return f"<!doctype html><html><head><meta charset='utf-8'><title>Sovereign Mitra: two pages</title><style>{CSS}</style></head><body>{PAGE1}{PAGE2}</body></html>"


async def pdf(html_path: Path, out: Path):
    from cdp import Browser
    async with Browser(port=9494, size=(900, 1300)) as b:
        await b.goto(html_path.resolve().as_uri(), 2)
        r = await b.cmd("Page.printToPDF", printBackground=True, preferCSSPageSize=True)
        out.write_bytes(base64.b64decode(r["data"]))


def main():
    hp = ROOT / "tools" / "sovereign_2pager.html"
    hp.write_text(build(), encoding="utf-8")
    out = ROOT / "Mitra_Sovereign_Plan_2pager.pdf"
    asyncio.run(pdf(hp, out))
    import pymupdf
    d = pymupdf.open(out)
    print("pages", len(d), "size", out.stat().st_size)
    for i, p in enumerate(d):
        print(f"page {i + 1}: {len(p.get_text())} chars")


if __name__ == "__main__":
    main()
