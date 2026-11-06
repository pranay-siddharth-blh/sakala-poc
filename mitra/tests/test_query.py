"""Ask-anything layer: the functions the live model calls for data questions, with the arguments it would pass, checked
against direct SQL on the POC database (read-only). No Gemini needed. Run from mitra/: python tests/test_query.py"""
import asyncio
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import query, store, tools  # noqa: E402

DB = sqlite3.connect(f"file:{Path(__file__).resolve().parents[2] / 'app' / 'data' / 'sakala.db'}?mode=ro", uri=True)
ok = fail = 0


def sql(q, *a):
    return DB.execute(q, a).fetchone()[0]


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1; print("  PASS", name)
    else:
        fail += 1; print("  FAIL", name, " <-", str(detail)[:300])


async def q(s, name, **args):
    r = await query.run(s, name, args)
    print(f"    {name}{args} -> {r['say'][:150]!r}")
    return r


async def main():
    cs = store.new_session("cs", "", "en")
    off = store.new_session("officer", "tah_piriyapatna", "en")
    pilot_gid = sql("SELECT r.gid FROM ipgrs_records r JOIN cases c ON c.id='GR-'||r.gid LIMIT 1")
    other_gid = sql("SELECT gid FROM ipgrs_records WHERE dept_code NOT IN ('REV','RDPR','FOOD') AND 'GR-'||gid NOT IN (SELECT id FROM cases) LIMIT 1")

    print("[one case / one G.Id]")
    r = await q(cs, "lookup_case", case_id=pilot_gid)
    lc = r["data"].get("live_case") or {}
    check("Excel G.Id in the pilot -> live case + iPGRS record", lc.get("id") == f"GR-{pilot_gid}" and r["data"].get("ipgrs_record"), r["data"].keys())
    check("status and officer match the database", lc.get("status") == sql("SELECT status FROM cases WHERE id=?", f"GR-{pilot_gid}") and lc.get("officer") in r["say"], lc)
    check("case card drawn on screen", any(u["op"] == "case" for u in r["ui"]), r["ui"])
    check("the case becomes the open case (for 'nudge this officer')", cs["state"].get("case_id") == f"GR-{pilot_gid}", cs["state"].get("case_id"))
    r = await q(cs, "lookup_case", case_id=other_gid)
    dept = sql("SELECT dept FROM ipgrs_records WHERE gid=?", other_gid)
    check("G.Id outside the pilot -> iPGRS record, says so", dept in r["say"] and "outside the pilot" in r["say"], r["say"])
    spoken = " ".join({"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine"}[d] for d in other_gid)
    r = await q(cs, "lookup_case", case_id=spoken)
    check("G.Id spoken as words", r["data"].get("found") and dept in r["say"], r["say"])
    r = await q(cs, "lookup_case", case_id="GR 999999")
    check("unknown id -> 'could not find', nothing invented", not r["data"].get("found") and "could not find" in r["say"], r["say"])
    r = await q(cs, "lookup_case", case_id="SK-RD855S260004811")
    check("Sakala application id", (r["data"].get("live_case") or {}).get("kind") == "application" and "overdue" in r["say"], r["say"])

    print("[the live caseload]")
    r = await q(cs, "find_cases", department="revenue", district="Bagalkote", status="open", limit=5)
    want = sql("SELECT COUNT(*) FROM cases WHERE dept_code='REV' AND district='Bagalkote' AND status IN ('Pending','In progress','Info requested')")
    check(f"Revenue open in Bagalkote = {want} (SQL)", r["data"]["total"] == want, r["data"]["total"])
    check("list drawn + remembered for 'open the second one'", any(u["op"] == "filter" for u in r["ui"]) and len(cs["state"].get("list") or []) == min(5, want), cs["state"].get("list"))
    res = await tools.execute(cs, "open_case", {"ordinal": 2})
    check("'open the second one' opens the 2nd listed case", (res["ui"] and res["ui"][0].get("case", {}).get("id")) == cs["state"]["list"][1], res["say"][:80])
    r = await q(cs, "find_cases", group_by="district", limit=31)
    check("cases by district: 31 districts, totals add up", r["data"]["distinct"] == 31 and sum(g["count"] for g in r["data"]["groups"]) == sql("SELECT COUNT(*) FROM cases"), r["data"]["distinct"])
    check("chart drawn for a breakdown (stage card)", any(u["op"] == "viz" and u["cards"] for u in r["ui"]), r["ui"][:1])
    r = await q(cs, "find_cases", officer="Tahsildar Hunsur")
    check("by officer (fuzzy name)", r["data"]["officer_matched"] == "Tahsildar Hunsur" and r["data"]["total"] == sql("SELECT COUNT(*) FROM cases WHERE owner='tah_hunsur'"), r["data"])
    r = await q(cs, "find_cases", overdue=True, group_by="officer")
    check("overdue by officer", r["data"]["total"] >= 0 and "groups" in r["data"], r["data"])
    r = await q(cs, "find_cases", status="scrutiny")
    check("at the scrutiny desk", r["data"]["total"] == sql("SELECT COUNT(*) FROM cases WHERE status='Scrutiny'"), r["data"]["total"])
    r = await q(cs, "find_cases", since_go_live=True, group_by="source")
    check("filed since go-live, by channel", r["data"]["total"] == sql("SELECT COUNT(*) FROM cases WHERE real=0 AND synthetic=0"), r["data"])
    r = await q(cs, "find_cases", service="ration", district="Mysuru")
    check("by service words + district", r["data"]["total"] >= 1, r["data"]["total"])
    r = await q(cs, "find_cases", vulnerable=True)
    check("vulnerable citizens", r["data"]["total"] == sql("SELECT COUNT(*) FROM cases WHERE vulnerable=1"), r["data"]["total"])

    print("[the 9,999 iPGRS records]")
    r = await q(cs, "ipgrs_records", department="health", group_by="district", limit=5)
    check("Health dept by district (SQL)", r["data"]["total"] == sql("SELECT COUNT(*) FROM ipgrs_records WHERE lower(dept) LIKE '%health%'"), r["data"]["total"])
    r = await q(cs, "ipgrs_records", source="mobile app", status="scrutiny")
    a = sql("SELECT COUNT(*) FROM ipgrs_records WHERE source LIKE '%Mobile App%'")
    b = sql("SELECT COUNT(*) FROM ipgrs_records WHERE source LIKE '%Mobile App%' AND status LIKE '%Scrutiny%'")
    check(f"app complaints stuck at scrutiny = {b} of {a} ({round(100 * b / max(1, a))}%)", r["data"]["total"] == b, r["data"]["total"])
    r = await q(cs, "ipgrs_records", service_type="sakala")
    check("Sakala-tagged records", r["data"]["total"] == sql("SELECT COUNT(*) FROM ipgrs_records WHERE lower(service_type)='sakala'"), r["data"]["total"])
    r = await q(cs, "ipgrs_records", group_by="department", limit=3)
    check("top departments", r["data"]["distinct"] == sql("SELECT COUNT(DISTINCT dept) FROM ipgrs_records"), r["data"]["distinct"])
    r = await q(cs, "ipgrs_records", group_by="day")
    check("by day (sample week)", len(r["data"]["groups"]) >= 5, r["data"]["groups"])

    print("[officers, places, statewide, Sakala 2025]")
    r = await q(off, "officer_profile", officer="PDO Attigodu")
    check("officer profile with reporting chain", r["data"].get("found") and "EO" in " ".join(r["data"]["reports_to"]), r["data"])
    r = await q(off, "officer_profile", officer="Collector of Mars")
    check("unknown officer -> 'could not find'", not r["data"].get("found"), r["say"])
    r = await q(cs, "place_info", place="Bylakuppe")
    check("a village: GP, taluk, district, officers", r["data"].get("taluk") == "Piriyapatna" and r["data"].get("officers_here"), r["data"])
    r = await q(cs, "place_info", place="Hunsur")
    check("a taluk: officers serving it", r["data"].get("is_a") == "taluk" and len(r["data"]["officers_here"]) >= 4, r["data"])
    r = await q(cs, "place_info", place="Atlantis")
    check("unknown place -> 'could not find'", not r["data"].get("found"), r["say"])
    r = await q(cs, "statewide_stats")
    check("statewide totals (SQL)", r["data"]["open"] == sql("SELECT COUNT(*) FROM cases WHERE status IN ('Pending','In progress','Info requested')"), r["data"]["open"])
    r = await q(cs, "sakala_2025")
    check("Sakala 2025 state figures (4.45% late, 7.42% rejected)", "4.45" in r["say"] and "7.42" in r["say"], r["say"])
    r = await q(cs, "sakala_2025", district="Bengaluru Urban")
    check("Bengaluru Urban worst (9.18%)", "9.18" in r["say"], r["say"])
    print(f"\n{ok}/{ok + fail} checks passed")


asyncio.run(main())
