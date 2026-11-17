"""News Intelligence: collectors, deduplication, sentiment analysis, verification."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
import structlog

from jarvis.agents.contracts import NewsEventType, Sentiment
from jarvis.agents.llm import ConfigurationError, complete_json
from jarvis.core.errors import retry_async

logger = structlog.get_logger(__name__)


@dataclass
class RawArticle:
    url: str
    title: str
    source: str
    published_at: datetime
    content_snippet: str = ""


RSS_SOURCES = [
    ("Coindesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("Cointelegraph", "https://cointelegraph.com/rss"),
    ("Bitcoin Magazine", "https://bitcoinmagazine.com/feed"),
]


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


# ------------------------------------------------------------------ #
# RSS Collector
# ------------------------------------------------------------------ #

async def collect_rss(
    sources: list[tuple[str, str]] = RSS_SOURCES,
    *,
    timeout: float = 15.0,
    max_per_source: int = 20,
) -> list[RawArticle]:
    """Fetch RSS feeds and return deduplicated RawArticle list."""
    articles: list[RawArticle] = []
    seen_hashes: set[str] = set()

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        for name, url in sources:
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    logger.warning("news.rss.fetch_failed", source=name, status=resp.status_code)
                    continue
                items = _parse_rss(resp.text, source_name=name)
                for art in items[:max_per_source]:
                    h = url_hash(art.url)
                    if h not in seen_hashes:
                        seen_hashes.add(h)
                        articles.append(art)
                logger.info("news.rss.fetched", source=name, count=len(items))
            except Exception as exc:  # noqa: BLE001
                logger.warning("news.rss.error", source=name, error_type=type(exc).__name__)

    return articles


def _parse_rss(xml_text: str, *, source_name: str) -> list[RawArticle]:
    articles = []
    try:
        root = ET.fromstring(xml_text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        # Handle both RSS 2.0 and Atom
        items = root.findall(".//item") or root.findall(".//atom:entry", ns)
        for item in items:
            title = (item.findtext("title") or item.findtext("atom:title", namespaces=ns) or "").strip()
            link = (item.findtext("link") or item.findtext("atom:link", namespaces=ns) or "").strip()
            if not link and (link_el := item.find("atom:link", ns)) is not None:
                link = link_el.get("href", "")
            pub_raw = item.findtext("pubDate") or item.findtext("atom:published", namespaces=ns) or ""
            snippet = (item.findtext("description") or item.findtext("atom:summary", namespaces=ns) or "")[:500]

            if not title or not link:
                continue
            try:
                pub_at = parsedate_to_datetime(pub_raw).astimezone(UTC).replace(tzinfo=UTC) if pub_raw else datetime.now(UTC)
            except Exception:
                pub_at = datetime.now(UTC)

            articles.append(RawArticle(url=link, title=title, source=source_name, published_at=pub_at, content_snippet=snippet))
    except ET.ParseError as exc:
        logger.warning("news.rss.parse_error", source=source_name, error=str(exc)[:100])
    return articles


# ------------------------------------------------------------------ #
# Sentiment analysis via LLM
# ------------------------------------------------------------------ #

_SENTIMENT_SYSTEM = """You are JARVIS News Intelligence — an expert crypto news analyst.
Analyze the article and return ONLY valid JSON:
{
  "sentiment": "bullish" | "bearish" | "neutral",
  "sentiment_score": -1.0 to 1.0,
  "event_type": "regulatory" | "technical" | "macro" | "exchange" | "partnership" | "hack_exploit" | "other",
  "symbols_mentioned": ["BTC", "ETH", ...],
  "summary": "<1-2 sentence factual summary>",
  "credibility_score": 0.0-1.0
}
Return ONLY the JSON. No explanation outside it."""


@dataclass
class SentimentResult:
    sentiment: Sentiment
    sentiment_score: float
    event_type: NewsEventType
    symbols_mentioned: list[str]
    summary: str
    credibility_score: float


async def analyze_sentiment(article: RawArticle) -> SentimentResult | None:
    """Analyze a single article via LLM. Returns None if LLM not configured."""
    user_prompt = f"Title: {article.title}\nSource: {article.source}\nContent: {article.content_snippet}"
    try:
        raw = await complete_json(_SENTIMENT_SYSTEM, user_prompt, temperature=0.1)
        return SentimentResult(
            sentiment=Sentiment(raw.get("sentiment", "neutral")),
            sentiment_score=float(raw.get("sentiment_score", 0.0)),
            event_type=NewsEventType(raw.get("event_type", "other")),
            symbols_mentioned=raw.get("symbols_mentioned", []),
            summary=raw.get("summary", article.title),
            credibility_score=float(raw.get("credibility_score", 0.5)),
        )
    except ConfigurationError:
        return _stub_sentiment(article)
    except Exception as exc:  # noqa: BLE001
        logger.warning("news.sentiment.error", title=article.title[:60], error_type=type(exc).__name__)
        return None


def _stub_sentiment(article: RawArticle) -> SentimentResult:
    """Returned when AI not configured."""
    return SentimentResult(
        sentiment=Sentiment.NEUTRAL,
        sentiment_score=0.0,
        event_type=NewsEventType.OTHER,
        symbols_mentioned=[],
        summary=article.title,
        credibility_score=0.5,
    )


# ------------------------------------------------------------------ #
# Verification: corroboration scoring
# ------------------------------------------------------------------ #

def compute_credibility(
    article: RawArticle,
    all_articles: list[RawArticle],
    *,
    base_score: float = 0.5,
    corroboration_boost: float = 0.1,
    max_boost: float = 0.3,
) -> float:
    """Score 0-1. Boosts when multiple sources cover similar topic."""
    title_words = set(article.title.lower().split())
    boost = 0.0
    for other in all_articles:
        if other.url == article.url:
            continue
        other_words = set(other.title.lower().split())
        overlap = len(title_words & other_words) / max(len(title_words), 1)
        if overlap > 0.4:
            boost = min(boost + corroboration_boost, max_boost)
    return min(base_score + boost, 1.0)
