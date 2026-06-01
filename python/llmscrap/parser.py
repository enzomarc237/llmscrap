"""
parser.py: Fetch any index URL and extract (title, url) pairs for .md links.

Supports:
- Plain text / Markdown indexes (e.g. llms.txt)
- HTML pages (href links)
"""

import re
import logging
from urllib.parse import urlparse
from dataclasses import dataclass, field
from typing import List

import requests

from .utils import resolve_url, is_md_url

logger = logging.getLogger("llmscrap")

# Markdown-style link: [Title](url)
_MD_LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
# Plain URL on its own line or after "- "
_PLAIN_URL_RE = re.compile(r'https?://\S+\.md\b')


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


def parse_index(url: str, timeout: int = 20) -> ParseResult:
    """
    Fetch `url` and extract all .md doc links.

    Returns a ParseResult with a list of DocLink entries.
    """
    result = ParseResult(index_url=url)

    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as e:
        result.errors.append(f"Failed to fetch index: {e}")
        logger.error("Failed to fetch index %s: %s", url, e)
        return result

    content_type = resp.headers.get("content-type", "")
    text = resp.text

    if "text/html" in content_type:
        links = _extract_from_html(text, url)
    else:
        links = _extract_from_text(text, url)

    result.links = links
    logger.info("Found %d .md links in %s", len(links), url)
    return result


def _extract_from_text(text: str, base_url: str) -> List[DocLink]:
    """Extract .md links from plain text / Markdown content."""
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
            if is_md_url(abs_url) and abs_url not in seen:
                seen.add(abs_url)
                links.append(DocLink(title=title, url=abs_url, section=current_section))

        # Plain .md URLs (no markdown syntax)
        if not _MD_LINK_RE.search(stripped):
            for match in _PLAIN_URL_RE.finditer(stripped):
                abs_url = match.group(0)
                if abs_url not in seen:
                    seen.add(abs_url)
                    title = urlparse(abs_url).path.split("/")[-1].replace(".md", "")
                    links.append(DocLink(title=title, url=abs_url, section=current_section))

    return links


def _extract_from_html(html: str, base_url: str) -> List[DocLink]:
    """Extract .md links from HTML content using simple regex (no heavy deps)."""
    links: List[DocLink] = []
    seen: set = set()

    # Match <a href="...">...</a>
    href_re = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>', re.IGNORECASE)

    for match in href_re.finditer(html):
        href, text = match.group(1), match.group(2).strip()
        abs_url = resolve_url(base_url, href)
        if is_md_url(abs_url) and abs_url not in seen:
            seen.add(abs_url)
            title = text or urlparse(abs_url).path.split("/")[-1].replace(".md", "")
            links.append(DocLink(title=title, url=abs_url))

    return links
