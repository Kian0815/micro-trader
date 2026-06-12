from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Asset, MarketTick, Position, PositionStatus


@dataclass
class RiskDecision:
    allowed: bool
    reason: str
    notional_eur: float = 0.0


class RiskEngine:
    def __init__(
        self,
        starting_capital_eur: float,
        reserve_cash_eur: float,
        max_notional_per_trade_eur: float,
        max_open_positions: int,
        max_daily_loss_eur: float,
        stop_loss_pct: float,
        take_profit_pct: float,
        trailing_stop_pct: float,
        max_tick_age_seconds: int,
        min_minutes_between_trades: int,
        max_gross_exposure_pct: float,
        max_symbol_exposure_pct: float,
        max_portfolio_drawdown_pct: float,
        liquidate_on_drawdown_breach: bool,
        asset_kind_exposure_limits: dict[str, float] | None = None,
    ) -> None:
        self.starting_capital_eur = starting_capital_eur
        self.reserve_cash_eur = reserve_cash_eur
        self.max_notional_per_trade_eur = max_notional_per_trade_eur
        self.max_open_positions = max_open_positions
        self.max_daily_loss_eur = max_daily_loss_eur
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.trailing_stop_pct = trailing_stop_pct
        self.max_tick_age_seconds = max_tick_age_seconds
        self.min_minutes_between_trades = min_minutes_between_trades
        self.max_gross_exposure_pct = max_gross_exposure_pct
        self.max_symbol_exposure_pct = max_symbol_exposure_pct
        self.max_portfolio_drawdown_pct = max_portfolio_drawdown_pct
        self.liquidate_on_drawdown_breach = liquidate_on_drawdown_breach
        self.asset_kind_exposure_limits = asset_kind_exposure_limits or {"etf": 0.7, "stock": 0.2, "crypto": 0.1}

    def available_cash(self, db: Session) -> float:
        return round(self.current_equity(db) - self.gross_open_notional(db), 2)

    def current_equity(self, db: Session) -> float:
        return round(self.starting_capital_eur + self.realized_pnl(db) + self.unrealized_pnl(db), 4)

    def realized_pnl(self, db: Session) -> float:
        return float(db.scalar(select(func.sum(Position.pnl_eur)).where(Position.pnl_eur.is_not(None))) or 0.0)

    def unrealized_pnl(self, db: Session) -> float:
        unrealized = 0.0
        positions = db.scalars(select(Position).where(Position.status == PositionStatus.OPEN)).all()
        for position in positions:
            latest_tick = db.scalar(
                select(MarketTick).where(MarketTick.asset_id == position.asset_id).order_by(MarketTick.captured_at.desc()).limit(1)
            )
            if not latest_tick:
                continue
            unrealized += (float(latest_tick.price) - position.entry_price) * position.quantity
        return round(unrealized, 4)

    def gross_open_notional(self, db: Session) -> float:
        return float(
            db.scalar(select(func.sum(Position.quantity * Position.entry_price)).where(Position.status == PositionStatus.OPEN))
            or 0.0
        )

    def gross_open_notional_for_symbol(self, db: Session, asset_id: int) -> float:
        return float(
            db.scalar(
                select(func.sum(Position.quantity * Position.entry_price)).where(
                    Position.status == PositionStatus.OPEN,
                    Position.asset_id == asset_id,
                )
            )
            or 0.0
        )

    def gross_open_notional_for_kind(self, db: Session, asset_kind: str) -> float:
        return float(
            db.scalar(
                select(func.sum(Position.quantity * Position.entry_price))
                .join(Asset, Asset.id == Position.asset_id)
                .where(Position.status == PositionStatus.OPEN, Asset.kind == asset_kind)
            )
            or 0.0
        )

    def peak_equity(self, db: Session) -> float:
        equity = float(self.starting_capital_eur)
        peak = equity
        closed_positions = db.scalars(
            select(Position).where(Position.status == PositionStatus.CLOSED).order_by(Position.closed_at.asc(), Position.opened_at.asc())
        ).all()
        for position in closed_positions:
            equity += float(position.pnl_eur or 0.0)
            peak = max(peak, equity)
        return round(max(peak, self.current_equity(db)), 4)

    def current_drawdown_pct(self, db: Session) -> float:
        peak = self.peak_equity(db)
        if peak <= 0:
            return 0.0
        drawdown = max(peak - self.current_equity(db), 0.0)
        return round((drawdown / peak) * 100, 2)

    def drawdown_lock_active(self, db: Session) -> bool:
        return self.current_drawdown_pct(db) >= self.max_portfolio_drawdown_pct

    def can_open_position(self, db: Session, asset: Asset | None = None) -> RiskDecision:
        if self.drawdown_lock_active(db):
            return RiskDecision(False, "Portfolio drawdown lock is active.")

        open_positions = db.scalar(
            select(func.count(Position.id)).where(Position.status == PositionStatus.OPEN)
        ) or 0
        if open_positions >= self.max_open_positions:
            return RiskDecision(False, "Open-position limit reached.")

        available_cash = self.available_cash(db)
        if available_cash <= self.reserve_cash_eur:
            return RiskDecision(False, "Reserve cash protection active.")

        daily_loss = abs(min(self._today_realized_pnl(db), 0.0))
        if daily_loss >= self.max_daily_loss_eur:
            return RiskDecision(False, "Daily loss circuit breaker active.")

        current_equity = max(self.current_equity(db), 0.0)
        if current_equity <= 0:
            return RiskDecision(False, "Current equity is depleted.")

        cash_room = available_cash - self.reserve_cash_eur
        if cash_room <= 0:
            return RiskDecision(False, "Not enough free cash after reserve.")

        gross_limit = current_equity * self.max_gross_exposure_pct
        gross_remaining = round(gross_limit - self.gross_open_notional(db), 4)
        if gross_remaining <= 0:
            return RiskDecision(False, "Gross exposure cap reached.")

        symbol_remaining = gross_remaining
        kind_remaining = gross_remaining
        if asset:
            symbol_limit = current_equity * self.max_symbol_exposure_pct
            symbol_remaining = round(symbol_limit - self.gross_open_notional_for_symbol(db, asset.id), 4)
            if symbol_remaining <= 0:
                return RiskDecision(False, f"{asset.symbol} position cap reached.")

            kind_limit_pct = self.asset_kind_exposure_limits.get(asset.kind.value, 0.0)
            kind_limit = current_equity * kind_limit_pct
            kind_remaining = round(kind_limit - self.gross_open_notional_for_kind(db, asset.kind.value), 4)
            if kind_remaining <= 0:
                return RiskDecision(False, f"{asset.kind.value} exposure cap reached.")

        notional = min(
            round(self.max_notional_per_trade_eur, 4),
            round(cash_room, 4),
            gross_remaining,
            symbol_remaining,
            kind_remaining,
        )
        if notional <= 0:
            return RiskDecision(False, "No safe trade size is available.")

        return RiskDecision(True, "Risk checks passed.", round(notional, 2))

    def control_snapshot(self, db: Session) -> dict:
        current_equity = self.current_equity(db)
        peak_equity = self.peak_equity(db)
        gross_open_notional = self.gross_open_notional(db)
        return {
            "current_equity_eur": current_equity,
            "peak_equity_eur": peak_equity,
            "available_cash_eur": self.available_cash(db),
            "gross_open_notional_eur": round(gross_open_notional, 4),
            "gross_exposure_pct": round((gross_open_notional / current_equity) * 100, 2) if current_equity > 0 else 0.0,
            "drawdown_pct": self.current_drawdown_pct(db),
            "drawdown_lock_active": self.drawdown_lock_active(db),
            "drawdown_liquidation_enabled": self.liquidate_on_drawdown_breach,
            "max_gross_exposure_pct": round(self.max_gross_exposure_pct * 100, 2),
            "max_symbol_exposure_pct": round(self.max_symbol_exposure_pct * 100, 2),
            "max_portfolio_drawdown_pct": round(self.max_portfolio_drawdown_pct, 2),
            "asset_kind_exposure_limits": {key: round(value * 100, 2) for key, value in self.asset_kind_exposure_limits.items()},
        }

    def _today_realized_pnl(self, db: Session) -> float:
        return float(
            db.scalar(
                select(func.sum(Position.pnl_eur)).where(
                    Position.status == PositionStatus.CLOSED,
                    func.date(Position.closed_at) == func.current_date(),
                )
            )
            or 0.0
        )
