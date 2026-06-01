"""Tests for storage.py"""
import json
import sqlite3
from pathlib import Path

import pytest

from llmscrap.fetcher import FetchSummary, DownloadResult
from llmscrap.storage import save_results, MANIFEST_FILE, DB_FILE


INDEX_URL = "https://docs.example.com/llms.txt"


def _make_summary(success=True):
    results = [
        DownloadResult(
            url="https://docs.example.com/intro.md",
            local_path="intro.md",
            title="Introduction",
            section="Docs",
            success=success,
            size_bytes=100 if success else 0,
            content="# Intro\nHello" if success else "",
            error=None if success else "HTTP 404",
        ),
        DownloadResult(
            url="https://docs.example.com/auth.md",
            local_path="guide/auth.md",
            title="Auth",
            section="Guide",
            success=True,
            size_bytes=200,
            content="# Auth\nSecure",
        ),
    ]
    return FetchSummary(
        total=2,
        downloaded=2 if success else 1,
        failed=0 if success else 1,
        results=results,
    )


def test_save_manifest(tmp_path):
    summary = _make_summary()
    artifacts = save_results(summary, tmp_path, INDEX_URL, formats=["json"])

    manifest_path = tmp_path / MANIFEST_FILE
    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text())

    assert data["index_url"] == INDEX_URL
    assert data["total"] == 2
    assert data["downloaded"] == 2
    assert len(data["entries"]) == 2


def test_manifest_has_sha256(tmp_path):
    summary = _make_summary()
    save_results(summary, tmp_path, INDEX_URL, formats=["json"])

    data = json.loads((tmp_path / MANIFEST_FILE).read_text())
    intro = next(e for e in data["entries"] if "intro.md" in e["local_path"])
    assert "sha256" in intro


def test_save_sqlite(tmp_path):
    summary = _make_summary()
    artifacts = save_results(summary, tmp_path, INDEX_URL, formats=["sqlite"])

    db_path = tmp_path / DB_FILE
    assert db_path.exists()

    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT * FROM docs").fetchall()
    conn.close()

    assert len(rows) == 2


def test_sqlite_fts_search(tmp_path):
    summary = _make_summary()
    save_results(summary, tmp_path, INDEX_URL, formats=["sqlite"])

    conn = sqlite3.connect(tmp_path / DB_FILE)
    rows = conn.execute(
        "SELECT title FROM docs_fts WHERE docs_fts MATCH 'Introduction'"
    ).fetchall()
    conn.close()

    assert len(rows) == 1
    assert rows[0][0] == "Introduction"


def test_save_both_formats(tmp_path):
    summary = _make_summary()
    artifacts = save_results(summary, tmp_path, INDEX_URL, formats=["json", "sqlite"])

    assert "manifest" in artifacts
    assert "sqlite" in artifacts
    assert (tmp_path / MANIFEST_FILE).exists()
    assert (tmp_path / DB_FILE).exists()
