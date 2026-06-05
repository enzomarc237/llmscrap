"""
storage.py: Save results as local mirror, manifest.json, and SQLite FTS5 index.
"""

import hashlib
import html
import json
import logging
import re
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from .fetcher import FetchSummary

logger = logging.getLogger("llmscrap")

MANIFEST_FILE = "manifest.json"
DB_FILE = "index.db"
BUNDLE_FILE = "bundle.md"
ZIP_FILE = "export.zip"
HTML_DIR = "html"
LLM_FILE = "llm_context.json"


def save_results(
    summary: FetchSummary,
    output_dir: Path,
    index_url: str,
    formats: List[str] = None,
) -> dict:
    """Persist download results and exports."""
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

    if "bundle" in formats:
        bundle_path = _write_bundle_markdown(summary, output_dir, index_url)
        artifacts["bundle"] = str(bundle_path)

    if "html" in formats:
        html_path = _write_html_export(summary, output_dir, index_url)
        artifacts["html"] = str(html_path)

    if "llm" in formats:
        llm_path = _write_llm_bundle(summary, output_dir, index_url)
        artifacts["llm"] = str(llm_path)

    if "zip" in formats:
        zip_path = _write_zip(summary, output_dir)
        artifacts["zip"] = str(zip_path)

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
            "duplicate_of": r.duplicate_of,
        }
        if not r.success:
            entry["error"] = r.error
        if r.success and r.content:
            entry["sha256"] = r.sha256 or hashlib.sha256(r.content.encode("utf-8")).hexdigest()
        entries.append(entry)

    manifest = {
        "index_url": index_url,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": summary.total,
        "downloaded": summary.downloaded,
        "failed": summary.failed,
        "cancelled": summary.cancelled,
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


def _write_bundle_markdown(summary: FetchSummary, output_dir: Path, index_url: str) -> Path:
    bundle_path = output_dir / BUNDLE_FILE
    parts = [f"# llmscrap bundle\n\nSource: {index_url}\n"]

    for r in summary.results:
        if not r.success:
            continue
        heading = r.title or r.url
        parts.append(f"\n\n## {heading}\n\nSource: {r.url}\n\n{r.content}\n")

    bundle_path.write_text("\n".join(parts), encoding="utf-8")
    return bundle_path


def _markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    html_lines: list[str] = []
    for raw in lines:
        line = raw.rstrip()
        if not line:
            continue
        escaped = html.escape(line)
        if line.startswith("### "):
            html_lines.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("# "):
            html_lines.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("- "):
            html_lines.append(f"<li>{html.escape(line[2:])}</li>")
        else:
            html_lines.append(f"<p>{escaped}</p>")
    return "\n".join(html_lines)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-").lower()
    return slug or "doc"


def _write_html_export(summary: FetchSummary, output_dir: Path, index_url: str) -> Path:
    html_dir = output_dir / HTML_DIR
    html_dir.mkdir(parents=True, exist_ok=True)

    links: list[str] = []
    for idx, r in enumerate(summary.results, start=1):
        if not r.success:
            continue
        filename = f"{idx:03d}-{_slugify(r.title or Path(r.local_path).stem)}.html"
        doc_path = html_dir / filename
        page = f"""<!doctype html>
<html><head><meta charset=\"utf-8\"/><title>{html.escape(r.title or r.url)}</title></head>
<body><h1>{html.escape(r.title or r.url)}</h1><p><a href=\"{html.escape(r.url)}\">source</a></p>{_markdown_to_html(r.content)}</body></html>"""
        doc_path.write_text(page, encoding="utf-8")
        links.append(f"<li><a href=\"{filename}\">{html.escape(r.title or r.url)}</a></li>")

    index_path = html_dir / "index.html"
    index_html = f"""<!doctype html>
<html><head><meta charset=\"utf-8\"/><title>llmscrap html export</title></head>
<body><h1>llmscrap html export</h1><p>Source: {html.escape(index_url)}</p><ul>{''.join(links)}</ul></body></html>"""
    index_path.write_text(index_html, encoding="utf-8")
    return index_path


def _extract_headings(markdown: str) -> list[str]:
    return [line.lstrip("#").strip() for line in markdown.splitlines() if line.startswith("#")]


def _estimate_tokens(markdown: str) -> int:
    words = len(markdown.split())
    return int(words * 1.3)


def _write_llm_bundle(summary: FetchSummary, output_dir: Path, index_url: str) -> Path:
    out = output_dir / LLM_FILE
    docs = []
    for r in summary.results:
        if not r.success:
            continue
        docs.append({
            "title": r.title,
            "url": r.url,
            "section": r.section,
            "headings": _extract_headings(r.content),
            "token_estimate": _estimate_tokens(r.content),
            "sha256": r.sha256,
            "content": r.content,
        })

    payload = {
        "index_url": index_url,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "documents": docs,
        "total_documents": len(docs),
        "total_token_estimate": sum(d["token_estimate"] for d in docs),
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def _write_zip(summary: FetchSummary, output_dir: Path) -> Path:
    zip_path = output_dir / ZIP_FILE
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for r in summary.results:
            if not r.success or r.duplicate_of:
                continue
            file_path = output_dir / r.local_path
            if file_path.exists() and file_path.is_file():
                archive.write(file_path, arcname=r.local_path)

        for optional in [MANIFEST_FILE, DB_FILE, BUNDLE_FILE, LLM_FILE]:
            candidate = output_dir / optional
            if candidate.exists():
                archive.write(candidate, arcname=optional)

        html_dir = output_dir / HTML_DIR
        if html_dir.exists():
            for item in html_dir.rglob("*.html"):
                archive.write(item, arcname=str(item.relative_to(output_dir)))

    return zip_path


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            index_url   TEXT NOT NULL,
            scraped_at  TEXT NOT NULL,
            total       INTEGER,
            downloaded  INTEGER,
            failed      INTEGER,
            cancelled   INTEGER
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
            duplicate_of  TEXT,
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
        "INSERT INTO runs (index_url, scraped_at, total, downloaded, failed, cancelled) VALUES (?,?,?,?,?,?)",
        (
            index_url,
            datetime.now(timezone.utc).isoformat(),
            summary.total,
            summary.downloaded,
            summary.failed,
            int(summary.cancelled),
        ),
    )
    run_id = cur.lastrowid

    for r in summary.results:
        content_preview = r.content[:500] if r.content else ""
        sha256 = r.sha256 or (hashlib.sha256(r.content.encode("utf-8")).hexdigest() if r.content else None)

        conn.execute(
            """INSERT INTO docs
               (run_id, url, local_path, title, section, size_bytes, sha256, success, error, duplicate_of, content_preview)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (run_id, r.url, r.local_path, r.title, r.section,
             r.size_bytes, sha256, int(r.success), r.error, r.duplicate_of, content_preview),
        )
