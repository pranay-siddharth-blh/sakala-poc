"""22 Oct 2026 (Pranay): a YAML knowledge base (mitra/knowledge.yaml + server/knowledge.py) answers general questions
(what is Sakala / Praja Seva / iPGRS, who is the Chief Secretary, compensation, appeals, how routing works, what Mitra can do)
through the SAME function path as everything else: intent `ask_knowledge` (rules brain deterministic, Gemini brain, Gemini
Live function), tool `t_ask_knowledge` -> the fact from the file + an answer card; follow-ups prefer related entries. The
model never answers such questions from memory: no match = "not in my notes". Backups in tools/backups/res22/."""
import ast
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BK = ROOT / "tools" / "backups" / "res22"
BK.mkdir(parents=True, exist_ok=True)


def patch(rel, pairs, subs=()):
    p = ROOT / rel
    s = p.read_text(encoding="utf-8")
    shutil.copy(p, BK / (p.name + ".3.bak"))
    for old, new in pairs:
        assert old in s, f"{rel}: missing\n{old[:160]}"
        s = s.replace(old, new, 1)
    for old, new in subs:
        s = s.replace(old, new)
    if rel.endswith(".py"):
        ast.parse(s)
    p.write_text(s, encoding="utf-8")
    print("patched", rel)


# ------------------------------------------------------------------ brain: the intent + the deterministic rule
patch("mitra/server/brain.py", [
    ('''    "identity":       (("*",),''',
     '''    "ask_knowledge":  (("*",), "A general-knowledge question, not about the live data: what Sakala / iPGRS / Praja Seva / the Act / compensation / "
                      "appeals / the scrutiny desk / the pipeline are, who the Chief Secretary, Chief Minister or a minister is, helpline numbers, how routing "
                      "or escalation works, what Mitra can do, Sakala's 2025 performance. `question` = the question as asked. Answered only from Mitra's notes.", ("question",)),
    "identity":       (("*",),'''),
    ('''    if pre["intent"] in ("go_to", "show_chart_as", "set_theme", "identity", "forget_conversation", "confirm_action", "cancel_action", "view_as_officer", "upload_document") \\''',
     '''    if pre["intent"] in ("go_to", "show_chart_as", "set_theme", "identity", "forget_conversation", "confirm_action", "cancel_action", "view_as_officer", "upload_document", "ask_knowledge") \\'''),
    # the knowledge rule sits after identity / navigation / upload and before the profile sections: a clear general question
    ('''    if has("move time", "move the clock", "forward", "advance", "days later", "next week", "tick") and (has("day", "days", "week", "clock", "time")):''',
     '''    if not re.search(r"\\b(who (are|made|built|created) you|what are you|are you (a )?(robot|human|bot|ai|real))\\b", low):
        from . import knowledge                   # "what is Sakala?", "who is the Chief Secretary?": the notes, deterministically
        ke, ks = knowledge.match(t, last=(c.get("kb_last") or ""), strict=True)
        if ke and not (prof == "citizen" and (c.get("flow") or "") in ("ask_place", "ask_gp", "confirm", "reply", "apply_name", "apply_village") and len(t.split()) <= 3):
            return {"intent": "ask_knowledge", "question": t}
    if has("move time", "move the clock", "forward", "advance", "days later", "next week", "tick") and (has("day", "days", "week", "clock", "time")):'''),
])

# ------------------------------------------------------------------ tools: the function, the catch-all, the context
patch("mitra/server/tools.py", [
    ('''async def t_identity(sess, args):''',
     '''async def t_ask_knowledge(sess, args):
    """A general question answered from mitra/knowledge.yaml and nothing else; the model only puts the fact into conversation."""
    from . import knowledge
    q = (args.get("question") or args.get("_text") or "").strip()
    st = sess["state"]
    k = knowledge.answer(q, last=st.get("kb_last") or "", strict=False)
    if not k:
        return {"say": "That is not in my notes yet, so I will not guess. I can tell you about Sakala, iPGRS, the Praja Seva Department, "
                       "compensation and appeals, the officers' ladder, how I route a request, or who the Chief Secretary is.",
                "data": {"known_topics": knowledge.topics()[:12]}}
    st["kb_last"] = k["id"]
    say = k["say"]
    html = f"<p>{_esc(k['say'])}</p>" + (f"<p class='more'>{_esc(k['more'])}</p>" if k.get("more") else "") + \\
           (f"<div class='src'>Source · {_esc(k['source'])}</div>" if k.get("source") else "")
    return {"say": say, "data": {"topic": k["topic"], "more": k.get("more") or "", "source": k.get("source") or "",
                                 "related": [r["topic"] for r in k.get("related") or []]},
            "ui": [{"op": "answer", "q": k["topic"], "html": html}]}


def _esc(s: str) -> str:
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def t_identity(sess, args):'''),
    ('''    "switch_profile": t_switch_profile, "go_to": t_go_to, "upload_document": t_upload_document,''',
     '''    "switch_profile": t_switch_profile, "go_to": t_go_to, "upload_document": t_upload_document, "ask_knowledge": t_ask_knowledge,'''),
    # the catch-all: a question the rules did not claim but the notes cover (loose bar) is answered from the notes
    ('''    t = (args.get("text") or args.get("_text") or "").strip()
    if sess["profile"] == "citizen":
        st = sess["state"]
        # mid-flow answers (a village, a reply to the officer) still belong to the flow; chit-chat is answered, never filed
        if t and (st.get("flow") in ("ask_place", "ask_gp", "confirm", "reply", "apply_name", "apply_village") or looks_like_problem(t)):
            return await t_citizen_text(sess, {"text": t})
        return {"say": chit_chat_reply(t)}
    return {"say": "I can act on Sakala cases and data. Ask me for help any time and I will tell you what I can do here."}''',
     '''    t = (args.get("text") or args.get("_text") or "").strip()
    if sess["profile"] == "citizen":
        st = sess["state"]
        # mid-flow answers (a village, a reply to the officer) still belong to the flow; chit-chat is answered, never filed
        if t and (st.get("flow") in ("ask_place", "ask_gp", "confirm", "reply", "apply_name", "apply_village") or looks_like_problem(t)):
            return await t_citizen_text(sess, {"text": t})
    from . import knowledge
    if t and not CHIT_RX.search(t) and knowledge.match(t, last=sess["state"].get("kb_last") or "", strict=False)[0]:
        return await t_ask_knowledge(sess, {"question": t})        # a general question the notes cover
    if sess["profile"] == "citizen":
        return {"say": chit_chat_reply(t)}
    return {"say": "I can act on Sakala cases and data, and answer questions about Sakala, iPGRS and the Praja Seva Department. Ask me for help any time."}'''),
])

# the brain's screen context carries the last knowledge topic so a follow-up ("and the compensation?") stays on topic
patch("mitra/server/main.py", [
    ('''    if s["profile"] == "citizen":
        c["chat_flow"] = st.get("flow") or st.get("chat_flow") or "menu"''',
     '''    if st.get("kb_last"):
        c["kb_last"] = st["kb_last"]                 # the last knowledge topic answered: a follow-up stays on it
    if s["profile"] == "citizen":
        c["chat_flow"] = st.get("flow") or st.get("chat_flow") or "menu"'''),
])

# ------------------------------------------------------------------ Live: the instruction
patch("mitra/server/live.py", [
    ('''        "If the person is only testing, joking or chatting ('hello hello', 'just checking', 'nothing'), answer briefly and "''',
     '''        "General questions that are not about the live data (what Sakala, iPGRS, Praja Seva or the Act are, compensation, appeals, "
        "helplines, who the Chief Secretary, Chief Minister or a minister is, how routing or escalation works, what you can do, Sakala's "
        "2025 performance) -> call ask_knowledge with the question. Its `say` is the fact: tell it warmly in your own words, keeping every "
        "name, number and date exactly; `data.more` holds detail for a follow-up and `data.related` the topics you can offer next. "
        "For a follow-up call ask_knowledge again with the fuller question. If it says the fact is not in its notes, say so; never "
        "answer such questions from memory.",
        "If the person is only testing, joking or chatting ('hello hello', 'just checking', 'nothing'), answer briefly and "'''),
])

# ------------------------------------------------------------------ phone: an answer card raises the sheet
patch("mitra/web/app.js", [
    ("const AUTO = { upload: 'left', case: 'right',", "const AUTO = { upload: 'left', answer: 'right', case: 'right',"),
])
print("done")
