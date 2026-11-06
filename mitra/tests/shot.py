"""Headless-Edge screenshot of the Mitra UI after a scripted voice turn (typed), for a visual check.
Usage: python tests/shot.py <profile> "<utterance>" <out.png>"""
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

B = "http://localhost:8030"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
profile, text, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])


def post(p, d):
    r = urllib.request.Request(B + p, data=json.dumps(d).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=180).read())


officer = {"citizen": "tah_piriyapatna", "officer": "tah_piriyapatna", "cs": ""}[profile]
s = post("/api/session", {"profile": profile, "officer": officer, "lang": "en"})
sid = s["session"]
for t in text.split("||"):
    r = post("/api/turn", {"session": sid, "text": t.strip(), "want_audio": False})
    print("  >", t.strip(), "->", r["intent"], "::", r["say"][:90])
# a page that restores this session, replays the UI ops and takes the shot
html = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
inject = f"""<script>
localStorage.setItem('jv_sid','{sid}');localStorage.setItem('jv_profile','{profile}');localStorage.setItem('jv_officer','{officer or 'tah_piriyapatna'}');
window.addEventListener('load',()=>{{setTimeout(async()=>{{
  J.sid='{sid}';J.profile='{profile}';J.officer='{officer or 'tah_piriyapatna'}';
  await session(false);
  const last={json.dumps(r.get('ui', []))};applyUi(last);captionYou({json.dumps(text.split('||')[-1].strip())});captionMitra({json.dumps(r['say'][:260])},0.01);setState('speaking','Mitra');
}},800)}});
</script>"""
tmp = Path(__file__).resolve().parents[1] / "web" / "shot.html"
tmp.write_text(html.replace("</body>", inject + "</body>"), encoding="utf-8")
tmp_out = Path(r"C:\Users\hp\AppData\Local\Temp\jv_shot.png")
subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars", "--window-size=1536,900",
                f"--user-data-dir={Path.home() / 'AppData/Local/Temp' / ('jv_edge_' + profile)}", "--virtual-time-budget=6000", "--timeout=20000",
                f"--screenshot={tmp_out}", f"{B}/shot.html?auto=1&noevents=1"], check=False, timeout=90)
time.sleep(0.5)
out.write_bytes(tmp_out.read_bytes())
tmp.unlink(missing_ok=True)
print("saved", out)
