"""One short Gemini Live probe (keeps credit use small): setup -> spoken reply -> function call -> audio input ->
interruption. Prints message shapes and timings, never the key. Run from mitra/: python tests/live_probe.py"""
import asyncio
import base64
import json
import sys
import time
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import config  # noqa: E402

import websockets  # noqa: E402

MODEL = config.get("GEMINI_LIVE_MODEL") or "gemini-3.8-live"
URL = ("wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key="
       + config.GEMINI_API_KEY)
WAV = Path(__file__).resolve().parents[2] / "tools" / "tests" / "asr_test.wav"


def shape(m: dict) -> str:
    def walk(o, d=0):
        if isinstance(o, dict) and d < 3:
            return {k: walk(v, d + 1) for k, v in o.items() if k != "data"}
        if isinstance(o, list):
            return [walk(o[0], d + 1)] if o else []
        return type(o).__name__ if not isinstance(o, (str, bool)) or len(str(o)) > 60 else o
    return json.dumps(walk(m))[:400]


async def collect(ws, label, t0, until=("turnComplete",), limit=25.0, on_tool=None):
    audio = 0; first = None; out_tx = []; in_tx = []; seen = set(); interrupted = False
    while True:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=limit)
        except asyncio.TimeoutError:
            print(f"  [{label}] timeout"); break
        m = json.loads(raw)
        for k in m:
            if k not in seen:
                seen.add(k); print(f"  [{label}] msg: {shape(m)}")
        if "toolCall" in m and on_tool:
            await on_tool(m["toolCall"])
        sc = m.get("serverContent") or {}
        for p in (sc.get("modelTurn") or {}).get("parts", []):
            if "inlineData" in p:
                audio += len(base64.b64decode(p["inlineData"]["data"]))
                first = first or time.time() - t0
        if sc.get("outputTranscription"):
            out_tx.append(sc["outputTranscription"].get("text", ""))
        if sc.get("inputTranscription"):
            in_tx.append(sc["inputTranscription"].get("text", ""))
        if sc.get("interrupted"):
            interrupted = True
        if any(sc.get(u) for u in until):
            break
    print(f"  [{label}] first audio {first and round(first, 2)}s, audio bytes {audio}, said: {''.join(out_tx)[:160]!r}, heard: {''.join(in_tx)[:120]!r}, interrupted={interrupted}")
    return interrupted


async def main():
    setup = {"setup": {
        "model": f"models/{MODEL}",
        "generationConfig": {"responseModalities": ["AUDIO"],
                             "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": config.get("GEMINI_VOICE") or "Kore"}}}},
        "systemInstruction": {"parts": [{"text": "You are Mitra, the voice of Sakala, Government of Karnataka. Be brief: one or two sentences."}]},
        "tools": [{"functionDeclarations": [{"name": "case_status", "description": "Status of a Sakala case by id.",
                                             "parameters": {"type": "OBJECT", "properties": {"case_id": {"type": "STRING"}}, "required": ["case_id"]}}]}],
        "inputAudioTranscription": {}, "outputAudioTranscription": {}}}
    t0 = time.time()
    async with websockets.connect(URL, max_size=None, open_timeout=15) as ws:
        await ws.send(json.dumps(setup))
        m = json.loads(await asyncio.wait_for(ws.recv(), 15))
        print(f"setup -> {shape(m)} in {time.time() - t0:.2f}s")

        t0 = time.time()
        await ws.send(json.dumps({"clientContent": {"turns": [{"role": "user", "parts": [{"text": "Hello, who are you?"}]}], "turnComplete": True}}))
        await collect(ws, "text->audio", t0)

        async def tool(tc):
            fc = tc["functionCalls"][0]
            print(f"  [tool] call {fc['name']} {fc.get('args')} after {time.time() - t1:.2f}s")
            await ws.send(json.dumps({"toolResponse": {"functionResponses": [{"id": fc.get("id"), "name": fc["name"],
                                      "response": {"status": "In progress", "officer": "PDO Attigodu", "days_left": 6}}]}}))
        t1 = time.time()
        await ws.send(json.dumps({"clientContent": {"turns": [{"role": "user", "parts": [{"text": "What is the status of GR-504227?"}]}], "turnComplete": True}}))
        await collect(ws, "function", t1, on_tool=tool)

        # audio in: the 16 kHz test clip in 100 ms chunks at real-time pace, then silence
        with wave.open(str(WAV)) as w:
            rate, pcm = w.getframerate(), w.readframes(w.getnframes())
        print(f"  clip: {rate} Hz, {len(pcm) / 2 / rate:.1f}s")
        step = rate // 10 * 2
        t2 = time.time()
        async def feed(data, pace=True):
            for i in range(0, len(data), step):
                await ws.send(json.dumps({"realtimeInput": {"audio": {"data": base64.b64encode(data[i:i + step]).decode(), "mimeType": f"audio/pcm;rate={rate}"}}}))
                if pace:
                    await asyncio.sleep(0.1)
        await feed(pcm + b"\0" * rate * 2 * 2)
        await collect(ws, "audio-in", t2)

        # interruption: ask for something long, then talk over it
        t3 = time.time()
        await ws.send(json.dumps({"clientContent": {"turns": [{"role": "user", "parts": [{"text": "Count slowly from one to thirty."}]}], "turnComplete": True}}))
        await asyncio.sleep(2.5)
        asyncio.create_task(feed(pcm))
        await collect(ws, "interrupt", t3, until=("turnComplete", "interrupted"))


asyncio.run(main())
