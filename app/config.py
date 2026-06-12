from functools import lru_cache
from urllib.parse import quote

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Micro Trader"
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://microtrader:microtrader@db:5432/microtrader"
    host_database_url: str = "postgresql+psycopg://microtrader:microtrader@localhost:5432/microtrader"
    public_equity_state_path: str = ""
    alphavantage_api_key: str = ""
    crypto_data_provider: str = "binance"
    etf_data_provider: str = "alpaca"
    finimpulse_api_token: str = ""
    twelvedata_api_key: str = ""
    broker_provider: str = "none"
    broker_mode: str = "paper"
    broker_enabled: bool = False
    broker_execution_target: str = "internal"
    broker_live_confirmed: bool = False
    live_emergency_stop: bool = True
    live_runbook_acknowledged: bool = False
    live_alerts_configured: bool = False
    operator_alert_transport: str = "none"
    operator_alert_webhook_url: str = ""
    operator_alert_telegram_bot_token: str = ""
    operator_alert_telegram_chat_id: str = ""
    operator_alert_slack_webhook_url: str = ""
    operator_alert_discord_webhook_url: str = ""
    operator_alert_whatsapp_bridge_url: str = ""
    operator_alert_signal_bridge_url: str = ""
    operator_alert_events_raw: str = Field(
        default="worker_failure,trade_fill,trade_rejection",
        alias="OPERATOR_ALERT_EVENTS",
    )
    alpaca_api_key: str = ""
    alpaca_api_secret: str = ""
    alpaca_base_url: str = ""
    fx_rate_provider: str = "frankfurter"
    fx_quote_ttl_seconds: int = 1800
    fx_usd_buffer_pct: float = 0.005
    log_level: str = "INFO"
    trading_enabled: bool = True
    simulation_enabled: bool = True
    tradeable_asset_kinds_raw: str = Field(default="etf,stock,crypto", alias="TRADEABLE_ASSET_KINDS")
    simulation_asset_kinds_raw: str = Field(default="etf,stock,crypto", alias="SIMULATION_ASSET_KINDS")
    unattended_setup_statuses_raw: str = Field(default="approved", alias="UNATTENDED_SETUP_STATUSES")
    min_data_coverage_ratio: float = 1.0
    halt_on_provider_warnings: bool = True
    halt_on_stale_quotes: bool = True
    provider_rate_limit_cooldown_seconds: int = 1800
    provider_error_cooldown_seconds: int = 300
    alpaca_quote_cache_ttl_seconds: int = 3600
    simulation_budgets_raw: str = Field(default="30,100,250", alias="SIMULATION_BUDGETS")

    starting_capital_eur: float = 30.0
    reserve_cash_eur: float = 10.0
    max_notional_per_trade_eur: float = 5.0
    max_open_positions: int = 1
    max_daily_loss_eur: float = 3.0
    max_gross_exposure_pct: float = 0.4
    max_symbol_exposure_pct: float = 0.2
    max_portfolio_drawdown_pct: float = 5.0
    liquidate_on_drawdown_breach: bool = True
    asset_kind_exposure_limits_raw: str = Field(default="etf:0.7,stock:0.2,crypto:0.1", alias="ASSET_KIND_EXPOSURE_LIMITS")
    min_signal_score_to_buy: float = 0.62
    min_sentiment_score_to_buy: float = 0.12
    min_momentum_score_to_buy: float = 0.03
    min_news_items_to_buy: int = 1
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.03
    trailing_stop_pct: float = 0.008
    max_tick_age_seconds: int = 900
    min_minutes_between_trades: int = 30
    worker_interval_seconds: int = 300
    watchlist_raw: str = Field(default="BTC,ETH,SOL,LINK", alias="WATCHLIST")
    etf_watchlist_raw: str = Field(default="SPY,QQQ,VTI", alias="ETF_WATCHLIST")
    stock_watchlist_raw: str = Field(default="AAPL,MSFT,NVDA", alias="STOCK_WATCHLIST")
    news_feeds_raw: str = Field(
        default=(
            "https://www.coindesk.com/arc/outboundfeeds/rss/,"
            "https://cointelegraph.com/rss,"
            "https://news.google.com/rss/search?q=%22SPY%22%20OR%20%22S%26P%20500%22%20OR%20%22SPDR%20S%26P%20500%20ETF%22&hl=en-US&gl=US&ceid=US:en,"
            "https://news.google.com/rss/search?q=%22QQQ%22%20OR%20%22Nasdaq%20100%22%20OR%20%22Invesco%20QQQ%22&hl=en-US&gl=US&ceid=US:en,"
            "https://news.google.com/rss/search?q=%22VTI%22%20OR%20%22Total%20Stock%20Market%22%20OR%20%22Vanguard%20Total%20Stock%20Market%22&hl=en-US&gl=US&ceid=US:en,"
            "https://news.google.com/rss/search?q=%22AAPL%22%20OR%20Apple%20stock&hl=en-US&gl=US&ceid=US:en,"
            "https://news.google.com/rss/search?q=%22MSFT%22%20OR%20Microsoft%20stock&hl=en-US&gl=US&ceid=US:en,"
            "https://news.google.com/rss/search?q=%22NVDA%22%20OR%20NVIDIA%20stock&hl=en-US&gl=US&ceid=US:en"
        ),
        alias="NEWS_FEEDS",
    )

    @property
    def watchlist(self) -> list[str]:
        return [item.strip().upper() for item in self.watchlist_raw.split(",") if item.strip()]

    @property
    def etf_watchlist(self) -> list[str]:
        return [item.strip().upper() for item in self.etf_watchlist_raw.split(",") if item.strip()]

    @property
    def stock_watchlist(self) -> list[str]:
        return [item.strip().upper() for item in self.stock_watchlist_raw.split(",") if item.strip()]

    @property
    def news_feeds(self) -> list[str]:
        feeds = [item.strip() for item in self.news_feeds_raw.split(",") if item.strip()]
        for feed in self._generated_market_feeds():
            if feed not in feeds:
                feeds.append(feed)
        return feeds

    @property
    def tradeable_asset_kinds(self) -> set[str]:
        return self._parse_asset_kinds(self.tradeable_asset_kinds_raw)

    @property
    def simulation_asset_kinds(self) -> set[str]:
        return self._parse_asset_kinds(self.simulation_asset_kinds_raw)

    @property
    def unattended_setup_statuses(self) -> set[str]:
        allowed = {"approved", "watch", "disabled"}
        parsed = {item.strip().lower() for item in self.unattended_setup_statuses_raw.split(",") if item.strip()}
        filtered = parsed & allowed
        return filtered or {"approved"}

    @property
    def simulation_budgets(self) -> list[float]:
        budgets: list[float] = []
        for item in self.simulation_budgets_raw.split(","):
            value = item.strip()
            if not value:
                continue
            try:
                amount = round(float(value), 2)
            except ValueError:
                continue
            if amount > 0:
                budgets.append(amount)
        return budgets or [100.0]

    @property
    def operator_alert_events(self) -> set[str]:
        allowed = {"worker_failure", "trade_fill", "trade_rejection"}
        parsed = {item.strip().lower() for item in self.operator_alert_events_raw.split(",") if item.strip()}
        filtered = parsed & allowed
        return filtered or {"worker_failure", "trade_fill", "trade_rejection"}

    @property
    def supported_operator_alert_transports(self) -> list[str]:
        return [
            "none",
            "telegram",
            "webhook",
            "slack",
            "discord",
            "whatsapp_bridge",
            "signal_bridge",
        ]

    @property
    def asset_kind_exposure_limits(self) -> dict[str, float]:
        allowed = {"crypto", "etf", "stock"}
        parsed: dict[str, float] = {}
        for item in self.asset_kind_exposure_limits_raw.split(","):
            value = item.strip()
            if not value or ":" not in value:
                continue
            key, raw_limit = value.split(":", 1)
            kind = key.strip().lower()
            if kind not in allowed:
                continue
            try:
                limit = float(raw_limit.strip())
            except ValueError:
                continue
            if limit <= 0:
                continue
            parsed[kind] = min(limit, 1.0)
        return parsed or {"etf": 0.7, "stock": 0.2, "crypto": 0.1}

    def _parse_asset_kinds(self, raw_value: str) -> set[str]:
        parsed = {item.strip().lower() for item in raw_value.split(",") if item.strip()}
        allowed = {"crypto", "etf", "stock"}
        filtered = parsed & allowed
        return filtered or {"etf", "stock", "crypto"}

    def _generated_market_feeds(self) -> list[str]:
        etf_queries = {
            "SPY": '"SPY" OR "S&P 500" OR "SPDR S&P 500 ETF"',
            "QQQ": '"QQQ" OR "Nasdaq 100" OR "Invesco QQQ"',
            "VTI": '"VTI" OR "Total Stock Market" OR "Vanguard Total Stock Market"',
        }
        stock_queries = {
            "AAPL": '"AAPL" OR "Apple stock" OR "Apple earnings"',
            "MSFT": '"MSFT" OR "Microsoft stock" OR "Microsoft earnings"',
            "NVDA": '"NVDA" OR "NVIDIA stock" OR "NVIDIA earnings"',
        }
        feeds: list[str] = []
        for symbol in self.etf_watchlist:
            query = etf_queries.get(symbol)
            if query:
                feeds.append(self._google_news_feed(query))
        for symbol in self.stock_watchlist:
            query = stock_queries.get(symbol)
            if query:
                feeds.append(self._google_news_feed(query))
        return feeds

    def _google_news_feed(self, query: str) -> str:
        return f"https://news.google.com/rss/search?q={quote(query)}&hl=en-US&gl=US&ceid=US:en"


@lru_cache
def get_settings() -> Settings:
    return Settings()
