"""Tests for fetcher.py"""
import json

import responses

from llmscrap.parser import DocLink
from llmscrap.fetcher import download_docs


BASE_URL = "https://docs.example.com/llms.txt"

LINKS = [
    DocLink(title="Introduction", url="https://docs.example.com/intro.md", section="Docs"),
    DocLink(title="Auth", url="https://docs.example.com/guide/auth.md", section="Guide"),
]


@responses.activate
def test_download_success(tmp_path):
    responses.add(responses.GET, LINKS[0].url, body="# Intro\nHello world", status=200)
    responses.add(responses.GET, LINKS[1].url, body="# Auth\nSecure it", status=200)

    summary = download_docs(LINKS, BASE_URL, tmp_path, workers=2, watch_progress=False)

    assert summary.downloaded == 2
    assert summary.failed == 0
    assert summary.total == 2


@responses.activate
def test_download_creates_files(tmp_path):
    responses.add(responses.GET, LINKS[0].url, body="# Intro", status=200)
    responses.add(responses.GET, LINKS[1].url, body="# Auth", status=200)

    download_docs(LINKS, BASE_URL, tmp_path, workers=2, watch_progress=False)

    assert (tmp_path / "intro.md").exists()
    assert (tmp_path / "guide" / "auth.md").exists()


@responses.activate
def test_download_handles_404(tmp_path):
    responses.add(responses.GET, LINKS[0].url, status=404)
    responses.add(responses.GET, LINKS[1].url, body="# Auth", status=200)

    summary = download_docs(LINKS, BASE_URL, tmp_path, workers=2, watch_progress=False)

    assert summary.downloaded == 1
    assert summary.failed == 1


@responses.activate
def test_download_writes_progress_file(tmp_path):
    responses.add(responses.GET, LINKS[0].url, body="# Intro", status=200)
    responses.add(responses.GET, LINKS[1].url, body="# Auth", status=200)

    download_docs(LINKS, BASE_URL, tmp_path, workers=1, watch_progress=True)

    progress_file = tmp_path / ".progress.json"
    assert progress_file.exists()
    data = json.loads(progress_file.read_text())
    assert "elapsed_sec" in data
    assert "eta_sec" in data
    assert data["total"] == 2


@responses.activate
def test_download_result_has_content_and_sha(tmp_path):
    responses.add(responses.GET, LINKS[0].url, body="# Intro Content", status=200)
    responses.add(responses.GET, LINKS[1].url, body="# Auth Content", status=200)

    summary = download_docs(LINKS, BASE_URL, tmp_path, workers=2, watch_progress=False)

    intro = next(r for r in summary.results if "intro.md" in r.url)
    assert intro.content == "# Intro Content"
    assert intro.size_bytes > 0
    assert intro.sha256


@responses.activate
def test_download_deduplicates_files(tmp_path):
    same = "# Same content"
    responses.add(responses.GET, LINKS[0].url, body=same, status=200)
    responses.add(responses.GET, LINKS[1].url, body=same, status=200)

    summary = download_docs(LINKS, BASE_URL, tmp_path, workers=2, watch_progress=False)

    deduped = [r for r in summary.results if r.duplicate_of]
    assert len(deduped) == 1
