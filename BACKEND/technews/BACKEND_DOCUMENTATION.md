# Tech News Backend Documentation

This document describes only the backend. It does not document the React/Vite frontend.

## 1. Backend purpose

The backend collects technology stories from configured external sources, normalizes and
categorizes them, removes duplicates, stores them in PostgreSQL, and exposes public and
administrator APIs.

The main backend stack is:

- **FastAPI** - HTTP API framework.
- **SQLAlchemy 2** - database models and queries.
- **Alembic** - database migrations.
- **PostgreSQL** - production database.
- **Redis** - Celery broker/backend, rate-limit storage, and ingestion lock.
- **Celery worker** - executes ingestion and ranking tasks.
- **Celery Beat** - creates scheduled tasks.
- **httpx** - outbound HTTP requests to source APIs and feeds.
- **feedparser** - RSS feed parsing.
- **Pydantic Settings** - environment configuration.

## 2. Important backend files

| File | Responsibility |
|---|---|
| `app/main.py` | Creates the FastAPI application, middleware, startup seeding, and routers |
| `app/config.py` | Environment-backed settings and default values |
| `app/db.py` | SQLAlchemy engine, sessions, and database dependency |
| `app/models.py` | Database models and relationships |
| `app/api/public.py` | Public news, search, collection, interaction, and comment endpoints |
| `app/api/admin.py` | Protected administration and ingestion endpoints |
| `app/celery_app.py` | Celery configuration and scheduled beat jobs |
| `app/tasks.py` | Celery task definitions and queue helpers |
| `app/services/ingest.py` | Source fetching, validation, deduplication, categorization, and saving |
| `app/services/dedupe.py` | URL/title normalization and duplicate detection |
| `app/services/categorize.py` | Category, relevance, and tag assignment |
| `app/services/ranking.py` | Trending and editorial ranking calculations |
| `app/connectors/` | External source connector implementations |
| `alembic/versions/` | Database migration history |
| `docker-compose.yml` | API, worker, beat, PostgreSQL, and Redis services |

## 3. Runtime architecture

The normal production flow is:

1. **Celery Beat** creates a scheduled ingestion task.
2. **Redis** delivers the task to a Celery worker.
3. The worker calls the enabled connectors.
4. Each connector fetches source data and converts it to a common `RawItem`.
5. The ingestion service validates URLs and titles.
6. Existing source IDs and duplicate URLs/titles are detected.
7. New items are categorized, tagged, scored, and saved.
8. Items can be published, placed in review, or rejected.
9. Ingestion logs and source health are saved.
10. Rankings are recomputed after ingestion.

The API process and worker are separate services. The API does not perform long-running
scraping directly; it queues ingestion work through Celery.

## 4. Services and Docker

`docker-compose.yml` defines these services:

- `db`: PostgreSQL 16, database name `technews`.
- `redis`: Redis 7.
- `api`: runs migrations and starts Uvicorn on port `8000`.
- `worker`: runs `celery -A app.celery_app.celery worker -l info`.
- `beat`: runs the scheduler. Exactly one Beat instance should run.

Start the backend:

```powershell
Copy-Item .env.example .env
docker compose up -d
```

Apply migrations manually when needed:

```powershell
docker compose run --rm api alembic upgrade head
```

Health check:

```text
GET http://localhost:8000/health
```

Expected response:

```json
{"ok": true}
```

## 5. Database structure

The schema is defined in `app/models.py` and created by Alembic migration `0002`.

### Main tables

- `users`: users and administrator roles. The current model is a minimal integration stub.
- `news_articles`: normalized stories, metadata, status, scores, and counters.
- `news_sources`: connector registry, enabled state, access type, health, and errors.
- `article_sources`: every source discovery for an article, including duplicate discoveries.
- `news_categories`: allowed category slugs and names.
- `tags`: normalized article tags.
- `article_tags`: many-to-many article/tag relationship.
- `article_rankings`: rolling views, likes, comments, freshness, editorial, and trending scores.
- `article_views`: qualified viewer views with one-view-per-viewer-per-day protection.
- `article_likes`: authenticated user likes with a unique user/article constraint.
- `saved_articles`: authenticated saved stories with a unique user/article constraint.
- `article_comments`: comments and soft-delete state.
- `ingestion_jobs`: one record per scheduled or manual ingestion run.
- `ingestion_logs`: per-source result, counts, timing, and error information.
- `admin_audit_logs`: administrator actions.

### Article statuses

- `pending`: waiting for review.
- `published`: visible through public APIs.
- `rejected`: not publicly visible.
- `archived`: retained but not publicly visible.

### Content types

- `VERIFIED_NEWS`
- `DEVELOPER_DISCOVERY`
- `RESEARCH_UPDATE`
- `PRODUCT_RELEASE`
- `COMMUNITY_DISCUSSION`

## 6. Ingestion and scraping

The ingestion entry point is `run_ingestion()` in `app/services/ingest.py`.

For each enabled connector, the backend:

1. Checks whether the connector is available with the configured credentials.
2. Fetches source data with timeout, retry, and backoff settings.
3. Records a per-source ingestion log.
4. Validates title and HTTP(S) URL.
5. Prevents repeat imports using source external IDs.
6. Finds duplicates using canonical URL and normalized/fuzzy title matching.
7. Attaches additional discoveries to an existing article when appropriate.
8. Assigns category, relevance, tags, and optional AI summary.
9. Publishes or queues the item according to relevance and review settings.
10. Updates connector health and ingestion counts.

An item is automatically rejected when its relevance is below `MIN_RELEVANCE`.
Social-source items and flagged items normally enter `pending` review. `AUTO_PUBLISH`
controls whether non-flagged items can be published automatically.

### Enabled source connectors by default

These free connectors are enabled when reference data is first seeded:

- Hacker News
- GitHub
- DEV
- arXiv
- Hugging Face
- Lobsters

These are disabled by default:

- TechCrunch, ScienceDaily, and Google News: terms-restricted.
- Reddit: requires approved OAuth/API access.
- X: requires paid API access and a bearer token.

Third-party thumbnails are stored only when `SHOW_THIRD_PARTY_THUMBNAILS=true`.

## 7. Exact scraping schedule

The schedule is configured by:

```text
TIMEZONE=Asia/Kolkata
INGEST_HOURS=0,8,16
```

Therefore scheduled ingestion runs every day at:

- **12:00 AM IST**
- **8:00 AM IST**
- **4:00 PM IST**

At **2:50 PM IST on November 15, 2026**, the next scheduled scrape is **4:00 PM IST
on November 15, 2026**.

The schedule is defined in `app/celery_app.py` using Celery Beat. It is code-defined,
not stored in a database.

The ingestion task also uses the Redis lock `technews:ingestion:lock`, so overlapping
ingestion runs are skipped. Run exactly one Beat service.

## 8. Other scheduled job

Ranking recalculation runs every hour at minute `15`:

```text
01:15, 02:15, 03:15, ... Asia/Kolkata time
```

This is the `app.tasks.rerank` task and is configured in `app/celery_app.py`.

## 9. Manual ingestion

An administrator can queue all enabled sources:

```text
POST /api/admin/ingestion/run
```

An administrator can queue one source:

```text
POST /api/admin/sources/{source_id}/fetch
```

These endpoints return `202 Accepted` with a queued job ID. The worker performs the
actual work asynchronously.

Check ingestion status:

```text
GET /api/admin/ingestion/status
```

View ingestion history:

```text
GET /api/admin/ingestion/logs
GET /api/admin/ingestion/logs?source=hackernews
```

The status response includes the configured timezone, schedule hours, current running
state, last job, and the next three scheduled runs.

## 10. Public API

The public router prefix is `/api/news`.

### News listing and discovery

```text
GET /api/news
GET /api/news/latest
GET /api/news/top
GET /api/news/trending
GET /api/news/most-read
GET /api/news/most-liked
GET /api/news/most-discussed
GET /api/news/{slug}
GET /api/news/categories
GET /api/news/collections/ai-ml
GET /api/news/collections/developer-discoveries
GET /api/news/collections/research-open-source
```

Supported list filters include:

- `q`: title search.
- `category`: category slug.
- `content_type`: content classification assigned to an article.
- `tag`: tag slug.
- `sort`: `latest`, `trending`, or `top` on the main endpoint.
- `page` and `page_size`.

Only articles with status `published` are returned publicly.

### User interactions

Authenticated endpoints include:

```text
POST   /api/news/{article_id}/like
DELETE /api/news/{article_id}/like
POST   /api/news/{article_id}/save
DELETE /api/news/{article_id}/save
GET    /api/news/liked
GET    /api/news/saved
POST   /api/news/{article_id}/view
GET    /api/news/{article_id}/comments
POST   /api/news/{article_id}/comments
PATCH  /api/news/{article_id}/comments/{comment_id}
DELETE /api/news/{article_id}/comments/{comment_id}
```

JWT authentication reads the user ID from the `sub` claim. Administrator access is
checked from the database user role, not trusted from the JWT role claim.

## 11. Administrator API

All `/api/admin` routes require an active database user with `role == "admin"`.

Main administrator operations:

```text
GET    /api/admin/dashboard
GET    /api/admin/news
POST   /api/admin/news
PATCH  /api/admin/news/{article_id}
DELETE /api/admin/news/{article_id}
POST   /api/admin/news/{article_id}/publish
POST   /api/admin/news/{article_id}/reject
POST   /api/admin/news/{article_id}/archive
GET    /api/admin/sources
PATCH  /api/admin/sources/{source_id}
POST   /api/admin/sources/{source_id}/fetch
POST   /api/admin/ingestion/run
GET    /api/admin/ingestion/status
GET    /api/admin/ingestion/logs
```

## 12. Configuration

Configuration is loaded from `.env` by `app/config.py`. Important settings include:

| Setting | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | local PostgreSQL URL | Database connection |
| `REDIS_URL` | local Redis URL | Celery and locking |
| `JWT_SECRET` | `change-me` | JWT signing secret; replace in deployment |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `VIEWER_HASH_SECRET` | `change-me-too` | Anonymous viewer hashing |
| `TIMEZONE` | `Asia/Kolkata` | Scheduler timezone |
| `INGEST_HOURS` | `0,8,16` | Daily scrape hours |
| `HTTP_TIMEOUT` | `15` seconds | Connector request timeout |
| `HTTP_RETRIES` | `3` | Connector retry count |
| `HTTP_BACKOFF` | `1` second | Retry backoff |
| `AUTO_PUBLISH` | `true` | Automatic publication behavior |
| `MIN_RELEVANCE` | `0.2` | Minimum relevance threshold |
| `AI_ENABLED` | `false` | Optional AI enrichment |
| `GITHUB_TOKEN` | empty | Higher GitHub API limits |
| `ENABLE_TERMS_RESTRICTED_SOURCES` | `false` | Enable restricted feeds |
| `REDDIT_COMMERCIAL_APPROVED` | `false` | Permit Reddit connector |
| `X_ENABLED` | `false` | Permit X connector |

Never commit real secrets. Keep credentials in environment variables.

## 13. Security and reliability

- CORS is configured through `CORS_ORIGINS`.
- API requests use rate limiting.
- Admin routes require database-backed authorization.
- URLs are checked for safe HTTP(S) schemes.
- Comment HTML is stripped before storage.
- Duplicate likes, saves, and qualified views are protected by database constraints.
- A Redis lock prevents simultaneous ingestion runs.
- Connector failures are isolated so one failed source does not discard other sources.
- Celery retries ingestion task failures up to three times with backoff.
- Ingestion failures are recorded in source status and ingestion logs.

## 14. Limitations and operational notes

- Connector tests use mocked responses; real source APIs should be smoke-tested carefully.
- Source terms and API access policies must be checked before enabling restricted sources.
- Deduplication is lexical and URL-based; paraphrased stories may not always merge.
- AI enrichment is optional and disabled by default.
- The current `User` model is an integration stub and should be mapped to the existing
  application users table when deployed into another application.
- Migration verification has primarily been done with SQLite tests; production uses
  PostgreSQL through Docker.
- The backend requires PostgreSQL, Redis, one Celery worker, and exactly one Beat process
  for scheduled ingestion.

## 15. Useful operational commands

```powershell
# Start all backend services
docker compose up -d

# View service status
docker compose ps

# Follow API logs
docker compose logs -f api

# Follow worker logs
docker compose logs -f worker

# Follow scheduler logs
docker compose logs -f beat

# Stop backend services
docker compose down

# Run backend tests locally
.\.venv\Scripts\python.exe -m pytest -q
```
