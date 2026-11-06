"""Builds Mitra_English_Sovereign_Models_and_Costs.pdf in the project root, for the AI ops team:
Part 1 = every model the English-only sovereign full-duplex architecture needs (ids, sizes, licences, placement, download order, data);
Part 2 = what Gemini costs now and at 1,000 / 10,000 / 50,000 users over 5 and 10 years.
HTML -> headless Edge over CDP -> Page.printToPDF (A4). Run: python tools/make_english_sovereign_pdf.py"""
import asyncio
import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "mitra" / "tests"))

CSS = """
@page { size: A4; margin: 10mm 11mm 10mm; }
body { font-family:"Segoe UI","Nirmala UI",sans-serif; color:#15202e; font-size:9.6px; line-height:1.32; }
h1 { font-size:18px; color:#0d2547; margin:0 0 2px; }
h1 span { font-weight:500; color:#4c5a6b; font-size:12px; }
.sub { color:#4c5a6b; font-size:9.8px; margin:0 0 8px; }
h2 { font-size:13px; color:#0d2547; margin:10px 0 4px; border-bottom:1.5px solid #16c784; padding-bottom:2px; page-break-after:avoid; }
h3 { font-size:10.4px; color:#0d2547; margin:7px 0 3px; page-break-after:avoid; }
p { margin:0 0 5px; }
table { width:100%; border-collapse:collapse; margin:2px 0 6px; page-break-inside:auto; }
tr { page-break-inside:avoid; }
th { background:#0d2547; color:#fff; text-align:left; padding:3.5px 5px; font-size:8.8px; }
td { padding:3px 5px; border-bottom:1px solid #dfe5ec; vertical-align:top; }
tr:nth-child(even) td { background:#f5f7fa; }
td.k { font-weight:700; }
td.n, th.n { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
code { font-family:Consolas,"Cascadia Mono",monospace; font-size:8.9px; background:#eef2f6; padding:0 3px; border-radius:3px; white-space:nowrap; }
.callout { border-left:3px solid #16c784; background:#f0fbf5; padding:4px 8px; margin:4px 0 6px; }
.warn { border-left:3px solid #f59e0b; background:#fff8ea; padding:4px 8px; margin:4px 0 6px; }
.two { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
.box { border:1px solid #cfd8e3; border-radius:5px; padding:5px 8px; background:#fbfcfe; page-break-inside:avoid; }
.box b.t { display:block; color:#0d2547; margin-bottom:2px; }
.kpi { display:grid; grid-template-columns:repeat(4,1fr); gap:6px; margin:4px 0 6px; }
.kpi > div { border:1px solid #cfd8e3; border-radius:5px; padding:4px 7px; background:#fff; }
.kpi .n { font-size:16px; font-weight:800; color:#0d2547; line-height:1.1; }
.kpi .t { font-size:8.5px; color:#4c5a6b; }
ol, ul { margin:2px 0 5px 15px; padding:0; } li { margin:1.5px 0; }
.foot { font-size:8.4px; color:#6b7786; margin-top:6px; }
.src { font-size:8.3px; color:#4c5a6b; }
.src a { color:#0d5c8f; text-decoration:none; }
.pb { page-break-before:always; }
"""

PART1 = """
<h1>Mitra · sovereign English full-duplex voice <span>· models to load, and what Gemini costs</span></h1>
<p class="sub">27 Oct 2026 · Sakala Mitra, Government of Karnataka · For the AI ops team · Scope: English only, every model free to download, licences that allow a government to run them in production, nothing leaves our hardware. Gemini Live stays the measured reference until the core matches it; it is never a training source. Hardware: the two H200s in the one office server.</p>

<h2>Part 1 · Every model the English sovereign architecture needs</h2>
<p>The architecture is the one in the 90-day plan with one change for English: the text brain becomes <b>gpt-oss-120b</b> instead of Sarvam, because it is Apache 2.0, stronger in English, and fits beside the duplex core on one card. One native duplex model hears and speaks at the same time; the existing Mitra router, SQL and tools decide; results are pushed back into the core and spoken in its own voice. No separate speech-to-text, text model and text-to-speech in the voice path.</p>

<h3>1.1 · The serving stack: what runs on the two cards at all times</h3>
<table>
<tr><th style="width:11%">Role</th><th style="width:19%">Model, Hugging Face id</th><th style="width:17%">Size on disk</th><th style="width:21%">Licence and condition</th><th>Why this one</th></tr>
<tr><td class="k">Duplex core, primary</td><td><code>nvidia/personaplex-7b-v1</code></td><td>7B, bf16, about 16 GB; gated, accept the terms on download</td><td>NVIDIA Open Model License; the card says "ready for commercial use". Base Moshi weights CC-BY-4.0, so Kyutai is credited in the product notice</td><td>Moshi with persona and voice prompts already trained in. Full-Duplex-Bench: interruption takeover 0.95 at 0.24 s, smooth turn-taking 0.908 at 0.17 s. Gemini Live measures 1.2 s.</td></tr>
<tr><td class="k">Duplex core, base and fallback</td><td><code>kyutai/moshiko-pytorch-bf16</code><br><code>kyutai/moshika-pytorch-bf16</code></td><td>7B plus depth transformer, about 16 GB each</td><td>CC-BY-4.0 weights; Python code MIT, Rust server Apache 2.0</td><td>The reference architecture. Needed anyway: PersonaPlex is built on Moshiko, and moshi-finetune trains on it.</td></tr>
<tr><td class="k">Audio codec</td><td><code>kyutai/mimi</code></td><td>96M, under 0.5 GB</td><td>CC-BY-4.0</td><td>12.5 Hz, 24 kHz, 1.1 kbps. Bundled with the core. The user transcript branch and the factory use it too.</td></tr>
<tr><td class="k">Live user transcript</td><td><code>kyutai/stt-1b-en_fr</code></td><td>1B, about 2 GB</td><td>CC-BY-4.0</td><td>Streaming, 0.5 s delay. Moshi's text stream covers only Mitra's own words, so the citizen's words for the dispatcher come from this.</td></tr>
<tr><td class="k">Text brain</td><td><code>openai/gpt-oss-120b</code></td><td>117B total, 5.1B active, MXFP4, about 65 GB, fits one 80 GB card</td><td>Apache 2.0</td><td>Picks the intent as guided JSON, words difficult replies, reasons. Runs on vLLM.</td></tr>
<tr><td class="k">Text brain, fast fallback</td><td><code>Qwen/Qwen3-30B-A3B</code></td><td>30B total, 3B active, FP8 about 31 GB</td><td>Apache 2.0</td><td>If the 120B is busy or memory is tight on the training nights.</td></tr>
<tr><td class="k">Voice activity</td><td><code>snakers4/silero-vad</code></td><td>2 MB</td><td>MIT</td><td>The relay's echo gate and silence watchdog.</td></tr>
<tr><td class="k">End-of-turn safety net</td><td><code>pipecat-ai/smart-turn-v3</code></td><td>about 30 MB, ONNX</td><td>BSD-2-Clause</td><td>Semantic end-of-turn in the safety controller for the harness and the overflow path; English covered.</td></tr>
<tr><td class="k">Noise suppression</td><td>DeepFilterNet3, <code>Rikorose/DeepFilterNet</code></td><td>about 10 MB</td><td>MIT or Apache 2.0, our choice</td><td>Cleans the 16 kHz mic stream before the core when the room is noisy; runs on CPU.</td></tr>
<tr><td class="k">Wake word</td><td>openWakeWord, <code>dscripka/openWakeWord</code>, with a "Hey Mitra" model we train</td><td>a few MB, CPU</td><td>Code Apache 2.0. The pre-trained example models are CC-BY-NC-SA, so we do not use those; a model we train ourselves is ours</td><td>Replaces Gemini's transcription of every room utterance in Standby. Trained from synthetic speech.</td></tr>
<tr><td class="k">Wake-word training voice</td><td>Piper, <code>rhasspy/piper</code></td><td>about 60 MB per voice</td><td>MIT</td><td>Generates the thousands of "Hey Mitra" clips openWakeWord needs.</td></tr>
</table>

<h3>1.2 · The factory and evaluation stack: offline, on the same cards at night</h3>
<table>
<tr><th style="width:13%">Role</th><th style="width:22%">Model</th><th style="width:10%">Size</th><th style="width:17%">Licence</th><th>Why</th></tr>
<tr><td class="k">Fine-tuning</td><td><code>kyutai-labs/moshi-finetune</code></td><td>code</td><td>Apache 2.0</td><td>LoRA or full tuning of Moshi and PersonaPlex. Their figure: one H100, 39.6 GB peak. Data is stereo WAV, Mitra left, user right, with JSON transcripts it can make itself.</td></tr>
<tr><td class="k">Synthetic dialogue voices</td><td><code>kyutai/tts-1.6b-en_fr</code> with <code>kyutai/tts-voices</code></td><td>1.8B, about 4 GB</td><td>CC-BY-4.0; cloning limited to the published voice embeddings</td><td>Streaming, batch throughput 75× real time. Voices the scripted Sakala dialogues in two voices. Same Mimi codec as the core.</td></tr>
<tr><td class="k">Second synthesis voice, for variety</td><td><code>ResembleAI/chatterbox</code></td><td>500M, about 2 GB</td><td>MIT</td><td>Different voice family for the citizen side; emotion control.</td></tr>
<tr><td class="k">Expressive multi-speaker synthesis</td><td><code>microsoft/VibeVoice-1.5B</code></td><td>3B, about 6 GB</td><td>MIT, but the card says research use only</td><td>Up to four speakers in one long recording; use only for evaluation material, not production.</td></tr>
<tr><td class="k">Conversational TTS, research</td><td><code>sesame/csm-1b</code>, <code>canopylabs/orpheus-3b-0.1-ft</code></td><td>2B and 4B</td><td>Apache 2.0, both gated</td><td>Alternatives for the citizen voice in synthetic data; Orpheus streams at about 200 ms.</td></tr>
<tr><td class="k">Scoring ASR, batch</td><td><code>nvidia/canary-qwen-2.5b</code> and <code>nvidia/parakeet-tdt-0.6b-v3</code></td><td>5 GB and 2.5 GB</td><td>CC-BY-4.0</td><td>Filters synthetic dialogues by word error and scores the core's output. Both top the open ASR leaderboard at about 6% WER.</td></tr>
<tr><td class="k">Scoring ASR, streaming reference</td><td><code>nvidia/nemotron-speech-streaming-en-0.6b</code></td><td>2.5 GB</td><td>NVIDIA Open Model License; verify the card</td><td>What Full-Duplex-Bench style timing measurements transcribe with.</td></tr>
<tr><td class="k">Independent ASR</td><td><code>openai/whisper-large-v3-turbo</code></td><td>1.6 GB</td><td>MIT</td><td>Second opinion in the filters so one recogniser's bias does not shape the data.</td></tr>
<tr><td class="k">Word timestamps</td><td><code>Qwen/Qwen3-ForcedAligner-0.6B</code></td><td>1.2 GB</td><td>Apache 2.0</td><td>Aligns transcripts to audio at 43 ms average error for the inner-monologue training targets.</td></tr>
<tr><td class="k">Speaker separation</td><td><code>pyannote/speaker-diarization-community-1</code></td><td>50 MB, gated</td><td>CC-BY-4.0</td><td>Splits any mixed recording into the two channels the trainer needs. Apache alternative: the <code>diarize</code> package.</td></tr>
<tr><td class="k">Benchmark</td><td>Full-Duplex-Bench, <code>DanielLin94144/Full-Duplex-Bench</code></td><td>code</td><td>licence file in the repo, read it</td><td>v1.0 pause handling, backchannel, turn-taking, interruption; v1.5 overlaps; v3.0 tool use under disfluent speech. The public yardstick PersonaPlex and Gemini are scored on.</td></tr>
<tr><td class="k">Dialogue scripts</td><td>gpt-oss-120b, already loaded</td><td></td><td>Apache 2.0</td><td>Writes the Sakala conversations with interruptions, repairs and backchannels for the factory.</td></tr>
<tr><td class="k">Guard, optional</td><td><code>ibm-granite/granite-guardian-3.3-8b</code></td><td>16 GB</td><td>Apache 2.0</td><td>A text safety and injection classifier behind our regex guard. Not needed for the sprint.</td></tr>
</table>

<h3>1.3 · The data: all free and licensed for a government product</h3>
<table>
<tr><th style="width:22%">Corpus</th><th>What</th><th style="width:15%">Hours</th><th style="width:33%">Terms</th></tr>
<tr><td class="k">Open Yap 1K, The Agentic Data Company</td><td>Natural two-speaker English conversations, each speaker on its own track, 48 kHz, 239 consented and paid speakers</td><td>1,000 h in 1,602 conversations</td><td>Free under its Data Use Agreement: commercial use, training and deployment allowed; no redistribution, no identifying speakers, no voice clones. Access is requested on their site and granted within hours. The 8.9 h sample is CC-BY-4.0 on Hugging Face.</td></tr>
<tr><td class="k">DailyTalk, <code>kyutai/DailyTalkContiguous</code></td><td>Scripted two-speaker dialogue in moshi-finetune's format</td><td>14 GB</td><td>CC-BY-SA 4.0</td></tr>
<tr><td class="k">AMI Meeting Corpus</td><td>Multi-speaker English meetings, close-talk mics</td><td>100 h</td><td>CC-BY-4.0</td></tr>
<tr><td class="k">Our own synthetic Sakala dialogues</td><td>Scripts by gpt-oss-120b, voiced by Kyutai TTS and Chatterbox, filtered by Canary and Whisper</td><td>2,000 to 5,000 h, made on our cards</td><td>Ours</td></tr>
<tr><td class="k">MUSAN, RIRS_NOISES</td><td>Noise, music, room impulse responses for augmentation</td><td></td><td>CC-BY-4.0, Apache 2.0</td></tr>
</table>

<div class="warn"><b>Two models researched and not recommended.</b> NVIDIA NemotronLabs VoiceChat 11B has the native tool-call stream we want, but its card puts it under the OpenMDW 1.1 licence and describes it as targeted at researchers and developers; secondary sources read it as research-only. Until legal reads that licence, it stays out. Sarvam-105B is Apache 2.0 and the right brain for Kannada later, but its FP8 build needs both cards, which this English sprint cannot give it.</div>

<h3>1.4 · Placement on the two H200s</h3>
<div class="two">
  <div class="box"><b class="t">GPU 1 · the duplex worker</b>PersonaPlex core, Mimi, Kyutai STT 1B, Silero, Smart Turn: about 22 GB of models and 0.6 GB per live session, so 100 to 150 sessions in memory.</div>
  <div class="box"><b class="t">GPU 2 · the brain, a second worker, the factory by night</b>gpt-oss-120b at 65 GB plus 20 GB of cache, a second duplex worker at 16 GB, and the factory models by night; moshi-finetune's 40 GB fits by pausing the second worker.</div>
</div>
<p><b>Total downloads about 230 GB.</b> Gated repositories (PersonaPlex, CSM, Orpheus, pyannote) need a Hugging Face account that has accepted each model's terms; the Open Yap 1K request is made on the publisher's site and is granted within hours.</p>

<h3>1.5 · Download order for AI ops, day one</h3>
<ol>
<li><code>nvidia/personaplex-7b-v1</code> (gated), <code>kyutai/moshiko-pytorch-bf16</code>, <code>kyutai/moshika-pytorch-bf16</code>, <code>kyutai/mimi</code></li>
<li><code>kyutai/stt-1b-en_fr</code>, <code>kyutai/tts-1.6b-en_fr</code>, <code>kyutai/tts-voices</code></li>
<li><code>openai/gpt-oss-120b</code>, <code>Qwen/Qwen3-30B-A3B</code> (FP8 build), vLLM</li>
<li><code>nvidia/canary-qwen-2.5b</code>, <code>nvidia/parakeet-tdt-0.6b-v3</code>, <code>openai/whisper-large-v3-turbo</code>, <code>Qwen/Qwen3-ForcedAligner-0.6B</code>, <code>pyannote/speaker-diarization-community-1</code> (gated)</li>
<li><code>snakers4/silero-vad</code>, <code>pipecat-ai/smart-turn-v3</code>, DeepFilterNet3, openWakeWord code with Piper, <code>ResembleAI/chatterbox</code></li>
<li>Code: <code>kyutai-labs/moshi</code> (Rust server), <code>kyutai-labs/moshi-finetune</code>, <code>DanielLin94144/Full-Duplex-Bench</code></li>
<li>Data: the Open Yap 1K access request, DailyTalk, AMI, MUSAN, RIRS_NOISES</li>
</ol>
<p class="foot">Legal reads the NVIDIA Open Model License before day 1; the answer is clean either way because Moshiko is CC-BY-4.0. Every CC-BY model is credited in the product notice. Nothing in this list phones home; every model is a file we hold on the office server.</p>
"""

PART2 = """
<h2 class="pb">Part 2 · What Gemini costs now and at scale</h2>
<p>Everything below is the metered cost of running Mitra on Gemini. It is what the sovereign stack in Part 1 replaces for English. One rupee figure throughout: <b>$1 = ₹95</b>, the observed rate in August and September 2026.</p>

<h3>2.1 · The rate card, paid tier, from Google's pricing page on 27 Oct 2026</h3>
<table>
<tr><th>Model</th><th>Text in</th><th>Text out</th><th>Audio in</th><th>Audio out</th></tr>
<tr><td class="k">Gemini 3.8 Live, the voice</td><td>$0.75 /M</td><td>$4.50 /M</td><td>$3.00 /M, $0.005 per minute</td><td>$12.00 /M, $0.018 per minute</td></tr>
<tr><td class="k">Gemini 3.8 Flash and 3.6 Flash</td><td>$0.75 /M, rising to $1.50 on 1 Jan 2027</td><td>$3.75 /M, rising to $7.50</td><td></td><td></td></tr>
<tr><td class="k">Gemini 3.1 Flash-Lite</td><td>$0.25 /M</td><td>$1.50 /M</td><td>$0.50 /M</td><td></td></tr>
<tr><td class="k">Gemini 3.8 Flash TTS</td><td>$0.50 /M, rising to $1.00</td><td></td><td></td><td>$9.00 /M, rising to $18.00</td></tr>
</table>
<p class="foot">Audio is billed at 25 tokens a second. The Live session is billed for the whole time it is open, whether or not anyone is speaking.</p>

<h3>2.2 · What one Mitra conversation costs</h3>
<p>From our own logs, a live conversation averages 8.5 user turns, nearly every one with a function call. The unit is a 5-minute conversation with the citizen and Mitra each speaking about a third of the time.</p>
<table>
<tr><th>Item</th><th class="n">Tokens or minutes</th><th class="n">Cost</th></tr>
<tr><td>Live audio in: the whole open session is billed</td><td class="n">5 min</td><td class="n">$0.025</td></tr>
<tr><td>Live audio out: Mitra speaking</td><td class="n">1.75 min</td><td class="n">$0.032</td></tr>
<tr><td>Live text: instruction, function declarations, results; about 8k tokens a turn if Google re-bills the context each turn, as developers report</td><td class="n">68k tokens</td><td class="n">$0.051, or $0.008 if the context is not re-billed</td></tr>
<tr><td>POC calls behind the filing: understanding on 3.6 Flash, a letter read, Kannada rendering</td><td class="n"></td><td class="n">about $0.010</td></tr>
<tr><td class="k">Per conversation</td><td class="n"></td><td class="n"><b>$0.08 to $0.12, about ₹9.5</b></td></tr>
<tr><td class="k">Per live minute</td><td class="n"></td><td class="n"><b>about ₹1.9</b></td></tr>
</table>

<div class="kpi">
  <div><div class="n">₹9.5</div><div class="t">one 5-minute conversation</div></div>
  <div><div class="n">₹1.9</div><div class="t">one live minute</div></div>
  <div><div class="n">₹209</div><div class="t">one daily user per month (22 days)</div></div>
  <div><div class="n">₹1–3k</div><div class="t">a week today, test batteries only</div></div>
</div>

<h3>2.3 · Today's spend</h3>
<p>The logs show 130 live conversations since 21 Oct, nearly all test batteries, plus the typed banks on the text models at a fraction of a rupee each. That is roughly ₹1,000 to ₹3,000 a week, which is why the prepaid balance ran out once on 17 Oct and has been fine since.</p>

<h3>2.4 · At scale, daily users</h3>
<p>Assumption: each user has one 5-minute conversation a day on 22 days a month, so ₹209 per user per month. The text-model price rise in January adds about 3%; the band allows 30% for that, for rupee movement and for longer conversations.</p>
<table>
<tr><th>Daily users</th><th class="n">Per month</th><th class="n">Per year</th><th class="n">5 years</th><th class="n">10 years</th></tr>
<tr><td class="k">1,000</td><td class="n">₹2.1 lakh</td><td class="n">₹25 lakh</td><td class="n">₹1.25 to 1.6 crore</td><td class="n">₹2.5 to 3.3 crore</td></tr>
<tr><td class="k">10,000</td><td class="n">₹21 lakh</td><td class="n">₹2.5 crore</td><td class="n">₹12.5 to 16 crore</td><td class="n">₹25 to 33 crore</td></tr>
<tr><td class="k">50,000</td><td class="n">₹1.05 crore</td><td class="n">₹12.5 crore</td><td class="n">₹63 to 82 crore</td><td class="n">₹125 to 165 crore</td></tr>
</table>

<h3>2.5 · At scale, if 50,000 means concurrent</h3>
<div class="warn">Fifty thousand people speaking to Mitra in the same minute for eight office hours is 24 million live minutes a day. At ₹1.9 a minute that is about <b>₹1 crore a day, ₹22 to 25 crore a month, ₹270 to 300 crore a year</b>, and ₹1,400 to 3,000 crore over five to ten years. Nobody should sign that; it is the case for owning.</div>

<h3>2.6 · The owning comparison, from the sovereign plan</h3>
<table>
<tr><th>Scale</th><th>Peak live sessions</th><th>Sovereign hardware, one time</th><th>Gemini, per year</th><th>Payback</th></tr>
<tr><td class="k">The pilot</td><td>tens</td><td>the two H200s we already own</td><td>a few lakh</td><td>zero API cost from the day the English core is live</td></tr>
<tr><td class="k">10,000 daily users</td><td>a few hundred</td><td>two to three nodes, ₹3 to 4 crore</td><td>₹2.5 crore</td><td>about 18 months</td></tr>
<tr><td class="k">50,000 daily users</td><td>a few thousand</td><td>about 12 nodes, ₹15 crore</td><td>₹12.5 crore</td><td>about 14 months</td></tr>
</table>
<p>After payback the sovereign stack costs power and people only. The audio, the text and the weights never leave the government's own hardware, which no Gemini plan, including Vertex Mumbai with zero retention, can offer.</p>

<h3>Sources</h3>
<p class="src">
<a href="https://ai.google.dev/gemini-api/docs/pricing">Gemini API pricing</a> ·
<a href="https://huggingface.co/nvidia/personaplex-7b-v1">PersonaPlex card</a> ·
<a href="https://github.com/kyutai-labs/moshi">Moshi repository</a> ·
<a href="https://github.com/kyutai-labs/moshi-finetune">moshi-finetune</a> ·
<a href="https://huggingface.co/kyutai/tts-1.6b-en_fr">Kyutai TTS 1.6B</a> ·
<a href="https://huggingface.co/kyutai/stt-1b-en_fr">Kyutai STT 1B</a> ·
<a href="https://huggingface.co/kyutai/mimi">Mimi</a> ·
<a href="https://huggingface.co/nvidia/NVIDIA-NemotronLabs-VoiceChat-11B">VoiceChat 11B card</a> ·
<a href="https://huggingface.co/openai/gpt-oss-120b">gpt-oss-120b</a> ·
<a href="https://huggingface.co/Qwen/Qwen3-30B-A3B">Qwen3-30B-A3B</a> ·
<a href="https://huggingface.co/sarvamai/sarvam-105b-fp8">Sarvam-105B FP8</a> ·
<a href="https://huggingface.co/blog/TheAgenticDataCompany/open-yap-1k">Open Yap 1K</a> ·
<a href="https://github.com/pipecat-ai/smart-turn">Smart Turn</a> ·
<a href="https://github.com/snakers4/silero-vad">Silero VAD</a> ·
<a href="https://github.com/Rikorose/DeepFilterNet">DeepFilterNet</a> ·
<a href="https://github.com/dscripka/openWakeWord">openWakeWord</a> ·
<a href="https://github.com/rhasspy/piper">Piper</a> ·
<a href="https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B">Qwen3-ForcedAligner</a> ·
<a href="https://huggingface.co/pyannote/speaker-diarization-community-1">pyannote community-1</a> ·
<a href="https://arxiv.org/pdf/2509.14128">Parakeet and Canary</a> ·
<a href="https://huggingface.co/openai/whisper-large-v3-turbo">Whisper large-v3-turbo</a> ·
<a href="https://huggingface.co/ResembleAI/chatterbox">Chatterbox</a> ·
<a href="https://huggingface.co/microsoft/VibeVoice-1.5B">VibeVoice</a> ·
<a href="https://huggingface.co/sesame/csm-1b">Sesame CSM</a> ·
<a href="https://huggingface.co/canopylabs/orpheus-3b-0.1-ft">Orpheus</a> ·
<a href="https://huggingface.co/ibm-granite/granite-guardian-3.3-8b">Granite Guardian</a> ·
<a href="https://github.com/DanielLin94144/Full-Duplex-Bench">Full-Duplex-Bench</a> ·
<a href="https://huggingface.co/kyutai/DailyTalkContiguous">DailyTalk</a> ·
<a href="https://groups.inf.ed.ac.uk/ami/corpus/">AMI corpus</a> ·
<a href="https://www.openslr.org/17/">MUSAN</a> ·
<a href="https://www.openslr.org/28/">RIRS_NOISES</a> ·
<a href="https://discuss.ai.google.dev/t/does-gemini-live-native-audio-bill-cumulative-prompt-tokens-on-every-turn-cost-seems-to-scale-with-turn-count-not-call-duration/173248">Live API token billing thread</a> ·
<a href="https://hdfcsky.com/news/rupee-rises-24-paise-to-close-at-95-46-against-us-dollar">Rupee rate</a>
</p>
"""


def build() -> str:
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>Mitra: English sovereign models and Gemini costs</title>"
            f"<style>{CSS}</style></head><body>{PART1}{PART2}</body></html>")


async def pdf(html_path: Path, out: Path):
    from cdp import Browser
    async with Browser(port=9495, size=(900, 1300)) as b:
        await b.goto(html_path.resolve().as_uri(), 2)
        r = await b.cmd("Page.printToPDF", printBackground=True, preferCSSPageSize=True,
                        displayHeaderFooter=True, headerTemplate="<span></span>",
                        footerTemplate="<div style='font-size:7px;color:#6b7786;width:100%;text-align:center;font-family:Segoe UI,sans-serif'>"
                                       "Mitra · sovereign English voice · models and Gemini costs · 27 Oct 2026 · page <span class='pageNumber'></span> of <span class='totalPages'></span></div>",
                        marginTop=0.39, marginBottom=0.45, marginLeft=0.43, marginRight=0.43)
        out.write_bytes(base64.b64decode(r["data"]))


def main():
    hp = ROOT / "tools" / "english_sovereign.html"
    hp.write_text(build(), encoding="utf-8")
    out = ROOT / "Mitra_English_Sovereign_Models_and_Costs.pdf"
    asyncio.run(pdf(hp, out))
    import pymupdf
    d = pymupdf.open(out)
    print("pages", len(d), "size", out.stat().st_size)
    for i, p in enumerate(d):
        print(f"page {i + 1}: {len(p.get_text())} chars")


if __name__ == "__main__":
    main()
