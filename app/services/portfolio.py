from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Position, PositionStatus, Signal
from app.schemas import SummaryOut
from app.services.risk import RiskEngine


class PortfolioService:
    def __init__(self, risk_engine: RiskEngine, starting_capital_eur: float, reserve_cash_eur: float) -> None:
        self.risk_engine = risk_engine
        self.starting_capital_eur = starting_capital_eur
        self.reserve_cash_eur = reserve_cash_eur

    def summary(self, db: Session) -> SummaryOut:
        return SummaryOut(
            starting_capital_eur=self.starting_capital_eur,
            reserve_cash_eur=self.reserve_cash_eur,
            available_cash_eur=self.risk_engine.available_cash(db),
            open_positions=db.scalar(select(func.count(Position.id)).where(Position.status == PositionStatus.OPEN)) or 0,
            closed_positions=db.scalar(select(func.count(Position.id)).where(Position.status == PositionStatus.CLOSED)) or 0,
            realized_pnl_eur=round(
                db.scalar(select(func.sum(Position.pnl_eur)).where(Position.pnl_eur.is_not(None))) or 0.0,
                4,
            ),
            latest_signal_count=db.scalar(select(func.count(Signal.id))) or 0,
            stop_loss_pct=self.risk_engine.stop_loss_pct,
            take_profit_pct=self.risk_engine.take_profit_pct,
            trailing_stop_pct=self.risk_engine.trailing_stop_pct,
        )
