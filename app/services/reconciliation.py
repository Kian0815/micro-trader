from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Asset, ExecutionIntent, ExecutionIntentStatus, Position, PositionStatus, ReconciliationSnapshot
from app.services.brokers import build_broker_adapter
from app.services.risk import RiskEngine


@dataclass
class ReconciliationStatus:
    status: str
    mode: str
    execution_target: str
    provider: str
    broker_connected: bool
    broker_account_id: str | None
    broker_buying_power: str | None
    ledger_open_positions: int
    ledger_closed_positions: int
    ledger_open_notional_eur: float
    ledger_realized_pnl_eur: float
    pending_intents: int
    failed_intents: int
    message: str
    broker_open_positions: int = 0
    broker_open_orders: int = 0
    broker_filled_orders: int = 0
    position_mismatches: list[str] | None = None
    intent_mismatches: list[str] | None = None
    broker_positions: list[dict] | None = None
    recent_broker_orders: list[dict] | None = None


class ReconciliationService:
    def __init__(self, settings: Settings, risk_engine: RiskEngine) -> None:
        self.settings = settings
        self.risk_engine = risk_engine
        self.broker_adapter = build_broker_adapter(settings)

    def snapshot(self, db: Session) -> ReconciliationStatus:
        broker_status = self.broker_adapter.status()
        broker_positions = self.broker_adapter.list_positions() if broker_status.connected else []
        broker_orders = self.broker_adapter.list_orders(status="all", limit=25) if broker_status.connected else []
        open_positions = int(db.scalar(select(func.count(Position.id)).where(Position.status == PositionStatus.OPEN)) or 0)
        closed_positions = int(db.scalar(select(func.count(Position.id)).where(Position.status == PositionStatus.CLOSED)) or 0)
        pending_intents = int(
            db.scalar(select(func.count(ExecutionIntent.id)).where(ExecutionIntent.status == ExecutionIntentStatus.PENDING)) or 0
        )
        failed_intents = int(
            db.scalar(select(func.count(ExecutionIntent.id)).where(ExecutionIntent.status == ExecutionIntentStatus.FAILED)) or 0
        )
        open_notional = self.risk_engine.gross_open_notional(db)
        realized_pnl = self.risk_engine.realized_pnl(db)
        ledger_positions = db.scalars(
            select(Position).join(Asset, Asset.id == Position.asset_id).where(Position.status == PositionStatus.OPEN)
        ).all()
        ledger_symbols: dict[str, float] = {}
        for position in ledger_positions:
            symbol = position.asset.symbol if position.asset else ""
            if not symbol:
                continue
            ledger_symbols[symbol] = ledger_symbols.get(symbol, 0.0) + float(position.quantity)
        broker_symbols = {row.symbol: float(row.qty) for row in broker_positions}
        position_mismatches: list[str] = []
        for symbol in sorted(set(ledger_symbols) | set(broker_symbols)):
            ledger_qty = round(ledger_symbols.get(symbol, 0.0), 8)
            broker_qty = round(broker_symbols.get(symbol, 0.0), 8)
            if abs(ledger_qty - broker_qty) > 0.0001:
                position_mismatches.append(f"{symbol}: ledger {ledger_qty} vs broker {broker_qty}")

        intent_mismatches: list[str] = []
        broker_orders_by_client = {row.client_order_id: row for row in broker_orders if row.client_order_id}
        broker_target_intents = db.scalars(
            select(ExecutionIntent)
            .where(ExecutionIntent.execution_target == "broker")
            .order_by(ExecutionIntent.created_at.desc())
            .limit(50)
        ).all()
        for intent in broker_target_intents:
            if intent.broker_order_id and intent.status == ExecutionIntentStatus.FILLED:
                continue
            if intent.intent_key not in broker_orders_by_client:
                intent_mismatches.append(f"{intent.intent_key}: no broker order matched this execution intent")
            else:
                broker_order = broker_orders_by_client[intent.intent_key]
                if intent.broker_order_id and broker_order.broker_order_id != intent.broker_order_id:
                    intent_mismatches.append(
                        f"{intent.intent_key}: ledger broker order {intent.broker_order_id} differs from broker {broker_order.broker_order_id}"
                    )

        status = "ok"
        messages: list[str] = []
        if self.settings.broker_execution_target != "internal":
            status = "warn"
            messages.append("Execution target is not internal, so the paper ledger is now audit-only.")
        else:
            messages.append("Internal paper ledger is the only active execution path.")
        if self.settings.broker_mode != "paper":
            status = "blocked"
            messages.append("Internal paper execution is blocked because broker mode is not paper.")
        if pending_intents > 0:
            status = "warn" if status == "ok" else status
            messages.append(f"{pending_intents} execution intent(s) are still pending.")
        if failed_intents > 0:
            status = "warn" if status == "ok" else status
            messages.append(f"{failed_intents} execution intent(s) failed and need review.")
        if self.settings.broker_execution_target == "broker" and not broker_status.connected:
            status = "blocked"
            messages.append("Broker execution target is configured but the broker is not connected.")
        if broker_status.connected and position_mismatches:
            status = "warn" if status == "ok" else status
            messages.append(f"{len(position_mismatches)} broker/ledger position mismatch(es) detected.")
        if broker_status.connected and intent_mismatches:
            status = "warn" if status == "ok" else status
            messages.append(f"{len(intent_mismatches)} broker execution intent mismatch(es) detected.")
        if self.settings.broker_mode == "live" and not self.settings.broker_live_confirmed:
            status = "blocked"
            messages.append("Live broker mode is configured without BROKER_LIVE_CONFIRMED=true.")

        return ReconciliationStatus(
            status=status,
            mode=self.settings.broker_mode,
            execution_target=self.settings.broker_execution_target,
            provider=broker_status.provider,
            broker_connected=broker_status.connected,
            broker_account_id=broker_status.account_id,
            broker_buying_power=broker_status.buying_power,
            ledger_open_positions=open_positions,
            ledger_closed_positions=closed_positions,
            ledger_open_notional_eur=round(open_notional, 4),
            ledger_realized_pnl_eur=round(realized_pnl, 4),
            pending_intents=pending_intents,
            failed_intents=failed_intents,
            message=" ".join(messages),
            broker_open_positions=len(broker_positions),
            broker_open_orders=len([row for row in broker_orders if row.status in {"new", "accepted", "pending_new", "partially_filled"}]),
            broker_filled_orders=len([row for row in broker_orders if row.status == "filled"]),
            position_mismatches=position_mismatches,
            intent_mismatches=intent_mismatches,
            broker_positions=[
                {
                    "symbol": row.symbol,
                    "qty": row.qty,
                    "market_value": row.market_value,
                    "side": row.side,
                    "avg_entry_price": row.avg_entry_price,
                    "current_price": row.current_price,
                    "unrealized_pl": row.unrealized_pl,
                    "currency": row.currency,
                }
                for row in broker_positions
            ],
            recent_broker_orders=[
                {
                    "broker_order_id": row.broker_order_id,
                    "client_order_id": row.client_order_id,
                    "symbol": row.symbol,
                    "side": row.side,
                    "status": row.status,
                    "notional": row.notional,
                    "qty": row.qty,
                    "filled_qty": row.filled_qty,
                    "filled_avg_price": row.filled_avg_price,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                }
                for row in broker_orders[:10]
            ],
        )

    def record_snapshot(self, db: Session) -> ReconciliationSnapshot:
        snapshot = self.snapshot(db)
        row = ReconciliationSnapshot(
            status=snapshot.status,
            mode=snapshot.mode,
            execution_target=snapshot.execution_target,
            provider=snapshot.provider,
            ledger_open_positions=snapshot.ledger_open_positions,
            ledger_closed_positions=snapshot.ledger_closed_positions,
            ledger_open_notional_eur=snapshot.ledger_open_notional_eur,
            ledger_realized_pnl_eur=snapshot.ledger_realized_pnl_eur,
            pending_intents=snapshot.pending_intents,
            failed_intents=snapshot.failed_intents,
            broker_connected=snapshot.broker_connected,
            broker_account_id=snapshot.broker_account_id,
            broker_buying_power=snapshot.broker_buying_power,
            message=snapshot.message,
        )
        db.add(row)
        return row
