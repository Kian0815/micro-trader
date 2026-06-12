from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Asset, ExecutionIntent, ExecutionIntentStatus, Position, Signal, Trade, TradeMode, TradeSide, TradeStatus
from app.services.brokers import build_broker_adapter
from app.services.operator_alerts import build_operator_alert_service


class ExecutionIntentService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.broker_adapter = build_broker_adapter(settings)
        self.operator_alert_service = build_operator_alert_service(settings)

    @property
    def internal_execution_allowed(self) -> bool:
        return self.settings.broker_execution_target.strip().lower() == "internal" and self.settings.broker_mode == "paper"

    def target_summary(self) -> dict[str, object]:
        blocked_reason = None
        if self.settings.broker_execution_target.strip().lower() != "internal":
            blocked_reason = (
                "Internal paper execution is disabled because BROKER_EXECUTION_TARGET is not set to internal."
            )
        elif self.settings.broker_mode != "paper":
            blocked_reason = "Internal paper execution is disabled because BROKER_MODE is not paper."
        return {
            "mode": self.settings.broker_mode,
            "execution_target": self.settings.broker_execution_target,
            "internal_execution_allowed": self.internal_execution_allowed,
            "live_guard_enabled": self.settings.broker_mode == "live" and not self.settings.broker_live_confirmed,
            "blocked_reason": blocked_reason,
        }

    def get_or_create_intent(
        self,
        db: Session,
        *,
        intent_key: str,
        asset: Asset,
        side: TradeSide,
        reason: str,
        source: str,
        notional_eur: float = 0.0,
        signal: Signal | None = None,
        price_hint: float | None = None,
    ) -> tuple[ExecutionIntent, bool]:
        existing = db.scalar(select(ExecutionIntent).where(ExecutionIntent.intent_key == intent_key))
        if existing:
            return existing, False

        intent = ExecutionIntent(
            intent_key=intent_key,
            asset_id=asset.id,
            signal_id=signal.id if signal else None,
            mode=self.settings.broker_mode,
            execution_target=self.settings.broker_execution_target,
            side=side,
            status=ExecutionIntentStatus.PENDING,
            source=source,
            notional_eur=round(notional_eur, 4),
            price_hint=price_hint,
            reason=reason,
            broker_provider=self.settings.broker_provider or "none",
            updated_at=datetime.utcnow(),
        )
        db.add(intent)
        db.flush()
        return intent, True

    def mark_skipped(self, intent: ExecutionIntent, *, error_message: str = "") -> None:
        intent.status = ExecutionIntentStatus.SKIPPED
        intent.error_message = error_message
        intent.updated_at = datetime.utcnow()

    def mark_failed(self, intent: ExecutionIntent, *, error_message: str, asset_symbol: str | None = None) -> None:
        intent.status = ExecutionIntentStatus.FAILED
        intent.error_message = error_message
        intent.updated_at = datetime.utcnow()
        self.operator_alert_service.emit(
            event_type="trade_rejection",
            severity="danger",
            title=f"{asset_symbol or 'Trade'} intent failed",
            message=error_message,
            details={
                "intent_key": intent.intent_key,
                "asset_symbol": asset_symbol,
                "side": intent.side.value,
                "execution_target": intent.execution_target,
                "mode": intent.mode,
            },
        )

    def mark_filled(
        self,
        intent: ExecutionIntent,
        *,
        quantity: float,
        position: Position | None = None,
        broker_order_id: str | None = None,
        broker_status: str | None = None,
        asset_symbol: str | None = None,
    ) -> None:
        intent.status = ExecutionIntentStatus.FILLED
        intent.quantity = quantity
        intent.position_id = position.id if position else intent.position_id
        intent.broker_order_id = broker_order_id
        intent.broker_status = broker_status
        intent.updated_at = datetime.utcnow()
        self.operator_alert_service.emit(
            event_type="trade_fill",
            severity="ok",
            title=f"{asset_symbol or 'Trade'} {intent.side.value} filled",
            message=f"{asset_symbol or 'Asset'} {intent.side.value} intent marked filled in {intent.mode}/{intent.execution_target}.",
            details={
                "intent_key": intent.intent_key,
                "asset_symbol": asset_symbol,
                "side": intent.side.value,
                "quantity": quantity,
                "execution_target": intent.execution_target,
                "mode": intent.mode,
                "broker_order_id": broker_order_id,
                "broker_status": broker_status,
            },
        )

    def record_trade(
        self,
        db: Session,
        *,
        asset_id: int,
        side: TradeSide,
        status: TradeStatus,
        notional_eur: float,
        quantity: float,
        price: float,
        reason: str,
    ) -> Trade:
        trade = Trade(
            asset_id=asset_id,
            mode=TradeMode.PAPER,
            execution_target=self.settings.broker_execution_target,
            side=side,
            status=status,
            notional_eur=round(notional_eur, 4),
            quantity=quantity,
            price=price,
            reason=reason,
        )
        db.add(trade)
        return trade
