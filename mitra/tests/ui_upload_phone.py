"""22 Oct 2026: the document door reachable in the PHONE app and by voice, and the product called plain "Mitra".
Phone (393x852, test instance 8031): the paperclip in the composer is visible for a citizen and hidden for the officer / CS;
"I want to upload a letter" (typed, same path as voice) -> upload_document -> the sheet rises to the request card, the drop
zone is on screen and lit; the letter chosen there is read into the form; the paperclip opens the picker (the click reaches the
file input). Web: the same sentence lights the drop zone. Rename sweep: no "Sakala Mitra" / "Sakala AI" anywhere in the served
pages, the visible text of the three desks (web + phone) or the splash; the splash title is "Mitra".
Usage: python tests/ui_upload_phone.py"""
import asyncio
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp import Browser  # noqa: E402

M = "http://localhost:8031"
LET = Path(__file__).resolve().parents[2] / "tools" / "tests" / "letters"
L1 = str(LET / "l1_kodigenahalli_water.jpeg")
TMP = Path(r"C:\Users\hp\AppData\Local\Temp")
ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1; print("  PASS", name)
    else:
        fail += 1; print("  FAIL", name, " <-", str(detail)[:400])


HELP = "window.sleep=ms=>new Promise(r=>setTimeout(r,ms));window.until=async(f,ms=30000)=>{const t=Date.now();while(Date.now()-t<ms){try{if(f())return true}catch(e){}await sleep(100)}return false};"
VIS = "(el)=>{if(!el)return false;const r=el.getBoundingClientRect();const cs=getComputedStyle(el);return r.width>0&&r.height>0&&cs.visibility!=='hidden'&&cs.display!=='none'&&+cs.opacity>.5&&r.top>=0&&r.bottom<=innerHeight+1}"


async def set_file(b, selector, path):
    doc = await b.cmd("DOM.getDocument", depth=-1, pierce=True)
    node = await b.cmd("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector=selector)
    await b.cmd("DOM.setFileInputFiles", files=[path], nodeId=node["nodeId"])


async def sweep(b, label):
    r = await b.eval(f"""(async()=>{{ const vis={VIS}; const bad=[]; const walk=(n)=>{{ for(const c of n.childNodes){{ if(c.nodeType===3){{ const t=c.textContent; if(/Sakala Mitra|Sakala AI/i.test(t) && vis(c.parentElement)) bad.push(t.trim().slice(0,60)); }} else if(c.nodeType===1 && !['SCRIPT','STYLE'].includes(c.tagName)) walk(c); }} }}; walk(document.body);
      const attrs=[...document.querySelectorAll('[title],[placeholder],[aria-label],[data-tip]')].flatMap(e=>['title','placeholder','aria-label','data-tip'].map(a=>e.getAttribute(a)||'')).filter(t=>/Sakala Mitra|Sakala AI/i.test(t));
      return {{bad, attrs, title:document.title}} }})()""", timeout=30)
    check(f"{label}: no 'Sakala Mitra' / 'Sakala AI' in visible text, tooltips or the tab title", not r["bad"] and not r["attrs"] and "Sakala" not in r["title"], r)


async def main():
    print("[served files]")
    hits = []
    for p in ("/", "/mitra.js?v=66", "/app.js", "/phone.js", "/portal.js", "/splash.js", "/mitra.css?v=64"):
        t = urllib.request.urlopen(M + p, timeout=30).read().decode("utf-8", "ignore")
        for m in __import__("re").finditer(r"Sakala Mitra|Sakala AI", t):
            line = t[max(0, m.start() - 40): m.end() + 40].replace("\n", " ")
            if not line.lstrip().startswith(("/*", "//", "*")):
                hits.append((p, line))
    check("no 'Sakala Mitra' / 'Sakala AI' in the served page and scripts (comments aside)", not hits, hits[:4])

    print("[phone: paperclip + upload by voice]")
    async with Browser(port=9411, size=(393, 852), gpu=True) as b:
        await b.goto(f"{M}/?intro=0", 2); await b.eval("localStorage.clear(); sessionStorage.clear(); 1")      # a fresh session: no form left open by an earlier run
        await b.goto(f"{M}/?auto=1&noevents=1&livetest=1&p=citizen&app=1&intro=0", 4)
        await b.eval(HELP)
        r = await b.eval(f"""(async()=>{{ const vis={VIS}; await until(()=>J.sid && document.querySelector('#attach'), 20000); await sleep(600);
          const at=document.querySelector('#attach'); const rc=at.getBoundingClientRect(); const comp=document.querySelector('.composer').getBoundingClientRect();
          return {{vis:vis(at), hidden:at.hidden, inComposer: rc.top>=comp.top-1 && rc.bottom<=comp.bottom+1, sheet:document.body.dataset.sheet, title:at.title,
                   brand:(document.querySelector('.brand-t b')||{{}}).innerText||'', sub:(document.querySelector('#profSub')||{{}}).textContent||''}} }})()""", timeout=60)
        check("citizen: the paperclip sits in the composer at the thumb, visible; header reads 'Mitra'", r["vis"] and not r["hidden"] and r["inComposer"] and r["brand"].strip() == "Mitra" and r["sub"].startswith("Mitra"), r)
        await sweep(b, "phone citizen")
        await b.shot(TMP / "up_phone_idle.png")
        r = await b.eval(f"""(async()=>{{ const vis={VIS}; const n=J.convo.length; document.querySelector('#text').value='I want to upload a letter'; document.querySelector('#send').click();
          await until(()=>J.convo.length>n, 60000); await sleep(900);
          const dz=document.querySelector('#dropz'); const last=J.convo.slice(-1)[0]||{{}};
          return {{say:last.say||'', intent:last.intent||'', sheet:document.body.dataset.sheet, tab:(document.querySelector('.msheet')||{{}}).dataset?.t, dz:!!dz, dzVis:vis(dz), pulse:dz?dz.classList.contains('lit'):false,
                   stage0:(document.querySelector('#right .pipe .step .d, #right .pipe .step')||{{}}).innerText||''}} }})()""", timeout=90)
        check("'I want to upload a letter' -> upload_document: the sheet rises to the request card, the drop zone is on screen and lit, Mitra says to tap it",
              r["intent"] == "upload_document" and r["sheet"] in ("half", "full") and r["tab"] == "left" and r["dz"] and r["dzVis"] and r["pulse"] and "upload" in r["say"].lower(), r)
        await b.shot(TMP / "up_phone_voice.png")
        # the paperclip: a real click reaches the file input (the picker itself cannot open headless; we watch the input's click)
        r = await b.eval("""(async()=>{ const inp=document.querySelector('#reqFile'); let hit=0; inp.addEventListener('click', e=>{ hit++; e.preventDefault(); }); document.querySelector('#attach').click(); await sleep(100); return {hit} })()""")
        check("the paperclip opens the file picker (the click reaches the file input)", r["hit"] == 1, r)
        await set_file(b, "#reqFile", L1)
        r = await b.eval("""(async()=>{ const res={}; res.form=await until(()=>document.querySelector('.docrev'), 150000); await sleep(800);
          const v=k=>{const e=document.querySelector(`.docrev [data-k="${k}"]`); return e?e.value:null}; res.name=v('name'); res.gid=v('grievance_id');
          res.meta=(document.querySelector('.docrev .dmeta')||{}).innerText||''; res.sheet=document.body.dataset.sheet; return res })()""", timeout=200)
        check("the letter chosen in the phone is read into the form (name, iPGRS number, 'read by Mitra')", r["form"] and "Narasimhaiah" in (r["name"] or "") and r["gid"] == "502806" and "read by Mitra" in r["meta"] and "Sakala" not in r["meta"], r)
        await b.shot(TMP / "up_phone_form.png")
        check("phone: no JS exceptions", not [e for e in b.events if e[0] == "exception"], b.events[:3])

    print("[phone: officer and CS have no paperclip; names read 'Mitra']")
    for prof in ("officer", "cs"):
        async with Browser(port=9412, size=(393, 852), gpu=True) as b:
            await b.goto(f"{M}/?auto=1&noevents=1&livetest=1&p={prof}&app=1&intro=0", 4)
            await b.eval(HELP)
            r = await b.eval(f"""(async()=>{{ const vis={VIS}; await until(()=>J.sid, 20000); await sleep(800); const at=document.querySelector('#attach'); return {{hidden:at?at.hidden:true, vis:vis(at)}} }})()""", timeout=60)
            check(f"{prof}: no paperclip", r["hidden"] and not r["vis"], r)
            await sweep(b, f"phone {prof}")

    print("[web: upload by voice lights the drop zone; splash and desks say 'Mitra']")
    async with Browser(port=9413, size=(1536, 864), gpu=True) as b:
        await b.goto(f"{M}/?intro=0&p=citizen&noevents=1&livetest=1", 3)
        await b.eval(HELP)
        r = await b.eval("""(async()=>{ await sleep(800); const t=document.querySelector('#spTitle'); return {title:(t||{}).innerText||'', letters:document.querySelectorAll('#spTitle .ch').length} })()""", timeout=30)
        check("the splash title is 'Mitra' (5 letters, no 'Sakala')", r["title"].replace(" ", "") == "Mitra" and r["letters"] == 5, r)
        await b.goto(f"{M}/?auto=1&noevents=1&livetest=1&p=citizen", 4)
        await b.eval(HELP)
        r = await b.eval(f"""(async()=>{{ const vis={VIS}; await until(()=>J.sid && document.querySelector('#dropz'), 20000); const n=J.convo.length;
          document.querySelector('#text').value='can I attach my written complaint?'; document.querySelector('#send').click(); await until(()=>J.convo.length>n, 60000); await sleep(700);
          const dz=document.querySelector('#dropz'); const last=J.convo.slice(-1)[0]||{{}}; const at=document.querySelector('#attach');
          return {{intent:last.intent||'', say:last.say||'', pulse:dz.classList.contains('lit'), dzVis:vis(dz), attach:vis(at), pill:(document.querySelector('#statusText')||{{}}).textContent||''}} }})()""", timeout=90)
        check("web: 'can I attach my written complaint?' -> upload_document, the drop zone lit, the paperclip present, the status pill says Mitra",
              r["intent"] == "upload_document" and r["pulse"] and r["dzVis"] and r["attach"] and r["pill"].startswith("Mitra"), r)
        await sweep(b, "web citizen")
        for prof in ("officer", "cs"):
            await b.eval(f"switchTo('{prof}')")
            await b.eval("""(async()=>{ await until(()=>!Portal.busy, 15000); await sleep(600); return true })()""", timeout=30)
            await sweep(b, f"web {prof}")
        await b.shot(TMP / "up_web_voice.png")
        check("web: no JS exceptions", not [e for e in b.events if e[0] == "exception"], b.events[:3])
    print(f"\n{ok} passed, {fail} failed")
    sys.exit(1 if fail else 0)


asyncio.run(main())
