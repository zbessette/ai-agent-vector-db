"""Small helpers shared by the JSON API and HTML page search routes."""
from typing import Optional


def filter_by_threshold(results: list[dict], threshold: Optional[float]) -> list[dict]:
    """Filter search results by minimum score (post-search, after limit).

    Note: this filters AFTER the search returned `top_k` results, so a high
    threshold can return fewer than `top_k` rows even if more above-threshold
    matches exist beyond the original cutoff. v1 accepts that behavior.
    """
    if threshold is None:
        return results
    return [r for r in results if r["score"] >= threshold]
