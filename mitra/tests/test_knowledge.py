"""The knowledge base (22 Oct 2026). 1. The matcher alone: 40 phrasings -> the right note, 0 false hits on 25 complaints / data
questions / commands. 2. Through the pipeline on a test instance (8031, cascade): intent ask_knowledge, the fact spoken, the
answer card, a follow-up that stays on topic, an unknown question answered with "not in my notes" (never invented), and a
data question still going to the data path. Run from mitra/: PYTHONIOENCODING=utf-8 python tests/test_knowledge.py [base]"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import knowledge as K  # noqa: E402

B = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8031"
ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1; print("  PASS", name)
    else:
        fail += 1; print("  FAIL", name, " <-", str(detail)[:300])


def post(p, d):
    r = urllib.request.Request(B + p, data=json.dumps(d).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=120).read())


print("[1. the matcher]")
K.load(force=True)
POS = [("what is sakala", "sakala"), ("hey mitra, can you tell me what sakala is?", "sakala"), ("what is praja seva", "praja_seva"),
       ("who is the chief secretary", "chief_secretary"), ("what's the name of the chief secretary of karnataka", "chief_secretary"), ("who is madam", "chief_secretary"),
       ("who is the chief minister", "cm"), ("how much compensation do i get if my certificate is late", "sakala_compensation"), ("how do I appeal", "sakala_appeal"),
       ("what is ipgrs", "ipgrs"), ("what is 1902", "ipgrs_helpline"), ("what number do i call for sakala", "sakala_helpline"), ("how does the routing work", "routing_how"),
       ("how accurate are you", "routing_how"), ("what is the scrutiny desk", "scrutiny_desk"), ("what can you do", "mitra_what"), ("explain the 8 stages", "mitra_pipeline"),
       ("which districts does the pilot cover", "pilot"), ("who is above the tahsildar", "officer_ladder"), ("how many days does the officer have", "escalation"),
       ("is my phone number safe", "privacy"), ("can you read a handwritten letter", "document_upload"), ("do you speak kannada", "kannada"),
       ("what was sakala's performance in 2025", "sakala_2025_performance"), ("which was the worst district in 2025", "sakala_2025_performance"),
       ("what is the difference between a grievance and a sakala application", "grievance_vs_sakala"), ("what is a gsc number", "gsc"),
       ("tell me about praja seva abhiyana", "praja_seva_abhiyana"), ("when is the wednesday review", "wednesday_review"), ("what is the 2026 amendment", "sakala_amendment_2026"),
       ("where do i apply for a caste certificate", "seva_sindhu"), ("what does rti have to do with it", "ipgrs_exclusions"), ("why is the government using ai", "ai_routing_news"),
       ("tell me about the praja seva department", "praja_seva"), ("who is harsha gupta", "praja_seva"), ("what is janaspandana", "ipgrs"), ("what is the sakala helpline", "sakala_helpline"),
       ("what happens if the officer does nothing", "escalation"), ("what is seva sindhu", "seva_sindhu"), ("how is a grievance escalated in ipgrs", "ipgrs_routing")]
NEG = ["there is no water in gorahalli", "how many overdue cases in mysuru", "show me the open cases", "the street light near the bus stand is not working",
       "take me back to the dashboard", "nudge the tahsildar of piriyapatna", "compare piriyapatna and hunsur", "my name is ramesh", "yes file it", "hello how are you",
       "read my inbox", "which officer has the most overdue cases", "open gr-504211", "i want to upload a letter", "which officer has the most overdue cases in hunsur taluk",
       "give me the position", "show the overdue cases on the map", "what is the status of my request", "the pdo has not come for 10 days", "i want to apply for a caste certificate",
       "accept the case", "what is the overdue count in piriyapatna", "how many cases are pending with the tahsildar", "switch to the officer screen", "the road in hunsur is bad"]
right = 0
for q, exp in POS:
    e, s = K.match(q, strict=True)
    got = e["id"] if e else None
    if got == exp:
        right += 1
    else:
        print(f"    miss {q!r} -> {got} ({s:.1f})")
check(f"{right}/{len(POS)} phrasings find the right note", right == len(POS))
hits = [(q, K.match(q, strict=True)[0]["id"]) for q in NEG if K.match(q, strict=True)[0]]
check(f"no false hits on {len(NEG)} complaints, data questions and commands", not hits, hits)
check("a follow-up prefers the related note ('and the appeals?' after compensation)", K.match("and the appeals?", last="sakala_compensation", strict=False)[0]["id"] == "sakala_appeal")
check("an unknown question gets nothing (never a guess)", K.match("what is the capital of france", strict=False)[0] is None and K.match("who won the cricket match", strict=False)[0] is None)

print("[2. through the pipeline (cascade)]")
for prof in ("citizen", "cs"):
    sid = post("/api/session", {"profile": prof, "lang": "en"})["session"]
    r = post("/api/turn", {"session": sid, "text": "what is sakala?", "want_audio": False})
    ans = [u for u in r.get("ui", []) if u.get("op") == "answer"]
    check(f"{prof}: 'what is sakala?' -> ask_knowledge, the fact (2011 Act, 1,446 services), an answer card",
          r.get("intent") == "ask_knowledge" and "1,446" in r.get("say", "") and ans and ans[0].get("q") == "Sakala", (r.get("intent"), r.get("say", "")[:120]))
    r = post("/api/turn", {"session": sid, "text": "and who is the chief secretary?", "want_audio": False})
    check(f"{prof}: 'who is the chief secretary?' -> Shalini Rajneesh", r.get("intent") == "ask_knowledge" and "Shalini Rajneesh" in r.get("say", ""), (r.get("intent"), r.get("say", "")[:120]))
    r = post("/api/turn", {"session": sid, "text": "how much compensation?", "want_audio": False})
    check(f"{prof}: follow-up 'how much compensation?' -> 20 rupees a day, 500 cap", r.get("intent") == "ask_knowledge" and "20 rupees" in r.get("say", "") and "500" in r.get("say", ""), (r.get("intent"), r.get("say", "")[:120]))
    r = post("/api/turn", {"session": sid, "text": "what is the capital of france?", "want_audio": False})
    check(f"{prof}: an unknown question -> 'not in my notes', nothing invented", "not in my notes" in r.get("say", "").lower() and "paris" not in r.get("say", "").lower(), (r.get("intent"), r.get("say", "")[:120]))
sid = post("/api/session", {"profile": "cs", "lang": "en"})["session"]
r = post("/api/turn", {"session": sid, "text": "how many overdue cases in Mysuru?", "want_audio": False})
check("cs: a data question still goes to the data path, not the notes", r.get("intent") != "ask_knowledge" and r.get("intent") in ("ask_data", "find_cases", "filter_cases", "summary"), (r.get("intent"), r.get("say", "")[:100]))
sid = post("/api/session", {"profile": "citizen", "lang": "en"})["session"]
r = post("/api/turn", {"session": sid, "text": "there is no water in Gorahalli", "want_audio": False})
check("citizen: a complaint is still filed as a complaint", r.get("intent") in ("chat_text", "smalltalk") and "not in my notes" not in r.get("say", "").lower() and ("water" in r.get("say", "").lower() or "understand" in r.get("say", "").lower()), (r.get("intent"), r.get("say", "")[:100]))
print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
