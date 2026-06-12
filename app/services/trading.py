from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Asset,
    AssetKind,
    ExecutionIntentStatus,
    MarketTick,
    Position,
    PositionStatus,
    Signal,
    SignalAction,
    Trade,
    TradeSide,
    TradeStatus,
)
from app.services.evaluation import StrategyProofService
from app.services.execution import ExecutionIntentService
from app.services.opportunity import BestOpportunitySelector
from app.services.risk import RiskEngine
from app.services.strategy import extract_setup_type


class PaperTrader:
    def __init__(
        self,
        risk_engine: RiskEngine,
        execution_service: ExecutionIntentService,
        proof_service: StrategyProofService,
        opportunity_selector: BestOpportunitySelector,
        allowed_asset_kinds: set[str] | None = None,
        allowed_setup_statuses: set[str] | None = None,
    ) -> None:
        self.risk_engine = risk_engine
        self.execution_service = execution_service
        self.proof_service = proof_service
        self.opportunity_selector = opportunity_selector
        self.allowed_asset_kinds = allowed_asset_kinds or {"etf"}
        self.allowed_setup_statuses = allowed_setup_statuses or {"approved"}

    def execute(self, db: Session, signals: list[Signal]) -> None:
        if not self.risk_engine:
            return
        if not self.execution_service.internal_execution_allowed:
            for signal in signals:
                asset = db.scalar(select(Asset).where(Asset.id == signal.asset_id))
                if not asset:
                    continue
                latest_tick = db.scalar(
                    select(MarketTick).where(MarketTick.asset_id == asset.id).order_by(MarketTick.captured_at.desc()).limit(1)
                )
                if not latest_tick:
                    continue
                self._record_skip(
                    db,
                    asset,
                    TradeSide.SELL if signal.action == SignalAction.SELL else TradeSide.BUY,
                    float(latest_tick.price),
                    self.execution_service.target_summary()["blocked_reason"] or "Internal execution is disabled.",
                    intent_key=self._signal_intent_key(signal, "blocked"),
                    source="engine",
                    signal=signal,
                )
            db.commit()
            return
        asset_ids = {signal.asset_id for signal in signals}
        assets = {
            asset.id: asset
            for asset in db.scalars(select(Asset).where(Asset.id.in_(asset_ids))).all()
        }
        signal_lookup = {signal.asset_id: signal for signal in signals}
        approval_map = self.proof_service.approval_map(db)

        self.manage_open_positions(db, signal_lookup)
        if self.risk_engine.drawdown_lock_active(db):
            if self.risk_engine.liquidate_on_drawdown_breach:
                self._liquidate_open_positions(db, "Portfolio drawdown lock triggered capital-preservation liquidation.")
            for signal in signals:
                asset = assets.get(signal.asset_id)
                if asset:
                    latest_tick = db.scalar(
                        select(MarketTick).where(MarketTick.asset_id == asset.id).order_by(MarketTick.captured_at.desc()).limit(1)
                    )
                    if latest_tick:
                        self._record_skip(
                            db,
                            asset,
                            TradeSide.SELL if signal.action == SignalAction.SELL else TradeSide.BUY,
                            float(latest_tick.price),
                            "Skipped because portfolio drawdown lock is active.",
                            intent_key=self._signal_intent_key(signal, "drawdown-lock"),
                            source="risk",
                            signal=signal,
                        )
            db.commit()
            return

        buy_signals: list[Signal] = []
        best_buy_candidate = self.opportunity_selector.best_eligible_candidate(db, signals=signals)

        for signal in signals:
            asset = assets.get(signal.asset_id)
            if not asset:
                continue
            latest_tick = db.scalar(
                select(MarketTick)
                .where(MarketTick.asset_id == asset.id)
                .order_by(MarketTick.captured_at.desc())
                .limit(1)
            )
            if not latest_tick:
                continue

            if self._tick_is_stale(latest_tick):
                self._record_skip(
                    db,
                    asset,
                    TradeSide.BUY,
                    float(latest_tick.price),
                    "Skipped because market data is stale.",
                    intent_key=self._signal_intent_key(signal, "stale"),
                    source="engine",
                    signal=signal,
                )
                continue

            if asset.kind.value not in self.allowed_asset_kinds:
                self._record_skip(
                    db,
                    asset,
                    TradeSide.SELL if signal.action == SignalAction.SELL else TradeSide.BUY,
                    float(latest_tick.price),
                    "Skipped because this asset universe is disabled.",
                    intent_key=self._signal_intent_key(signal, "universe-disabled"),
                    source="engine",
                    signal=signal,
                )
                continue

            if asset.kind in {AssetKind.ETF, AssetKind.STOCK} and not self._is_us_market_open():
                self._record_skip(
                    db,
                    asset,
                    TradeSide.SELL if signal.action == SignalAction.SELL else TradeSide.BUY,
                    float(latest_tick.price),
                    "Skipped because the US market session is closed.",
                    intent_key=self._signal_intent_key(signal, "market-closed"),
                    source="engine",
                    signal=signal,
                )
                continue

            if signal.action == SignalAction.BUY:
                buy_signals.append(signal)
            elif signal.action == SignalAction.SELL:
                self._try_sell(db, asset, latest_tick.price, signal)

        best_buy_asset_id = best_buy_candidate.asset_id if best_buy_candidate else None
        for signal in buy_signals:
            asset = assets.get(signal.asset_id)
            if not asset:
                continue
            latest_tick = db.scalar(
                select(MarketTick)
                .where(MarketTick.asset_id == asset.id)
                .order_by(MarketTick.captured_at.desc())
                .limit(1)
            )
            if not latest_tick:
                continue
            if best_buy_asset_id is None:
                self._try_buy(db, asset, latest_tick.price, signal, approval_map)
                continue
            if signal.asset_id != best_buy_asset_id:
                self._record_skip(
                    db,
                    asset,
                    TradeSide.BUY,
                    float(latest_tick.price),
                    f"Skipped buy because {best_buy_candidate.symbol} ranked as the strongest current opportunity across enabled lanes.",
                    intent_key=self._signal_intent_key(signal, "not-best-opportunity"),
                    source="opportunity",
                    signal=signal,
                )
                continue
            self._try_buy(db, asset, float(latest_tick.price), signal, approval_map)

        db.commit()

    def manage_open_positions(self, db: Session, signal_lookup: dict[int, Signal] | None = None) -> int:
        closed_positions = 0
        positions = db.scalars(select(Position).where(Position.status == PositionStatus.OPEN)).all()
        for position in positions:
            latest_tick = db.scalar(
                select(MarketTick)
                .where(MarketTick.asset_id == position.asset_id)
                .order_by(MarketTick.captured_at.desc())
                .limit(1)
            )
            if not latest_tick:
                continue
            if self._tick_is_stale(latest_tick):
                continue

            asset = db.scalar(select(Asset).where(Asset.id == position.asset_id))
            if asset and asset.kind in {AssetKind.ETF, AssetKind.STOCK} and not self._is_us_market_open():
                continue

            current_price = float(latest_tick.price)
            protective_stop = max(position.stop_loss, current_price * (1 - self.risk_engine.trailing_stop_pct))
            if current_price > position.entry_price:
                position.stop_loss = round(protective_stop, 4)

            signal = signal_lookup.get(position.asset_id) if signal_lookup else None
            if current_price <= position.stop_loss:
                self._close_position(
                    db,
                    position,
                    current_price,
                    "Automatic stop loss triggered to cap downside.",
                    intent_key=f"protective-stop:{position.id}:{int(latest_tick.captured_at.timestamp())}",
                    source="risk",
                )
                closed_positions += 1
            elif current_price >= position.take_profit:
                self._close_position(
                    db,
                    position,
                    current_price,
                    "Automatic take profit locked in gains.",
                    intent_key=f"take-profit:{position.id}:{int(latest_tick.captured_at.timestamp())}",
                    source="risk",
                )
                closed_positions += 1
            elif signal and signal.action == SignalAction.SELL:
                self._close_position(
                    db,
                    position,
                    current_price,
                    "Automatic defensive exit after a sell signal.",
                    intent_key=self._signal_intent_key(signal, f"defensive-sell-position-{position.id}"),
                    source="engine",
                    signal=signal,
                )
                closed_positions += 1
        return closed_positions

    def manual_buy(self, db: Session, asset_symbol: str, notional_eur: float, reason: str) -> Position:
        if not self.execution_service.internal_execution_allowed:
            blocked_reason = self.execution_service.target_summary()["blocked_reason"] or "Internal execution is disabled."
            raise ValueError(str(blocked_reason))
        asset = db.scalar(select(Asset).where(Asset.symbol == asset_symbol.upper()))
        if not asset:
            raise ValueError(f"Unknown asset symbol: {asset_symbol}")
        latest_tick = db.scalar(
            select(MarketTick).where(MarketTick.asset_id == asset.id).order_by(MarketTick.captured_at.desc()).limit(1)
        )
        if not latest_tick:
            raise ValueError("No market price available for this asset.")

        existing_open = db.scalar(
            select(Position).where(Position.asset_id == asset.id, Position.status == PositionStatus.OPEN)
        )
        if existing_open:
            raise ValueError("A position is already open for this asset.")

        risk = self.risk_engine.can_open_position(db, asset)
        if not risk.allowed:
            raise ValueError(risk.reason)

        allowed_notional = min(round(notional_eur, 2), risk.notional_eur)
        if allowed_notional <= 0:
            raise ValueError("Requested notional is too small.")

        position = self._open_position(
            db,
            asset,
            float(latest_tick.price),
            allowed_notional,
            reason,
            intent_key=self._manual_intent_key(asset, TradeSide.BUY),
            source="manual",
        )
        db.commit()
        db.refresh(position)
        return position

    def manual_sell(self, db: Session, asset_symbol: str, exit_price: float | None, reason: str) -> Position:
        if not self.execution_service.internal_execution_allowed:
            blocked_reason = self.execution_service.target_summary()["blocked_reason"] or "Internal execution is disabled."
            raise ValueError(str(blocked_reason))
        asset = db.scalar(select(Asset).where(Asset.symbol == asset_symbol.upper()))
        if not asset:
            raise ValueError(f"Unknown asset symbol: {asset_symbol}")
        position = db.scalar(
            select(Position).where(Position.asset_id == asset.id, Position.status == PositionStatus.OPEN)
        )
        if not position:
            raise ValueError("No open position to close for this asset.")

        if exit_price is None:
            latest_tick = db.scalar(
                select(MarketTick).where(MarketTick.asset_id == asset.id).order_by(MarketTick.captured_at.desc()).limit(1)
            )
            if not latest_tick:
                raise ValueError("No market price available for this asset.")
            exit_price = float(latest_tick.price)

        self._close_position(
            db,
            position,
            exit_price,
            reason,
            intent_key=self._manual_intent_key(asset, TradeSide.SELL, position.id),
            source="manual",
        )
        db.commit()
        db.refresh(position)
        return position

    def preview_roundtrip(self, db: Session, asset_symbol: str, notional_eur: float, scenario_pct: float) -> dict:
        asset = db.scalar(select(Asset).where(Asset.symbol == asset_symbol.upper()))
        if not asset:
            raise ValueError(f"Unknown asset symbol: {asset_symbol}")
        latest_tick = db.scalar(
            select(MarketTick).where(MarketTick.asset_id == asset.id).order_by(MarketTick.captured_at.desc()).limit(1)
        )
        if not latest_tick:
            raise ValueError("No market price available for this asset.")

        entry_price = float(latest_tick.price)
        quantity = round(notional_eur / entry_price, 8)
        exit_price = round(entry_price * (1 + scenario_pct / 100), 4)
        pnl_eur = round((exit_price - entry_price) * quantity, 4)
        pnl_pct = round((pnl_eur / notional_eur) * 100, 2) if notional_eur else 0.0
        return {
            "asset_symbol": asset.symbol,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "notional_eur": round(notional_eur, 2),
            "quantity": quantity,
            "scenario_pct": round(scenario_pct, 2),
            "pnl_eur": pnl_eur,
            "pnl_pct": pnl_pct,
        }

    def _is_us_market_open(self) -> bool:
        now_et = datetime.now(ZoneInfo("America/New_York"))
        if now_et.weekday() >= 5:
            return False
        open_time = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        close_time = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
        return open_time <= now_et <= close_time

    def _try_buy(
        self,
        db: Session,
        asset: Asset,
        price: float,
        signal: Signal,
        approval_map: dict[tuple[str, str], object],
    ) -> None:
        setup_type = extract_setup_type(signal.rationale) or "unknown"
        approval_row = approval_map.get((asset.kind.value, setup_type))
        approval_status = getattr(approval_row, "approval_status", "watch")
        approval_note = getattr(approval_row, "note", "No resolved setup evidence yet.")
        if approval_status not in self.allowed_setup_statuses:
            self._record_skip(
                db,
                asset,
                TradeSide.BUY,
                price,
                f"Skipped buy because setup {setup_type} is {approval_status} for unattended mode. {approval_note}",
                intent_key=self._signal_intent_key(signal, f"setup-{approval_status}"),
                source="strategy-proof",
                signal=signal,
            )
            return

        existing_open = db.scalar(
            select(Position).where(Position.asset_id == asset.id, Position.status == PositionStatus.OPEN)
        )
        if existing_open:
            self._record_skip(
                db,
                asset,
                TradeSide.BUY,
                price,
                "Skipped buy because a position is already open.",
                intent_key=self._signal_intent_key(signal, "duplicate-open"),
                source="engine",
                signal=signal,
            )
            return

        risk = self.risk_engine.can_open_position(db, asset)
        if not risk.allowed:
            self._record_skip(
                db,
                asset,
                TradeSide.BUY,
                price,
                f"Skipped buy: {risk.reason}",
                intent_key=self._signal_intent_key(signal, "risk-blocked"),
                source="risk",
                signal=signal,
            )
            return

        if self._in_cooldown(db, asset.id):
            self._record_skip(
                db,
                asset,
                TradeSide.BUY,
                price,
                f"Skipped buy because the per-asset cooldown of {self.risk_engine.min_minutes_between_trades} minutes is active.",
                intent_key=self._signal_intent_key(signal, "cooldown"),
                source="risk",
                signal=signal,
            )
            return

        self._open_position(
            db,
            asset,
            price,
            risk.notional_eur,
            signal.rationale,
            intent_key=self._signal_intent_key(signal, "buy"),
            source="engine",
            signal=signal,
        )

    def _try_sell(self, db: Session, asset: Asset, price: float, signal: Signal) -> None:
        position = db.scalar(
            select(Position).where(Position.asset_id == asset.id, Position.status == PositionStatus.OPEN)
        )
        if not position:
            return

        self._close_position(
            db,
            position,
            price,
            signal.rationale,
            intent_key=self._signal_intent_key(signal, f"sell-position-{position.id}"),
            source="engine",
            signal=signal,
        )

    def _liquidate_open_positions(self, db: Session, reason: str) -> int:
        closed_positions = 0
        positions = db.scalars(select(Position).where(Position.status == PositionStatus.OPEN)).all()
        for position in positions:
            latest_tick = db.scalar(
                select(MarketTick).where(MarketTick.asset_id == position.asset_id).order_by(MarketTick.captured_at.desc()).limit(1)
            )
            if not latest_tick or self._tick_is_stale(latest_tick):
                continue
            asset = db.scalar(select(Asset).where(Asset.id == position.asset_id))
            if not asset:
                continue
            self._close_position(
                db,
                position,
                float(latest_tick.price),
                reason,
                intent_key=self._manual_intent_key(asset, TradeSide.SELL, position.id, prefix="risk-liquidation"),
                source="risk",
            )
            closed_positions += 1
        return closed_positions

    def _tick_is_stale(self, tick: MarketTick) -> bool:
        age = datetime.utcnow() - tick.captured_at
        return age.total_seconds() > self.risk_engine.max_tick_age_seconds

    def _in_cooldown(self, db: Session, asset_id: int) -> bool:
        last_trade = db.scalar(
            select(Trade)
            .where(Trade.asset_id == asset_id, Trade.status == TradeStatus.FILLED)
            .order_by(Trade.executed_at.desc())
            .limit(1)
        )
        if not last_trade:
            return False
        return last_trade.executed_at >= datetime.utcnow() - timedelta(minutes=self.risk_engine.min_minutes_between_trades)

    def _record_skip(
        self,
        db: Session,
        asset: Asset,
        side: TradeSide,
        price: float,
        reason: str,
        *,
        intent_key: str,
        source: str,
        signal: Signal | None = None,
    ) -> None:
        intent, created = self.execution_service.get_or_create_intent(
            db,
            intent_key=intent_key,
            asset=asset,
            side=side,
            reason=reason,
            source=source,
            notional_eur=0.0,
            signal=signal,
            price_hint=price,
        )
        if not created and intent.status != ExecutionIntentStatus.PENDING:
            return
        self.execution_service.mark_skipped(intent, error_message=reason)
        self.execution_service.record_trade(
            db,
            asset_id=asset.id,
            side=side,
            status=TradeStatus.SKIPPED,
            notional_eur=0.0,
            quantity=0.0,
            price=price,
            reason=reason,
        )

    def _open_position(
        self,
        db: Session,
        asset: Asset,
        price: float,
        notional_eur: float,
        reason: str,
        *,
        intent_key: str,
        source: str,
        signal: Signal | None = None,
    ) -> Position:
        intent, created = self.execution_service.get_or_create_intent(
            db,
            intent_key=intent_key,
            asset=asset,
            side=TradeSide.BUY,
            reason=reason,
            source=source,
            notional_eur=notional_eur,
            signal=signal,
            price_hint=price,
        )
        if not created and intent.status == ExecutionIntentStatus.FILLED and intent.position:
            return intent.position
        if not self.execution_service.internal_execution_allowed:
            self.execution_service.mark_failed(intent, error_message="Internal paper execution is disabled.")
            raise ValueError("Internal paper execution is disabled.")
        quantity = round(notional_eur / price, 8)
        position = Position(
            asset_id=asset.id,
            quantity=quantity,
            entry_price=price,
            stop_loss=round(price * (1 - self.risk_engine.stop_loss_pct), 4),
            take_profit=round(price * (1 + self.risk_engine.take_profit_pct), 4),
        )
        db.add(position)
        db.flush()
        self.execution_service.mark_filled(intent, quantity=quantity, position=position)
        self.execution_service.record_trade(
            db,
            asset_id=asset.id,
            side=TradeSide.BUY,
            status=TradeStatus.FILLED,
            notional_eur=round(notional_eur, 2),
            quantity=quantity,
            price=price,
            reason=reason,
        )
        return position

    def _close_position(
        self,
        db: Session,
        position: Position,
        price: float,
        reason: str,
        *,
        intent_key: str,
        source: str,
        signal: Signal | None = None,
    ) -> None:
        asset = db.scalar(select(Asset).where(Asset.id == position.asset_id))
        if not asset:
            return
        intent, created = self.execution_service.get_or_create_intent(
            db,
            intent_key=intent_key,
            asset=asset,
            side=TradeSide.SELL,
            reason=reason,
            source=source,
            notional_eur=round(position.quantity * price, 4),
            signal=signal,
            price_hint=price,
        )
        if not created and intent.status == ExecutionIntentStatus.FILLED:
            return
        pnl = round((price - position.entry_price) * position.quantity, 4)
        position.status = PositionStatus.CLOSED
        position.closed_at = datetime.utcnow()
        position.exit_price = price
        position.pnl_eur = pnl
        self.execution_service.mark_filled(intent, quantity=position.quantity, position=position)
        self.execution_service.record_trade(
            db,
            asset_id=position.asset_id,
            side=TradeSide.SELL,
            status=TradeStatus.FILLED,
            notional_eur=round(position.quantity * price, 4),
            quantity=position.quantity,
            price=price,
            reason=reason,
        )

    def _signal_intent_key(self, signal: Signal, suffix: str) -> str:
        return f"signal:{signal.id}:{suffix}"

    def _manual_intent_key(self, asset: Asset, side: TradeSide, position_id: int | None = None, prefix: str = "manual") -> str:
        anchor = position_id if position_id is not None else int(datetime.utcnow().timestamp() * 1000)
        return f"{prefix}:{asset.symbol}:{side.value}:{anchor}"
