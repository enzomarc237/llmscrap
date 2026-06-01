"""Tests for parser.py"""
import pytest
import responses as rsps_lib
import responses

from llmscrap.parser import parse_index, DocLink


SAMPLE_INDEX_URL = "https://docs.example.com/llms.txt"
SAMPLE_TEXT = """\
# Example Docs

## Getting Started

- [Introduction](https://docs.example.com/intro.md): Get started.
- [Quick Start](https://docs.example.com/quick-start.md)

## Advanced

- [Auth](https://docs.example.com/advanced/auth.md): Authentication guide.
- [Not a doc](https://docs.example.com/about)
"""


@responses.activate
def test_parse_plain_text_index():
    responses.add(responses.GET, SAMPLE_INDEX_URL, body=SAMPLE_TEXT, status=200,
                  content_type="text/plain")
    result = parse_index(SAMPLE_INDEX_URL)

    assert result.index_url == SAMPLE_INDEX_URL
    assert len(result.errors) == 0
    assert len(result.links) == 3

    urls = [l.url for l in result.links]
    assert "https://docs.example.com/intro.md" in urls
    assert "https://docs.example.com/quick-start.md" in urls
    assert "https://docs.example.com/advanced/auth.md" in urls
    # Non-.md link should be excluded
    assert "https://docs.example.com/about" not in urls


@responses.activate
def test_parse_extracts_sections():
    responses.add(responses.GET, SAMPLE_INDEX_URL, body=SAMPLE_TEXT, status=200,
                  content_type="text/plain")
    result = parse_index(SAMPLE_INDEX_URL)

    intro = next(l for l in result.links if "intro.md" in l.url)
    assert intro.section == "Getting Started"

    auth = next(l for l in result.links if "auth.md" in l.url)
    assert auth.section == "Advanced"


@responses.activate
def test_parse_extracts_titles():
    responses.add(responses.GET, SAMPLE_INDEX_URL, body=SAMPLE_TEXT, status=200,
                  content_type="text/plain")
    result = parse_index(SAMPLE_INDEX_URL)

    intro = next(l for l in result.links if "intro.md" in l.url)
    assert intro.title == "Introduction"


@responses.activate
def test_parse_deduplicates_links():
    text = """\
- [Intro](https://docs.example.com/intro.md)
- [Intro Again](https://docs.example.com/intro.md)
"""
    responses.add(responses.GET, SAMPLE_INDEX_URL, body=text, status=200,
                  content_type="text/plain")
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
  <a href="/guide/auth.md">Auth</a>
  <a href="/about">About</a>
</body></html>
"""
    responses.add(responses.GET, SAMPLE_INDEX_URL, body=html, status=200,
                  content_type="text/html")
    result = parse_index(SAMPLE_INDEX_URL)

    assert len(result.links) == 2
    urls = [l.url for l in result.links]
    assert any("intro.md" in u for u in urls)
    assert any("auth.md" in u for u in urls)


@responses.activate
def test_parse_resolves_relative_urls():
    text = "- [Guide](../guide/intro.md)\n"
    base = "https://docs.example.com/v2/llms.txt"
    responses.add(responses.GET, base, body=text, status=200, content_type="text/plain")
    result = parse_index(base)

    assert len(result.links) == 1
    assert result.links[0].url == "https://docs.example.com/guide/intro.md"
