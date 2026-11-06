"""The document door in the browsers, on the REAL handwritten letters (Pranay's WhatsApp photos, tools/tests/letters/).
Mitra (test instance 8031, fake Live): the drop zone on the request card, letter 1 (Kodigenahalli water, photographed sideways)
-> turned upright, read into the official form (fields, thumbnails, confidence dots, the quoted iPGRS record matched), a typed
edit, ONE Submit -> routed to the Kodigenahalli PDO, the case on the POC with src=document and the form. Same inside the phone.
Letter 2 (Chintamani scholarship, outside the pilot): the form stays, Submit sends it WITH the letter to the scrutiny desk.
The WhatsApp POC (8020): the "Upload a written complaint" tile -> modal -> form -> Submit (letter 1 registered; letter 3,
Kannada, municipal -> scrutiny desk) -> the cards in the chat and the 8 stages lit.
Usage: python tests/ui_docupload.py"""
import asyncio
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp import Browser  # noqa: E402

M = "http://localhost:8031"
POC = "http://localhost:8020"
LET = Path(__file__).resolve().parents[2] / "tools" / "tests" / "letters"
L1, L2, L3 = str(LET / "l1_kodigenahalli_water.jpeg"), str(LET / "l2_chintamani_ssp.jpeg"), str(LET / "l3_kannada_drain.jpeg")
TMP = Path(r"C:\Users\hp\AppData\Local\Temp")
ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1; print("  PASS", name)
    else:
        fail += 1; print("  FAIL", name, " <-", str(detail)[:400])


def poc(p):
    return json.loads(urllib.request.urlopen(POC + p, timeout=60).read())


HELP = "window.sleep=ms=>new Promise(r=>setTimeout(r,ms));window.until=async(f,ms=30000)=>{const t=Date.now();while(Date.now()-t<ms){try{if(f())return true}catch(e){}await sleep(100)}return false};"


async def set_file(b, selector, path):
    doc = await b.cmd("DOM.getDocument", depth=-1, pierce=True)
    node = await b.cmd("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector=selector)
    await b.cmd("DOM.setFileInputFiles", files=[path], nodeId=node["nodeId"])


READ_JS = """(async()=>{{ const W={win}; const d=W.document; const res={{}}; const t0=Date.now();
      res.reading=await until(()=>(d.querySelector('#dropz')||{{}}).className?.includes('busy') || d.querySelector('.docrev'), 10000);
      res.form=await until(()=>d.querySelector('.docrev'), 150000); res.secs=(Date.now()-t0)/1000; await sleep(1200);
      const v=k=>{{const e=d.querySelector(`.docrev [data-k="${{k}}"]`); return e?e.value:null}};
      res.fields={{name:v('name'), phone:v('phone'), village:v('village'), gp:v('gp'), taluk:v('taluk'), date:v('letter_date'), gid:v('grievance_id')}};
      res.thumbs=d.querySelectorAll('.docrev .dthumbs img').length; res.dots=d.querySelectorAll('.docrev .cdot.ok').length;
      const im=d.querySelector('.docrev .dthumbs img'); res.upright=im? (im.naturalHeight>im.naturalWidth):false;
      res.rec=(d.querySelector('.docrev .drec')||{{}}).innerText||''; res.meta=(d.querySelector('.docrev .dmeta')||{{}}).innerText||'';
      res.officer=(d.querySelector('.docrev .who .n')||{{}}).textContent||''; res.submit=(d.querySelector('#docSubmit')||{{}}).innerText||'';
      const rc=d.querySelector('.docrev').getBoundingClientRect(); res.fits=rc.left>=-1 && rc.right<=W.innerWidth+1;
      res.say=(W.eval('J.convo')||[]).slice(-1).map(x=>x.say||'')[0]||''; return res }})()"""


async def mitra_flow(b, label, win="window", sel="#reqFile"):
    r = await b.eval(f"""(async()=>{{ const W={win}; await until(()=>W.eval('!!J.sid') && W.document.querySelector('#dropz'), 20000);
      const dz=W.document.querySelector('#dropz'); const rc=dz.getBoundingClientRect(); return {{dz:!!dz, w:Math.round(rc.width), text:dz.innerText.slice(0,80)}} }})()""", timeout=60)
    check(f"{label}: the drop zone is on the request card", r["dz"] and "Upload a written complaint" in r["text"], r)
    await set_file(b, sel, L1)
    r = await b.eval(READ_JS.format(win=win), timeout=200)
    f = r["fields"]
    check(f"{label}: letter 1 read into the form in {r.get('secs', 0):.0f} s (name, date, village, taluk, iPGRS number; no phone invented)",
          r["form"] and "Narasimhaiah" in (f["name"] or "") and f["date"] == "2026-09-29" and f["village"] == "Kodigenahalli" and f["taluk"] == "Madhugiri" and f["gid"] == "502806" and not f["phone"], r)
    check(f"{label}: turned upright, the iPGRS record matched and shown, confidence dots, the Kodigenahalli PDO, one Submit, fits",
          r["upright"] and "turned upright" in r["meta"] and "502806" in r["rec"] and "Water" in r["rec"] and r["dots"] >= 5 and "Kodigenahalli" in r["officer"] and "Submit" in r["submit"] and r["fits"], r)
    check(f"{label}: Mitra says what she read, with the record", "read the letter" in r["say"].lower() and "narasimhaiah" in r["say"].lower() and "502806" in r["say"], r["say"])
    check(f"{label}: read within 25 s", r.get("secs", 99) < 25, r.get("secs"))
    await b.shot(TMP / f"doc_{label}_form.png")
    r = await b.eval(f"""(async()=>{{ const W={win}; const d=W.document; const res={{}};
      d.querySelector('.docrev [data-k="phone"]').value='NA'; d.querySelector('.docrev [data-k="complainant_address"]').value='Near the BSNL tower, Kodigenahalli';
      const n=W.eval('J.convo.length'); d.querySelector('#docSubmit').click();
      res.routed=await until(()=>d.querySelector('[data-id=routed]'), 60000); await until(()=>W.eval('J.convo.length')>n, 60000); await sleep(400);
      res.cid=((d.querySelector('[data-id=routed]')||{{}}).innerText||'').match(/GR-\\d+/)?.[0]; res.say=(W.eval('J.convo')||[]).slice(-1).map(x=>x.say||'')[0]||'';
      res.stages=[...d.querySelectorAll('#right .pipe .step.done')].length; return res }})()""", timeout=120)
    check(f"{label}: Submit files it (routed card, reference spoken)", r["routed"] and r["cid"] and r["cid"] in r["say"], r)
    if r.get("cid"):
        cj = poc(f"/api/case/{r['cid']}")
        d = cj.get("doc") or {}
        check(f"{label}: the case carries the form: src=document, NA phone = not provided, the typed address, the record, the transcript, the Kodigenahalli PDO",
              cj["src"] == "document" and d.get("phone") == "" and "phone" in (d.get("not_provided") or []) and d.get("complainant_address") == "Near the BSNL tower, Kodigenahalli"
              and d.get("record") == "502806" and len(d.get("transcript") or "") > 100 and "kodigenahalli" in (cj.get("owner") or "").lower(),
              {"src": cj.get("src"), "doc": {k: d.get(k) for k in ("phone", "not_provided", "complainant_address", "record")}, "owner": cj.get("owner")})
    await b.shot(TMP / f"doc_{label}_filed.png")


async def scrutiny_flow(b, label, win="window", sel="#reqFile"):
    await b.eval(f"""(async()=>{{ const W={win}; await until(()=>W.eval('!!J.sid') && W.document.querySelector('#dropz'), 20000); return true }})()""", timeout=60)
    await set_file(b, sel, L2)
    r = await b.eval(READ_JS.format(win=win), timeout=200)
    f = r["fields"]
    check(f"{label}: letter 2 read (name, phone, date, taluk, iPGRS number), outside the pilot: the form stays, Submit goes to the scrutiny desk",
          r["form"] and "Keerthana" in (f["name"] or "") and f["phone"] == "7483828985" and f["date"] == "2026-10-12" and f["taluk"] == "Chintamani" and f["gid"] == "502854"
          and "502854" in r["rec"] and "Scholarship" in r["rec"] and "scrutiny desk" in r["submit"].lower(), r)
    check(f"{label}: Mitra explains: outside the pilot, the record, submit", "keerthana" in r["say"].lower() and "scrutiny" in r["say"].lower() and "502854" in r["say"], r["say"])
    await b.shot(TMP / f"doc_{label}_scrutiny_form.png")
    r = await b.eval(f"""(async()=>{{ const W={win}; const d=W.document; const res={{}}; const n=W.eval('J.convo.length');
      d.querySelector('#docSubmit').click(); await until(()=>W.eval('J.convo.length')>n, 60000); await sleep(400);
      res.say=(W.eval('J.convo')||[]).slice(-1).map(x=>x.say||'')[0]||''; res.cid=res.say.match(/GR-\\d+/)?.[0];
      res.stage=[...d.querySelectorAll('#right .pipe .step')].map(e=>e.innerText).join(' | '); return res }})()""", timeout=120)
    check(f"{label}: Submit sends it to the scrutiny desk (reference spoken)", r["cid"] and "scrutiny" in r["say"].lower(), r)
    if r.get("cid"):
        cj = poc(f"/api/case/{r['cid']}")
        d = cj.get("doc") or {}
        check(f"{label}: the scrutiny case holds the letter: status Scrutiny, the EO of Chintamani, src=document, record 502854, phone kept",
              cj.get("status") == "Scrutiny" and cj.get("owner") == "eo_chintamani" and cj.get("src") == "document" and d.get("record") == "502854" and d.get("phone") == "7483828985",
              {"status": cj.get("status"), "owner": cj.get("owner"), "src": cj.get("src"), "rec": d.get("record")})


POC_READ = """(async()=>{ const res={}; const t0=Date.now(); res.form=await until(()=>document.querySelector('#duGo'), 150000); res.secs=(Date.now()-t0)/1000; await sleep(800);
          const v=k=>{const e=document.querySelector(`[data-k="${k}"]`); return e?e.value:null};
          res.fields={name:v('name'), phone:v('phone'), village:v('village'), taluk:v('taluk'), gid:v('grievance_id')}; res.pages=document.querySelectorAll('.du-pages img').length;
          const im=document.querySelector('.du-pages img'); res.upright=im?(im.naturalHeight>im.naturalWidth):false; res.rec=(document.querySelector('.du-rec')||{}).innerText||'';
          res.officer=(document.querySelector('.du-who b')||{}).textContent||''; res.stage3=(document.querySelector('.pl-step[data-s="3"] .pl-note')||{}).textContent||'';
          res.btn=document.querySelector('#duGo').innerText; res.note=[...document.querySelectorAll('.du-note')].map(e=>e.innerText).join(' | '); return res })()"""
POC_SUBMIT = """(async()=>{ const res={}; const ph=document.querySelector('[data-k="phone"]'); if(ph && !ph.value) ph.value='NA'; document.querySelector('#duGo').click();
          res.done=await until(()=>document.querySelector('#duClose'), 60000); res.reg=(document.querySelector('.du-done')||{}).innerText||'';
          const oks=document.querySelectorAll('#waBody .wa-ok'); res.chat=(oks[oks.length-1]||{}).innerText||''; res.stage7=(document.querySelector('.pl-step[data-s="7"]')||{}).className||'';
          res.route=!!document.querySelector('#plResult .pl-route'); document.querySelector('#duClose').click(); await sleep(300); return res })()"""


async def main():
    print("[Mitra, web desk: letter 1 filed]")
    async with Browser(port=9401, size=(1536, 864), gpu=True) as b:
        await b.goto(f"{M}/?auto=1&noevents=1&livetest=1&p=citizen", 4)
        await b.eval(HELP)
        await mitra_flow(b, "web")
        check("web: no JS exceptions", not [e for e in b.events if e[0] == "exception"], b.events[:3])
    print("[Mitra, web desk: letter 2 to the scrutiny desk]")
    async with Browser(port=9404, size=(1536, 864), gpu=True) as b:
        await b.goto(f"{M}/?auto=1&noevents=1&livetest=1&p=citizen", 4)
        await b.eval(HELP)
        await scrutiny_flow(b, "web")
        check("web scrutiny: no JS exceptions", not [e for e in b.events if e[0] == "exception"], b.events[:3])
    print("[Mitra, inside the phone: letter 1]")
    async with Browser(port=9402, size=(393, 852), gpu=True) as b:
        await b.goto(f"{M}/?auto=1&noevents=1&livetest=1&p=citizen&app=1&intro=0", 4)
        await b.eval(HELP)
        await mitra_flow(b, "phone")
        check("phone: no JS exceptions", not [e for e in b.events if e[0] == "exception"], b.events[:3])
    print("[WhatsApp POC: letter 1 registered, letter 3 (Kannada, municipal) to the scrutiny desk]")
    async with Browser(port=9403, size=(1536, 864), gpu=True) as b:
        await b.goto(f"{POC}/?p=citizen", 6)
        await b.eval(HELP)
        r = await b.eval("""(async()=>{ const res={}; res.tile=await until(()=>document.querySelector('.du-tile'), 15000);
          document.querySelector('.du-tile').click(); res.modal=await until(()=>document.querySelector('#duFile'), 5000); return res })()""")
        check("the upload tile and its modal", r["tile"] and r["modal"], r)
        await set_file(b, "#duFile", L1)
        r = await b.eval(POC_READ, timeout=200)
        f = r["fields"]
        check(f"POC: letter 1 read in {r.get('secs', 0):.0f} s: upright page, fields, the record, the Kodigenahalli PDO previewed, stage 3 from the letter",
              r["form"] and "Narasimhaiah" in (f["name"] or "") and f["village"] == "Kodigenahalli" and f["gid"] == "502806" and r["upright"] and "502806" in r["rec"] and "Kodigenahalli" in r["officer"] and "letter" in r["stage3"].lower(), r)
        await b.shot(TMP / "doc_poc_form.png")
        r = await b.eval(POC_SUBMIT, timeout=120)
        check("POC: Submit files it: Registered, the card in the chat, Behind the chat lit to stage 8, the routing card", r["done"] and "Registered" in r["reg"] and "Registered" in r["chat"] and "done" in r["stage7"] and r["route"], r)
        r = await b.eval("""(async()=>{ const res={}; document.querySelector('.du-tile').click(); res.modal=await until(()=>document.querySelector('#duFile'), 5000); return res })()""")
        check("the modal opens again for another letter", r["modal"], r)
        await set_file(b, "#duFile", L3)
        r = await b.eval(POC_READ, timeout=200)
        f = r["fields"]
        check("POC: letter 3 (Kannada) read: Kannada name kept, phone, iPGRS number, record 502976 (Urban Development), Submit to the scrutiny desk",
              r["form"] and f["phone"] == "7892245524" and f["gid"] == "502976" and "502976" in r["rec"] and "scrutiny desk" in r["btn"].lower() and "scrutiny" in r["note"].lower(), r)
        await b.shot(TMP / "doc_poc_scrutiny.png")
        r = await b.eval(POC_SUBMIT, timeout=120)
        check("POC: Submit sends letter 3 to the scrutiny desk, card in the chat", r["done"] and "scrutiny" in r["reg"].lower() and "scrutiny" in r["chat"].lower(), r)
        check("POC: no JS exceptions", not [e for e in b.events if e[0] == "exception"], b.events[:3])
    print(f"\n{ok} passed, {fail} failed")
    sys.exit(1 if fail else 0)


asyncio.run(main())
