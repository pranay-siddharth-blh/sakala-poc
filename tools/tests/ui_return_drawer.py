"""POC officer drawer (web): 'Return · not my jurisdiction' with a suggestion (22 Oct 2026, Pranay). Headless Edge over CDP,
using Mitra's driver. Officer Tahsildar Piriyapatna opens a case, opens Return, types 'Tahsildar Hunsur': the button turns into
'Send to Tahsildar Hunsur' with the explanation, sending moves the case; typing nothing keeps 'Return to scrutiny desk';
typing an unknown name says the scrutiny desk will route it. Run from app/: python ../tools/tests/ui_return_drawer.py"""
import asyncio
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "mitra" / "tests"))
from cdp import Browser  # noqa: E402

B = "http://localhost:8020"
DB = ROOT / "app" / "data" / "sakala.db"
ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1; print("  PASS", name)
    else:
        fail += 1; print("  FAIL", name, " <-", str(detail)[:400])


def q1(sql, *a):
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    r = c.execute(sql, a).fetchone(); c.close()
    return dict(r) if r else None


JS = """(async()=>{ const sl=ms=>new Promise(r=>setTimeout(r,ms)); const res={};
  const until=async(f,ms)=>{ const t0=Date.now(); while(Date.now()-t0<ms){ try{ if(f()) return true; }catch(e){} await sl(100);} return false; };
  await until(()=>document.querySelector('#aReturn'), 15000);
  document.querySelector('#aReturn').click(); await until(()=>document.querySelector('#retS'), 3000);
  res.form = !!document.querySelector('#retS') && !!document.querySelector('#retP');
  res.btn0 = document.querySelector('#doRet').textContent;
  const type=(sel,v)=>{ const el=document.querySelector(sel); el.value=v; el.dispatchEvent(new Event('input')); };
  type('#retS','nobody in particular'); await sl(900); res.btnUnknown=document.querySelector('#doRet').textContent; res.hintUnknown=document.querySelector('#retHint').textContent;
  type('#retS','Tahsildar Hunsur'); await sl(900); res.btn=document.querySelector('#doRet').textContent; res.hint=document.querySelector('#retHint').textContent;
  document.querySelector('#doRet').click(); await sl(2500);
  res.toast=(document.querySelector('.toast')||{}).innerText||''; res.drawerOpen=!!document.querySelector('.drawer.open');
  return res })()"""


async def main():
    cid = q1("SELECT id FROM cases WHERE owner='tah_piriyapatna' AND status='Pending' AND kind='GRIEVANCE' ORDER BY id DESC LIMIT 1")["id"]
    print(f"[POC officer drawer · {cid}]")
    async with Browser(port=9461, size=(1536, 864), gpu=True) as b:
        await b.goto(f"{B}/?p=officer&off=tah_piriyapatna&open={cid}", 6)
        r = await b.eval(JS, timeout=60)
        check("the Return form has 'suggest the right officer' and 'or where it belongs'", r.get("form"), r)
        check("nothing typed -> 'Return to scrutiny desk'", r.get("btn0") == "Return to scrutiny desk", r.get("btn0"))
        check("an unknown name -> stays 'Return to scrutiny desk' and says the desk will route it",
              r.get("btnUnknown") == "Return to scrutiny desk" and "scrutiny desk will route" in (r.get("hintUnknown") or ""), r)
        check("'Tahsildar Hunsur' -> the button reads 'Send to Tahsildar Hunsur' with the reason", r.get("btn") == "Send to Tahsildar Hunsur" and "notified" in (r.get("hint") or ""), r)
        after = q1("SELECT owner, status FROM cases WHERE id=?", cid)
        check("sending moves the case to Tahsildar Hunsur (Pending)", after == {"owner": "tah_hunsur", "status": "Pending"}, after)
        check("toast says Transferred", "Transferred" in (r.get("toast") or "") or not r.get("drawerOpen"), r)
        await b.shot(Path(r"C:\Users\hp\AppData\Local\Temp") / "ui_return_drawer.png")
        check("no JS exceptions", not [e for e in b.events if e[0] == "exception"], b.events[:3])
    print(f"\n{ok} passed, {fail} failed")
    sys.exit(1 if fail else 0)


asyncio.run(main())
