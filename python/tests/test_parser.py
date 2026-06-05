"""Tests for parser.py"""
import responses

from llmscrap.parser import parse_index


SAMPLE_INDEX_URL = "https://docs.example.com/llms.txt"
SAMPLE_TEXT = """\
# Example Docs

## Getting Started

- [Introduction](https://docs.example.com/intro.md): Get started.
- [Quick Start](https://docs.example.com/quick-start.md)

## Advanced

- [Auth](https://docs.example.com/advanced/auth.md): Authentication guide.
- [Not a doc](https://example.com/about)
"""


@responses.activate
def test_parse_plain_text_index():
    responses.add(responses.GET, SAMPLE_INDEX_URL, body=SAMPLE_TEXT, status=200, content_type="text/plain")
    result = parse_index(SAMPLE_INDEX_URL)

    assert result.index_url == SAMPLE_INDEX_URL
    assert len(result.links) == 3


@responses.activate
def test_parse_extracts_sections_and_titles():
    responses.add(responses.GET, SAMPLE_INDEX_URL, body=SAMPLE_TEXT, status=200, content_type="text/plain")
    result = parse_index(SAMPLE_INDEX_URL)

    intro = next(l for l in result.links if "intro.md" in l.url)
    assert intro.section == "Getting Started"
    assert intro.title == "Introduction"


@responses.activate
def test_parse_deduplicates_links():
    text = """\
- [Intro](https://docs.example.com/intro.md)
- [Intro Again](https://docs.example.com/intro.md)
"""
    responses.add(responses.GET, SAMPLE_INDEX_URL, body=text, status=200, content_type="text/plain")
    result = parse_index(SAMPLE_INDEX_URL)
    assert len(result.links) == 1


@responses.activate
def test_parse_handles_fetch_error():
    responses.add(responses.GET, SAMPLE_INDEX_URL, status=404)
    result = parse_index(SAMPLE_INDEX_URL)

    assert len(result.links) == 0
    assert len(result.errors) > 0


@responses.activate
def test_parse_html_index():
    html = """\
<html><body>
  <a href="/guide/intro.md">Introduction</a>
  <a href="/guide/auth.mdx">Auth</a>
  <a href="/guide/notes.txt">Notes</a>
</body></html>
"""
    responses.add(responses.GET, SAMPLE_INDEX_URL, body=html, status=200, content_type="text/html")
    result = parse_index(SAMPLE_INDEX_URL)

    assert len(result.links) == 3


@responses.activate
def test_parse_resolves_relative_urls_and_query_formats():
    text = "- [Guide](../guide/intro.md?format=md)\n- [Txt](https://docs.example.com/guide/readme.txt)\n"
    base = "https://docs.example.com/v2/llms.txt"
    responses.add(responses.GET, base, body=text, status=200, content_type="text/plain")
    result = parse_index(base)

    urls = [l.url for l in result.links]
    assert "https://docs.example.com/guide/intro.md?format=md" in urls
    assert "https://docs.example.com/guide/readme.txt" in urls


@responses.activate
def test_parse_blocks_external_by_default():
    text = "- [Ext](https://other.example.com/file.md)\n"
    responses.add(responses.GET, SAMPLE_INDEX_URL, body=text, status=200, content_type="text/plain")

    result = parse_index(SAMPLE_INDEX_URL)
    assert result.links == []

    allow = parse_index(SAMPLE_INDEX_URL, allow_external=True)
    assert len(allow.links) == 1


@responses.activate
def test_parse_recursive_crawl():
    root = "https://docs.example.com/llms.txt"
    first = "https://docs.example.com/guide/a.md"
    second = "https://docs.example.com/guide/b.md"

    responses.add(responses.GET, root, body=f"- [A]({first})", status=200, content_type="text/plain")
    responses.add(responses.GET, first, body=f"- [B]({second})", status=200, content_type="text/plain")
    responses.add(responses.GET, second, body="# done", status=200, content_type="text/plain")

    result = parse_index(root, recursive_depth=1)
    urls = [l.url for l in result.links]
    assert first in urls
    assert second in urls
