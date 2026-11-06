"""Portal: the profile-switch transition in a real headless browser (CDP). Every permutation of Citizen / Officer /
Chief Secretary through the profile menu, "View as the officer", the officer picker and a voice switch (UI op): the
portal covers the screen with the right title and route, the new profile is built underneath, the portal closes and
the screen rises into place, no JS errors.
Usage: python tests/ui_portal.py [base]   (default http://localhost:8031)"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cdp import Browser  # noqa: E402

B = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8031"
TMP = Path(r"C:\Users\hp\AppData\Local\Temp")
ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1; print("  PASS", name)
    else:
        fail += 1; print("  FAIL", name, " <-", str(detail)[:320])


PERMS = [("citizen", "officer"), ("officer", "cs"), ("cs", "officer"), ("officer", "citizen"), ("citizen", "cs"), ("cs", "citizen")]
TITLE = {"citizen": "Opening the Citizen desk", "officer": "Opening the Officer desk", "cs": "Opening the Chief Secretary desk"}


async def main():
    async with Browser(port=9336, size=(1536, 864)) as b:
        await b.goto(f"{B}/?auto=1&noevents=1&livetest=1&p=citizen", 4)
        await b.eval("window.sleep=ms=>new Promise(r=>setTimeout(r,ms));window.until=async(f,ms=20000)=>{const t=Date.now();while(Date.now()-t<ms){try{if(f())return true}catch(e){}await sleep(50)}return false};"
                     "window.pstate=()=>{const p=document.querySelector('#portal');return {on:!!p&&p.classList.contains('in'),out:!!p&&p.classList.contains('out'),title:p&&p.querySelector('#ptTitle').textContent,from:p&&p.querySelector('#ptFrom').textContent,to:p&&p.querySelector('#ptTo').textContent,"
                     "vis:!!p&&getComputedStyle(p).display!=='none'}};")
        await b.eval("until(()=>J.profile==='citizen'&&!!document.querySelector('#profBtn'))")
        n = 0
        for frm, to in PERMS:
            n += 1
            r = await b.eval(f"""(async()=>{{
              const res={{}}; await until(()=>!Portal.busy); await sleep(300);
              if(J.profile!=='{frm}'){{ res.setup='was '+J.profile; }}
              document.querySelector('#profBtn').click(); await sleep(150);
              const t0=performance.now();
              document.querySelector('#profiles button[data-p="{to}"]').click();
              await sleep(120); res.during=pstate(); res.bodyOut=document.body.classList.contains('portal-out');
              await sleep(500); res.mid=pstate();
              await until(()=>document.body.classList.contains('portal-in')); res.revealAt=Math.round(performance.now()-t0);
              res.profileAtReveal=J.profile; res.panels=document.querySelectorAll('#left > *, #right > *').length;
              await until(()=>!document.querySelector('#portal').classList.contains('in')); await sleep(200);
              res.after=pstate(); res.profile=J.profile; res.btn=document.querySelector('#profName').textContent;
              res.stageVisible=getComputedStyle(document.querySelector('.stage')).opacity;
              return res}})()""")
            print(f"   {frm}->{to}", json.dumps(r)[:300])
            if n == 1:
                await b.shot(TMP / "portal_mid.png")
            check(f"{frm} -> {to}: portal covers the screen with '{TITLE[to]}', route {frm} -> {to}",
                  r["during"]["on"] and r["during"]["vis"] and r["bodyOut"] and r["mid"]["title"] == TITLE[to] and r["mid"]["to"].lower().startswith({"cs": "chief", "officer": "officer", "citizen": "citizen"}[to]), r)
            check(f"{frm} -> {to}: new profile built under the portal, revealed after >=1.2 s, portal gone, screen back",
                  r["profileAtReveal"] == to and r["profile"] == to and r["revealAt"] >= 1150 and not r["after"]["on"] and not r["after"]["vis"] and r["panels"] > 0 and float(r["stageVisible"]) > .95, r)
        # mid-transition screenshot for the eye
        await b.eval("(async()=>{await until(()=>!Portal.busy);document.querySelector('#profBtn').click();await sleep(100);document.querySelector('#profiles button[data-p=\"cs\"]').click();await sleep(900)})()")
        await b.shot(TMP / "portal_cs.png")
        await b.eval("until(()=>!Portal.busy&&!document.querySelector('#portal').classList.contains('in'))")
        print("[other entry points]")
        r = await b.eval("""(async()=>{const res={}; await until(()=>!Portal.busy);
          const ids=Object.keys(J.boot.officers); const oid=ids.find(i=>i!==J.officer); const o=J.boot.officers[oid];
          viewAsOfficer(oid); await sleep(300); res.title=pstate().title; res.want=`Opening ${o.short}'s desk`;
          await until(()=>!document.querySelector('#portal').classList.contains('in')); res.profile=J.profile; res.officer=J.officer===oid;
          const sel=document.querySelector('#officerSel'); const other=[...sel.options].map(x=>x.value).find(v=>v!==J.officer);
          sel.value=other; sel.onchange(); await sleep(300); res.selTitle=pstate().title; res.selWant=`Opening ${J.boot.officers[other].short}'s desk`;
          await until(()=>!document.querySelector('#portal').classList.contains('in')); res.selOfficer=J.officer===other;
          UI.profile({profile:'citizen'}); await sleep(200); res.voice=pstate(); res.voiceProfile=J.profile;
          await until(()=>!document.querySelector('#portal').classList.contains('in')); res.voiceGone=!pstate().vis;
          return res})()""")
        print("   ", json.dumps(r)[:400])
        check("'View as the officer' opens that officer's desk through the portal", r["title"] == r["want"] and r["profile"] == "officer" and r["officer"], r)
        check("logging in as another officer goes through the portal", r["selTitle"] == r["selWant"] and r["selOfficer"], r)
        check("a voice switch (server-side) is covered by the portal and then revealed", r["voice"]["on"] and r["voice"]["title"] == TITLE["citizen"] and r["voiceProfile"] == "citizen" and r["voiceGone"], r)
        errs = [e for e in b.events if e[0] == "exception"]
        check("no JS exceptions", not errs, errs)
    print(f"\n{ok} passed, {fail} failed")


asyncio.run(main())
