"""
cli.py: Command-line entry point for llmscrap.
"""

import argparse
import json
import sys
from pathlib import Path

from .fetcher import download_docs
from .parser import parse_index, DocLink
from .storage import save_results
from .utils import setup_logging


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="llmscrap",
        description="Download docs from any doc index URL (e.g. llms.txt)",
    )
    p.add_argument("url", help="Index URL to scrape (e.g. https://docs.example.com/llms.txt)")
    p.add_argument(
        "-o", "--output",
        default="downloads",
        metavar="DIR",
        help="Output directory (default: ./downloads)",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=4,
        metavar="N",
        help="Parallel download workers (default: 4)",
    )
    p.add_argument(
        "--timeout",
        type=int,
        default=20,
        metavar="SECS",
        help="Per-request timeout in seconds (default: 20)",
    )
    p.add_argument(
        "--format",
        dest="formats",
        nargs="+",
        choices=["json", "sqlite", "bundle", "zip", "html", "llm"],
        default=["json", "sqlite"],
        metavar="FORMAT",
        help="Output formats: json, sqlite, bundle, zip, html, llm",
    )
    p.add_argument("--allow-external", action="store_true", help="Allow links outside index domain")
    p.add_argument("--recursive-depth", type=int, default=0, help="Recursive crawl depth for doc links")
    p.add_argument("--request-delay", type=float, default=0.0, help="Delay (sec) between HTTP requests")
    p.add_argument("--user-agent", default="llmscrap/0.2", help="Custom HTTP user-agent")
    p.add_argument("--polite", action="store_true", help="Polite mode (auto throttling)")
    p.add_argument("--preview-json", action="store_true", help="Print parsed links as JSON and exit")
    p.add_argument("--links-file", help="Path to JSON file containing selected links [{title,url,section}]")
    p.add_argument("--retry-failed-from", help="Manifest path; retry only failed docs from that run")
    p.add_argument("--cancel-file", help="Path to cancellation marker file")
    p.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable .progress.json file (used by Tauri UI)",
    )
    p.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose debug logging",
    )
    return p


def _load_links_from_file(path: str) -> list[DocLink]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return [DocLink(title=item.get("title") or item["url"], url=item["url"], section=item.get("section", "")) for item in payload]


def _load_failed_links_from_manifest(path: str) -> list[DocLink]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    links = []
    for entry in payload.get("entries", []):
        if not entry.get("success"):
            links.append(DocLink(
                title=entry.get("title") or entry.get("url", "document"),
                url=entry["url"],
                section=entry.get("section", ""),
            ))
    return links


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logger = setup_logging(verbose=args.verbose)
    output_dir = Path(args.output)
    watch_progress = not args.no_progress

    links: list[DocLink] = []

    if args.links_file:
        links = _load_links_from_file(args.links_file)
    elif args.retry_failed_from:
        links = _load_failed_links_from_manifest(args.retry_failed_from)
    else:
        logger.info("Fetching index: %s", args.url)
        parse_result = parse_index(
            args.url,
            timeout=args.timeout,
            allow_external=args.allow_external,
            recursive_depth=max(args.recursive_depth, 0),
            request_delay=max(args.request_delay, 0),
            user_agent=args.user_agent,
        )

        if args.preview_json:
            print(json.dumps({
                "index_url": parse_result.index_url,
                "errors": parse_result.errors,
                "links": [
                    {"title": l.title, "url": l.url, "section": l.section}
                    for l in parse_result.links
                ],
            }, ensure_ascii=False))
            return 0 if not parse_result.errors else 1

        if parse_result.errors and not parse_result.links:
            for err in parse_result.errors:
                logger.error(err)
            return 1

        links = parse_result.links

    if not links:
        logger.warning("No doc links found for %s", args.url)
        return 1

    logger.info("Found %d docs to download → %s", len(links), output_dir)

    # ── Step 2: Download ─────────────────────────────────────────────────────
    summary = download_docs(
        links=links,
        base_url=args.url,
        output_dir=output_dir,
        workers=args.workers,
        timeout=args.timeout,
        watch_progress=watch_progress,
        request_delay=max(args.request_delay, 0),
        user_agent=args.user_agent,
        polite=args.polite,
        cancel_file=Path(args.cancel_file) if args.cancel_file else None,
    )

    # ── Step 3: Save results ─────────────────────────────────────────────────
    artifacts = save_results(
        summary=summary,
        output_dir=output_dir,
        index_url=args.url,
        formats=args.formats,
    )

    # ── Summary ──────────────────────────────────────────────────────────────
    print()
    print(f"  [OK] Downloaded : {summary.downloaded}/{summary.total}")
    if summary.failed:
        print(f"  [!!] Failed     : {summary.failed}")
    if summary.cancelled:
        print("  [!!] Cancelled  : true")
    for fmt, path in artifacts.items():
        print(f"  [>]  {fmt:<8}: {path}")
    print()

    if summary.cancelled:
        return 3
    return 0 if summary.failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
