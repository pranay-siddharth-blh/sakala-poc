"""ಸಲ್ಲಿಸಿ (submit) said on a Kannada live session after a letter was read: what the model calls, and whether the relay's net files it."""
import asyncio, base64, json, time, urllib.request, websockets
B = "http://localhost:8030"
def post(p, d):
    r = urllib.request.Request(B + p, data=json.dumps(d).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=180).read())
async def main():
    sid = post("/api/session", {"profile": "citizen", "officer": "", "lang": "kn"})["session"]
    ev = []
    async with websockets.connect(f"ws://localhost:8030/ws/live?session={sid}", max_size=None) as ws:
        async def rd():
            try:
                async for m in ws:
                    if isinstance(m, str): ev.append(json.loads(m))
            except Exception: pass
        t = asyncio.create_task(rd())
        for _ in range(100):
            if any(e.get("type") == "ready" for e in ev): break
            await asyncio.sleep(0.1)
        b = base64.b64encode(open(r"D:\Sakala POC\tools\tests\letters\l1_kodigenahalli_water.jpeg", "rb").read()).decode()
        r = post("/api/document", {"session": sid, "file_b64": b, "media_type": "image/jpeg", "filename": "l1.jpeg", "want_audio": False})
        print("doc say:", r["say"][:80])
        import sys
        if "--race" in sys.argv:     # the browser's read-out of the document reply, and 'submit' said while it is still being read
            await ws.send(json.dumps({"type": "text", "system": True, "text": "(Say this to the person now, in casual spoken Kannada, keeping every id, name, place, number and date exactly, then stop. Call no function.) " + r["say"]}))
            await asyncio.sleep(float(sys.argv[sys.argv.index("--race") + 1]) if len(sys.argv) > sys.argv.index("--race") + 1 else 2.5)
        n = len(ev); t0 = time.time()
        await ws.send(json.dumps({"type": "text", "text": "ಸಲ್ಲಿಸಿ"}))
        for _ in range(400):
            await asyncio.sleep(0.1)
            tcs = [e for e in ev[n:] if e.get("type") == "turn_complete"]
            if len(tcs) >= 2 or (tcs and "confirm" not in json.dumps(ev[n:])) and time.time() - t0 > 20: break
        print(f"({time.time()-t0:.1f}s)")
        for e in ev[n:]:
            if e.get("type") in ("tool", "turn_complete", "reconfigure"):
                print("  ", e.get("type"), e.get("name", ""), "auto" if e.get("auto") else "", "intent=" + str(e.get("intent", "")), "|", (e.get("say") or e.get("mitra") or "")[:100])
        t.cancel()
asyncio.run(main())
