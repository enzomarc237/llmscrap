"""llmscrap: Download Markdown docs from any .md index URL."""

from .parser import parse_index
from .fetcher import download_docs
from .storage import save_results

__version__ = "0.1.0"
__all__ = ["parse_index", "download_docs", "save_results"]
