"""Render the four launcher logos (icons/*.svg) to Windows .ico files (16-256 px, transparent corners).
Run from anywhere: python "D:\\Sakala POC\\launchers\\make_icons.py". Uses headless Edge through mitra/tests/cdp.py."""
import asyncio
import base64
import io
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "mitra" / "tests"))
from cdp import Browser  # noqa: E402

NAMES = ["mitra", "whatsapp_poc", "kpcl", "rdpr"]
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


async def main():
    async with Browser(port=9471, size=(512, 512)) as b:
        await b.cmd("Emulation.setDefaultBackgroundColorOverride", color={"r": 0, "g": 0, "b": 0, "a": 0})
        await b.cmd("Emulation.setDeviceMetricsOverride", width=512, height=512, deviceScaleFactor=1, mobile=False)
        for n in NAMES:
            svg = (HERE / "icons" / f"{n}.svg").read_text(encoding="utf-8")
            html = ("<!doctype html><html><head><style>html,body{margin:0;background:transparent;overflow:hidden}"
                    "svg{width:512px;height:512px;display:block}</style></head><body>" + svg + "</body></html>")
            await b.goto("data:text/html;base64," + base64.b64encode(html.encode()).decode(), 1.2)
            r = await b.cmd("Page.captureScreenshot", format="png", clip={"x": 0, "y": 0, "width": 512, "height": 512, "scale": 1})
            img = Image.open(io.BytesIO(base64.b64decode(r["data"]))).convert("RGBA")
            img.save(HERE / "icons" / f"{n}.png")
            img.save(HERE / "icons" / f"{n}.ico", sizes=SIZES)
            print(n, img.size, (HERE / "icons" / f"{n}.ico").stat().st_size, "bytes")


asyncio.run(main())
