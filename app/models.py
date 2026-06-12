from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class AssetKind(str, Enum):
    CRYPTO = "crypto"
    ETF = "etf"
    STOCK = "stock"


class SignalAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class PositionStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class TradeMode(str, Enum):
    PAPER = "paper"


class TradeSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class TradeStatus(str, Enum):
    FILLED = "filled"
    SKIPPED = "skipped"


class ExecutionIntentStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    SKIPPED = "skipped"
    FAILED = "failed"


class SimulationStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    kind: Mapped[AssetKind] = mapped_column(SqlEnum(AssetKind))
    external_id: Mapped[str] = mapped_column(String(64), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    ticks: Mapped[list["MarketTick"]] = relationship(back_populates="asset")
    news_items: Mapped[list["NewsItem"]] = relationship(back_populates="asset")
    signals: Mapped[list["Signal"]] = relationship(back_populates="asset")
    positions: Mapped[list["Position"]] = relationship(back_populates="asset")
    trades: Mapped[list["Trade"]] = relationship(back_populates="asset")


class MarketTick(Base):
    __tablename__ = "market_ticks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    price: Mapped[float] = mapped_column(Float)
    change_24h_pct: Mapped[float] = mapped_column(Float)
    volume_24h: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(32), default="coingecko")
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    asset: Mapped["Asset"] = relationship(back_populates="ticks")


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("assets.id"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(280))
    summary: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(1024), unique=True)
    sentiment_score: Mapped[float] = mapped_column(Float)
    event_type: Mapped[str] = mapped_column(String(64), default="general")
    published_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    asset: Mapped["Asset | None"] = relationship(back_populates="news_items")


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    action: Mapped[SignalAction] = mapped_column(SqlEnum(SignalAction))
    score: Mapped[float] = mapped_column(Float, index=True)
    sentiment_score: Mapped[float] = mapped_column(Float)
    momentum_score: Mapped[float] = mapped_column(Float)
    rationale: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    asset: Mapped["Asset"] = relationship(back_populates="signals")


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    status: Mapped[PositionStatus] = mapped_column(SqlEnum(PositionStatus), default=PositionStatus.OPEN)
    quantity: Mapped[float] = mapped_column(Float)
    entry_price: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    take_profit: Mapped[float] = mapped_column(Float)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_eur: Mapped[float | None] = mapped_column(Float, nullable=True)

    asset: Mapped["Asset"] = relationship(back_populates="positions")


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    mode: Mapped[TradeMode] = mapped_column(SqlEnum(TradeMode), default=TradeMode.PAPER)
    execution_target: Mapped[str] = mapped_column(String(16), default="internal", index=True)
    side: Mapped[TradeSide] = mapped_column(SqlEnum(TradeSide))
    status: Mapped[TradeStatus] = mapped_column(SqlEnum(TradeStatus), default=TradeStatus.FILLED)
    notional_eur: Mapped[float] = mapped_column(Float)
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(Text)
    executed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    asset: Mapped["Asset"] = relationship(back_populates="trades")


class ExecutionIntent(Base):
    __tablename__ = "execution_intents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    intent_key: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    signal_id: Mapped[int | None] = mapped_column(ForeignKey("signals.id"), nullable=True, index=True)
    position_id: Mapped[int | None] = mapped_column(ForeignKey("positions.id"), nullable=True, index=True)
    mode: Mapped[str] = mapped_column(String(16), default="paper", index=True)
    execution_target: Mapped[str] = mapped_column(String(16), default="internal", index=True)
    side: Mapped[TradeSide] = mapped_column(SqlEnum(TradeSide))
    status: Mapped[ExecutionIntentStatus] = mapped_column(SqlEnum(ExecutionIntentStatus), default=ExecutionIntentStatus.PENDING, index=True)
    source: Mapped[str] = mapped_column(String(24), default="engine", index=True)
    notional_eur: Mapped[float] = mapped_column(Float, default=0.0)
    price_hint: Mapped[float | None] = mapped_column(Float, nullable=True)
    quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    broker_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    broker_order_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    broker_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    asset: Mapped["Asset"] = relationship()
    signal: Mapped["Signal | None"] = relationship()
    position: Mapped["Position | None"] = relationship()


class ReconciliationSnapshot(Base):
    __tablename__ = "reconciliation_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(16), default="ok", index=True)
    mode: Mapped[str] = mapped_column(String(16), default="paper", index=True)
    execution_target: Mapped[str] = mapped_column(String(16), default="internal", index=True)
    provider: Mapped[str] = mapped_column(String(32), default="none")
    ledger_open_positions: Mapped[int] = mapped_column(Integer, default=0)
    ledger_closed_positions: Mapped[int] = mapped_column(Integer, default=0)
    ledger_open_notional_eur: Mapped[float] = mapped_column(Float, default=0.0)
    ledger_realized_pnl_eur: Mapped[float] = mapped_column(Float, default=0.0)
    pending_intents: Mapped[int] = mapped_column(Integer, default=0)
    failed_intents: Mapped[int] = mapped_column(Integer, default=0)
    broker_connected: Mapped[bool] = mapped_column(Boolean, default=False)
    broker_account_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    broker_buying_power: Mapped[str | None] = mapped_column(String(80), nullable=True)
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class StrategySimulation(Base):
    __tablename__ = "strategy_simulations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), index=True)
    scenario_key: Mapped[str] = mapped_column(String(32), default="sim_100", index=True)
    scenario_label: Mapped[str] = mapped_column(String(64), default="EUR 100")
    setup_type: Mapped[str] = mapped_column(String(32), default="balanced", index=True)
    opened_signal_score: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[SimulationStatus] = mapped_column(SqlEnum(SimulationStatus), default=SimulationStatus.ACTIVE)
    initial_notional_eur: Mapped[float] = mapped_column(Float)
    quantity: Mapped[float] = mapped_column(Float)
    entry_price: Mapped[float] = mapped_column(Float)
    latest_price: Mapped[float] = mapped_column(Float)
    pnl_eur: Mapped[float] = mapped_column(Float, default=0.0)
    pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)
    stop_price: Mapped[float] = mapped_column(Float)
    take_profit_price: Mapped[float] = mapped_column(Float)
    trailing_stop_price: Mapped[float] = mapped_column(Float)
    alert_flags: Mapped[str] = mapped_column(Text, default="")
    opened_reason: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    asset: Mapped["Asset"] = relationship()
    alerts: Mapped[list["SimulationAlert"]] = relationship(back_populates="simulation")


class SimulationAlert(Base):
    __tablename__ = "simulation_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    simulation_id: Mapped[int] = mapped_column(ForeignKey("strategy_simulations.id"), index=True)
    level: Mapped[str] = mapped_column(String(16), default="info")
    title: Mapped[str] = mapped_column(String(120))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    simulation: Mapped["StrategySimulation"] = relationship(back_populates="alerts")


class EngineRun(Base):
    __tablename__ = "engine_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(16), default="ok", index=True)
    assets_count: Mapped[int] = mapped_column(Integer, default=0)
    news_items_count: Mapped[int] = mapped_column(Integer, default=0)
    signals_count: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class StateEvent(Base):
    __tablename__ = "state_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_key: Mapped[str] = mapped_column(String(64), index=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    severity: Mapped[str] = mapped_column(String(16), default="info", index=True)
    title: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(Text)
    fingerprint: Mapped[str] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class ProviderHealthSample(Base):
    __tablename__ = "provider_health_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(128), index=True)
    asset_kind: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(16), default="ok", index=True)
    attempted_assets: Mapped[int] = mapped_column(Integer, default=0)
    successful_assets: Mapped[int] = mapped_column(Integer, default=0)
    failed_assets: Mapped[int] = mapped_column(Integer, default=0)
    stale_assets: Mapped[int] = mapped_column(Integer, default=0)
    cache_used: Mapped[bool] = mapped_column(Boolean, default=False)
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class SignalOutcomeSnapshot(Base):
    __tablename__ = "signal_outcome_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signal_id: Mapped[int] = mapped_column(ForeignKey("signals.id"), index=True)
    horizon_hours: Mapped[int] = mapped_column(Integer, index=True)
    signal_price: Mapped[float] = mapped_column(Float)
    observed_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_move_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    decision_edge_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    outcome_label: Mapped[str] = mapped_column(String(32), default="")
    outcome_status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    signal: Mapped["Signal"] = relationship()
