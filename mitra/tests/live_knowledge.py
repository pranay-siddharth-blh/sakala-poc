"""The knowledge base on the REAL Gemini Live model (8030): general questions become ask_knowledge calls, the fact is spoken
conversationally with the names and numbers intact, a follow-up stays on topic, an unknown question is never answered from
memory, and a data question still goes to the data functions. Run from mitra/: python tests/live_knowledge.py [base]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_battery as LB  # noqa: E402

if len(sys.argv) > 1:
    LB.B = sys.argv[1]; LB.W = LB.B.replace("http", "ws")


def kb(*words):
    return lambda n, s, t: "ask_knowledge" in n and all(w.lower() in s.lower() for w in words)


async def main():
    print("[citizen: general questions in conversation]")
    await LB.session("citizen", [
        ("what is Sakala?", kb("2012")),
        ("and who is the Chief Secretary?", kb("Shalini")),
        ("how much compensation do I get if my certificate is late?", kb("20", "500")),
        ("what is the capital of France?", lambda n, s, t: "paris" not in s.lower() and ("not in my notes" in s.lower() or "ask_knowledge" in n or "sakala" in s.lower())),
    ])
    print("[chief secretary: knowledge and data side by side]")
    await LB.session("cs", [
        ("what is the Praja Seva Department?", kb("Harsha Gupta")),
        ("how did Sakala do in 2025?", lambda n, s, t: ("ask_knowledge" in n or "sakala_2025" in n) and "4.45" in s),   # the notes or the real report table: the same numbers
        ("how many overdue cases are there in Mysuru?", lambda n, s, t: "ask_knowledge" not in n and n),
    ])
    print(f"\n{LB.ok}/{LB.ok + LB.fail} checks passed")
    for f in LB.FAILS:
        print("  FAIL:", f)
    sys.exit(1 if LB.fail else 0)


import asyncio  # noqa: E402
asyncio.run(main())
