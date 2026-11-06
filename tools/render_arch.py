"""Renders tools/arch_technical.html to Sakala_AI_POC_Technical_Architecture.png (device scale 2 → 3200 px wide) and .pdf
in the project root, with headless Edge over the DevTools protocol (mitra/tests/cdp.py). Checks that no card overflows.
Run: python tools/render_arch.py"""
import asyncio
import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "mitra" / "tests"))
W, H = 1600, 1510          # CSS px of the page (keep in step with .page in arch_technical.html)


async def main():
    from cdp import Browser
    src = ROOT / "tools" / "arch_technical.html"
    async with Browser(port=9497, size=(W, H)) as b:
        await b.cmd("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=2, mobile=False)
        await b.goto(src.resolve().as_uri(), 3)
        info = await b.eval("""(() => {
            const page = document.querySelector('.page');
            const over = [...document.querySelectorAll('.card,.pb,.panel,.stat')].filter(e => e.scrollHeight > e.clientHeight + 1 || e.scrollWidth > e.clientWidth + 1)
                .map(e => (e.querySelector('h4,.ph')?.textContent || e.className).slice(0, 40));
            return {w: document.documentElement.scrollWidth, h: document.documentElement.scrollHeight, page: page && page.getBoundingClientRect().height, over};
        })()""")
        print("page", info)
        if info["over"]:
            print("OVERFLOW in:", info["over"])
        r = await b.cmd("Page.captureScreenshot", format="png", captureBeyondViewport=True,
                        clip={"x": 0, "y": 0, "width": W, "height": max(H, int(info["h"])), "scale": 1})
        png = ROOT / "Sakala_AI_POC_Technical_Architecture.png"
        png.write_bytes(base64.b64decode(r["data"]))
        # one PDF page the exact size of the rendered page (the CSS @page rule is replaced by the measured height)
        ph = max(H, int(info["h"]) + 4)
        await b.eval(f"document.head.insertAdjacentHTML('beforeend', '<style>@page {{ size: {W}px {ph}px; margin: 0 }}</style>'); true")
        r = await b.cmd("Page.printToPDF", printBackground=True, preferCSSPageSize=True, marginTop=0, marginBottom=0, marginLeft=0, marginRight=0, scale=1)
        pdf = ROOT / "Sakala_AI_POC_Technical_Architecture.pdf"
        pdf.write_bytes(base64.b64decode(r["data"]))
        import pymupdf                       # a sub-pixel spill can add a blank trailing page: drop it
        d = pymupdf.open(pdf)
        while len(d) > 1 and not d[-1].get_text().strip():
            d.delete_page(len(d) - 1)
        if len(d) == 1:
            d.save(str(pdf) + ".tmp"); d.close(); Path(str(pdf) + ".tmp").replace(pdf)
        else:
            print("PDF has", len(d), "pages with text; left as printed"); d.close()
        print("wrote", png.name, png.stat().st_size, "bytes;", pdf.name, pdf.stat().st_size, "bytes")


if __name__ == "__main__":
    asyncio.run(main())
