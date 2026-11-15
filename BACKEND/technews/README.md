# Tech News

FastAPI + SQLAlchemy 2 + Alembic + Celery/Redis. `docker compose up` (copy `.env.example` → `.env` first), or `pytest` (42 tests, no network/Redis/Postgres needed).

## Frontend

The React/Vite frontend lives in `frontend/` and reads the public news API. Start the API first, then run:

```powershell
cd frontend
npm install
npm run dev
```

By default it calls `http://localhost:8000`. Set `VITE_API_URL` before `npm run dev` when the API is hosted elsewhere. The page shows loading, empty, and API error states without fabricating news.

## Integrating with your existing app (I could not inspect it)
1. `app/models.py::User` is a **stub**. Point it at your real users table (needs `id`, `role`, `is_active`; `display_name` optional) and delete migration `0001_users_stub`.
2. `app/security.py` expects a JWT signed with your `JWT_SECRET`/`JWT_ALGORITHM`, claim `sub` = user id. Admin = `users.role == "admin"` (read from DB, not the token).
3. Endpoints per your spec, plus `GET /api/news/collections/{ai-ml|developer-discoveries|research-open-source}` and `GET /api/news/liked`.

## Source status
| Source | Access | Default | Notes |
|---|---|---|---|
| Hacker News, GitHub, DEV, arXiv, Hugging Face, Lobsters | free | enabled | GitHub: set `GITHUB_TOKEN` for sane limits |
| TechCrunch, ScienceDaily, Google News | terms-restricted | **disabled** | I can't verify current feed terms. Read them, then `ENABLE_TERMS_RESTRICTED_SOURCES=true` |
| Reddit | approval required | disabled | needs OAuth creds + `REDDIT_COMMERCIAL_APPROVED=true` |
| X | paid API | disabled | needs `X_ENABLED=true` + bearer token on a tier that includes search |

## Known limitations (read these)
- **Never run against live APIs.** Connectors are tested only against mocked responses; field names (esp. Hugging Face `sort=trendingScore`, GitHub search) should be smoke-tested once with a real run.
- **Cold start**: with the spec weights, ~85% of the trending score comes from on-site engagement, so a new site has near-zero signal. `W_EXTERNAL` (HN score, stars, etc.) exists but defaults to 0; try 0.15.
- **Dedup is lexical** (URL, normalised title, conservative fuzzy match; titles differing in any number never merge). Paraphrased headlines of the same story will NOT merge. Embedding similarity is not implemented.
- **Google News links** mostly stay as `news.google.com` redirects; resolving them needs unofficial decoding, which I did not implement. They're upgraded to the publisher URL when another source finds the same story.
- Relevance is keyword-based unless the optional AI layer is on; expect misclassification.
- API credentials are env-only; the admin API shows connector status but does not accept secrets (deliberate).
- Per-source rate-limit quota display is not implemented; rate-limit *handling* is.
- Migration verified on SQLite only.
- Third-party thumbnails are not stored unless `SHOW_THIRD_PARTY_THUMBNAILS=true`.
- Beat: one instance only. Schedule is code-defined (no DB scheduler) and a Redis lock prevents overlapping runs.
