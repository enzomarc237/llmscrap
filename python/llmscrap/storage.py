"""
storage.py: Save results as local mirror, manifest.json, and SQLite FTS5 index.
"""

import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from .fetcher import FetchSummary, DownloadResult

logger = logging.getLogger("llmscrap")

MANIFEST_FILE = "manifest.json"
DB_FILE = "index.db"


def save_results(
    summary: FetchSummary,
    output_dir: Path,
    index_url: str,
    formats: List[str] = None,
) -> dict:
    """
    Persist download results.

    Args:
        summary: FetchSummary from fetcher
        output_dir: Root directory where files were saved
        index_url: Original index URL
        formats: List of output formats. Options: "json", "sqlite". Default: both.

    Returns:
        dict with paths to generated artifacts.
    """
    if formats is None:
        formats = ["json", "sqlite"]

    output_dir = Path(output_dir)
    artifacts = {}

    if "json" in formats:
        manifest_path = _write_manifest(summary, output_dir, index_url)
        artifacts["manifest"] = str(manifest_path)

    if "sqlite" in formats:
        db_path = _write_sqlite(summary, output_dir, index_url)
        artifacts["sqlite"] = str(db_path)

    logger.info("Saved artifacts: %s", artifacts)
    return artifacts


def _write_manifest(summary: FetchSummary, output_dir: Path, index_url: str) -> Path:
    manifest_path = output_dir / MANIFEST_FILE
    entries = []

    for r in summary.results:
        entry = {
            "url": r.url,
            "local_path": r.local_path,
            "title": r.title,
            "section": r.section,
            "success": r.success,
            "size_bytes": r.size_bytes,
        }
        if not r.success:
            entry["error"] = r.error
        if r.success and r.content:
            entry["sha256"] = hashlib.sha256(r.content.encode("utf-8")).hexdigest()
        entries.append(entry)

    manifest = {
        "index_url": index_url,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": summary.total,
        "downloaded": summary.downloaded,
        "failed": summary.failed,
        "entries": entries,
    }

    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Manifest written to %s", manifest_path)
    return manifest_path


def _write_sqlite(summary: FetchSummary, output_dir: Path, index_url: str) -> Path:
    db_path = output_dir / DB_FILE
    conn = sqlite3.connect(db_path)

    try:
        _ensure_schema(conn)
        _upsert_run(conn, summary, index_url)
        conn.commit()
    finally:
        conn.close()

    logger.info("SQLite index written to %s", db_path)
    return db_path


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            index_url   TEXT NOT NULL,
            scraped_at  TEXT NOT NULL,
            total       INTEGER,
            downloaded  INTEGER,
            failed      INTEGER
        );

        CREATE TABLE IF NOT EXISTS docs (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id        INTEGER REFERENCES runs(id),
            url           TEXT NOT NULL,
            local_path    TEXT,
            title         TEXT,
            section       TEXT,
            size_bytes    INTEGER,
            sha256        TEXT,
            success       INTEGER,
            error         TEXT,
            content_preview TEXT
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
            title,
            section,
            content_preview,
            content='docs',
            content_rowid='id'
        );

        CREATE TRIGGER IF NOT EXISTS docs_ai AFTER INSERT ON docs BEGIN
            INSERT INTO docs_fts(rowid, title, section, content_preview)
            VALUES (new.id, new.title, new.section, new.content_preview);
        END;
    """)


def _upsert_run(conn: sqlite3.Connection, summary: FetchSummary, index_url: str) -> None:
    cur = conn.execute(
        "INSERT INTO runs (index_url, scraped_at, total, downloaded, failed) VALUES (?,?,?,?,?)",
        (index_url, datetime.now(timezone.utc).isoformat(), summary.total, summary.downloaded, summary.failed),
    )
    run_id = cur.lastrowid

    for r in summary.results:
        content_preview = r.content[:500] if r.content else ""
        sha256 = hashlib.sha256(r.content.encode("utf-8")).hexdigest() if r.content else None

        conn.execute(
            """INSERT INTO docs
               (run_id, url, local_path, title, section, size_bytes, sha256, success, error, content_preview)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (run_id, r.url, r.local_path, r.title, r.section,
             r.size_bytes, sha256, int(r.success), r.error, content_preview),
        )
