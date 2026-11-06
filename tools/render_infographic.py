"""Renders tools/sovereign_infographic.html to 'Sovereign Native Voice Architecture Infographic.png' (device scale 2)
in the project root with headless Edge over the DevTools protocol. Reports overflow. Run: python tools/render_infographic.py"""
import asyncio
import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "mitra" / "tests"))
W, H = 1800, 1180


async def main():
    from cdp import Browser
    src = ROOT / "tools" / "sovereign_infographic.html"
    async with Browser(port=9496, size=(W, H)) as b:
        await b.cmd("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=2, mobile=False)
        await b.goto(src.resolve().as_uri(), 3)
        info = await b.eval("""(() => {
            const over = [...document.querySelectorAll('.panel,.box,.tile,.tl,.f,.main,.page')]
              .filter(e => e.scrollHeight > e.clientHeight + 1 || e.scrollWidth > e.clientWidth + 1)
              .map(e => (e.querySelector('h2,h4,b')?.textContent || e.className).slice(0, 36) + ` (${e.scrollHeight}>${e.clientHeight})`);
            const main = document.querySelector('.main').getBoundingClientRect();
            return {docH: document.documentElement.scrollHeight, mainBottom: Math.round(main.bottom), over};
        })()""")
        print(info)
        r = await b.cmd("Page.captureScreenshot", format="png", clip={"x": 0, "y": 0, "width": W, "height": H, "scale": 1})
        out = ROOT / "Sovereign Native Voice Architecture Infographic.png"
        out.write_bytes(base64.b64decode(r["data"]))
        print("wrote", out.name, out.stat().st_size, "bytes")


if __name__ == "__main__":
    asyncio.run(main())
