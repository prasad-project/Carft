# Resume Upload & Data Extraction Engine

Local, rule-based resume parser. **No LLM, no external AI/parsing API, no database.**
PDF/DOCX in → text (embedded or OCR) → structured JSON with source page, source text, confidence and warnings.

## Run (development)
```bash
# system deps (Ubuntu/Debian): OCR + PDF rasteriser
sudo apt-get install -y tesseract-ocr poppler-utils

cd BACKEND/resume-extraction-engine/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000        # http://localhost:8000/docs

The frontend is maintained separately in the repository's `FRONTEND` directory.
It communicates with this service through the API. Set
`NEXT_PUBLIC_RESUME_API_URL=http://localhost:8000` for local development, then
run the frontend from that directory.
```
Docker (backend only): `cp .env.example .env && docker compose up --build`.

## Try it without the UI
```bash
R=$(curl -s -F "file=@sample_resumes/scanned.pdf;type=application/pdf" localhost:8000/api/v1/resumes/upload)
ID=$(echo $R | python -c "import sys,json;print(json.load(sys.stdin)['resume_id'])")
TOK=$(echo $R | python -c "import sys,json;print(json.load(sys.stdin)['owner_token'])")
curl -s -X POST -H "X-Owner-Token: $TOK" -H 'Content-Type: application/json' -d "{\"resume_id\":\"$ID\"}" localhost:8000/api/v1/resumes/extract
curl -s -H "X-Owner-Token: $TOK" localhost:8000/api/v1/resumes/$ID/status
curl -s -H "X-Owner-Token: $TOK" localhost:8000/api/v1/resumes/$ID/result
```

## API (`/api/v1/resumes`)
| Method | Path | Notes |
|---|---|---|
| POST | `/upload` | multipart `file`. Returns `resume_id` + secret `owner_token` |
| POST | `/extract` | `{resume_id}`; starts background job; also used for retry |
| GET | `/{id}/status` | real stage states, progress = done stages / 12, live detail (e.g. "OCR page 2 of 3") |
| GET | `/{id}/text` | per-page text, method (embedded/ocr), OCR confidence |
| GET/PUT | `/{id}/result` | structured JSON; PUT saves user corrections (schema-validated) |
| GET | `/{id}/download-json`, `/download-text` | `?token=` accepted for browser downloads |
| DELETE | `/{id}` | removes file + results |

Every call after upload needs `X-Owner-Token`. Wrong token and unknown id both return 404.

## Tests & evaluation
```bash
cd backend
pytest -q                      # 48 tests: parsers, PDF/DOCX/OCR, pipeline, API, security
python -m scripts.evaluate     # field precision/recall on differently-styled synthetic resumes
```
The evaluation set is tiny and written by the same author as the parser, so it is a regression signal,
**not** an accuracy claim. It deliberately includes one hard case (non-standard headings) that loses most fields.
Real-world accuracy must be measured on your own resumes before you rely on it.

## Not done / deviations from the original spec
* No PostgreSQL (you asked for none): results are in memory and expire (`RETENTION_MINUTES`).
* No user accounts: ownership = per-upload secret token. Add real auth before exposing publicly.
* Malware scanning is ClamAV-optional (`CLAMAV_ENABLED`), off by default; the built-in check only rejects PDF
  JavaScript/Launch actions and macro-enabled DOCX.
* Docling fallback is wired in but untested (not installed here).
* Edit in UI is limited to personal-information fields; other sections are read-only (the PUT API accepts any field).
* See `docs/ARCHITECTURE.md` for confidence rules and known limitations.
