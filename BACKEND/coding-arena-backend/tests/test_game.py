import os
import tempfile
import uuid

_tmp = tempfile.mkdtemp()
os.environ.update(DATABASE_URL=f"sqlite+aiosqlite:///{_tmp}/t.db", REDIS_URL="fakeredis://",
                  START_COUNTDOWN_SECONDS="0", JWT_SECRET="test-secret-test-secret-test-secret-123")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

from app.game.scoring import accuracy, decide_winner, points_for  # noqa: E402
from app.main import app  # noqa: E402


# ---------- unit ----------
def test_scoring_rules():
    assert points_for(True, 0, 10_000, 10, 5) == (15, 5)
    assert points_for(True, 10_000, 10_000, 10, 5) == (10, 0)
    assert points_for(False, 0, 10_000, 10, 5) == (0, 0)  # never negative
    assert accuracy(0, 0) == 0 and accuracy(8, 10) == 80


def test_winner_tiebreaks():
    a = {"user_id": "a", "score": 10, "correct": 1, "avg_rt": 900}
    b = {"user_id": "b", "score": 10, "correct": 1, "avg_rt": 500}
    assert decide_winner(a, b) == "b"  # lower avg response time
    assert decide_winner(a, {**a, "user_id": "b"}) is None  # draw
    assert decide_winner({**a, "correct": 2}, b) == "a"
    assert decide_winner({**a, "score": 20}, b) == "a"


# ---------- integration ----------
@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def login(c, name):
    r = c.post("/api/v1/auth/dev-login", json={"username": f"{name}_{uuid.uuid4().hex[:6]}" if name != "admin" else "admin"})
    d = r.json()
    return {"h": {"Authorization": f"Bearer {d['access_token']}"}, "id": d["user_id"], "token": d["access_token"]}


@pytest.fixture()
def world(client):
    admin = login(client, "admin")
    dom = client.post("/api/v1/admin/domains", headers=admin["h"],
                      json={"name": "T", "slug": f"t-{uuid.uuid4().hex[:8]}"}).json()["id"]
    qs = [{"domain_id": dom, "question_text": f"{dom} question {i}", "difficulty": ["EASY", "MEDIUM", "HARD"][i % 3],
           "options": [{"id": L, "text": f"opt{L}{i}"} for L in "ABCD"], "correct_option": "ABCD"[i % 4],
           "explanation": "because", "status": "PUBLISHED"} for i in range(34)]
    assert client.post("/api/v1/admin/questions/import", headers=admin["h"], json=qs).json()["imported"] == 34
    return {"admin": admin, "dom": dom, "a": login(client, "alice"), "b": login(client, "bob")}


def make_room(c, w, count=5, ready=True):
    room = c.post("/api/v1/rooms", headers=w["a"]["h"], json={"domain_id": w["dom"], "duration_seconds": 60,
                                                              "question_count": count}).json()
    assert c.post("/api/v1/rooms/join", headers=w["b"]["h"], json={"room_code": room["room_code"]}).status_code == 200
    if ready:
        c.post(f"/api/v1/rooms/{room['id']}/ready", headers=w["b"]["h"], json={"ready": True})
    return room


def ws_url(room_id, who):
    return f"/ws/game/{room_id}?token={who['token']}"


def until(ws, typ, limit=200):
    seen = []
    for _ in range(limit):
        e = ws.receive_json()
        seen.append(e)
        if e["type"] == typ:
            return e, seen
    raise AssertionError(f"never saw {typ}: {[x['type'] for x in seen]}")


def answer_key(c, w):
    rows = c.get(f"/api/v1/admin/questions?domain_id={w['dom']}&limit=200", headers=w["admin"]["h"]).json()
    return {q["id"]: {o["id"]: o["text"] for o in q["options"]}[q["correct_option"]] for q in rows}


def test_room_rules(client, world):
    w = world
    room = make_room(client, w, ready=False)
    assert len(room["room_code"]) == 6 and room["invite_link"].endswith(room["room_code"])
    c3 = login(client, "carol")
    assert client.post("/api/v1/rooms/join", headers=c3["h"], json={"room_code": room["room_code"]}).status_code == 409  # full
    assert client.post("/api/v1/rooms/join", headers=c3["h"], json={"room_code": "ZZZZZZ"}).status_code == 404
    assert client.get(f"/api/v1/rooms/{room['id']}", headers=c3["h"]).status_code == 403
    assert client.post(f"/api/v1/rooms/{room['id']}/start", headers=w["b"]["h"]).status_code == 403  # host only
    assert client.post(f"/api/v1/rooms/{room['id']}/start", headers=w["a"]["h"]).status_code == 409  # b not ready
    assert client.post(f"/api/v1/rooms/{room['id']}/cancel", headers=w["b"]["h"]).status_code == 403
    assert client.post(f"/api/v1/rooms/{room['id']}/cancel", headers=w["a"]["h"]).json()["status"] == "CANCELLED"
    small = client.post("/api/v1/rooms", headers=w["a"]["h"], json={"domain_id": w["dom"], "duration_seconds": 90})
    assert small.status_code == 422  # unsupported duration


def test_ws_auth(client, world):
    room = make_room(client, world)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/game/{room['id']}?token=garbage"):
            pass
    outsider = login(client, "mallory")
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(ws_url(room["id"], outsider)):
            pass


def test_full_match(client, world):
    w = world
    key = answer_key(client, w)
    room = make_room(client, w, count=5)
    with client.websocket_connect(ws_url(room["id"], w["a"])) as wa, client.websocket_connect(ws_url(room["id"], w["b"])) as wb:
        until(wa, "room.state"), until(wb, "room.state")
        assert client.post(f"/api/v1/rooms/{room['id']}/start", headers=w["a"]["h"]).status_code == 200
        seen_q = {"a": [], "b": []}
        for i in range(5):
            qa, _ = until(wa, "match.question")
            qb, _ = until(wb, "match.question")
            assert qa["payload"] == qb["payload"] or qa["payload"]["question_id"] == qb["payload"]["question_id"]
            assert qa["payload"]["deadline_ms"] == qb["payload"]["deadline_ms"]  # synchronized deadline
            assert "correct" not in str(qa["payload"]).lower()  # no answer leakage
            seen_q["a"].append(qa["payload"]["question_id"])
            seen_q["b"].append(qb["payload"]["question_id"])
            qid, opts = qa["payload"]["question_id"], qa["payload"]["options"]
            right = next(o["id"] for o in opts if o["text"] == key[qid])
            wrong = next(o["id"] for o in opts if o["id"] != right)
            wa.send_json({"type": "match.answer", "payload": {"question_id": qid, "option": right, "request_id": f"r{i}"}})
            wb.send_json({"type": "match.answer", "payload": {"question_id": qid, "option": wrong, "request_id": f"r{i}"}})
            res, _ = until(wa, "match.answer_result")
            assert res["payload"]["correct_option"] == right
        assert seen_q["a"] == seen_q["b"] and len(set(seen_q["a"])) == 5  # identical order, no repeats
        done, _ = until(wa, "match.completed")
        until(wb, "match.completed")
    p = done["payload"]
    assert p["winner_id"] == w["a"]["id"] and not p["is_draw"]
    board = {r["user_id"]: r for r in p["scoreboard"]}
    assert board[w["a"]["id"]]["correct"] == 5 and board[w["a"]["id"]]["score"] >= 50
    assert board[w["b"]["id"]]["score"] == 0 and board[w["b"]["id"]]["incorrect"] == 5
    assert p["rewards"][w["a"]["id"]]["arena_points"] == 50 and p["rewards"][w["b"]["id"]]["arena_points"] == 10
    # persisted results, history, stats, points
    mid = p["match_id"]
    res = client.get(f"/api/v1/matches/{mid}/results", headers=w["a"]["h"]).json()
    assert res["winner_id"] == w["a"]["id"]
    assert client.get(f"/api/v1/matches/{mid}/results", headers=login(client, "eve")["h"]).status_code == 404
    st = client.get("/api/v1/players/me/stats", headers=w["a"]["h"]).json()
    assert st["wins"] == 1 and st["total_points"] == 50 and st["current_streak"] == 1 and st["average_accuracy"] == 100
    sb = client.get("/api/v1/players/me/stats", headers=w["b"]["h"]).json()
    assert sb["losses"] == 1 and sb["total_points"] == 10
    act = client.get("/api/v1/players/me/activity?result=WIN", headers=w["a"]["h"]).json()
    assert act["total"] == 1 and act["items"][0]["opponent"]["user_id"] == w["b"]["id"]
    assert len(client.get("/api/v1/players/me/points/history", headers=w["a"]["h"]).json()) == 1  # exactly once


def test_duplicate_and_invalid_answers(client, world):
    w = world
    room = make_room(client, w, count=5)
    with client.websocket_connect(ws_url(room["id"], w["a"])) as wa, client.websocket_connect(ws_url(room["id"], w["b"])) as wb:
        until(wa, "room.state"), until(wb, "room.state")
        client.post(f"/api/v1/rooms/{room['id']}/start", headers=w["a"]["h"])
        q, _ = until(wa, "match.question")
        qid = q["payload"]["question_id"]
        send = lambda ws, **p: ws.send_json({"type": "match.answer", "payload": p})
        send(wa, question_id=qid, option="A", request_id="x1")
        until(wa, "match.answer_received")
        send(wa, question_id=qid, option="B", request_id="x2")  # second answer, new request id
        err, _ = until(wa, "match.error")
        assert err["payload"]["code"] == "ALREADY_ANSWERED"
        send(wa, question_id=qid, option="A", request_id="x1")  # replayed message: silently ignored
        send(wa, question_id="not-active", option="A", request_id="x3")
        err, _ = until(wa, "match.error")
        assert err["payload"]["code"] == "QUESTION_INACTIVE"
        send(wa, question_id=qid, option="Z", request_id="x4")
        err, _ = until(wa, "match.error")
        assert err["payload"]["code"] == "BAD_PAYLOAD"
        # spoofing: B cannot answer on behalf of A, answers are bound to the socket's authenticated user
        send(wb, question_id=qid, option="C", request_id="x1")
        until(wb, "match.answer_received")  # B's own answer, independent of A's request id
        until(wa, "match.answer_result")
        # reconnect mid-match gets a full snapshot
        with client.websocket_connect(ws_url(room["id"], w["b"])) as wb2:
            snap, _ = until(wb2, "match.state")
            assert snap["payload"]["scoreboard"] and "correct_option" not in str(snap["payload"])
