"""
fetcher.py: Parallel HTTP downloads with retry logic and progress tracking.

Progress is written to <output_dir>/.progress.json for Tauri file-watcher.
"""

import hashlib
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .utils import url_to_local_path

logger = logging.getLogger("llmscrap")


@dataclass
class DownloadResult:
    url: str
    local_path: str
    title: str
    section: str
    success: bool
    error: Optional[str] = None
    size_bytes: int = 0
    content: str = ""
    sha256: Optional[str] = None
    duplicate_of: Optional[str] = None


@dataclass
class FetchSummary:
    total: int
    downloaded: int
    failed: int
    results: List[DownloadResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    cancelled: bool = False


def _make_session(retries: int = 3, backoff: float = 0.5, user_agent: str = "llmscrap/0.2") -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})
    retry = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def _write_progress(
    progress_file: Path,
    downloaded: int,
    total: int,
    current_url: str,
    current_title: str,
    failed: int,
    start_time: float,
) -> None:
    elapsed = time.time() - start_time
    speed = downloaded / elapsed if elapsed > 0 else 0
    remaining = max(total - downloaded, 0)
    eta = remaining / speed if speed > 0 else None
    progress_file.write_text(
        json.dumps({
            "downloaded": downloaded,
            "total": total,
            "failed": failed,
            "current": current_url,
            "current_title": current_title,
            "speed_files_per_sec": round(speed, 2),
            "percent": round((downloaded / total * 100) if total else 0, 1),
            "elapsed_sec": round(elapsed, 1),
            "eta_sec": round(eta, 1) if eta is not None else None,
        }),
        encoding="utf-8",
    )


def _download_one(
    link,
    base_url: str,
    output_dir: Path,
    session: requests.Session,
    timeout: int,
    hash_index: dict[str, str],
    hash_lock: threading.Lock,
    request_delay: float,
    cancel_file: Optional[Path],
) -> DownloadResult:
    local_rel = url_to_local_path(link.url, base_url)
    local_path = output_dir / local_rel

    if cancel_file and cancel_file.exists():
        return DownloadResult(
            url=link.url,
            local_path=str(local_rel),
            title=link.title,
            section=link.section,
            success=False,
            error="cancelled",
        )

    try:
        if request_delay > 0:
            time.sleep(request_delay)

        resp = session.get(link.url, timeout=timeout)
        resp.raise_for_status()
        content = resp.text
        sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()

        with hash_lock:
            duplicate_of = hash_index.get(sha256)
            if duplicate_of is None:
                hash_index[sha256] = str(local_rel)

        if duplicate_of is None:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(content, encoding="utf-8")

        return DownloadResult(
            url=link.url,
            local_path=str(local_rel if duplicate_of is None else duplicate_of),
            title=link.title,
            section=link.section,
            success=True,
            size_bytes=len(content.encode("utf-8")),
            content=content,
            sha256=sha256,
            duplicate_of=duplicate_of,
        )
    except Exception as e:
        logger.warning("Failed to download %s: %s", link.url, e)
        return DownloadResult(
            url=link.url,
            local_path=str(local_rel),
            title=link.title,
            section=link.section,
            success=False,
            error=str(e),
        )


def download_docs(
    links,
    base_url: str,
    output_dir: Path,
    workers: int = 4,
    timeout: int = 20,
    watch_progress: bool = True,
    request_delay: float = 0,
    user_agent: str = "llmscrap/0.2",
    polite: bool = False,
    cancel_file: Optional[Path] = None,
) -> FetchSummary:
    """Download all links in parallel."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    progress_file = output_dir / ".progress.json"
    total = len(links)
    downloaded = 0
    failed = 0
    start_time = time.time()
    results: List[DownloadResult] = []
    errors: List[str] = []

    if polite and request_delay <= 0:
        request_delay = 0.35

    session = _make_session(user_agent=user_agent)
    hash_index: dict[str, str] = {}
    hash_lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _download_one,
                link,
                base_url,
                output_dir,
                session,
                timeout,
                hash_index,
                hash_lock,
                request_delay,
                cancel_file,
            ): link
            for link in links
        }

        for future in as_completed(futures):
            result = future.result()
            results.append(result)

            if result.success:
                downloaded += 1
                logger.debug("✓ %s", result.local_path)
            else:
                failed += 1
                if result.error:
                    errors.append(f"{result.url}: {result.error}")
                logger.warning("✗ %s — %s", result.url, result.error)

            if watch_progress:
                _write_progress(
                    progress_file,
                    downloaded,
                    total,
                    result.url,
                    result.title,
                    failed,
                    start_time,
                )

    cancelled = bool(cancel_file and cancel_file.exists())

    # Write final progress state
    if watch_progress:
        _write_progress(progress_file, downloaded, total, "", "", failed, start_time)

    return FetchSummary(
        total=total,
        downloaded=downloaded,
        failed=failed,
        results=results,
        errors=errors,
        cancelled=cancelled,
    )
