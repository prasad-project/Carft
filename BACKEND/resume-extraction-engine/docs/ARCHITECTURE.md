# Architecture

```
upload ─▶ validate ─▶ [job store + private file] ─▶ extract (background thread)
   1 validate  2 read  3 detect type  4 extract text (PyMuPDF / python-docx)
   5 detect scanned pages  6 OCR (pdf2image → OpenCV → Tesseract) only on pages that need it
   7 sections  8 personal  9 education+experience  10 skills+projects  11 other  12 JSON
```

* `services/` – I/O: validation, PDF/DOCX extraction, OCR, preprocessing, pipeline, job store.
* `parser/` – pure functions over `Line(text, page, ocr_conf)`; each module is independently testable.
* `schemas/` – Pydantic models; `PUT /result` re-validates user corrections against them.
* No database: jobs live in memory; uploads in a private (0700/0600) temp dir. Both are deleted after
  `RETENTION_MINUTES`, on `DELETE`, and at startup/shutdown. A server restart loses all results.

## Confidence (deterministic)
* `extraction_metadata.field_traces`: value, page, source line, rule name, confidence, status.
* Email 0.99. Phone: 0.95 Indian mobile, 0.93 10-digit starting 6-9, 0.90 `+`+10-15 digits, 0.85 US format,
  else 0.60; +0.05 if labelled.
* Name = 0.20 base +0.30 first usable line +0.20 two/three tokens +0.15 capitalised +0.25 token in email.
* Entries = weighted completeness of fields the rules found (experience: title .30, company .30, dates .25, body .15).
* OCR lines: confidence is capped at Tesseract's mean word confidence for that line.
* `status = verified` only if confidence ≥ 0.85, else `needs_review`.

## Skills
Confirmed skills come only from skills sections. Mentions elsewhere go to `skills.inferred_from_context`.
Ambiguous names (C, R, Go, Spring, Requests, Excel, ...) and soft skills never match outside a skills section.

## Known limitations
* Section detection is exact-match on a heading dictionary. Non-standard headings ("Career Highlights",
  "Where I studied") send their content to `unclassified_text` (kept, not categorised).
* Entry boundaries in free-form experience/project layouts are heuristic. Review `needs_review` items.
* OCR depends on scan quality; only English is installed by default.
* Single process: job state and rate limiting are in memory; multiple workers need shared state first.
* The PDF JavaScript scan is byte-level and misses objects inside compressed streams. Enable ClamAV
  (`CLAMAV_ENABLED=true`, `clamscan` installed) for real malware scanning.
