from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

import httpx

from app.config import Settings


logger = logging.getLogger(__name__)


@dataclass
class FxQuote:
    provider: str
    base: str
    quote: str
    rate: float
    as_of: str


class FrankfurterFxService:
    def __init__(self, ttl_seconds: int = 1800) -> None:
        self.ttl_seconds = ttl_seconds
        self.base_url = "https://api.frankfurter.dev/v1/latest"
        self._cached_quote: FxQuote | None = None
        self._cached_at: datetime | None = None

    def latest_eur_usd(self) -> FxQuote:
        if self._cached_quote and self._cached_at and self._cached_at >= datetime.utcnow() - timedelta(seconds=self.ttl_seconds):
            return self._cached_quote

        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            response = client.get(self.base_url, params={"from": "EUR", "to": "USD"})
            response.raise_for_status()
            payload = response.json()

        rate = float((payload.get("rates") or {}).get("USD") or 0.0)
        if rate <= 0:
            raise ValueError("EUR/USD quote provider returned no usable USD rate.")

        quote = FxQuote(
            provider="frankfurter",
            base="EUR",
            quote="USD",
            rate=rate,
            as_of=str(payload.get("date") or datetime.utcnow().date().isoformat()),
        )
        self._cached_quote = quote
        self._cached_at = datetime.utcnow()
        return quote


class FxService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.provider = settings.fx_rate_provider.strip().lower()
        self.frankfurter = FrankfurterFxService(ttl_seconds=settings.fx_quote_ttl_seconds)

    def latest_eur_usd(self) -> FxQuote:
        if self.provider == "frankfurter":
            return self.frankfurter.latest_eur_usd()
        logger.warning("Unknown FX provider '%s', falling back to frankfurter.", self.provider)
        return self.frankfurter.latest_eur_usd()

    def eur_to_usd(self, amount_eur: float, apply_buffer: bool = True) -> tuple[float, FxQuote]:
        if amount_eur <= 0:
            raise ValueError("EUR notional must be positive for FX conversion.")
        quote = self.latest_eur_usd()
        gross_usd = amount_eur * quote.rate
        if apply_buffer:
            gross_usd *= max(0.0, 1 - self.settings.fx_usd_buffer_pct)
        return round(gross_usd, 2), quote


def build_fx_service(settings: Settings) -> FxService:
    return FxService(settings)
