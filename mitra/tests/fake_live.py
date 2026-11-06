"""A local stand-in for Gemini Live (same wire protocol: setup / clientContent / realtimeInput / toolCall / toolResponse /
serverContent with audio, transcripts, interrupted, turnComplete), so the duplex relay and the browser can be built and
tested offline without spending credits. The "model" is Mitra's own rules brain: it picks a declared function, waits for
the tool response and speaks its `say` (as transcript + quiet PCM audio). Text that starts with "[voice] " is treated as
speech (an inputTranscription is sent first). Any new input while it is speaking interrupts it.

Run: python tests/fake_live.py [port]     (default 8099)   then start Mitra with MITRA_LIVE_URL=ws://127.0.0.1:8099"""
import asyncio
import base64
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import websockets  # noqa: E402

from server import brain  # noqa: E402

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8099
FAIL = "--fail" in sys.argv          # behave like a quota error: refuse the session


def pcm(seconds: float) -> bytes:
    n = int(24000 * seconds)
    return b"".join(int(800 * math.sin(i / 12)).to_bytes(2, "little", signed=True) for i in range(n))


async def handler(ws):
    raw = json.loads(await ws.recv())
    if FAIL:
        await ws.close(1011, "RESOURCE_EXHAUSTED: quota")
        return
    st = raw["setup"]
    fns = {d["name"] for d in st["tools"][0]["functionDeclarations"]}
    instr = st["systemInstruction"]["parts"][0]["text"]
    prof = re.search(r"PROFILE: (\w+)", instr).group(1)
    m = re.search(r"Current screen context: (\{.*\})", instr)
    state = {"context": json.loads(m.group(1)) if m else {}, "speaking": None, "tool": None}
    await ws.send(json.dumps({"setupComplete": {}}))

    async def speak(text: str):
        try:
            words = text.split()
            for i in range(0, len(words), 6):
                part = " ".join(words[i:i + 6]) + " "
                await ws.send(json.dumps({"serverContent": {"outputTranscription": {"text": part}}}))
                chunk = pcm(0.25)
                await ws.send(json.dumps({"serverContent": {"modelTurn": {"parts": [{"inlineData": {"mimeType": "audio/pcm;rate=24000",
                                                                                                     "data": base64.b64encode(chunk).decode()}}]}}}))
                await asyncio.sleep(0.12)
            await ws.send(json.dumps({"serverContent": {"turnComplete": True}}))
        except asyncio.CancelledError:
            pass

    async def user_turn(text: str, spoken: bool):
        if state["speaking"] and not state["speaking"].done():
            state["speaking"].cancel()
            await ws.send(json.dumps({"serverContent": {"interrupted": True}}))
        if spoken:
            await ws.send(json.dumps({"serverContent": {"inputTranscription": {"text": text}}}))
        ctx = {"profile": prof, "context": state["context"], "options": [], "history": []}
        if text.startswith("(") and "then stop" in text[:200]:   # a line Mitra asks the model to read out (a notification, a document reply): say it, never act on it
            state["speaking"] = asyncio.create_task(speak(text.split(")", 1)[-1].strip()))
            return
        # test directives (26 Oct): imitate the real model's bad days. '!!repeat N <text>' calls the function N times with
        # slightly different arguments before speaking (what Gemini did in the demo); '!!twice <text>' calls statewide_stats
        # first, then the right function; '!!silent on' makes the NEXT turn call nothing and just say 'Okay.' (the harness must act).
        repeat, twice = 1, False
        if state.pop("silent", False):
            state["speaking"] = asyncio.create_task(speak("Okay."))
            return
        if text.strip() == "!!silent on":
            state["silent"] = True
            state["speaking"] = asyncio.create_task(speak("Okay."))
            return
        mr = re.match(r"!!repeat (\d+)\s+", text)
        if mr:
            repeat, text = int(mr.group(1)), text[mr.end():]
        if text.startswith("!!twice "):
            twice, text = True, text[8:]
        dec = brain.rules(ctx, text)
        name = dec.pop("intent", "smalltalk")
        if name in ("ask_data", "summary", "tracker", "smalltalk") and prof in ("cs", "officer"):
            from server import tools as _tools        # like the real model: a data question goes straight to its data function
            if not _tools._boot.get("geo"):
                try:
                    import urllib.request as _u
                    _tools._boot.update(json.loads(_u.urlopen("http://localhost:8020/api/bootstrap", timeout=30).read()))
                except Exception:
                    pass
            rt = _tools.route_question(text, prof, {"scope": (state["context"] or {}).get("scope") or {}})
            if rt and rt[0] in fns:
                name, dec = rt[0], dict(rt[1])
        if name not in fns:
            say = "I can help with Sakala cases and data. What would you like to do?"
        else:
            calls = ([("statewide_stats", {})] if twice and "statewide_stats" in fns else []) + [(name, {**dec, **({"limit": 8 + i} if i else {})}) for i in range(repeat)]
            say = "Done."
            for i, (nm, ar) in enumerate(calls):
                fut = asyncio.get_event_loop().create_future()
                state["tool"] = fut
                await ws.send(json.dumps({"toolCall": {"functionCalls": [{"id": f"fc{i + 1}", "name": nm, "args": ar}]}}))
                await ws.send(json.dumps({"serverContent": {"turnComplete": True}}))     # like Gemini: the tool-call turn ends first
                resp = await asyncio.wait_for(fut, 60)
                r = resp["functionResponses"][0]["response"]
                state["context"] = r.get("context") or state["context"]
                say = r.get("say") or "Done."
                if len(calls) > 1:
                    await asyncio.sleep(0.25)
        state["speaking"] = asyncio.create_task(speak(say))

    async for raw in ws:
        msg = json.loads(raw)
        if "toolResponse" in msg and state["tool"]:
            state["tool"].set_result(msg["toolResponse"])
        elif "clientContent" in msg:
            text = "".join(p.get("text", "") for t in msg["clientContent"]["turns"] for p in t["parts"])
            spoken = text.startswith("[voice] ")
            asyncio.create_task(user_turn(text[8:] if spoken else text, spoken))
        elif "realtimeInput" in msg:
            a = msg["realtimeInput"].get("audio")
            if a and state["speaking"] and not state["speaking"].done():
                b = base64.b64decode(a["data"])
                loud = max((abs(int.from_bytes(b[i:i + 2], "little", signed=True)) for i in range(0, len(b) - 1, 64)), default=0)
                if loud > 4000:                       # someone talks over it: barge-in
                    state["speaking"].cancel()
                    await ws.send(json.dumps({"serverContent": {"interrupted": True}}))


async def main():
    async with websockets.serve(handler, "127.0.0.1", PORT, max_size=None):
        print(f"fake Live on ws://127.0.0.1:{PORT}{' (failing)' if FAIL else ''}", flush=True)
        await asyncio.Future()


asyncio.run(main())
