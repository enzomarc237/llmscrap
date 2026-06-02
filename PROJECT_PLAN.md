# llmscrap — Current Plan (Export)

Last updated: 2026-06-02

## Current state

The project is now in a **working desktop MVP** state.

- Python scraping engine is implemented and tested (parser, fetcher, storage, CLI).
- Tauri + React desktop UI is implemented (form, progress polling, result panel).
- Python CLI is bundled as a sidecar binary into the Tauri app.
- Windows release artifacts are being produced (MSI + NSIS installer).

## What is already completed

1. **Core scraper (Python)**
   - Parses index URLs and extracts `.md` links (including relative links).
   - Downloads docs in parallel with retries and progress tracking.
   - Saves outputs to manifest and SQLite (FTS-ready schema).

2. **Desktop app (Tauri + React)**
   - UI workflow: input URL → pick output folder → run scrape → inspect results.
   - Native commands wired: scrape, read progress, reveal folder.
   - Rust crate naming/build issues resolved.

3. **Packaging**
   - Sidecar build script in place (`scripts/build-python-sidecar.ps1`).
   - Tauri build pipeline runs web build + sidecar build before bundle.
   - Bundled sidecar path configured in `src-tauri/tauri.conf.json`.

## Canonical build flow

```powershell
npm install
npm run tauri dev
npx tauri build
```

## Next (recommended order)

1. **Release readiness**
   - Smoke-test installer output on a clean machine (no Python installed).
   - Verify first-run scrape and folder reveal behavior end to end.
   - Confirm app metadata (name, icon, versioning, signing strategy).

2. **Product hardening**
   - Add robust error surfaces in UI (network failures, invalid index, permissions).
   - Add cancellation/retry UX and clearer status messages.
   - Add “recent jobs” history persisted locally.

3. **Phase 2 features**
   - Local search/browse over scraped docs (SQLite FTS in UI).
   - Export options (JSONL/zip) and incremental sync mode.
   - Optional updater/release channel strategy.

## Suggested immediate milestone

Ship **v0.1.0 internal release** with installer + sidecar + MVP scrape flow, then prioritize search + incremental sync for v0.2.0.
