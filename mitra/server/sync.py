"""Live sync: tails the Sakala change feed (/api/changes: new case events + officer notifications) every
0.7 s and pushes each change to every open screen over SSE. A subscriber that belongs to a citizen session
is told which events are about its own cases (`mine`); session ids themselves never leave the server."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime

from . import notify, sakala, store


class Broker:
    def __init__(self):
        self.queues: dict[asyncio.Queue, str] = {}      # queue -> Mitra session id of that screen ("" if none)

    def _sess(self, sid: str) -> dict:
        # read at send time: the same screen may have switched profile or officer since it subscribed
        return (store.get_session(sid) if sid else None) or {}

    async def publish(self, event: dict):
        event.setdefault("t", datetime.now().isoformat(timespec="seconds"))
        sess = event.pop("session", None)
        for q, sid in list(self.queues.items()):
            e = dict(event)
            if sess is not None:
                mine_sess = self._sess(sid).get("chat_session") or ""
                e["mine"] = bool(mine_sess and sess == mine_sess)
            try:
                q.put_nowait(e)
            except asyncio.QueueFull:
                pass

    async def publish_feed(self, row: dict | None):
        """A feed row becomes a notification card on every screen it concerns, and only those."""
        if not row:
            return
        for q, sid in list(self.queues.items()):
            s = self._sess(sid)
            if not s or not notify.relevant(row, s):
                continue
            try:
                q.put_nowait({"type": "notify", "card": notify.card(row, s)})
            except asyncio.QueueFull:
                pass

    def subscribe(self, sid: str = "") -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=400)
        self.queues[q] = sid or ""
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self.queues.pop(q, None)


broker = Broker()


def classify(what: str) -> str:
    w = (what or "").lower()
    if w.startswith("re-opened by the citizen"):        # the citizen rejected the resolution (one rung up the ladder)
        return "reopened"
    if w.startswith("routed to") or w.startswith("application registered"):
        return "new"
    if "escalat" in w or "deadline missed" in w:
        return "escalated"
    if "accepted" in w:
        return "accepted"
    if "asked citizen" in w:
        return "info"
    if "resolved with atr" in w:
        return "resolved"
    if "atr flagged" in w:
        return "atr_flagged"
    if "rejected" in w:
        return "rejected"
    if w.startswith("transferred to"):                  # returned with a suggestion: straight to the suggested officer
        return "rerouted"
    if "returned" in w:
        return "returned"
    if "scrutiny desk: routed" in w:
        return "rerouted"
    if "reminder from" in w:
        return "nudge"
    if "citizen replied" in w:
        return "citizen_reply"
    if "citizen confirmed" in w:
        return "feedback_yes"
    if "not solved" in w:
        return "reopened"
    if "appealed" in w:
        return "appeal"
    if "compensation" in w or "hrms" in w:
        return "compensation"
    return "update"


async def poller(interval: float = 0.7):
    last_e = last_n = None
    prev_now = None
    while True:
        try:
            if last_e is None:
                head = await sakala._get("/api/changes", after_event=10 ** 12, after_notif=10 ** 12, limit=1)
                last_e, last_n, prev_now = head["last_event"], head["last_notif"], head["now"]
            ch = await sakala._get("/api/changes", after_event=last_e, after_notif=last_n, limit=200)
            if ch["now"] != prev_now:
                prev_now = ch["now"]
                await broker.publish({"type": "clock", "now": ch["now"]})
            # a demo reset rewinds the ids: forget the old news and start again from the new head
            if ch["last_event"] < last_e or ch["last_notif"] < last_n:
                notify.reset()
                last_e = None
                continue
            for e in ch["events"]:
                change = classify(e["what"])
                await broker.publish({"type": "case", "change": change, "id": e["case_id"], "what": e["what"], "who": e["who"],
                                      "note": (e.get("note") or "")[:200], "status": e["status"], "owner": e["owner"], "level": e["level"],
                                      "service": e.get("service"), "taluk": e.get("taluk"), "gp": e.get("gp"), "src": e.get("src"),
                                      "session": e.get("session") or "", "at": e["t"]})
                await broker.publish_feed(notify.log_case(e, change))
            for n in ch["notifs"]:
                await broker.publish({"type": "notif", "to": n["officer_id"], "m": n["msg"], "at": n["t"]})
                await broker.publish_feed(notify.log_notif(n))
            last_e, last_n = ch["last_event"], ch["last_notif"]
        except Exception as e:  # Sakala down: keep trying quietly
            await asyncio.sleep(2.0)
            continue
        await asyncio.sleep(interval)


def sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
