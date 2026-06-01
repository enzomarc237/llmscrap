"""Shared utilities: URL resolution, logging setup."""

import logging
import re
from urllib.parse import urljoin, urlparse


def setup_logging(verbose: bool = False) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        level=level,
    )
    return logging.getLogger("llmscrap")


def resolve_url(base: str, href: str) -> str:
    """Resolve href against base URL, returning absolute URL."""
    return urljoin(base, href)


def is_md_url(url: str) -> bool:
    """Return True if the URL path ends with .md."""
    path = urlparse(url).path
    return path.endswith(".md")


def url_to_local_path(url: str, base_url: str) -> str:
    """
    Convert a doc URL to a relative local file path mirroring the URL structure.
    e.g. https://docs.example.com/guide/auth.md -> guide/auth.md
    """
    base_parsed = urlparse(base_url)
    doc_parsed = urlparse(url)

    # Use the doc's path, stripping leading slash
    path = doc_parsed.path.lstrip("/")

    # If base URL has a path prefix (e.g. /docs/), strip it from the doc path
    base_path = base_parsed.path.lstrip("/")
    if base_path and path.startswith(base_path):
        path = path[len(base_path):].lstrip("/")

    return path if path else "index.md"


def sanitize_filename(name: str) -> str:
    """Remove characters unsafe for file names."""
    return re.sub(r'[<>:"/\\|?*]', "_", name)
