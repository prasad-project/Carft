# Coding Arena backend (MCQ duels)

FastAPI + SQLAlchemy (PostgreSQL in prod, SQLite in dev) + Redis (live match state, Pub/Sub). MCQ only: no IDE, no code execution.

## Run
```bash
pip install -r requirements.txt
python scripts/seed.py                     # 55 domains + 45 generated Python questions
uvicorn app.main:app --reload              # open http://localhost:8000  (two browser tabs = two players)
pytest -q                                  # 6 tests
```
Dev defaults: SQLite + in-process fakeredis (single process only). Prod: set `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `ENABLE_DEV_LOGIN=false` (see `.env.example`, `docker-compose.yml`).
`/api/v1/auth/dev-login` is passwordless and dev-only; plug a real IdP into `app/core/security.py` for prod. Username `admin` gets admin rights in dev.

## Built in this pass
Auth/JWT, domains (admin-extensible), admin question bank (validation, dedupe, archive, JSON import, configurable scoring/reward rules), private rooms (code, join, ready, settings, start, leave, cancel, expiry), WebSocket hub over Redis Pub/Sub, server-authoritative engine (timers, scoring with speed bonus, tie-break winner, draw), live scoreboard, reconnect snapshot, abandonment forfeit, exactly-once rewards (unique constraint), Elo-style rating, stats, activity (paginated + filters), points history, startup reconciliation, per-user WS rate limit, static game page at `/`.

## Not built yet
Random matchmaking, daily challenges, leaderboards, Celery workers, Alembic migrations (tables are created with `create_all`), MATCH_EVENTS persistence, load tests. Admin rules live in Redis (`PUT /api/v1/admin/rules`) and are lost if Redis is wiped.

## Timing model
Per-question window = `duration / question_count` minus a reveal pause (default 300 ms, capped at 20%). Match end is a hard cap; the engine never schedules past it; unreached questions count as unanswered. A question closes early once both players answered. Pool must have >= max(question_count, 30) published questions.

## WebSocket
`/ws/game/{room_id}?token=JWT` (channel is the room; match events carry `match_id`). Envelope: `{event_id, room_id, match_id, seq, ts, type, payload}`.

Client -> server: `room.join`, `room.ready {ready}`, `room.start`, `room.leave`, `match.answer {question_id, option: A-D, request_id}`, `match.reconnect`, `match.ping`.
Server -> client: `room.state`, `room.player_joined|player_ready|player_left`, `match.started`, `match.question`, `match.answer_received` (to sender only, no correctness), `match.question_timeout`, `match.answer_result` (reveals correct option + explanation to both), `match.score_update`, `match.player_disconnected|reconnected`, `match.state` (reconnect snapshot), `match.completed`, `match.cancelled`, `match.error {code,message}`, `match.pong`.

Rules: server receive time decides eligibility; one answer per player per question; replayed `request_id` is a no-op; correct answers are never sent before reveal; options are shuffled deterministically per match, same for both players.

## REST (`/api/v1`)
auth: `POST /auth/dev-login`, `GET /auth/me` · domains: `GET /domains`, `GET /domains/{id}/questions/count` · rooms: `POST /rooms`, `POST /rooms/join`, `GET|PATCH /rooms/{id}`, `POST /rooms/{id}/ready|start|leave|cancel` · matches: `GET /matches/{id}`, `/results`, `/history` · players: `GET /players/me/stats|activity|points|points/history|performance` · admin: `POST /admin/domains`, `POST|GET /admin/questions`, `PATCH|DELETE /admin/questions/{id}`, `POST /admin/questions/import`, `GET|PUT /admin/rules`, `GET /admin/analytics`.

## Scaling note
Match loops run as asyncio tasks in the process that started the match; Redis holds the state and fans events out, so sockets can be on any instance, but a crashed owner cancels its match on recovery (no rewards). Moving loop ownership to workers is the next step.
