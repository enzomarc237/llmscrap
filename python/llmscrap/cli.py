"""
cli.py: Command-line entry point for llmscrap.

Usage:
    python -m llmscrap <index_url> [options]

Examples:
    python -m llmscrap https://docs.qoder.com/llms.txt
    python -m llmscrap https://docs.qoder.com/llms.txt -o ./docs --workers 8
"""

import argparse
import sys
from pathlib import Path

from .parser import parse_index
from .fetcher import download_docs
from .storage import save_results
from .utils import setup_logging


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="llmscrap",
        description="Download Markdown docs from any .md index URL (e.g. llms.txt)",
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
        choices=["json", "sqlite"],
        default=["json", "sqlite"],
        metavar="FORMAT",
        help="Output formats: json, sqlite (default: both)",
    )
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


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logger = setup_logging(verbose=args.verbose)
    output_dir = Path(args.output)
    watch_progress = not args.no_progress

    # ── Step 1: Parse index ──────────────────────────────────────────────────
    logger.info("Fetching index: %s", args.url)
    parse_result = parse_index(args.url, timeout=args.timeout)

    if parse_result.errors:
        for err in parse_result.errors:
            logger.error(err)
        return 1

    if not parse_result.links:
        logger.warning("No .md links found in %s", args.url)
        return 1

    logger.info("Found %d docs to download → %s", len(parse_result.links), output_dir)

    # ── Step 2: Download ─────────────────────────────────────────────────────
    summary = download_docs(
        links=parse_result.links,
        base_url=args.url,
        output_dir=output_dir,
        workers=args.workers,
        timeout=args.timeout,
        watch_progress=watch_progress,
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
    for fmt, path in artifacts.items():
        print(f"  [>]  {fmt:<8}: {path}")
    print()

    return 0 if summary.failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
