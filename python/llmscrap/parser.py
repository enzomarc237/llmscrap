"""
parser.py: Fetch any index URL and extract (title, url) pairs for docs.

Supports:
- Plain text / Markdown indexes (e.g. llms.txt)
- HTML pages (href links)
- Optional recursive crawl over discovered Markdown-like links
"""

import logging
import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import List
from urllib.parse import urlparse

import requests

from .utils import resolve_url, is_doc_url

logger = logging.getLogger("llmscrap")

# Markdown-style link: [Title](url)
_MD_LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
# Plain URL on its own line or after "- "
_PLAIN_URL_RE = re.compile(r'https?://\S+')
# Match <a href="...">...</a>
_HTML_HREF_RE = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>', re.IGNORECASE)


@dataclass
class DocLink:
    title: str
    url: str
    section: str = ""


@dataclass
class ParseResult:
    index_url: str
    links: List[DocLink] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def parse_index(
    url: str,
    timeout: int = 20,
    allow_external: bool = False,
    recursive_depth: int = 0,
    request_delay: float = 0,
    user_agent: str | None = None,
) -> ParseResult:
    """
    Fetch `url` and extract all supported doc links.

    Returns a ParseResult with a list of DocLink entries.
    """
    result = ParseResult(index_url=url)
    root = urlparse(url)
    root_host = root.netloc.lower()

    headers = {"User-Agent": user_agent or "llmscrap/0.2"}

    def _fetch(page_url: str) -> tuple[str, str] | tuple[None, None]:
        try:
            resp = requests.get(page_url, timeout=timeout, headers=headers)
            resp.raise_for_status()
            if request_delay > 0:
                time.sleep(request_delay)
            return resp.text, resp.headers.get("content-type", "")
        except requests.RequestException as e:
            result.errors.append(f"Failed to fetch {page_url}: {e}")
            logger.error("Failed to fetch %s: %s", page_url, e)
            return None, None

    def _is_allowed(candidate: str) -> bool:
        if allow_external:
            return True
        parsed = urlparse(candidate)
        return parsed.netloc.lower() == root_host

    def _extract(text: str, content_type: str, base_url: str) -> List[DocLink]:
        if "text/html" in content_type:
            return _extract_from_html(text, base_url)
        return _extract_from_text(text, base_url)

    visited_pages: set[str] = set()
    seen_docs: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(url, 0)])

    while queue:
        current_url, depth = queue.popleft()
        if current_url in visited_pages:
            continue
        visited_pages.add(current_url)

        text, content_type = _fetch(current_url)
        if text is None:
            continue

        links = _extract(text, content_type or "", current_url)
        for link in links:
            if not _is_allowed(link.url):
                continue
            if link.url not in seen_docs:
                seen_docs.add(link.url)
                result.links.append(link)

        if depth < recursive_depth:
            for link in links:
                if not _is_allowed(link.url):
                    continue
                queue.append((link.url, depth + 1))

    logger.info("Found %d doc links in %s", len(result.links), url)
    return result


def _extract_from_text(text: str, base_url: str) -> List[DocLink]:
    """Extract doc links from plain text / Markdown content."""
    links: List[DocLink] = []
    seen: set = set()
    current_section = ""

    for line in text.splitlines():
        stripped = line.strip()

        # Detect section headers (## Section Name)
        if stripped.startswith("#"):
            current_section = stripped.lstrip("#").strip()
            continue

        # Markdown links: [Title](url)
        for match in _MD_LINK_RE.finditer(stripped):
            title, href = match.group(1), match.group(2)
            abs_url = resolve_url(base_url, href)
            if is_doc_url(abs_url) and abs_url not in seen:
                seen.add(abs_url)
                links.append(DocLink(title=title, url=abs_url, section=current_section))

        # Plain URLs
        if not _MD_LINK_RE.search(stripped):
            for match in _PLAIN_URL_RE.finditer(stripped):
                abs_url = resolve_url(base_url, match.group(0))
                if is_doc_url(abs_url) and abs_url not in seen:
                    seen.add(abs_url)
                    parsed = urlparse(abs_url)
                    title = parsed.path.split("/")[-1] or parsed.netloc
                    links.append(DocLink(title=title, url=abs_url, section=current_section))

    return links


def _extract_from_html(html: str, base_url: str) -> List[DocLink]:
    """Extract doc links from HTML content using regex (no heavy deps)."""
    links: List[DocLink] = []
    seen: set = set()

    for match in _HTML_HREF_RE.finditer(html):
        href, text = match.group(1), match.group(2).strip()
        abs_url = resolve_url(base_url, href)
        if is_doc_url(abs_url) and abs_url not in seen:
            seen.add(abs_url)
            title = text or urlparse(abs_url).path.split("/")[-1].replace(".md", "")
            links.append(DocLink(title=title, url=abs_url))

    return links
