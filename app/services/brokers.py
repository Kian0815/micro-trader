from dataclasses import dataclass

import httpx

from app.config import Settings
from app.services.fx import build_fx_service


@dataclass
class BrokerStatus:
    provider: str
    mode: str
    enabled: bool
    configured: bool
    connected: bool
    account_id: str | None
    account_status: str | None
    buying_power: str | None
    currency: str | None
    message: str


@dataclass
class BrokerOrderPreview:
    provider: str
    mode: str
    endpoint: str
    payload: dict
    warning: str
    requested_notional_eur: float | None = None
    converted_notional_usd: float | None = None
    fx_rate_eur_usd: float | None = None
    fx_rate_provider: str | None = None
    fx_rate_as_of: str | None = None
    fx_buffer_pct: float | None = None


@dataclass
class BrokerCapabilities:
    provider: str
    mode: str
    execution_target: str
    enabled: bool
    supports_paper: bool
    supports_live: bool
    supported_asset_kinds: list[str]
    requires_usd_notional: bool
    submit_enabled: bool
    live_guard_enabled: bool
    notes: list[str]


@dataclass
class BrokerOrderResult:
    provider: str
    mode: str
    submitted: bool
    dry_run: bool
    endpoint: str
    payload: dict
    client_order_id: str | None
    broker_order_id: str | None
    broker_status: str | None
    message: str
    requested_notional_eur: float | None = None
    converted_notional_usd: float | None = None
    fx_rate_eur_usd: float | None = None
    fx_rate_provider: str | None = None
    fx_rate_as_of: str | None = None
    fx_buffer_pct: float | None = None


@dataclass
class BrokerPosition:
    symbol: str
    qty: float
    market_value: float
    side: str
    avg_entry_price: float | None
    current_price: float | None
    unrealized_pl: float | None
    currency: str | None


@dataclass
class BrokerOrder:
    broker_order_id: str
    client_order_id: str | None
    symbol: str
    side: str
    status: str
    notional: float | None
    qty: float | None
    filled_qty: float | None
    filled_avg_price: float | None
    created_at: str | None
    updated_at: str | None


class BaseBrokerAdapter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.fx_service = build_fx_service(settings)

    def status(self) -> BrokerStatus:
        return BrokerStatus(
            provider="none",
            mode=self.settings.broker_mode,
            enabled=self.settings.broker_enabled,
            configured=False,
            connected=False,
            account_id=None,
            account_status=None,
            buying_power=None,
            currency=None,
            message="No broker adapter selected.",
        )

    def preview_order(self, symbol: str, side: str, notional: float, client_order_id: str | None = None) -> BrokerOrderPreview:
        return BrokerOrderPreview(
            provider="none",
            mode=self.settings.broker_mode,
            endpoint="",
            payload={},
            warning="No real broker adapter selected.",
            requested_notional_eur=round(notional, 2),
        )

    def capabilities(self) -> BrokerCapabilities:
        return BrokerCapabilities(
            provider="none",
            mode=self.settings.broker_mode,
            execution_target=self.settings.broker_execution_target,
            enabled=self.settings.broker_enabled,
            supports_paper=False,
            supports_live=False,
            supported_asset_kinds=[],
            requires_usd_notional=False,
            submit_enabled=False,
            live_guard_enabled=False,
            notes=[
                "No broker provider selected.",
                "Internal paper trading remains the only execution path.",
            ],
        )

    def submit_order(
        self,
        symbol: str,
        side: str,
        notional: float,
        dry_run: bool = True,
        client_order_id: str | None = None,
    ) -> BrokerOrderResult:
        preview = self.preview_order(symbol, side, notional, client_order_id=client_order_id)
        return BrokerOrderResult(
            provider=preview.provider,
            mode=self.settings.broker_mode,
            submitted=False,
            dry_run=dry_run,
            endpoint=preview.endpoint,
            payload=preview.payload,
            client_order_id=client_order_id,
            broker_order_id=None,
            broker_status=None,
            message="No broker adapter selected, so the order was not submitted.",
            requested_notional_eur=preview.requested_notional_eur,
            converted_notional_usd=preview.converted_notional_usd,
            fx_rate_eur_usd=preview.fx_rate_eur_usd,
            fx_rate_provider=preview.fx_rate_provider,
            fx_rate_as_of=preview.fx_rate_as_of,
            fx_buffer_pct=preview.fx_buffer_pct,
        )

    def list_positions(self) -> list[BrokerPosition]:
        return []

    def list_orders(self, status: str = "all", limit: int = 50) -> list[BrokerOrder]:
        return []


class AlpacaBrokerAdapter(BaseBrokerAdapter):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.base_url = settings.alpaca_base_url or (
            "https://paper-api.alpaca.markets" if settings.broker_mode == "paper" else "https://api.alpaca.markets"
        )

    @property
    def configured(self) -> bool:
        return bool(self.settings.alpaca_api_key and self.settings.alpaca_api_secret)

    def status(self) -> BrokerStatus:
        if not self.configured:
            return BrokerStatus(
                provider="alpaca",
                mode=self.settings.broker_mode,
                enabled=self.settings.broker_enabled,
                configured=False,
                connected=False,
                account_id=None,
                account_status=None,
                buying_power=None,
                currency=None,
                message="Alpaca adapter is configured in code but missing API credentials.",
            )

        try:
            with httpx.Client(timeout=10.0, headers=self._headers()) as client:
                response = client.get(f"{self.base_url}/v2/account")
                response.raise_for_status()
                payload = response.json()
            return BrokerStatus(
                provider="alpaca",
                mode=self.settings.broker_mode,
                enabled=self.settings.broker_enabled,
                configured=True,
                connected=True,
                account_id=payload.get("account_number") or payload.get("id"),
                account_status=payload.get("status"),
                buying_power=payload.get("buying_power"),
                currency=payload.get("currency"),
                message="Connected to Alpaca Trading API.",
            )
        except Exception as exc:
            return BrokerStatus(
                provider="alpaca",
                mode=self.settings.broker_mode,
                enabled=self.settings.broker_enabled,
                configured=True,
                connected=False,
                account_id=None,
                account_status=None,
                buying_power=None,
                currency=None,
                message=f"Connection check failed: {exc}",
            )

    def preview_order(self, symbol: str, side: str, notional: float, client_order_id: str | None = None) -> BrokerOrderPreview:
        endpoint = f"{self.base_url}/v2/orders"
        try:
            fx_quote = self.fx_service.latest_eur_usd()
            usd_notional, _ = self.fx_service.eur_to_usd(notional, apply_buffer=True)
        except Exception as exc:
            return BrokerOrderPreview(
                provider="alpaca",
                mode=self.settings.broker_mode,
                endpoint=endpoint,
                payload={},
                warning=f"FX conversion failed, so this broker preview is blocked: {exc}",
                requested_notional_eur=round(notional, 2),
            )
        payload = {
            "symbol": symbol,
            "side": side,
            "type": "market",
            "time_in_force": "day",
            "notional": usd_notional,
        }
        if client_order_id:
            payload["client_order_id"] = client_order_id
        return BrokerOrderPreview(
            provider="alpaca",
            mode=self.settings.broker_mode,
            endpoint=endpoint,
            payload=payload,
            warning=(
                f"Converted EUR {notional:.2f} to USD {usd_notional:.2f} using EUR/USD {fx_quote.rate:.4f} "
                f"with a {self.settings.fx_usd_buffer_pct * 100:.2f}% safety buffer."
            ),
            requested_notional_eur=round(notional, 2),
            converted_notional_usd=usd_notional,
            fx_rate_eur_usd=fx_quote.rate,
            fx_rate_provider=fx_quote.provider,
            fx_rate_as_of=fx_quote.as_of,
            fx_buffer_pct=round(self.settings.fx_usd_buffer_pct * 100, 4),
        )

    def capabilities(self) -> BrokerCapabilities:
        return BrokerCapabilities(
            provider="alpaca",
            mode=self.settings.broker_mode,
            execution_target=self.settings.broker_execution_target,
            enabled=self.settings.broker_enabled,
            supports_paper=True,
            supports_live=True,
            supported_asset_kinds=["etf", "stock"],
            requires_usd_notional=True,
            submit_enabled=self.settings.broker_enabled and self.configured,
            live_guard_enabled=not self.settings.broker_live_confirmed,
            notes=[
                "Paper endpoint is the safest first step for real broker connectivity.",
                "ETF and stock notional should be sized in USD before live submission.",
                "This project still uses the internal ledger as its source of truth unless you explicitly change the execution target.",
            ],
        )

    def submit_order(
        self,
        symbol: str,
        side: str,
        notional: float,
        dry_run: bool = True,
        client_order_id: str | None = None,
    ) -> BrokerOrderResult:
        preview = self.preview_order(symbol, side, notional, client_order_id=client_order_id)
        if not preview.payload:
            return BrokerOrderResult(
                provider="alpaca",
                mode=self.settings.broker_mode,
                submitted=False,
                dry_run=dry_run,
                endpoint=preview.endpoint,
                payload=preview.payload,
                client_order_id=client_order_id,
                broker_order_id=None,
                broker_status=None,
                message=preview.warning,
                requested_notional_eur=preview.requested_notional_eur,
                converted_notional_usd=preview.converted_notional_usd,
                fx_rate_eur_usd=preview.fx_rate_eur_usd,
                fx_rate_provider=preview.fx_rate_provider,
                fx_rate_as_of=preview.fx_rate_as_of,
                fx_buffer_pct=preview.fx_buffer_pct,
            )
        if not self.settings.broker_enabled:
            return BrokerOrderResult(
                provider="alpaca",
                mode=self.settings.broker_mode,
                submitted=False,
                dry_run=dry_run,
                endpoint=preview.endpoint,
                payload=preview.payload,
                client_order_id=client_order_id,
                broker_order_id=None,
                broker_status=None,
                message="Broker submission is disabled. Set BROKER_ENABLED=true to allow broker paper or live calls.",
                requested_notional_eur=preview.requested_notional_eur,
                converted_notional_usd=preview.converted_notional_usd,
                fx_rate_eur_usd=preview.fx_rate_eur_usd,
                fx_rate_provider=preview.fx_rate_provider,
                fx_rate_as_of=preview.fx_rate_as_of,
                fx_buffer_pct=preview.fx_buffer_pct,
            )
        if not self.configured:
            return BrokerOrderResult(
                provider="alpaca",
                mode=self.settings.broker_mode,
                submitted=False,
                dry_run=dry_run,
                endpoint=preview.endpoint,
                payload=preview.payload,
                client_order_id=client_order_id,
                broker_order_id=None,
                broker_status=None,
                message="Broker credentials are missing, so the order was not submitted.",
                requested_notional_eur=preview.requested_notional_eur,
                converted_notional_usd=preview.converted_notional_usd,
                fx_rate_eur_usd=preview.fx_rate_eur_usd,
                fx_rate_provider=preview.fx_rate_provider,
                fx_rate_as_of=preview.fx_rate_as_of,
                fx_buffer_pct=preview.fx_buffer_pct,
            )
        if self.settings.broker_mode == "live" and not self.settings.broker_live_confirmed:
            return BrokerOrderResult(
                provider="alpaca",
                mode=self.settings.broker_mode,
                submitted=False,
                dry_run=dry_run,
                endpoint=preview.endpoint,
                payload=preview.payload,
                client_order_id=client_order_id,
                broker_order_id=None,
                broker_status=None,
                message="Live mode is blocked until BROKER_LIVE_CONFIRMED=true is set explicitly.",
                requested_notional_eur=preview.requested_notional_eur,
                converted_notional_usd=preview.converted_notional_usd,
                fx_rate_eur_usd=preview.fx_rate_eur_usd,
                fx_rate_provider=preview.fx_rate_provider,
                fx_rate_as_of=preview.fx_rate_as_of,
                fx_buffer_pct=preview.fx_buffer_pct,
            )
        if dry_run:
            return BrokerOrderResult(
                provider="alpaca",
                mode=self.settings.broker_mode,
                submitted=False,
                dry_run=True,
                endpoint=preview.endpoint,
                payload=preview.payload,
                client_order_id=client_order_id,
                broker_order_id=None,
                broker_status=None,
                message="Dry run only. The broker payload is ready, but nothing was sent.",
                requested_notional_eur=preview.requested_notional_eur,
                converted_notional_usd=preview.converted_notional_usd,
                fx_rate_eur_usd=preview.fx_rate_eur_usd,
                fx_rate_provider=preview.fx_rate_provider,
                fx_rate_as_of=preview.fx_rate_as_of,
                fx_buffer_pct=preview.fx_buffer_pct,
            )

        with httpx.Client(timeout=15.0, headers=self._headers()) as client:
            response = client.post(preview.endpoint, json=preview.payload)
            response.raise_for_status()
            payload = response.json()
        return BrokerOrderResult(
            provider="alpaca",
            mode=self.settings.broker_mode,
            submitted=True,
            dry_run=False,
            endpoint=preview.endpoint,
            payload=preview.payload,
            client_order_id=payload.get("client_order_id") or client_order_id,
            broker_order_id=payload.get("id"),
            broker_status=payload.get("status"),
            message="Order submitted to Alpaca Trading API.",
            requested_notional_eur=preview.requested_notional_eur,
            converted_notional_usd=preview.converted_notional_usd,
            fx_rate_eur_usd=preview.fx_rate_eur_usd,
            fx_rate_provider=preview.fx_rate_provider,
            fx_rate_as_of=preview.fx_rate_as_of,
            fx_buffer_pct=preview.fx_buffer_pct,
        )

    def list_positions(self) -> list[BrokerPosition]:
        if not self.configured:
            return []
        try:
            with httpx.Client(timeout=15.0, headers=self._headers()) as client:
                response = client.get(f"{self.base_url}/v2/positions")
                response.raise_for_status()
                payload = response.json()
        except Exception:
            return []
        rows: list[BrokerPosition] = []
        for item in payload:
            try:
                qty = float(item.get("qty") or 0.0)
                market_value = float(item.get("market_value") or 0.0)
                rows.append(
                    BrokerPosition(
                        symbol=str(item.get("symbol") or "").upper(),
                        qty=abs(qty),
                        market_value=market_value,
                        side="long" if qty >= 0 else "short",
                        avg_entry_price=float(item.get("avg_entry_price")) if item.get("avg_entry_price") is not None else None,
                        current_price=float(item.get("current_price")) if item.get("current_price") is not None else None,
                        unrealized_pl=float(item.get("unrealized_pl")) if item.get("unrealized_pl") is not None else None,
                        currency=item.get("currency"),
                    )
                )
            except (TypeError, ValueError):
                continue
        return rows

    def list_orders(self, status: str = "all", limit: int = 50) -> list[BrokerOrder]:
        if not self.configured:
            return []
        try:
            with httpx.Client(timeout=15.0, headers=self._headers()) as client:
                response = client.get(
                    f"{self.base_url}/v2/orders",
                    params={"status": status, "limit": limit, "direction": "desc"},
                )
                response.raise_for_status()
                payload = response.json()
        except Exception:
            return []
        rows: list[BrokerOrder] = []
        for item in payload:
            try:
                rows.append(
                    BrokerOrder(
                        broker_order_id=str(item.get("id") or ""),
                        client_order_id=item.get("client_order_id"),
                        symbol=str(item.get("symbol") or "").upper(),
                        side=str(item.get("side") or ""),
                        status=str(item.get("status") or ""),
                        notional=float(item.get("notional")) if item.get("notional") is not None else None,
                        qty=float(item.get("qty")) if item.get("qty") is not None else None,
                        filled_qty=float(item.get("filled_qty")) if item.get("filled_qty") is not None else None,
                        filled_avg_price=float(item.get("filled_avg_price")) if item.get("filled_avg_price") is not None else None,
                        created_at=item.get("created_at"),
                        updated_at=item.get("updated_at"),
                    )
                )
            except (TypeError, ValueError):
                continue
        return rows

    def _headers(self) -> dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.settings.alpaca_api_key,
            "APCA-API-SECRET-KEY": self.settings.alpaca_api_secret,
        }


def build_broker_adapter(settings: Settings) -> BaseBrokerAdapter:
    provider = settings.broker_provider.lower().strip()
    if provider == "alpaca":
        return AlpacaBrokerAdapter(settings)
    return BaseBrokerAdapter(settings)
