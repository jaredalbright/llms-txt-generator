"""URL normalization, filtering, scoring, and ranking utilities."""

import re
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode


# Query parameters to strip (tracking / analytics)
_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "ref", "source", "mc_cid", "mc_eid",
})

# Junk URL patterns — pages that should never reach the LLM
JUNK_PATTERNS: list[re.Pattern] = [
    re.compile(r"/login(?:[/?#]|$)", re.IGNORECASE),
    re.compile(r"/logout(?:[/?#]|$)", re.IGNORECASE),
    re.compile(r"/signup(?:[/?#]|$)", re.IGNORECASE),
    re.compile(r"/register(?:[/?#]|$)", re.IGNORECASE),
    re.compile(r"/auth/", re.IGNORECASE),
    re.compile(r"/admin(?:[/?#]|$)", re.IGNORECASE),
    # /api/ but NOT /api-reference or /api-docs
    re.compile(r"/api(?:/[^-]|/?\?|/?#|/?$)", re.IGNORECASE),
    re.compile(r"/page/\d+", re.IGNORECASE),
    re.compile(r"/tag/", re.IGNORECASE),
    re.compile(r"/category/", re.IGNORECASE),
    re.compile(r"/cart(?:[/?#]|$)", re.IGNORECASE),
    re.compile(r"/checkout(?:[/?#]|$)", re.IGNORECASE),
    re.compile(r"/search(?:[/?#]|$)", re.IGNORECASE),
    re.compile(r"/feed(?:[/?#]|$)", re.IGNORECASE),
    re.compile(r"/rss(?:[/?#]|$)", re.IGNORECASE),
    re.compile(r"/wp-admin/", re.IGNORECASE),
    re.compile(r"/wp-json/", re.IGNORECASE),
    # File extensions that aren't useful HTML pages
    re.compile(r"\.(xml|json|pdf|zip|png|jpg|jpeg|gif|svg|css|js|woff2?|ttf|eot|ico)(\?|$)", re.IGNORECASE),
]

# Source weights for URL scoring
_SOURCE_WEIGHTS = {"nav": 3.0, "sitemap": 2.0, "body": 1.0}


def normalize_url(url: str) -> str:
    """Normalize a URL for deduplication.

    - Lowercase scheme + netloc
    - Strip fragments and tracking query params
    - Remove trailing slash (except root /)
    - Collapse double slashes in path
    """
    parsed = urlparse(url)

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Collapse double slashes in path
    path = re.sub(r"/{2,}", "/", parsed.path)

    # Remove trailing slash unless root
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    # Strip tracking query params
    if parsed.query:
        params = parse_qs(parsed.query, keep_blank_values=True)
        filtered = {k: v for k, v in params.items() if k.lower() not in _TRACKING_PARAMS}
        query = urlencode(filtered, doseq=True) if filtered else ""
    else:
        query = ""

    # Drop fragment entirely
    return urlunparse((scheme, netloc, path, parsed.params, query, ""))


def _is_junk(url: str) -> bool:
    """Check if a URL matches any junk pattern."""
    parsed = urlparse(url)
    path = parsed.path
    for pattern in JUNK_PATTERNS:
        if pattern.search(path):
            return True
    return False


def filter_junk_urls(urls) -> list[str]:
    """Normalize, filter junk, and deduplicate URLs."""
    seen: set[str] = set()
    result: list[str] = []
    for url in urls:
        normalized = normalize_url(url)
        if normalized in seen:
            continue
        seen.add(normalized)
        if not _is_junk(normalized):
            result.append(normalized)
    return result


def score_url(
    url: str,
    *,
    source: str = "body",
    depth: int = 0,
    inlink_count: int = 0,
) -> float:
    """Score a URL based on its discovery metadata.

    Higher score = more important page.
    """
    source_weight = _SOURCE_WEIGHTS.get(source, 1.0)
    depth_score = 1.0 / (1 + depth)
    inlink_bonus = min(inlink_count, 5) * 0.2
    segment_count = len([s for s in urlparse(url).path.split("/") if s])
    path_penalty = 0.1 * max(segment_count - 1, 0)

    return source_weight + depth_score + inlink_bonus - path_penalty


def rank_and_cap(url_metas: dict[str, dict], max_pages: int) -> list[str]:
    """Score each URL, sort descending, return top max_pages.

    url_metas: {url: {"source": str, "depth": int, "inlink_count": int}}
    Always includes the homepage (path is / or empty) regardless of score.
    """
    scored: list[tuple[str, float]] = []
    homepage: str | None = None

    for url, meta in url_metas.items():
        s = score_url(url, **meta)
        scored.append((url, s))
        parsed = urlparse(url)
        if parsed.path in ("", "/"):
            homepage = url

    scored.sort(key=lambda x: x[1], reverse=True)
    result = [url for url, _ in scored[:max_pages]]

    # Ensure homepage is always present
    if homepage and homepage not in result:
        result.append(homepage)

    return result
