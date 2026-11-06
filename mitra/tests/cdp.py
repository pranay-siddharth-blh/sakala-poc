"""A tiny real-time browser driver over the Chrome DevTools Protocol (headless Edge), for UI tests that involve live
WebSockets (where --virtual-time-budget races ahead of the network). No extra packages: websockets + urllib only.

    async with Browser() as b:
        await b.goto(url)
        result = await b.eval("(async () => { ...; return {...} })()")   # awaited, JSON-serialisable result
        await b.shot("out.png")
"""
import asyncio
import base64
import json
import subprocess
import time
import urllib.request
from pathlib import Path

import websockets

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


class Browser:
    def __init__(self, port=9333, size=(1536, 864), gpu=False):
        self.port, self.size, self.id, self.gpu = port, size, 0, gpu

    async def __aenter__(self):
        prof = Path.home() / "AppData/Local/Temp" / f"jv_cdp_{self.port}"
        self.proc = subprocess.Popen([EDGE, "--headless=new"] + ([] if self.gpu else ["--disable-gpu"]) + ["--no-first-run", "--hide-scrollbars", "--mute-audio",
                                      "--autoplay-policy=no-user-gesture-required", f"--window-size={self.size[0]},{self.size[1]}",
                                      f"--remote-debugging-port={self.port}", f"--user-data-dir={prof}", "about:blank"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        url = None
        for _ in range(60):
            try:
                tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json", timeout=2).read())
                url = next(t["webSocketDebuggerUrl"] for t in tabs if t.get("type") == "page")
                break
            except Exception:
                time.sleep(0.25)
        self.ws = await websockets.connect(url, max_size=None)
        self.events = []
        await self.cmd("Page.enable"); await self.cmd("Runtime.enable")
        # silence: Windows speaks speechSynthesis through the OS voice even with --mute-audio, so the tests must never speak aloud
        await self.cmd("Page.addScriptToEvaluateOnNewDocument", source=(
            "try{const ss=window.speechSynthesis;if(ss){ss.speak=function(u){setTimeout(()=>{try{u.onstart&&u.onstart({});u.onend&&u.onend({})}catch(e){}},30)};"
            "ss.cancel=function(){};}}catch(e){}"))
        return self

    async def __aexit__(self, *a):
        try:
            await self.ws.close()
        finally:
            self.proc.kill()

    async def cmd(self, method, **params):
        self.id += 1
        mid = self.id
        await self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            m = json.loads(await self.ws.recv())
            if m.get("id") == mid:
                if "error" in m:
                    raise RuntimeError(m["error"])
                return m.get("result", {})
            if m.get("method") == "Runtime.exceptionThrown":
                d = m["params"]["exceptionDetails"]
                self.events.append(("exception", (d.get("exception") or {}).get("description") or d.get("text")))
            elif m.get("method") == "Runtime.consoleAPICalled" and m["params"]["type"] == "error":
                self.events.append(("console", " ".join(str(a.get("value", a.get("description", ""))) for a in m["params"]["args"])))

    async def goto(self, url, wait=2.5):
        await self.cmd("Page.navigate", url=url)
        await asyncio.sleep(wait)

    async def eval(self, expr, timeout=180):
        r = await asyncio.wait_for(self.cmd("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True), timeout)
        if r.get("exceptionDetails"):
            raise RuntimeError((r["exceptionDetails"].get("exception") or {}).get("description") or r["exceptionDetails"].get("text"))
        return (r.get("result") or {}).get("value")

    async def shot(self, path):
        r = await self.cmd("Page.captureScreenshot", format="png")
        Path(path).write_bytes(base64.b64decode(r["data"]))
