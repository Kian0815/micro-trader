from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import feedparser
from dateutil import parser as date_parser
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Asset, NewsItem

ETF_ALIASES = {
    "SPY": ["spy", "spdr s&p 500", "s&p 500 etf", "sp500 etf", "s&p 500", "spdr s&p 500 etf trust"],
    "QQQ": ["qqq", "invesco qqq", "nasdaq 100 etf", "nasdaq 100", "invesco qqq trust"],
    "VTI": ["vti", "vanguard total stock market", "total stock market etf", "us total stock market"],
}

STOCK_ALIASES = {
    "AAPL": ["aapl", "apple", "iphone maker", "apple inc"],
    "MSFT": ["msft", "microsoft", "azure", "microsoft corporation"],
    "NVDA": ["nvda", "nvidia", "gpu maker", "nvidia corporation"],
}

ALL_SYMBOL_ALIASES = {
    **ETF_ALIASES,
    **STOCK_ALIASES,
}


WEIGHTED_POSITIVE_TERMS = {
    "surge": 0.6,
    "approval": 0.8,
    "partnership": 0.5,
    "record": 0.5,
    "upgrade": 0.7,
    "growth": 0.5,
    "adoption": 0.6,
    "launch": 0.4,
    "breakout": 0.8,
    "bullish": 0.9,
    "gain": 0.4,
    "beats": 0.9,
    "beat": 0.8,
    "inflows": 0.7,
    "rebound": 0.5,
    "strength": 0.4,
    "strong": 0.4,
    "outperform": 0.8,
    "buyback": 0.6,
    "rally": 0.8,
}

WEIGHTED_NEGATIVE_TERMS = {
    "hack": 1.0,
    "lawsuit": 0.7,
    "selloff": 0.9,
    "crash": 1.0,
    "exploit": 1.0,
    "ban": 0.8,
    "fraud": 1.0,
    "bearish": 0.9,
    "loss": 0.5,
    "liquidation": 0.8,
    "investigation": 0.8,
    "downgrade": 0.8,
    "misses": 0.9,
    "miss": 0.7,
    "weak": 0.5,
    "warning": 0.6,
    "fragility": 0.6,
    "risk": 0.4,
    "downside": 0.6,
}

POSITIVE_PHRASES = {
    "all-time high": 1.0,
    "beats expectations": 1.0,
    "beat expectations": 1.0,
    "record inflows": 1.0,
    "strong demand": 0.7,
    "working better": 0.5,
    "price targets": 0.5,
    "holders defend": 0.4,
}

NEGATIVE_PHRASES = {
    "profit warning": 1.0,
    "misses expectations": 1.0,
    "missed expectations": 1.0,
    "near-term downside": 0.8,
    "creating fragility": 0.8,
    "wild days are over": 0.4,
    "liquidity crunch": 1.0,
}

EVENT_KEYWORDS = {
    "regulation": "regulation",
    "etf": "etf",
    "hack": "security",
    "exploit": "security",
    "partnership": "partnership",
    "upgrade": "upgrade",
    "earnings": "earnings",
    "guidance": "guidance",
    "buyback": "capital-return",
    "contract": "contract",
    "deal": "contract",
    "downgrade": "downgrade",
    "investigation": "investigation",
    "listing": "listing",
}


@dataclass
class ScoredArticle:
    title: str
    summary: str
    url: str
    source: str
    published_at: datetime
    symbol: str | None
    sentiment_score: float
    event_type: str


class NewsService:
    def __init__(self, feeds: list[str]) -> None:
        self.feeds = feeds
        self.max_article_age = timedelta(hours=72)

    def ingest(self, db: Session, assets: list[Asset]) -> int:
        asset_lookup = {asset.symbol: asset for asset in assets}
        inserted = 0
        for feed_url in self.feeds:
            scoped_symbols = self._scoped_symbols_for_feed(feed_url)
            scoped_lookup = (
                {symbol: asset_lookup[symbol] for symbol in scoped_symbols if symbol in asset_lookup}
                if scoped_symbols
                else asset_lookup
            )
            parsed = feedparser.parse(feed_url)
            source = parsed.feed.get("title", feed_url)
            for entry in parsed.entries[:20]:
                url = entry.get("link")
                if not url:
                    continue
                exists = db.scalar(select(NewsItem.id).where(NewsItem.url == url))
                if exists:
                    continue
                article = self._score_entry(scoped_lookup, source, entry)
                if not article:
                    continue
                if article.published_at < datetime.utcnow() - self.max_article_age:
                    continue
                asset = asset_lookup.get(article.symbol) if article.symbol else None
                db.add(
                    NewsItem(
                        asset_id=asset.id if asset else None,
                        source=article.source,
                        title=article.title,
                        summary=article.summary,
                        url=article.url,
                        sentiment_score=article.sentiment_score,
                        event_type=article.event_type,
                        published_at=article.published_at,
                    )
                )
                inserted += 1
        db.commit()
        return inserted

    def refresh_recent(self, db: Session, assets: list[Asset], hours: int = 48) -> int:
        asset_lookup = {asset.symbol: asset for asset in assets}
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        items = db.scalars(select(NewsItem).where(NewsItem.published_at >= cutoff)).all()
        refreshed = 0
        for item in items:
            rescored = self._score_text(
                asset_lookup,
                source=item.source,
                title=item.title,
                summary=item.summary,
                url=item.url,
                published_at=item.published_at,
            )
            if not rescored:
                continue
            asset = asset_lookup.get(rescored.symbol) if rescored.symbol else None
            item.asset_id = asset.id if asset else None
            item.sentiment_score = rescored.sentiment_score
            item.event_type = rescored.event_type
            refreshed += 1
        db.commit()
        return refreshed

    def _score_entry(self, asset_lookup: dict[str, Asset], source: str, entry: dict) -> ScoredArticle | None:
        title = entry.get("title", "").strip()
        summary = entry.get("summary", "").strip()
        published_value = entry.get("published") or entry.get("updated")
        if published_value:
            published_at = date_parser.parse(published_value)
        else:
            published_at = datetime.now(timezone.utc)
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        return self._score_text(
            asset_lookup,
            source=source,
            title=title,
            summary=summary,
            url=entry["link"],
            published_at=published_at.astimezone(timezone.utc).replace(tzinfo=None),
        )

    def _score_text(
        self,
        asset_lookup: dict[str, Asset],
        source: str,
        title: str,
        summary: str,
        url: str,
        published_at: datetime,
    ) -> ScoredArticle | None:
        combined = f"{title} {summary}".lower()
        matched_symbol = self._pick_best_symbol(asset_lookup, title.lower(), combined)
        if not matched_symbol:
            return None

        sentiment = self._score_sentiment(title.lower(), combined)

        event_type = "general"
        for keyword, label in EVENT_KEYWORDS.items():
            if keyword in combined:
                event_type = label
                break

        return ScoredArticle(
            title=title,
            summary=summary[:2000],
            url=url,
            source=source[:64],
            published_at=published_at,
            symbol=matched_symbol,
            sentiment_score=sentiment,
            event_type=event_type,
        )

    def _pick_best_symbol(self, asset_lookup: dict[str, Asset], title_text: str, combined: str) -> str | None:
        scored_matches: list[tuple[float, str]] = []
        for symbol, asset in asset_lookup.items():
            score = self._asset_match_score(title_text, combined, symbol, asset.name.lower())
            if score > 0:
                scored_matches.append((score, symbol))

        if not scored_matches:
            return None

        scored_matches.sort(reverse=True)
        top_score, top_symbol = scored_matches[0]
        if top_score < 1.5:
            return None

        return top_symbol

    def _scoped_symbols_for_feed(self, feed_url: str) -> set[str]:
        lower_feed = feed_url.lower()
        scoped: set[str] = set()
        for symbol, aliases in ALL_SYMBOL_ALIASES.items():
            encoded_symbol = f"%22{symbol.lower()}%22"
            if encoded_symbol in lower_feed:
                scoped.add(symbol)
                continue
            for alias in aliases:
                if alias.replace(" ", "%20") in lower_feed:
                    scoped.add(symbol)
                    break
        return scoped

    def _asset_match_score(self, title_text: str, combined: str, symbol: str, asset_name: str) -> float:
        score = 0.0
        symbol_token = symbol.lower()
        if f" {symbol_token} " in f" {title_text} ":
            score += 2.5
        elif f" {symbol_token} " in f" {combined} ":
            score += 1.5

        if asset_name in title_text:
            score += 2.0
        elif asset_name in combined:
            score += 1.0

        for alias in ETF_ALIASES.get(symbol, []) + STOCK_ALIASES.get(symbol, []):
            if alias in title_text:
                score += 1.8
            elif alias in combined:
                score += 0.9

        return score

    def _score_sentiment(self, title_text: str, combined: str) -> float:
        positive_score = self._weighted_term_score(title_text, combined, WEIGHTED_POSITIVE_TERMS, POSITIVE_PHRASES)
        negative_score = self._weighted_term_score(title_text, combined, WEIGHTED_NEGATIVE_TERMS, NEGATIVE_PHRASES)
        sentiment = (positive_score - negative_score) / 3.0
        return max(min(sentiment, 1.0), -1.0)

    def _weighted_term_score(
        self,
        title_text: str,
        combined: str,
        terms: dict[str, float],
        phrases: dict[str, float],
    ) -> float:
        score = 0.0
        padded_title = f" {title_text} "
        padded_combined = f" {combined} "
        for term, weight in terms.items():
            token = f" {term} "
            if token in padded_title:
                score += weight * 1.6
            elif token in padded_combined:
                score += weight
        for phrase, weight in phrases.items():
            if phrase in title_text:
                score += weight * 1.8
            elif phrase in combined:
                score += weight
        return score
