"""Report writer — saves agent reports as Markdown + JSON files."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

REPORTS_DIR = Path("agent_reports")


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_market_report(report: dict, *, run_id: str, symbol: str) -> Path:
    """Write market analysis report to disk. Returns the markdown path."""
    date_str = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    base = _ensure_dir(REPORTS_DIR / "market" / symbol)
    md_path = base / f"{date_str}_{run_id[:8]}.md"
    json_path = base / f"{date_str}_{run_id[:8]}.json"

    signal = report.get("signal", "unknown")
    confidence = report.get("confidence", 0.0)
    reasoning = report.get("reasoning", "")
    indicators = report.get("indicators", {})

    md = f"""# Market Analysis — {symbol}

**Generated:** {datetime.now(UTC).isoformat()}
**Run ID:** {run_id}
**Signal:** {signal.upper()}
**Confidence:** {confidence:.0%}

## Indicators
| Indicator | Value |
|-----------|-------|
"""
    for k, v in indicators.items():
        md += f"| {k} | {round(v, 4) if v is not None else 'N/A'} |\n"

    md += f"\n## Reasoning\n{reasoning}\n"

    md_path.write_text(md, encoding="utf-8")
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    logger.info("report_writer.market_saved", path=str(md_path))
    return md_path


def write_news_report(report: dict, *, run_id: str) -> Path:
    """Write news intelligence report to disk."""
    date_str = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    base = _ensure_dir(REPORTS_DIR / "news")
    md_path = base / f"{date_str}_{run_id[:8]}.md"
    json_path = base / f"{date_str}_{run_id[:8]}.json"

    sentiment = report.get("overall_sentiment", "neutral")
    score = report.get("sentiment_score", 0.0)
    events = report.get("key_events", [])
    articles = report.get("top_articles", [])

    md = f"""# News Intelligence Report

**Generated:** {datetime.now(UTC).isoformat()}
**Run ID:** {run_id}
**Overall Sentiment:** {sentiment.upper()} ({score:+.2f})

## Key Events
"""
    for ev in events:
        md += f"- {ev}\n"

    md += "\n## Top Articles\n"
    for art in articles[:5]:
        md += f"- [{art.get('title', '')}]({art.get('url', '')}) — {art.get('source', '')} ({art.get('sentiment', '')})\n"

    md_path.write_text(md, encoding="utf-8")
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    logger.info("report_writer.news_saved", path=str(md_path))
    return md_path


def write_proposal_report(proposal: dict, verdict: str, *, run_id: str) -> Path:
    """Write chief analyst proposal/decision report."""
    date_str = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    base = _ensure_dir(REPORTS_DIR / "proposals")
    md_path = base / f"{date_str}_{run_id[:8]}_{verdict}.md"
    json_path = base / f"{date_str}_{run_id[:8]}_{verdict}.json"

    md = f"""# Trade Proposal — {verdict.upper()}

**Generated:** {datetime.now(UTC).isoformat()}
**Run ID:** {run_id}

```json
{json.dumps(proposal, indent=2, default=str)}
```
"""
    md_path.write_text(md, encoding="utf-8")
    json_path.write_text(json.dumps(proposal, indent=2, default=str), encoding="utf-8")
    logger.info("report_writer.proposal_saved", path=str(md_path), verdict=verdict)
    return md_path
