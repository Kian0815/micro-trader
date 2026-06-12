from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import time

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Asset, AssetKind, MarketTick, ProviderHealthSample


logger = logging.getLogger(__name__)


def _provider_chain_label(names: list[str]) -> str:
    if not names:
        return "none"
    compact = "+".join(names)
    return compact[:120]


def _provider_message(
    *,
    kind_name: str,
    preferred_provider: str,
    actual_provider: str,
    provider_summary: str,
    kind_success: int,
    fallback_used: bool,
) -> str:
    status_line = (
        f"{kind_name.upper()} quotes fetched from {actual_provider}. {provider_summary}"
        if kind_success
        else f"No {kind_name.upper()} quotes returned; fallback chain exhausted. {provider_summary}"
    )
    fallback_line = "Fallback used." if fallback_used else "Preferred provider satisfied the request."
    return f"Preferred: {preferred_provider}. Actual: {actual_provider}. {fallback_line} {status_line}"


def _freshness_label(*, age_seconds: int, max_tick_age_seconds: int, recent_cache_ttl_seconds: int, source: str) -> str:
    if age_seconds <= max_tick_age_seconds:
        return "fresh"
    if source == "alpaca" and age_seconds <= recent_cache_ttl_seconds:
        return "recent"
    return "stale"


@dataclass
class MarketSnapshot:
    symbol: str
    price: float
    change_24h_pct: float
    volume_24h: float


class CoinGeckoMarketDataService:
    def __init__(self) -> None:
        self.base_url = "https://api.coingecko.com/api/v3"
        self.last_status = "ok"
        self.last_message = "Idle."
        self.last_error_type = ""

    def fetch(self, assets: list[Asset]) -> list[MarketSnapshot]:
        if not assets:
            self.last_status = "ok"
            self.last_message = "No crypto assets requested."
            self.last_error_type = ""
            return []
        ids = ",".join(asset.external_id for asset in assets)
        try:
            with httpx.Client(timeout=20.0) as client:
                response = client.get(
                    f"{self.base_url}/coins/markets",
                    params={
                        "vs_currency": "eur",
                        "ids": ids,
                        "price_change_percentage": "24h",
                        "per_page": len(assets),
                        "page": 1,
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            self.last_status = "error"
            self.last_error_type = "rate_limit" if exc.response.status_code == 429 else "http"
            self.last_message = f"CoinGecko request failed with {exc.response.status_code}."
            logger.warning("CoinGecko market request failed: %s", exc)
            return []
        except httpx.HTTPError as exc:
            self.last_status = "error"
            self.last_error_type = "http"
            self.last_message = f"CoinGecko request failed: {exc}"
            logger.warning("CoinGecko market request failed: %s", exc)
            return []

        rows = []
        for item in payload:
            rows.append(
                MarketSnapshot(
                    symbol=item["symbol"].upper(),
                    price=float(item["current_price"]),
                    change_24h_pct=float(item.get("price_change_percentage_24h_in_currency") or 0.0),
                    volume_24h=float(item.get("total_volume") or 0.0),
                )
            )
        self.last_status = "ok" if len(rows) == len(assets) else ("warn" if rows else "error")
        self.last_error_type = ""
        self.last_message = (
            "Crypto quotes fetched from CoinGecko."
            if rows
            else "CoinGecko returned no crypto quotes."
        )
        return rows

    def persist(self, db: Session, assets: list[Asset]) -> dict[str, MarketTick]:
        snapshots = self.fetch(assets)
        latest_by_symbol: dict[str, MarketTick] = {}
        asset_by_symbol = {asset.symbol: asset for asset in assets}
        for snapshot in snapshots:
            asset = asset_by_symbol.get(snapshot.symbol)
            if not asset:
                continue
            tick = MarketTick(
                asset_id=asset.id,
                price=snapshot.price,
                change_24h_pct=snapshot.change_24h_pct,
                volume_24h=snapshot.volume_24h,
            )
            db.add(tick)
            latest_by_symbol[snapshot.symbol] = tick
        db.commit()
        return latest_by_symbol


class BinanceMarketDataService:
    def __init__(self) -> None:
        self.base_url = "https://api.binance.com/api/v3"
        self.last_status = "ok"
        self.last_message = "Idle."
        self.last_error_type = ""

    def fetch(self, assets: list[Asset]) -> list[MarketSnapshot]:
        if not assets:
            self.last_status = "ok"
            self.last_message = "No crypto assets requested."
            self.last_error_type = ""
            return []

        rows: list[MarketSnapshot] = []
        had_rate_limit = False
        had_error = False
        with httpx.Client(timeout=20.0) as client:
            for asset in assets:
                pair = f"{asset.symbol.upper()}EUR"
                try:
                    response = client.get(
                        f"{self.base_url}/ticker/24hr",
                        params={"symbol": pair},
                    )
                    response.raise_for_status()
                    payload = response.json()
                except httpx.HTTPStatusError as exc:
                    had_error = True
                    if exc.response.status_code == 429:
                        had_rate_limit = True
                    logger.warning("Binance market quote request failed for %s: %s", asset.symbol, exc)
                    continue
                except httpx.HTTPError as exc:
                    had_error = True
                    logger.warning("Binance market quote request failed for %s: %s", asset.symbol, exc)
                    continue

                if "lastPrice" not in payload:
                    had_error = True
                    logger.warning("Binance market quote skipped for %s: no usable price returned.", asset.symbol)
                    continue

                try:
                    rows.append(
                        MarketSnapshot(
                            symbol=asset.symbol,
                            price=float(payload.get("lastPrice") or 0.0),
                            change_24h_pct=float(payload.get("priceChangePercent") or 0.0),
                            volume_24h=float(payload.get("quoteVolume") or 0.0),
                        )
                    )
                except (TypeError, ValueError):
                    had_error = True
                    logger.warning("Binance market quote skipped for %s: invalid numeric fields.", asset.symbol)

        self.last_error_type = "rate_limit" if had_rate_limit else ("http" if had_error else "")
        self.last_status = "ok" if len(rows) == len(assets) else ("warn" if rows else "error")
        self.last_message = (
            "Binance returned crypto spot quotes."
            if rows
            else ("Binance rate limited or returned no crypto quotes." if had_rate_limit else "Binance returned no crypto quotes.")
        )
        return rows

    def persist(self, db: Session, assets: list[Asset]) -> dict[str, MarketTick]:
        snapshots = self.fetch(assets)
        latest_by_symbol: dict[str, MarketTick] = {}
        asset_by_symbol = {asset.symbol: asset for asset in assets}
        for snapshot in snapshots:
            asset = asset_by_symbol.get(snapshot.symbol)
            if not asset or snapshot.price <= 0:
                continue
            tick = MarketTick(
                asset_id=asset.id,
                price=snapshot.price,
                change_24h_pct=snapshot.change_24h_pct,
                volume_24h=snapshot.volume_24h,
                source="binance",
            )
            db.add(tick)
            latest_by_symbol[snapshot.symbol] = tick
        db.commit()
        return latest_by_symbol


class AlphaVantageEtfDataService:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.base_url = "https://www.alphavantage.co/query"
        self.last_status = "ok"
        self.last_message = "Idle."
        self.last_error_type = ""

    def fetch(self, assets: list[Asset]) -> list[MarketSnapshot]:
        if not assets or not self.api_key:
            self.last_status = "warn" if assets else "ok"
            self.last_message = "Alpha Vantage API key missing." if assets else "No market assets requested."
            self.last_error_type = "config" if assets else ""
            return []

        rows: list[MarketSnapshot] = []
        had_rate_limit = False
        had_error = False
        with httpx.Client(timeout=20.0) as client:
            for index, asset in enumerate(assets):
                try:
                    response = client.get(
                        self.base_url,
                        params={
                            "function": "GLOBAL_QUOTE",
                            "symbol": asset.external_id,
                            "apikey": self.api_key,
                        },
                    )
                    response.raise_for_status()
                    payload = response.json()
                except httpx.HTTPStatusError as exc:
                    had_error = True
                    if exc.response.status_code == 429:
                        had_rate_limit = True
                    logger.warning("Alpha Vantage market quote request failed for %s: %s", asset.symbol, exc)
                    payload = {}
                except httpx.HTTPError as exc:
                    had_error = True
                    logger.warning("Alpha Vantage market quote request failed for %s: %s", asset.symbol, exc)
                    payload = {}
                quote = payload.get("Global Quote", {})
                if not quote:
                    note = payload.get("Note") or payload.get("Information") or "No quote returned."
                    if "frequency" in note.lower() or "rate limit" in note.lower():
                        had_rate_limit = True
                    logger.warning("Alpha Vantage market quote skipped for %s: %s", asset.symbol, note)
                else:
                    rows.append(
                        MarketSnapshot(
                            symbol=asset.symbol,
                            price=float(quote.get("05. price") or 0.0),
                            change_24h_pct=float((quote.get("10. change percent") or "0").replace("%", "")),
                            volume_24h=float(quote.get("06. volume") or 0.0),
                        )
                )
                if index < len(assets) - 1:
                    time.sleep(1.1)
        self.last_error_type = "rate_limit" if had_rate_limit else ("http" if had_error else "")
        self.last_status = "ok" if len(rows) == len(assets) else ("warn" if rows else "error")
        self.last_message = (
            "Alpha Vantage returned market quotes."
            if rows
            else ("Alpha Vantage rate limited or returned no quotes." if had_rate_limit else "Alpha Vantage returned no quotes.")
        )
        return rows

    def persist(self, db: Session, assets: list[Asset]) -> dict[str, MarketTick]:
        snapshots = self.fetch(assets)
        latest_by_symbol: dict[str, MarketTick] = {}
        asset_by_symbol = {asset.symbol: asset for asset in assets}
        for snapshot in snapshots:
            asset = asset_by_symbol.get(snapshot.symbol)
            if not asset or snapshot.price <= 0:
                continue
            tick = MarketTick(
                asset_id=asset.id,
                price=snapshot.price,
                change_24h_pct=snapshot.change_24h_pct,
                volume_24h=snapshot.volume_24h,
                source="alphavantage",
            )
            db.add(tick)
            latest_by_symbol[snapshot.symbol] = tick
        db.commit()
        return latest_by_symbol


class FinImpulseMarketDataService:
    def __init__(self, api_token: str) -> None:
        self.api_token = api_token
        self.url = "https://api.finimpulse.com/v1/summary"
        self.last_status = "ok"
        self.last_message = "Idle."
        self.last_error_type = ""

    def fetch(self, assets: list[Asset]) -> list[MarketSnapshot]:
        if not assets or not self.api_token:
            self.last_status = "warn" if assets else "ok"
            self.last_message = "FinImpulse token missing." if assets else "No market assets requested."
            self.last_error_type = "config" if assets else ""
            return []

        rows: list[MarketSnapshot] = []
        had_rate_limit = False
        had_error = False
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_token}",
        }
        with httpx.Client(timeout=20.0, headers=headers) as client:
            for asset in assets:
                try:
                    response = client.post(self.url, json={"symbol": asset.external_id, "tag": "micro-trader"})
                    response.raise_for_status()
                    payload = response.json()
                except httpx.HTTPStatusError as exc:
                    had_error = True
                    if exc.response.status_code == 429:
                        had_rate_limit = True
                    logger.warning("FinImpulse market quote request failed for %s: %s", asset.symbol, exc)
                    continue
                except httpx.HTTPError as exc:
                    had_error = True
                    logger.warning("FinImpulse market quote request failed for %s: %s", asset.symbol, exc)
                    continue
                data = payload.get("result") or payload.get("data") or payload
                price = (
                    data.get("current_price")
                    or data.get("regular_market_day_high")
                    or data.get("regular_market_previous_close")
                    or data.get("previous_close")
                    or data.get("regular_market_price")
                    or data.get("nav_price")
                    or 0.0
                )
                change_pct = data.get("regular_market_change_percent") or 0.0
                volume = data.get("regular_market_volume") or data.get("volume") or 0.0
                if not price:
                    logger.warning("FinImpulse market quote skipped for %s: no usable price returned.", asset.symbol)
                    continue
                rows.append(
                    MarketSnapshot(
                        symbol=asset.symbol,
                        price=float(price),
                        change_24h_pct=float(change_pct),
                        volume_24h=float(volume),
                    )
                )
        self.last_error_type = "rate_limit" if had_rate_limit else ("http" if had_error else "")
        self.last_status = "ok" if len(rows) == len(assets) else ("warn" if rows else "error")
        self.last_message = (
            "FinImpulse returned market quotes."
            if rows
            else ("FinImpulse rate limited or returned no quotes." if had_rate_limit else "FinImpulse returned no quotes.")
        )
        return rows

    def persist(self, db: Session, assets: list[Asset]) -> dict[str, MarketTick]:
        snapshots = self.fetch(assets)
        latest_by_symbol: dict[str, MarketTick] = {}
        asset_by_symbol = {asset.symbol: asset for asset in assets}
        for snapshot in snapshots:
            asset = asset_by_symbol.get(snapshot.symbol)
            if not asset or snapshot.price <= 0:
                continue
            tick = MarketTick(
                asset_id=asset.id,
                price=snapshot.price,
                change_24h_pct=snapshot.change_24h_pct,
                volume_24h=snapshot.volume_24h,
                source="finimpulse",
            )
            db.add(tick)
            latest_by_symbol[snapshot.symbol] = tick
        db.commit()
        return latest_by_symbol


class TwelveDataMarketDataService:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.url = "https://api.twelvedata.com/quote"
        self.last_status = "ok"
        self.last_message = "Idle."
        self.last_error_type = ""

    def fetch(self, assets: list[Asset]) -> list[MarketSnapshot]:
        if not assets or not self.api_key:
            self.last_status = "warn" if assets else "ok"
            self.last_message = "Twelve Data API key missing." if assets else "No market assets requested."
            self.last_error_type = "config" if assets else ""
            return []

        rows: list[MarketSnapshot] = []
        had_rate_limit = False
        had_error = False
        with httpx.Client(timeout=20.0) as client:
            for asset in assets:
                try:
                    response = client.get(
                        self.url,
                        params={"symbol": asset.external_id, "apikey": self.api_key},
                    )
                    response.raise_for_status()
                    payload = response.json()
                except httpx.HTTPStatusError as exc:
                    had_error = True
                    if exc.response.status_code == 429:
                        had_rate_limit = True
                    logger.warning("Twelve Data market quote request failed for %s: %s", asset.symbol, exc)
                    continue
                except httpx.HTTPError as exc:
                    had_error = True
                    logger.warning("Twelve Data market quote request failed for %s: %s", asset.symbol, exc)
                    continue

                if payload.get("status") == "error":
                    had_error = True
                    message = str(payload.get("message", "Unknown error"))
                    if "429" in message or "rate" in message.lower() or "limit" in message.lower():
                        had_rate_limit = True
                    logger.warning("Twelve Data market quote skipped for %s: %s", asset.symbol, payload.get("message", "Unknown error"))
                    continue

                try:
                    close = float(payload.get("close") or 0.0)
                    previous_close = float(payload.get("previous_close") or 0.0)
                    percent_change = ((close / previous_close) - 1) * 100 if previous_close > 0 else 0.0
                    rows.append(
                        MarketSnapshot(
                            symbol=asset.symbol,
                            price=close,
                            change_24h_pct=round(percent_change, 4),
                            volume_24h=float(payload.get("volume") or 0.0),
                        )
                    )
                except (TypeError, ValueError):
                    logger.warning("Twelve Data market quote skipped for %s: invalid numeric fields.", asset.symbol)
                    had_error = True
        self.last_error_type = "rate_limit" if had_rate_limit else ("http" if had_error else "")
        self.last_status = "ok" if len(rows) == len(assets) else ("warn" if rows else "error")
        self.last_message = (
            "Twelve Data returned market quotes."
            if rows
            else ("Twelve Data rate limited or returned no quotes." if had_rate_limit else "Twelve Data returned no quotes.")
        )
        return rows

    def persist(self, db: Session, assets: list[Asset]) -> dict[str, MarketTick]:
        snapshots = self.fetch(assets)
        latest_by_symbol: dict[str, MarketTick] = {}
        asset_by_symbol = {asset.symbol: asset for asset in assets}
        for snapshot in snapshots:
            asset = asset_by_symbol.get(snapshot.symbol)
            if not asset or snapshot.price <= 0:
                continue
            tick = MarketTick(
                asset_id=asset.id,
                price=snapshot.price,
                change_24h_pct=snapshot.change_24h_pct,
                volume_24h=snapshot.volume_24h,
                source="twelvedata",
            )
            db.add(tick)
            latest_by_symbol[snapshot.symbol] = tick
        db.commit()
        return latest_by_symbol


class AlpacaMarketDataService:
    def __init__(self, api_key: str, api_secret: str) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://data.alpaca.markets/v2/stocks/snapshots"
        self.last_status = "ok"
        self.last_message = "Idle."
        self.last_error_type = ""

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def fetch(self, assets: list[Asset]) -> list[MarketSnapshot]:
        if not assets or not self.configured:
            self.last_status = "warn" if assets else "ok"
            self.last_message = "Alpaca market-data credentials missing." if assets else "No market assets requested."
            self.last_error_type = "config" if assets else ""
            return []

        rows: list[MarketSnapshot] = []
        had_rate_limit = False
        had_error = False
        symbols = ",".join(asset.external_id for asset in assets)
        try:
            with httpx.Client(timeout=20.0, headers=self._headers()) as client:
                response = client.get(self.base_url, params={"symbols": symbols})
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            had_error = True
            if exc.response.status_code == 429:
                had_rate_limit = True
            logger.warning("Alpaca market snapshot request failed: %s", exc)
            payload = {}
        except httpx.HTTPError as exc:
            had_error = True
            logger.warning("Alpaca market snapshot request failed: %s", exc)
            payload = {}

        snapshots = payload.get("snapshots") if isinstance(payload, dict) else {}
        if not snapshots and isinstance(payload, dict):
            # Alpaca snapshot responses may return symbols at the top level.
            snapshots = {
                key: value
                for key, value in payload.items()
                if isinstance(value, dict)
            }
        for asset in assets:
            snapshot = snapshots.get(asset.external_id) or snapshots.get(asset.symbol)
            if not snapshot:
                continue
            latest_trade = snapshot.get("latestTrade") or {}
            minute_bar = snapshot.get("minuteBar") or {}
            daily_bar = snapshot.get("dailyBar") or {}
            prev_daily_bar = snapshot.get("prevDailyBar") or {}
            price = (
                latest_trade.get("p")
                or minute_bar.get("c")
                or daily_bar.get("c")
                or prev_daily_bar.get("c")
                or 0.0
            )
            previous_close = prev_daily_bar.get("c") or 0.0
            change_pct = 0.0
            try:
                price_value = float(price or 0.0)
                previous_close_value = float(previous_close or 0.0)
                if previous_close_value > 0:
                    change_pct = round(((price_value / previous_close_value) - 1) * 100, 4)
                volume_value = float(daily_bar.get("v") or prev_daily_bar.get("v") or 0.0)
            except (TypeError, ValueError):
                had_error = True
                logger.warning("Alpaca market snapshot skipped for %s: invalid numeric fields.", asset.symbol)
                continue
            if price_value <= 0:
                continue
            rows.append(
                MarketSnapshot(
                    symbol=asset.symbol,
                    price=price_value,
                    change_24h_pct=change_pct,
                    volume_24h=volume_value,
                )
            )

        self.last_error_type = "rate_limit" if had_rate_limit else ("http" if had_error else "")
        self.last_status = "ok" if len(rows) == len(assets) else ("warn" if rows else "error")
        self.last_message = (
            "Alpaca returned ETF/stock market snapshots."
            if rows
            else ("Alpaca rate limited or returned no quotes." if had_rate_limit else "Alpaca returned no quotes.")
        )
        return rows

    def persist(self, db: Session, assets: list[Asset]) -> dict[str, MarketTick]:
        snapshots = self.fetch(assets)
        latest_by_symbol: dict[str, MarketTick] = {}
        asset_by_symbol = {asset.symbol: asset for asset in assets}
        for snapshot in snapshots:
            asset = asset_by_symbol.get(snapshot.symbol)
            if not asset or snapshot.price <= 0:
                continue
            tick = MarketTick(
                asset_id=asset.id,
                price=snapshot.price,
                change_24h_pct=snapshot.change_24h_pct,
                volume_24h=snapshot.volume_24h,
                source="alpaca",
            )
            db.add(tick)
            latest_by_symbol[snapshot.symbol] = tick
        db.commit()
        return latest_by_symbol

    def _headers(self) -> dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret,
        }


class MarketDataRouter:
    def __init__(
        self,
        alphavantage_api_key: str,
        crypto_data_provider: str = "binance",
        etf_data_provider: str = "alphavantage",
        finimpulse_api_token: str = "",
        twelvedata_api_key: str = "",
        alpaca_api_key: str = "",
        alpaca_api_secret: str = "",
        provider_rate_limit_cooldown_seconds: int = 1800,
        provider_error_cooldown_seconds: int = 300,
        alpaca_quote_cache_ttl_seconds: int = 3600,
    ) -> None:
        self.crypto_data_provider = crypto_data_provider.strip().lower()
        self.crypto_services = {
            "binance": BinanceMarketDataService(),
            "coingecko": CoinGeckoMarketDataService(),
        }
        self.etf_data_provider = etf_data_provider.strip().lower()
        self.alpaca_service = AlpacaMarketDataService(alpaca_api_key, alpaca_api_secret)
        self.alphavantage_service = AlphaVantageEtfDataService(alphavantage_api_key)
        self.finimpulse_service = FinImpulseMarketDataService(finimpulse_api_token)
        self.twelvedata_service = TwelveDataMarketDataService(twelvedata_api_key)
        self.provider_rate_limit_cooldown_seconds = provider_rate_limit_cooldown_seconds
        self.provider_error_cooldown_seconds = provider_error_cooldown_seconds
        self.alpaca_quote_cache_ttl_seconds = alpaca_quote_cache_ttl_seconds
        self.last_provider_report: dict[str, dict] = {}

    def persist(self, db: Session, assets: list[Asset]) -> dict[str, MarketTick]:
        latest: dict[str, MarketTick] = {}
        crypto_assets = [asset for asset in assets if asset.kind == AssetKind.CRYPTO]
        market_assets = [asset for asset in assets if asset.kind in {AssetKind.ETF, AssetKind.STOCK}]

        crypto_latest: dict[str, MarketTick] = {}
        crypto_order = [self.crypto_data_provider, "coingecko", "binance"]
        crypto_seen: set[str] = set()
        remaining_crypto_assets = list(crypto_assets)
        crypto_messages: list[str] = []
        crypto_used_providers: list[str] = []
        crypto_skipped_providers: list[str] = []
        crypto_status = "ok"
        for name in crypto_order:
            if name in crypto_seen or name not in self.crypto_services:
                continue
            crypto_seen.add(name)
            if self._provider_in_cooldown(db, name):
                crypto_skipped_providers.append(name)
                crypto_messages.append(f"{name} cooling down after recent provider failures")
                continue
            if not remaining_crypto_assets:
                break
            provider_latest = self.crypto_services[name].persist(db, remaining_crypto_assets)
            crypto_used_providers.append(name)
            crypto_messages.append(self.crypto_services[name].last_message)
            crypto_latest.update(provider_latest)
            if provider_latest:
                remaining_crypto_assets = [asset for asset in remaining_crypto_assets if asset.symbol not in provider_latest]
            if self.crypto_services[name].last_status in {"warn", "error"}:
                crypto_status = "warn" if provider_latest else "error"
        latest.update(crypto_latest)
        selected_crypto_provider = " -> ".join(crypto_used_providers) if crypto_used_providers else "none"
        crypto_summary = "; ".join(crypto_messages) if crypto_messages else "No crypto providers were available."
        if crypto_skipped_providers:
            crypto_summary = f"{crypto_summary}; skipped {', '.join(crypto_skipped_providers)} on cooldown."
        self.last_provider_report["crypto"] = {
            "provider": selected_crypto_provider,
            "preferred_provider": self.crypto_data_provider,
            "actual_provider": selected_crypto_provider,
            "fallback_used": bool(crypto_used_providers and crypto_used_providers[0] != self.crypto_data_provider) or len(crypto_used_providers) > 1,
            "asset_kind": "crypto",
            "attempted_assets": len(crypto_assets),
            "successful_assets": len(crypto_latest),
            "failed_assets": max(len(crypto_assets) - len(crypto_latest), 0),
            "status": (
                "ok"
                if len(crypto_latest) == len(crypto_assets)
                else ("warn" if crypto_latest else "error")
            ),
            "message": _provider_message(
                kind_name="crypto",
                preferred_provider=self.crypto_data_provider,
                actual_provider=selected_crypto_provider,
                provider_summary=crypto_summary,
                kind_success=len(crypto_latest),
                fallback_used=bool(crypto_used_providers and crypto_used_providers[0] != self.crypto_data_provider) or len(crypto_used_providers) > 1,
            ),
        }
        try:
            services_by_name = {
                "alpaca": self.alpaca_service,
                "alphavantage": self.alphavantage_service,
                "finimpulse": self.finimpulse_service,
                "twelvedata": self.twelvedata_service,
            }
            primary_name = self.etf_data_provider if self.etf_data_provider in services_by_name else "alpaca"
            fallback_order = [name for name in ("twelvedata", "alphavantage", "finimpulse") if name != primary_name]
            market_latest: dict[str, MarketTick] = {}
            remaining_assets = list(market_assets)
            provider_messages: list[str] = []
            used_providers: list[str] = []
            skipped_providers: list[str] = []
            cache_hits = 0
            cache_symbols: list[str] = []

            primary_service = services_by_name[primary_name]
            if not self._provider_in_cooldown(db, primary_name):
                primary_latest = primary_service.persist(db, remaining_assets)
                used_providers.append(primary_name)
                provider_messages.append(primary_service.last_message)
                market_latest.update(primary_latest)
                if primary_latest:
                    remaining_assets = [asset for asset in remaining_assets if asset.symbol not in primary_latest]
            else:
                skipped_providers.append(primary_name)
                provider_messages.append(f"{primary_name} cooling down after recent provider failures")

            if remaining_assets and primary_name == "alpaca":
                cached_ticks = self._recent_cached_ticks(
                    db,
                    remaining_assets,
                    source="alpaca",
                    max_age_seconds=self.alpaca_quote_cache_ttl_seconds,
                )
                if cached_ticks:
                    market_latest.update(cached_ticks)
                    cache_hits = len(cached_ticks)
                    cache_symbols = sorted(cached_ticks)
                    provider_messages.append(
                        f"Reused {cache_hits} recent Alpaca cached quote(s): {', '.join(cache_symbols)}."
                    )
                    remaining_assets = [asset for asset in remaining_assets if asset.symbol not in cached_ticks]

            if remaining_assets:
                provider_messages.append("Emergency fallback chain engaged for uncovered ETF/stock symbols.")
                for name in fallback_order:
                    if self._provider_in_cooldown(db, name):
                        skipped_providers.append(name)
                        provider_messages.append(f"{name} cooling down after recent provider failures")
                        continue
                    if not remaining_assets:
                        break
                    provider_latest = services_by_name[name].persist(db, remaining_assets)
                    used_providers.append(name)
                    provider_messages.append(services_by_name[name].last_message)
                    market_latest.update(provider_latest)
                    if provider_latest:
                        remaining_assets = [asset for asset in remaining_assets if asset.symbol not in provider_latest]
        except Exception as exc:
            logger.warning("Market data provider chain failed for ETF/stock universe: %s", exc)
            market_latest = {}
            selected_provider = self.etf_data_provider
            self.last_provider_report["etf"] = {
                "provider": selected_provider,
                "preferred_provider": self.etf_data_provider,
                "actual_provider": selected_provider,
                "fallback_used": False,
                "cache_used": False,
                "asset_kind": "etf",
                "attempted_assets": len([asset for asset in market_assets if asset.kind == AssetKind.ETF]),
                "successful_assets": 0,
                "failed_assets": len([asset for asset in market_assets if asset.kind == AssetKind.ETF]),
                "status": "error",
                "message": f"ETF provider chain failed: {exc}",
            }
            self.last_provider_report["stock"] = {
                "provider": selected_provider,
                "preferred_provider": self.etf_data_provider,
                "actual_provider": selected_provider,
                "fallback_used": False,
                "cache_used": False,
                "asset_kind": "stock",
                "attempted_assets": len([asset for asset in market_assets if asset.kind == AssetKind.STOCK]),
                "successful_assets": 0,
                "failed_assets": len([asset for asset in market_assets if asset.kind == AssetKind.STOCK]),
                "status": "error",
                "message": f"Stock provider chain failed: {exc}",
            }
        else:
            actual_chain = list(used_providers)
            if cache_hits:
                actual_chain.append("alpaca_cache")
            selected_provider = _provider_chain_label(actual_chain)
            provider_summary = "; ".join(provider_messages) if provider_messages else "No market providers were available."
            if skipped_providers:
                provider_summary = f"{provider_summary}; skipped {', '.join(skipped_providers)} on cooldown."
            for kind_name, kind_enum in (("etf", AssetKind.ETF), ("stock", AssetKind.STOCK)):
                kind_assets = [asset for asset in market_assets if asset.kind == kind_enum]
                kind_success = len([asset for asset in kind_assets if asset.symbol in market_latest])
                attempted = len(kind_assets)
                status = "ok"
                if kind_success < attempted:
                    status = "warn" if kind_success > 0 else "error"
                fallback_used = any(name != primary_name for name in used_providers[1:]) or (
                    used_providers and used_providers[0] != primary_name
                )
                if primary_name == "alpaca" and kind_success == attempted and not fallback_used:
                    status = "ok"
                self.last_provider_report[kind_name] = {
                    "provider": selected_provider,
                    "preferred_provider": self.etf_data_provider,
                    "actual_provider": selected_provider,
                    "fallback_used": fallback_used,
                    "cache_used": bool(cache_hits),
                    "asset_kind": kind_name,
                    "attempted_assets": attempted,
                    "successful_assets": kind_success,
                    "failed_assets": max(attempted - kind_success, 0),
                    "status": status,
                    "message": _provider_message(
                        kind_name=kind_name,
                        preferred_provider=self.etf_data_provider,
                        actual_provider=selected_provider,
                        provider_summary=provider_summary,
                        kind_success=kind_success,
                        fallback_used=fallback_used,
                    ),
                }
        latest.update(market_latest)
        return latest

    def _recent_cached_ticks(
        self,
        db: Session,
        assets: list[Asset],
        *,
        source: str,
        max_age_seconds: int,
    ) -> dict[str, MarketTick]:
        cached: dict[str, MarketTick] = {}
        cutoff = datetime.utcnow() - timedelta(seconds=max_age_seconds)
        for asset in assets:
            tick = db.scalar(
                select(MarketTick)
                .where(
                    MarketTick.asset_id == asset.id,
                    MarketTick.source == source,
                    MarketTick.captured_at >= cutoff,
                )
                .order_by(MarketTick.captured_at.desc())
                .limit(1)
            )
            if tick:
                cached[asset.symbol] = tick
        return cached

    def _provider_in_cooldown(self, db: Session, provider_name: str) -> bool:
        if provider_name == "alpaca":
            return False
        samples = db.scalars(
            select(ProviderHealthSample)
            .order_by(ProviderHealthSample.created_at.desc())
            .limit(30)
        ).all()
        latest_sample = next(
            (
                sample
                for sample in samples
                if sample.provider == provider_name or provider_name in (sample.provider or "")
            ),
            None,
        )
        if not latest_sample:
            return False
        message = (latest_sample.message or "").lower()
        is_rate_limited = "429" in message or "rate limit" in message or "cooldown" in message
        cooldown_seconds = (
            self.provider_rate_limit_cooldown_seconds
            if is_rate_limited
            else self.provider_error_cooldown_seconds
        )
        return latest_sample.created_at >= datetime.utcnow() - timedelta(seconds=cooldown_seconds) and latest_sample.status in {"warn", "error"}
