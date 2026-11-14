"""Server-authoritative MCQ match engine. Live state lives in Redis (m:{match_id}*), durable results in the DB."""
import asyncio
import json
import logging
import random
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.redis import get_redis, get_rules
from app.core.security import ArenaError
from app.database.models import (Match, MatchAnswer, MatchPlayer, MatchQuestion, PlayerStats, PointsTransaction,
                                 Question, Room, RoomPlayer, User)
from app.database.session import SessionLocal
from app.game.scoring import accuracy, decide_winner, points_for
from app.realtime.hub import publish
from app.services.question_service import pool_size

log = logging.getLogger("arena.engine")
TASKS: set[asyncio.Task] = set()
LETTERS = ["A", "B", "C", "D"]


def ms() -> int:
    return int(time.time() * 1000)


def dt(m: int) -> datetime:
    return datetime.fromtimestamp(m / 1000, tz=timezone.utc)


async def _sleep_until(target_ms: int):
    while (d := target_ms - ms()) > 0:
        await asyncio.sleep(min(d / 1000, 0.05))


# ---------- match creation ----------
async def _select_questions(s, room: Room, user_ids: list[str]) -> list[Question]:
    qs = list((await s.execute(select(Question).where(Question.domain_id == room.domain_id,
                                                      Question.status == "PUBLISHED"))).scalars())
    recent = set((await s.execute(
        select(MatchQuestion.question_id).join(MatchPlayer, MatchPlayer.match_id == MatchQuestion.match_id)
        .where(MatchPlayer.user_id.in_(user_ids)).order_by(MatchQuestion.id.desc()).limit(200))).scalars())
    rng = random.SystemRandom()
    fresh = [q for q in qs if q.id not in recent]
    old = [q for q in qs if q.id in recent]
    rng.shuffle(fresh), rng.shuffle(old)
    pool = fresh + old  # unseen first, recent only as a fallback
    picked: list[Question] = []
    buckets = {d: [q for q in pool if q.difficulty == d] for d in ("EASY", "MEDIUM", "HARD")}
    while len(picked) < room.question_count and any(buckets.values()):  # round-robin over difficulties
        for d in buckets:
            if buckets[d] and len(picked) < room.question_count:
                picked.append(buckets[d].pop(0))
    rng.shuffle(picked)
    return picked


def _public_q(qj: dict, index: int, total: int) -> dict:
    return {"question_id": qj["id"], "index": index, "total": total, "question_text": qj["text"],
            "code_snippet": qj["code"], "options": qj["options"], "difficulty": qj["difficulty"],
            "topic": qj["topic"], "question_type": qj["type"]}


async def start_match(s, room: Room) -> Match:
    r = get_redis()
    rps = list((await s.execute(select(RoomPlayer).where(RoomPlayer.room_id == room.id))).scalars())
    if len(rps) != 2 or not all(p.is_ready for p in rps):
        raise ArenaError("NOT_READY", "Both players must be present and ready", 409)
    if room.status != "READY":
        raise ArenaError("ROOM_CLOSED", f"Room is {room.status}", 409)
    uids = [p.user_id for p in rps]
    users = {u.id: u for u in (await s.execute(select(User).where(User.id.in_(uids)))).scalars()}
    qs = await _select_questions(s, room, uids)
    if len(qs) < room.question_count or await pool_size(s, room.domain_id) < max(room.question_count, settings.min_pool_size):
        raise ArenaError("INSUFFICIENT_QUESTIONS", "Not enough published questions", 409)
    m = Match(room_id=room.id, game_mode="PRIVATE_ROOM", domain_id=room.domain_id,
              duration_seconds=room.duration_seconds, question_count=len(qs), status="STARTING")
    s.add(m)
    await s.flush()
    for u in uids:
        s.add(MatchPlayer(match_id=m.id, user_id=u))
    rng = random.Random(m.id)  # deterministic per match => identical option order for both players
    qjson = []
    for i, q in enumerate(qs):
        s.add(MatchQuestion(match_id=m.id, question_id=q.id, question_order=i))
        orig = {o["id"]: o["text"] for o in q.options}
        order = LETTERS[:]
        rng.shuffle(order)  # displayed slot k shows original option order[k]
        shown = [{"id": LETTERS[k], "text": orig[order[k]]} for k in range(4)]
        qjson.append(json.dumps({"id": q.id, "text": q.question_text, "code": q.code_snippet, "options": shown,
                                 "correct": LETTERS[order.index(q.correct_option)], "map": dict(zip(LETTERS, order)),
                                 "explanation": q.explanation, "difficulty": q.difficulty, "topic": q.topic,
                                 "type": q.question_type}))
    room.status = "STARTING"
    await s.commit()
    starts_at = ms() + int(settings.start_countdown_seconds * 1000)
    meta = [{"user_id": u, "display_name": users[u].display_name, "avatar_url": users[u].avatar_url} for u in uids]
    pipe = r.pipeline()
    pipe.hset(f"m:{m.id}", mapping={"room_id": room.id, "status": "STARTING", "count": len(qs), "idx": -1,
                                    "duration": room.duration_seconds, "starts_at": starts_at,
                                    "players": json.dumps(meta), "domain_id": room.domain_id})
    pipe.rpush(f"m:{m.id}:q", *qjson)
    pipe.hset(f"m:{m.id}:conn", mapping={u: "1" for u in uids})
    pipe.set(f"room:{room.id}:match", m.id, ex=7200)
    for k in ("", ":q", ":conn"):
        pipe.expire(f"m:{m.id}{k}", 7200)
    await pipe.execute()
    await publish(room.id, "match.started", {"match_id": m.id, "starts_at_ms": starts_at, "server_now_ms": ms(),
                                             "duration_seconds": room.duration_seconds, "question_count": len(qs),
                                             "players": meta}, match_id=m.id)
    t = asyncio.create_task(_guard(m.id))
    TASKS.add(t)
    t.add_done_callback(TASKS.discard)
    return m


async def _guard(mid: str):
    try:
        await run_match(mid)
    except Exception:
        log.exception("match %s crashed; cancelling without rewards", mid)
        await cancel_match(mid, "ENGINE_ERROR")


# ---------- main loop ----------
async def _abandoned(mid: str, uids: list[str]) -> str | None:
    conn = await get_redis().hgetall(f"m:{mid}:conn")
    w = settings.reconnect_window_seconds * 1000
    gone = [u for u in uids if conn.get(u, "1") != "1" and ms() - int(conn[u]) > w]
    return gone[0] if len(gone) == 1 else None


async def scoreboard(mid: str) -> list[dict]:
    r = get_redis()
    st, sc = await r.hgetall(f"m:{mid}"), await r.hgetall(f"m:{mid}:s")
    conn = await r.hgetall(f"m:{mid}:conn")
    asked = int(st.get("asked", 0))  # questions already revealed
    rows = []
    for p in json.loads(st["players"]):
        u = p["user_id"]
        g = lambda k: int(sc.get(f"{u}:{k}", 0))
        ans = g("answered")
        rows.append({**p, "score": g("score"), "correct": g("correct"), "incorrect": ans - g("correct"),
                     "unanswered": max(0, asked - ans), "accuracy": accuracy(g("correct"), ans),
                     "avg_response_ms": round(g("rt") / ans) if ans else None,
                     "connected": conn.get(u, "1") == "1"})
    rows.sort(key=lambda x: (-x["score"], -x["correct"], x["avg_response_ms"] if x["avg_response_ms"] is not None
                             else 1 << 60))
    for i, x in enumerate(rows):
        x["rank"] = i + 1
    return rows


async def run_match(mid: str):
    r = get_redis()
    rules = await get_rules()
    st = await r.hgetall(f"m:{mid}")
    room_id, count = st["room_id"], int(st["count"])
    duration_ms, starts_at = int(st["duration"]) * 1000, int(st["starts_at"])
    uids = [p["user_id"] for p in json.loads(st["players"])]
    per_ms = duration_ms // count
    await _sleep_until(starts_at)
    match_end = starts_at + duration_ms  # hard cap: nothing is ever scheduled past this
    await r.hset(f"m:{mid}", mapping={"status": "IN_PROGRESS", "match_end": match_end})
    async with SessionLocal() as s:
        m = await s.get(Match, mid)
        m.status, m.started_at = "IN_PROGRESS", dt(starts_at)
        room = await s.get(Room, room_id)
        room.status = "IN_PROGRESS"
        await s.commit()
    reason, abandoned_by = "COMPLETED", None
    for i in range(count):
        t0 = ms()
        if t0 >= match_end:
            break
        if (abandoned_by := await _abandoned(mid, uids)):
            reason = "ABANDONED"
            break
        pause = min(int(rules["reveal_pause_ms"]), int(per_ms * 0.2))
        deadline = min(t0 + per_ms - pause, match_end)
        qj = json.loads(await r.lindex(f"m:{mid}:q", i))
        await r.hset(f"m:{mid}", mapping={"idx": i, "qid": qj["id"], "qstart": t0, "qdeadline": deadline,
                                          "window": deadline - t0, "qclosed": 0})
        await r.rpush(f"m:{mid}:qt", json.dumps({"order": i, "qid": qj["id"], "at": t0, "deadline": deadline}))
        await publish(room_id, "match.question", {**_public_q(qj, i, count), "activated_at_ms": t0,
                                                  "deadline_ms": deadline, "server_now_ms": t0}, match_id=mid)
        while ms() < deadline and await r.hlen(f"m:{mid}:ans:{i}") < len(uids):
            await asyncio.sleep(0.02)
        timed_out = ms() >= deadline
        await r.hset(f"m:{mid}", "qclosed", 1)
        if timed_out:
            await asyncio.sleep(0.03)  # let in-flight accepted answers land
        await _reveal(mid, room_id, i, qj, uids, deadline, timed_out)
        if i < count - 1 and ms() < match_end:
            await _sleep_until(min(ms() + pause, match_end))
    await finish_match(mid, reason, abandoned_by)


async def _reveal(mid, room_id, i, qj, uids, deadline, timed_out):
    r = get_redis()
    raw = await r.hgetall(f"m:{mid}:ans:{i}")
    results, missing = {}, []
    for u in uids:
        a = json.loads(raw[u]) if u in raw else None
        if a and a["at"] <= deadline:
            pipe = r.pipeline()
            pipe.hincrby(f"m:{mid}:s", f"{u}:answered", 1)
            pipe.hincrby(f"m:{mid}:s", f"{u}:score", a["pts"])
            pipe.hincrby(f"m:{mid}:s", f"{u}:bonus", a["bonus"])
            pipe.hincrby(f"m:{mid}:s", f"{u}:rt", a["rt"])
            if a["ok"]:
                pipe.hincrby(f"m:{mid}:s", f"{u}:correct", 1)
            pipe.rpush(f"m:{mid}:log", json.dumps({"order": i, "qid": qj["id"], "uid": u, "opt": qj["map"][a["opt"]],
                                                   "ok": a["ok"], "rt": a["rt"], "pts": a["pts"], "at": a["at"]}))
            await pipe.execute()
            results[u] = {"selected": a["opt"], "is_correct": a["ok"], "points": a["pts"], "response_ms": a["rt"]}
        else:
            results[u] = {"selected": None, "is_correct": False, "points": 0, "response_ms": None}
            missing.append(u)
    await r.hset(f"m:{mid}", "asked", i + 1)
    if missing and timed_out:
        await publish(room_id, "match.question_timeout", {"question_id": qj["id"], "index": i,
                                                          "unanswered_user_ids": missing}, match_id=mid)
    await publish(room_id, "match.answer_result", {"question_id": qj["id"], "index": i, "correct_option": qj["correct"],
                                                   "explanation": qj["explanation"], "results": results}, match_id=mid)
    await publish(room_id, "match.score_update", {"index": i, "scoreboard": await scoreboard(mid)}, match_id=mid)


# ---------- answers ----------
async def submit_answer(mid: str, user_id: str, question_id: str, option: str, request_id: str) -> dict:
    t = ms()  # server receive time is the only clock that counts
    r = get_redis()
    st = await r.hgetall(f"m:{mid}")
    if not st or st.get("status") != "IN_PROGRESS":
        raise ArenaError("MATCH_NOT_ACTIVE", "Match is not in progress")
    uids = [p["user_id"] for p in json.loads(st["players"])]
    if user_id not in uids:
        raise ArenaError("FORBIDDEN", "Not a player in this match", 403)
    if option not in LETTERS:
        raise ArenaError("INVALID_OPTION", "option must be A-D")
    if question_id != st.get("qid") or st.get("qclosed") != "0":
        raise ArenaError("QUESTION_INACTIVE", "That question is not active")
    if t >= int(st["qdeadline"]) or t >= int(st["match_end"]):
        raise ArenaError("TOO_LATE", "Answer window closed")
    if not await r.sadd(f"m:{mid}:req", f"{user_id}:{request_id}"):
        return {"duplicate": True, "question_id": question_id}  # replayed message: idempotent no-op
    i = int(st["idx"])
    qj = json.loads(await r.lindex(f"m:{mid}:q", i))
    rules = await get_rules()
    rt = t - int(st["qstart"])
    ok = option == qj["correct"]
    pts, bonus = points_for(ok, rt, int(st["window"]), rules["base_points"], rules["max_speed_bonus"])
    if not await r.hsetnx(f"m:{mid}:ans:{i}", user_id, json.dumps({"opt": option, "at": t, "rt": rt, "ok": ok,
                                                                    "pts": pts, "bonus": bonus})):
        raise ArenaError("ALREADY_ANSWERED", "One answer per question")
    await publish(st["room_id"], "match.answer_received", {"question_id": question_id, "request_id": request_id},
                  to=user_id, match_id=mid)  # no correctness leaked before the window closes
    return {"accepted": True, "question_id": question_id}


# ---------- presence / snapshot ----------
async def match_for_room(room_id: str) -> str | None:
    return await get_redis().get(f"room:{room_id}:match")


async def set_presence(mid: str, user_id: str, connected: bool):
    await get_redis().hset(f"m:{mid}:conn", user_id, "1" if connected else str(ms()))


async def snapshot(mid: str, user_id: str) -> dict:
    r = get_redis()
    st = await r.hgetall(f"m:{mid}")
    if not st:
        raise ArenaError("NOT_FOUND", "Match state not available", 404)
    snap = {"match_id": mid, "status": st["status"], "server_now_ms": ms(), "starts_at_ms": int(st["starts_at"]),
            "question_count": int(st["count"]), "duration_seconds": int(st["duration"]),
            "scoreboard": await scoreboard(mid), "current_question": None}
    if st["status"] == "IN_PROGRESS" and int(st["idx"]) >= 0 and st.get("qclosed") == "0":
        i = int(st["idx"])
        qj = json.loads(await r.lindex(f"m:{mid}:q", i))
        mine = await r.hget(f"m:{mid}:ans:{i}", user_id)
        snap["current_question"] = {**_public_q(qj, i, int(st["count"])), "activated_at_ms": int(st["qstart"]),
                                    "deadline_ms": int(st["qdeadline"]), "already_answered": mine is not None}
    return snap


# ---------- completion ----------
async def finish_match(mid: str, reason: str, abandoned_by: str | None = None):
    r = get_redis()
    if not await r.set(f"m:{mid}:finish", 1, nx=True, ex=3600):
        return  # someone else is finishing: exactly-once
    rules = await get_rules()
    st, sc = await r.hgetall(f"m:{mid}"), await r.hgetall(f"m:{mid}:s")
    uids = [p["user_id"] for p in json.loads(st["players"])]
    asked = int(st.get("asked", 0))
    per = {}
    for u in uids:
        g = lambda k: int(sc.get(f"{u}:{k}", 0))
        ans = g("answered")
        per[u] = {"user_id": u, "score": g("score"), "correct": g("correct"), "answered": ans, "bonus": g("bonus"),
                  "unanswered": max(0, int(st["count"]) - ans), "avg_rt": (g("rt") / ans) if ans else None}
    a, b = (per[u] for u in uids)
    winner = decide_winner(a, b)
    if reason == "ABANDONED" and abandoned_by:
        winner = next(u for u in uids if u != abandoned_by)
    reward = {u: ("DRAW" if winner is None else "WIN" if u == winner else "LOSS") for u in uids}
    pts_for = {"WIN": rules["reward_win"], "LOSS": rules["reward_loss"], "DRAW": rules["reward_draw"]}
    log_rows = [json.loads(x) for x in await r.lrange(f"m:{mid}:log", 0, -1)]
    qts = [json.loads(x) for x in await r.lrange(f"m:{mid}:qt", 0, -1)]
    async with SessionLocal() as s:
        m = await s.get(Match, mid)
        if m.status in ("COMPLETED", "CANCELLED"):
            return
        m.status, m.ended_at, m.winner_id, m.end_reason = "COMPLETED", dt(ms()), winner, reason
        mps = {x.user_id: x for x in (await s.execute(select(MatchPlayer).where(MatchPlayer.match_id == mid))).scalars()}
        stats = {x.user_id: x for x in (await s.execute(select(PlayerStats).where(PlayerStats.user_id.in_(uids)))).scalars()}
        old_rating = {u: stats[u].rating for u in uids}
        for u in uids:
            p, mp, ps = per[u], mps[u], stats[u]
            acc = accuracy(p["correct"], p["answered"])
            mp.final_score, mp.correct_answers, mp.incorrect_answers = p["score"], p["correct"], p["answered"] - p["correct"]
            mp.unanswered, mp.accuracy, mp.average_response_time = p["unanswered"], acc, p["avg_rt"]
            mp.speed_bonus, mp.result, mp.points_earned = p["bonus"], reward[u], pts_for[reward[u]]
            n = ps.matches_played
            ps.average_accuracy = round((ps.average_accuracy * n + acc) / (n + 1), 2)
            ps.matches_played = n + 1
            ps.highest_accuracy = max(ps.highest_accuracy, acc)
            ps.total_correct += p["correct"]
            ps.total_incorrect += p["answered"] - p["correct"]
            ps.best_match_score = max(ps.best_match_score, p["score"])
            ps.total_points += pts_for[reward[u]]
            if reward[u] == "WIN":
                ps.wins, ps.current_streak = ps.wins + 1, ps.current_streak + 1
                ps.longest_streak = max(ps.longest_streak, ps.current_streak)
            else:
                ps.current_streak = 0
                if reward[u] == "LOSS":
                    ps.losses += 1
                else:
                    ps.draws += 1
            opp = next(x for x in uids if x != u)
            sc_ = {"WIN": 1, "DRAW": .5, "LOSS": 0}[reward[u]]
            ps.rating = round(old_rating[u] + 32 * (sc_ - 1 / (1 + 10 ** ((old_rating[opp] - old_rating[u]) / 400))))
            try:
                async with s.begin_nested():
                    s.add(PointsTransaction(user_id=u, source_type="MATCH", source_id=mid,
                                            transaction_type=f"MATCH_{reward[u]}", points=pts_for[reward[u]]))
            except IntegrityError:
                log.warning("duplicate reward blocked for %s/%s", u, mid)
        for row in log_rows:
            s.add(MatchAnswer(match_id=mid, question_id=row["qid"], user_id=row["uid"], selected_option=row["opt"],
                              is_correct=row["ok"], response_time_ms=row["rt"], points_awarded=row["pts"],
                              submitted_at=dt(row["at"])))
        for q in qts:
            mq = (await s.execute(select(MatchQuestion).where(MatchQuestion.match_id == mid,
                                                              MatchQuestion.question_order == q["order"]))).scalar_one()
            mq.activated_at, mq.deadline_at = dt(q["at"]), dt(q["deadline"])
        room = await s.get(Room, m.room_id)
        room.status = "COMPLETED"
        await s.commit()
    await r.hset(f"m:{mid}", mapping={"status": "COMPLETED", "asked": asked})
    board = await scoreboard(mid)
    await publish(st["room_id"], "match.completed",
                  {"match_id": mid, "winner_id": winner, "is_draw": winner is None, "reason": reason,
                   "scoreboard": board, "rewards": {u: {"result": reward[u], "arena_points": pts_for[reward[u]]}
                                                    for u in uids}}, match_id=mid)
    for k in ("", ":q", ":s", ":conn", ":log", ":qt", ":req"):
        await r.expire(f"m:{mid}{k}", 600)


async def cancel_match(mid: str, reason: str):
    """Interrupted/crashed match: no rewards, no stats changes."""
    r = get_redis()
    st = await r.hgetall(f"m:{mid}")
    async with SessionLocal() as s:
        m = await s.get(Match, mid)
        if not m or m.status in ("COMPLETED", "CANCELLED"):
            return
        m.status, m.ended_at, m.end_reason = "CANCELLED", dt(ms()), reason
        if m.room_id and (room := await s.get(Room, m.room_id)):
            room.status = "CANCELLED"
        await s.commit()
    if st:
        await r.hset(f"m:{mid}", "status", "CANCELLED")
        await publish(st["room_id"], "match.cancelled", {"match_id": mid, "reason": reason}, match_id=mid)


async def reconcile():
    """Startup recovery: DB says live but Redis lost the state (or no owner) => cancel without rewards."""
    r = get_redis()
    async with SessionLocal() as s:
        ids = (await s.execute(select(Match.id).where(Match.status.in_(("STARTING", "IN_PROGRESS"))))).scalars().all()
    n = 0
    for mid in ids:
        st = await r.hgetall(f"m:{mid}")
        orphan = st and st.get("status") == "IN_PROGRESS" and int(st.get("match_end", 0)) < ms() - 10_000
        if not st or orphan or st.get("status") in ("COMPLETED", "CANCELLED"):
            await cancel_match(mid, "RECOVERY")
            n += 1
    return n
