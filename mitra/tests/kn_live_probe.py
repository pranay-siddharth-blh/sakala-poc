"""Kannada on the live voice model (22 Oct 2026): does it hear Kannada (audio in), call the right function with the Kannada
words intact, and answer in spoken Kannada (Kannada script in the output transcript), and how fast?
Run from mitra/: PYTHONIOENCODING=utf-8 python tests/kn_live_probe.py"""
import asyncio
import base64
import io
import json
import sys
import time
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import websockets  # noqa: E402

from server import config, live, speech  # noqa: E402

URL = live.LIVE_URL + f"?key={config.GEMINI_API_KEY}"
KN = lambda s: sum(1 for ch in s if "ಀ" <= ch <= "೿")
OUT = Path(__file__).resolve().parent / "kn_clips"
OUT.mkdir(exist_ok=True)

PERSONA = ("You are Mitra, the Kannada voice assistant of the Government of Karnataka's grievance system (Sakala / iPGRS). "
           "Speak ONLY natural, warm, spoken Kannada (Kannada script), short sentences, like a helpful person at the taluk office. "
           "Keep ids, numbers and official names exact. You act only through the functions. When a citizen describes a problem, "
           "call chat_text with their words exactly as said (Kannada as Kannada). When a function returns, tell the person its `say` in Kannada.")
DECLS = [{"name": "chat_text", "description": "A citizen describes a problem or answers a question.", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
         {"name": "find_cases", "description": "Count / list grievances with filters.", "parameters": {"type": "object", "properties": {"taluk": {"type": "string"}, "status": {"type": "string"}, "department": {"type": "string"}}}}]


def setup(voice):
    return {"setup": {"model": f"models/{live.LIVE_MODEL}",
                      "generationConfig": {"responseModalities": ["AUDIO"], "temperature": 0.6,
                                           "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}, "languageCode": "kn-IN"}},
                      "systemInstruction": {"parts": [{"text": PERSONA}]}, "tools": [{"functionDeclarations": DECLS}],
                      "realtimeInputConfig": {"automaticActivityDetection": {"silenceDurationMs": 700, "prefixPaddingMs": 200}},
                      "inputAudioTranscription": {}, "outputAudioTranscription": {}}}


async def turn(ws, send, say_back):
    t0 = time.time(); first_audio = None; tool = None; outx = ""; inx = ""; audio = bytearray(); t_tool = None
    await send()
    while True:
        try:
            m = json.loads(await asyncio.wait_for(ws.recv(), 40))
        except asyncio.TimeoutError:
            break
        if "toolCall" in m:
            fc = m["toolCall"]["functionCalls"][0]; tool = fc; t_tool = time.time() - t0
            await ws.send(json.dumps({"toolResponse": {"functionResponses": [{"id": fc["id"], "name": fc["name"], "response": {"say": say_back}}]}}))
            continue
        sc = m.get("serverContent") or {}
        if "inputTranscription" in sc:
            inx += sc["inputTranscription"].get("text", "")
        if "outputTranscription" in sc:
            outx += sc["outputTranscription"].get("text", "")
        for p in (sc.get("modelTurn") or {}).get("parts", []):
            if "inlineData" in p:
                if first_audio is None:
                    first_audio = time.time() - t0
                audio += base64.b64decode(p["inlineData"]["data"])
        if sc.get("turnComplete") and (tool is None or outx):
            break
    return {"tool": tool and {"name": tool["name"], "args": tool.get("args")}, "t_tool": t_tool and round(t_tool, 2), "first_audio": first_audio and round(first_audio, 2),
            "in": inx[:120], "out": outx[:200], "kn_out": KN(outx), "audio_s": round(len(audio) / 48000, 1)}, bytes(audio)


def wav16k(raw24: bytes) -> bytes:
    import numpy as np
    a = np.frombuffer(raw24, dtype=np.int16).astype(np.float32)
    idx = np.arange(0, len(a), 1.5)
    b = np.interp(idx, np.arange(len(a)), a).astype(np.int16)
    return b.tobytes()


async def main(voice="Kore"):
    print("== voice", voice)
    async with websockets.connect(URL, max_size=None) as ws:
        t = time.time(); await ws.send(json.dumps(setup(voice))); r = json.loads(await ws.recv()); print("setup", round(time.time() - t, 2), list(r)[:1])
        # 1. Kannada text in -> function args in Kannada -> Kannada speech out
        r1, a1 = await turn(ws, lambda: ws.send(json.dumps({"clientContent": {"turns": [{"role": "user", "parts": [{"text": "ನಮ್ಮ ಗೊರಹಳ್ಳಿ ಗ್ರಾಮದಲ್ಲಿ ಒಂದು ವಾರದಿಂದ ಕುಡಿಯುವ ನೀರು ಬರುತ್ತಿಲ್ಲ"}]}], "turnComplete": True}})),
                            "ಇದು ಕುಡಿಯುವ ನೀರು ಪೂರೈಕೆ ಸಮಸ್ಯೆ, ಗ್ರಾಮೀಣಾಭಿವೃದ್ಧಿ ಇಲಾಖೆ. ಚಪ್ಪರದಹಳ್ಳಿ ಗ್ರಾಮ ಪಂಚಾಯಿತಿ, ಪಿರಿಯಾಪಟ್ಟಣ. ದಾಖಲಿಸಲೇ?")
        print("text-in ", json.dumps(r1, ensure_ascii=False))
        (OUT / f"reply_{voice}.pcm").write_bytes(a1)
    # 2. Kannada AUDIO in: use Mitra's own Kannada TTS to make a clip, then stream it at 16 kHz
    wav, prov = await speech.tts("ಹುಣಸೂರು ತಾಲ್ಲೂಕಿನಲ್ಲಿ ಎಷ್ಟು ದೂರುಗಳು ಬಾಕಿ ಇವೆ?", "kn")
    print("tts clip:", prov, len(wav or b""))
    if wav:
        with wave.open(io.BytesIO(wav)) as w:
            sr = w.getframerate(); raw = w.readframes(w.getnframes())
        pcm16 = wav16k(raw) if sr == 24000 else raw
        async with websockets.connect(URL, max_size=None) as ws:
            await ws.send(json.dumps(setup(voice))); await ws.recv()

            async def send_audio():
                for i in range(0, len(pcm16), 3200):
                    await ws.send(json.dumps({"realtimeInput": {"audio": {"data": base64.b64encode(pcm16[i:i + 3200]).decode(), "mimeType": "audio/pcm;rate=16000"}}}))
                    await asyncio.sleep(0.1)
                silence = b"\x00" * 3200
                for _ in range(12):
                    await ws.send(json.dumps({"realtimeInput": {"audio": {"data": base64.b64encode(silence).decode(), "mimeType": "audio/pcm;rate=16000"}}}))
                    await asyncio.sleep(0.1)
            r2, a2 = await turn(ws, send_audio, "ಹುಣಸೂರು ತಾಲ್ಲೂಕಿನಲ್ಲಿ 42 ದೂರುಗಳು ಬಾಕಿ ಇವೆ.")
            print("audio-in", json.dumps(r2, ensure_ascii=False))


asyncio.run(main(*(sys.argv[1:] or ["Kore"])))
