# PRD — llmscrap Web App (No Desktop, No Python)

## 1. Product Summary

llmscrap Web App lets users ingest any URL that returns an index of Markdown links (for example `llms.txt`-style indexes), fetch and normalize those docs, store them, search them, and export them — fully in a web stack.

This version is **browser + web backend only**:
- No Tauri / Rust desktop shell
- No Python runtime

---

## 2. Goals

1. Accept an index URL and extract all `.md` links reliably.
2. Download and store markdown content with metadata.
3. Provide searchable project-level knowledge bases.
4. Support re-sync/incremental updates.
5. Enable export for downstream AI/RAG workflows.

## 3. Non-Goals (v1)

- Semantic vector search in first release.
- Multi-tenant enterprise RBAC.
- Browser extension and offline desktop packaging.
- Full website crawling outside index-driven ingestion.

---

## 4. Target Users

1. **Developers** building local/internal doc datasets.
2. **AI builders** needing clean markdown corpora for RAG pipelines.
3. **Technical writers/PMs** monitoring docs changes over time.

---

## 5. Core User Stories

1. As a user, I can create a “source” by entering an index URL.
2. As a user, I can run a scrape job and see live progress.
3. As a user, I can view downloaded docs and failed URLs.
4. As a user, I can search docs by keyword.
5. As a user, I can re-run sync and only fetch changed/new files.
6. As a user, I can export data as JSON/JSONL/ZIP.

---

## 6. Functional Requirements

## 6.1 Source Management
- Create, edit, delete source.
- Source fields: `name`, `indexUrl`, `defaultOutputFormat`, `syncInterval` (optional).
- URL validation and normalization.

## 6.2 Index Parsing
- Fetch index URL (text/markdown/html response).
- Extract all `.md` URLs.
- Resolve relative links against index URL.
- Deduplicate links.

## 6.3 Scrape Jobs
- Manual run + scheduled run support.
- Job states: `queued`, `running`, `completed`, `failed`, `cancelled`.
- Per-file result tracking (`success`, `failed`, status code, retry count).
- Retry policy with capped backoff.

## 6.4 Storage
- Persist:
  - source metadata
  - job metadata
  - documents (url, title, content, hash, lastFetchedAt)
  - job file events and errors
- Keep version/hash for incremental sync.

## 6.5 Search & Browse
- Full-text search over stored markdown.
- Filter by source, job, date range, status.
- Doc detail view with raw markdown and metadata.

## 6.6 Export
- Export per source or per job:
  - JSON manifest
  - JSONL document stream
  - ZIP of markdown files + manifest

## 6.7 API
- Public/internal REST API for all major operations.
- Streaming progress updates via SSE or WebSockets.

---

## 7. Non-Functional Requirements

- **Performance**: parse 1k links in <5s (excluding remote latency).
- **Scalability**: support parallel job workers.
- **Reliability**: idempotent job execution and resumable retries.
- **Security**:
  - URL allow/block rules (SSRF protection)
  - request timeout and max response size
  - rate limiting and auth
- **Observability**: structured logs + metrics + job traces.

---

## 8. Proposed Web Stack

- **Frontend**: React + Next.js + TypeScript + shadcn/ui + Tailwind
- **Backend**: Node.js (NestJS or Next.js Route Handlers) + TypeScript
- **Queue/Workers**: BullMQ + Redis
- **Database**: PostgreSQL
- **Search**: PostgreSQL FTS (v1), optional Meilisearch/OpenSearch later
- **Storage**: S3-compatible object storage (or local in dev)
- **Realtime**: SSE first, optional WebSockets
- **Auth**: NextAuth/Auth.js (or Clerk)
- **Deploy**: Docker + Fly.io/Render/AWS

---

## 9. Data Model (v1)

- `sources`
  - id, name, index_url, created_at, updated_at
- `jobs`
  - id, source_id, status, started_at, finished_at, stats_json
- `documents`
  - id, source_id, url, title, content_md, content_hash, fetched_at
- `job_items`
  - id, job_id, document_url, status, http_status, error_message, retries

---

## 10. UX Scope (v1)

1. **Sources page**: list/create/edit sources.
2. **Run job modal**: kick off scrape with advanced options.
3. **Job detail**: live progress, success/failure breakdown.
4. **Documents page**: search + document preview.
5. **Export action**: download JSON/JSONL/ZIP.

---

## 11. MVP Milestones

## Phase 1 — Foundations
- Source CRUD
- Index parsing endpoint
- Job orchestration skeleton

## Phase 2 — Ingestion
- Worker downloads + retries
- Document storage + hashing
- Job progress streaming

## Phase 3 — Retrieval
- Search UI + API
- Document detail
- Export endpoints

## Phase 4 — Hardening
- SSRF protections + limits
- Rate limiting + auth
- Monitoring dashboards

---

## 12. Success Metrics

- Job success rate (target >95% for reachable sources).
- Median job completion time by link count.
- Search latency p95 (<500ms for typical source corpus).
- Weekly active sources/jobs.
- Export completion rate.

---

## 13. Risks & Mitigations

1. **Malformed indexes** → robust parser fallback modes.
2. **Remote rate limits/timeouts** → adaptive concurrency + retries.
3. **Huge docs** → max file size caps + streaming fetch.
4. **Security exposure via arbitrary URLs** → strict network egress policy and URL validation.

---

## 14. Open Decisions

1. Auth required in first public version, or single-user mode first?
2. PostgreSQL FTS only, or include Meilisearch from v1?
3. Per-source scheduling in app, or rely on external cron triggers?
4. Multi-project workspace model in v1 or v2?

