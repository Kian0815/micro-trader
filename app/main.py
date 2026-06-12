from contextlib import asynccontextmanager
from datetime import datetime
import json
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.bootstrap import seed_assets
from app.config import get_settings
from app.db import (
    Base,
    engine,
    ensure_asset_kind_enum,
    ensure_execution_audit_schema,
    ensure_provider_health_schema,
    ensure_signal_outcome_schema,
    ensure_simulation_schema,
    ensure_state_event_schema,
    get_db,
)
from app.engine import run_engine_cycle
from app.models import (
    Asset,
    AssetKind,
    EngineRun,
    ExecutionIntent,
    ExecutionIntentStatus,
    MarketTick,
    NewsItem,
    Position,
    PositionStatus,
    ProviderHealthSample,
    Signal,
    SignalAction,
    SignalOutcomeSnapshot,
    SimulationAlert,
    StrategySimulation,
    Trade,
    TradeSide,
)
from app.schemas import (
    ActiveDemoPositionOut,
    ApprovalFocusReportOut,
    LaunchReadinessReportOut,
    LiveDeploymentReadinessOut,
    GoLiveRunbookOut,
    OperatorAlertPolicyOut,
    AssetOut,
    BenchmarkReportOut,
    BrokerCapabilitiesOut,
    BrokerOrderOut,
    BrokerOrderResultOut,
    BrokerPositionOut,
    BrokerStatusOut,
    DemoPreviewOut,
    ExecutionIntentOut,
    NewsItemOut,
    PerformanceOut,
    PendingSetupReportOut,
    PositionOut,
    ReconciliationDetailOut,
    ReconciliationStatusOut,
    SignalOut,
    SetupMonitorReportOut,
    SetupScorecardReportOut,
    SetupWalkForwardReportOut,
    SimulationAlertOut,
    SimulationOut,
    StateEventOut,
    SummaryOut,
    TradeOut,
)
from app.services.backtesting import WalkForwardAnalysisService
from app.services.brokers import build_broker_adapter
from app.services.evaluation import StrategyProofService
from app.services.events import StateEventService
from app.services.execution import ExecutionIntentService
from app.services.opportunity import BestOpportunitySelector
from app.services.operator_alerts import build_operator_alert_service
from app.services.portfolio import PortfolioService
from app.services.reconciliation import ReconciliationService
from app.services.risk import RiskEngine
from app.services.simulation import BestAssetSimulationService
from app.services.strategy import StrategyEngine, extract_news_count, extract_setup_type
from app.services.trading import PaperTrader


settings = get_settings()
templates = Jinja2Templates(directory="app/templates")
PUBLIC_EQUITY_STATE_PATH = (
    Path(settings.public_equity_state_path)
    if settings.public_equity_state_path
    else Path.home() / ".codex/state/plugins/oai-maintained-plugins/public-equity-investing/onboarding-state.json"
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_asset_kind_enum()
    ensure_signal_outcome_schema()
    ensure_simulation_schema()
    ensure_execution_audit_schema()
    ensure_provider_health_schema()
    ensure_state_event_schema()
    with Session(engine) as db:
        seed_assets(db, settings.watchlist, settings.etf_watchlist, settings.stock_watchlist)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


def build_portfolio_service() -> PortfolioService:
    risk_engine = build_risk_engine()
    return PortfolioService(risk_engine, settings.starting_capital_eur, settings.reserve_cash_eur)


def build_risk_engine() -> RiskEngine:
    return RiskEngine(
        starting_capital_eur=settings.starting_capital_eur,
        reserve_cash_eur=settings.reserve_cash_eur,
        max_notional_per_trade_eur=settings.max_notional_per_trade_eur,
        max_open_positions=settings.max_open_positions,
        max_daily_loss_eur=settings.max_daily_loss_eur,
        stop_loss_pct=settings.stop_loss_pct,
        take_profit_pct=settings.take_profit_pct,
        trailing_stop_pct=settings.trailing_stop_pct,
        max_tick_age_seconds=settings.max_tick_age_seconds,
        min_minutes_between_trades=settings.min_minutes_between_trades,
        max_gross_exposure_pct=settings.max_gross_exposure_pct,
        max_symbol_exposure_pct=settings.max_symbol_exposure_pct,
        max_portfolio_drawdown_pct=settings.max_portfolio_drawdown_pct,
        liquidate_on_drawdown_breach=settings.liquidate_on_drawdown_breach,
        asset_kind_exposure_limits=settings.asset_kind_exposure_limits,
    )


def build_trader() -> PaperTrader:
    return PaperTrader(
        build_risk_engine(),
        build_execution_service(),
        build_strategy_proof_service(),
        build_opportunity_selector(),
        allowed_asset_kinds=settings.tradeable_asset_kinds,
        allowed_setup_statuses=settings.unattended_setup_statuses,
    )


def build_execution_service() -> ExecutionIntentService:
    return ExecutionIntentService(settings)


def build_operator_alerts():
    return build_operator_alert_service(settings)


def build_state_event_service() -> StateEventService:
    return StateEventService()


def build_reconciliation_service() -> ReconciliationService:
    return ReconciliationService(settings, build_risk_engine())


def build_simulation_service() -> BestAssetSimulationService:
    return BestAssetSimulationService(
        stop_loss_pct=settings.stop_loss_pct,
        take_profit_pct=settings.take_profit_pct,
        trailing_stop_pct=settings.trailing_stop_pct,
        proof_service=build_strategy_proof_service(),
        opportunity_selector=build_opportunity_selector(),
        simulation_budgets=settings.simulation_budgets,
        max_signal_age_seconds=settings.max_tick_age_seconds,
        allowed_asset_kinds=settings.simulation_asset_kinds,
        allowed_setup_statuses=settings.unattended_setup_statuses,
    )


def build_strategy_proof_service() -> StrategyProofService:
    return StrategyProofService(build_strategy_engine())


def build_opportunity_selector() -> BestOpportunitySelector:
    return BestOpportunitySelector(
        build_strategy_proof_service(),
        build_walkforward_service(),
        max_signal_age_seconds=settings.max_tick_age_seconds,
        max_tick_age_seconds=settings.max_tick_age_seconds,
        allowed_asset_kinds=settings.tradeable_asset_kinds,
        allowed_setup_statuses=settings.unattended_setup_statuses,
    )


def build_walkforward_service() -> WalkForwardAnalysisService:
    return WalkForwardAnalysisService(build_strategy_engine())


def build_strategy_engine() -> StrategyEngine:
    return StrategyEngine(
        min_signal_score_to_buy=settings.min_signal_score_to_buy,
        min_sentiment_score_to_buy=settings.min_sentiment_score_to_buy,
        min_momentum_score_to_buy=settings.min_momentum_score_to_buy,
        min_news_items_to_buy=settings.min_news_items_to_buy,
    )


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    portfolio = build_portfolio_service()
    broker_adapter = build_broker_adapter(settings)
    broker_status = broker_adapter.status()
    broker_capabilities = broker_adapter.capabilities()
    reconciliation_status = build_reconciliation_service().snapshot(db)
    simulation_service = build_simulation_service()
    active_simulation = simulation_service.get_active(db)
    active_simulations = simulation_service.list_active(db)
    simulation_overview = simulation_service.scenario_overview(db)
    simulation_alerts = simulation_service.list_alerts(db)
    simulation_performance = simulation_service.performance_summary(db)
    state_events = _compact_state_events(build_state_event_service().list_recent(db, limit=30), limit=10)
    summary = portfolio.summary(db)
    assets = db.scalars(select(Asset).order_by(Asset.symbol)).all()
    crypto_assets = [asset for asset in assets if asset.kind == AssetKind.CRYPTO]
    etf_assets = [asset for asset in assets if asset.kind == AssetKind.ETF]
    stock_assets = [asset for asset in assets if asset.kind == AssetKind.STOCK]
    news_items = db.scalars(
        select(NewsItem).options(joinedload(NewsItem.asset)).order_by(NewsItem.published_at.desc()).limit(10)
    ).all()
    signals = _latest_signals(db, limit=10)
    trades = db.scalars(select(Trade).options(joinedload(Trade.asset)).order_by(Trade.executed_at.desc()).limit(10)).all()
    execution_intents = db.scalars(
        select(ExecutionIntent).options(joinedload(ExecutionIntent.asset)).order_by(ExecutionIntent.created_at.desc()).limit(10)
    ).all()
    positions = db.scalars(select(Position).options(joinedload(Position.asset)).order_by(Position.opened_at.desc()).limit(10)).all()
    featured_open_position = next((position for position in positions if position.status == PositionStatus.OPEN), None)
    featured_open_position_status = _active_demo_position_snapshot(db, featured_open_position)
    latest_engine_run = db.scalar(select(EngineRun).order_by(EngineRun.completed_at.desc()).limit(1))
    latest_market = _latest_market_rows(db, assets)
    last_engine_at = signals[0].created_at if signals else None
    provider_health = _provider_health_summary(db)
    provider_audit = _provider_audit(provider_health)
    diagnostics = _strategy_diagnostics(signals, latest_market)
    signal_outcomes = _signal_outcome_summary(db)
    pending_setups = _pending_setup_summary(db)
    best_opportunity = build_opportunity_selector().summary(db, signals=signals)
    setup_scorecards = build_strategy_proof_service().build_scorecard(db).to_dict()
    setup_walkforward = build_walkforward_service().build_report(db).to_dict()
    setup_scorecards = _split_setup_rows(setup_scorecards)
    setup_walkforward = _split_setup_rows(setup_walkforward)
    board_focus = _apply_etf_regime_focus(
        best_opportunity=best_opportunity,
        pending_setups=pending_setups,
        setup_scorecards=setup_scorecards,
        setup_walkforward=setup_walkforward,
        strategy_diagnostics=diagnostics,
    )
    diagnostics = board_focus["strategy_diagnostics"]
    pending_setups = board_focus["pending_setups"]
    setup_scorecards = board_focus["setup_scorecards"]
    setup_walkforward = board_focus["setup_walkforward"]
    setup_monitor = _setup_monitor_summary(setup_walkforward, pending_setups, best_opportunity)
    approval_focus = _approval_focus_summary(setup_scorecards, setup_walkforward, pending_setups, best_opportunity)
    performance_report = _performance_report(db, summary.starting_capital_eur)
    benchmark_report = _benchmark_report(db, performance_report["strategy_return_pct"])
    performance_report["benchmark_alpha_summary"] = _benchmark_alpha_summary(benchmark_report)
    risk_snapshot = build_risk_engine().control_snapshot(db)
    autopilot_status = _autopilot_status(signals, latest_market, provider_health, risk_snapshot)
    simulation_trigger_status = _simulation_trigger_status(active_simulation, best_opportunity, autopilot_status)
    launch_readiness = _launch_readiness_summary(
        latest_engine_run=latest_engine_run,
        provider_health=provider_health,
        setup_monitor=setup_monitor,
        approval_focus=approval_focus,
        reconciliation_status=reconciliation_status,
        broker_status=broker_status,
        risk_snapshot=risk_snapshot,
        autopilot_status=autopilot_status,
    )
    live_deployment = _live_deployment_readiness(
        launch_readiness=launch_readiness,
        broker_status=broker_status,
        reconciliation_status=reconciliation_status,
    )
    operator_alert_policy = _operator_alert_policy()
    go_live_runbook = _go_live_runbook()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "summary": summary,
            "broker_status": broker_status,
            "broker_capabilities": broker_capabilities,
            "reconciliation_status": reconciliation_status,
            "active_simulation": active_simulation,
            "active_simulations": active_simulations,
            "simulation_overview": simulation_overview,
            "simulation_alerts": simulation_alerts,
            "simulation_performance": simulation_performance,
            "state_events": state_events,
            "assets": assets,
            "crypto_assets": crypto_assets,
            "etf_assets": etf_assets,
            "stock_assets": stock_assets,
            "news_items": news_items,
            "crypto_news_items": [item for item in news_items if item.asset and item.asset.kind == AssetKind.CRYPTO],
            "etf_news_items": [item for item in news_items if item.asset and item.asset.kind == AssetKind.ETF],
            "stock_news_items": [item for item in news_items if item.asset and item.asset.kind == AssetKind.STOCK],
            "signals": signals,
            "crypto_signals": [signal for signal in signals if signal.asset.kind == AssetKind.CRYPTO],
            "etf_signals": [signal for signal in signals if signal.asset.kind == AssetKind.ETF],
            "stock_signals": [signal for signal in signals if signal.asset.kind == AssetKind.STOCK],
            "trades": trades,
            "execution_intents": execution_intents,
            "positions": positions,
            "featured_open_position": featured_open_position,
            "featured_open_position_status": featured_open_position_status,
            "latest_market": latest_market,
            "crypto_market": [row for row in latest_market if row["kind"] == AssetKind.CRYPTO.value],
            "etf_market": [row for row in latest_market if row["kind"] == AssetKind.ETF.value],
            "stock_market": [row for row in latest_market if row["kind"] == AssetKind.STOCK.value],
            "simulation_plan": _simulation_plan(active_simulation),
            "simulation_trigger_status": simulation_trigger_status,
            "engine_timing": _engine_timing(last_engine_at),
            "execution_guardrails": _execution_guardrails(latest_engine_run, autopilot_status, risk_snapshot),
            "provider_health": provider_health,
            "provider_audit": provider_audit,
            "strategy_diagnostics": diagnostics,
            "strategy_diagnostics_note": board_focus["strategy_diagnostics_note"],
            "signal_outcomes": signal_outcomes,
            "pending_setups": pending_setups,
            "best_opportunity": best_opportunity,
            "setup_monitor": setup_monitor,
            "approval_focus": approval_focus,
            "launch_readiness": launch_readiness,
            "live_deployment": live_deployment,
            "operator_alert_policy": operator_alert_policy,
            "go_live_runbook": go_live_runbook,
            "setup_scorecards": setup_scorecards,
            "setup_walkforward": setup_walkforward,
            "benchmark_report": benchmark_report,
            "performance_report": performance_report,
            "risk_snapshot": risk_snapshot,
            "research_connectors": _public_equity_connectors_status(),
            "autopilot_status": autopilot_status,
            "message": request.query_params.get("message"),
            "demo_preview": _demo_preview_from_request(request),
        },
    )


@app.get("/live", response_class=HTMLResponse)
def live_monitor(request: Request, db: Session = Depends(get_db)):
    assets = db.scalars(select(Asset).order_by(Asset.symbol)).all()
    engine_runs = db.scalars(select(EngineRun).order_by(EngineRun.completed_at.desc()).limit(12)).all()
    signals = _latest_signals(db, limit=20)
    trades = db.scalars(select(Trade).options(joinedload(Trade.asset)).order_by(Trade.executed_at.desc()).limit(20)).all()
    news_items = db.scalars(
        select(NewsItem).options(joinedload(NewsItem.asset)).order_by(NewsItem.published_at.desc()).limit(20)
    ).all()
    latest_market = _latest_market_rows(db, assets)
    latest_signal_at = signals[0].created_at if signals else None
    latest_engine_run = engine_runs[0] if engine_runs else None
    provider_health = _provider_health_summary(db)
    provider_audit = _provider_audit(provider_health)
    performance_report = _performance_report(db, build_portfolio_service().starting_capital_eur)
    benchmark_report = _benchmark_report(db, performance_report["strategy_return_pct"])
    performance_report["benchmark_alpha_summary"] = _benchmark_alpha_summary(benchmark_report)
    setup_scorecards = build_strategy_proof_service().build_scorecard(db).to_dict()
    setup_walkforward = build_walkforward_service().build_report(db).to_dict()
    setup_scorecards = _split_setup_rows(setup_scorecards)
    setup_walkforward = _split_setup_rows(setup_walkforward)
    pending_setups = _pending_setup_summary(db)
    best_opportunity = build_opportunity_selector().summary(db, signals=signals)
    board_focus = _apply_etf_regime_focus(
        best_opportunity=best_opportunity,
        pending_setups=pending_setups,
        setup_scorecards=setup_scorecards,
        setup_walkforward=setup_walkforward,
        strategy_diagnostics=_strategy_diagnostics(signals, latest_market),
    )
    pending_setups = board_focus["pending_setups"]
    setup_scorecards = board_focus["setup_scorecards"]
    setup_walkforward = board_focus["setup_walkforward"]
    setup_monitor = _setup_monitor_summary(setup_walkforward, pending_setups, best_opportunity)
    approval_focus = _approval_focus_summary(setup_scorecards, setup_walkforward, pending_setups, best_opportunity)
    risk_snapshot = build_risk_engine().control_snapshot(db)
    autopilot_status = _autopilot_status(signals, latest_market, provider_health, risk_snapshot)
    simulation_trigger_status = _simulation_trigger_status(build_simulation_service().get_active(db), best_opportunity, autopilot_status)
    reconciliation_status = build_reconciliation_service().snapshot(db)
    broker_status = build_broker_adapter(settings).status()
    launch_readiness = _launch_readiness_summary(
        latest_engine_run=latest_engine_run,
        provider_health=provider_health,
        setup_monitor=setup_monitor,
        approval_focus=approval_focus,
        reconciliation_status=reconciliation_status,
        broker_status=broker_status,
        risk_snapshot=risk_snapshot,
        autopilot_status=autopilot_status,
    )
    live_deployment = _live_deployment_readiness(
        launch_readiness=launch_readiness,
        broker_status=broker_status,
        reconciliation_status=reconciliation_status,
    )
    operator_alert_policy = _operator_alert_policy()
    go_live_runbook = _go_live_runbook()
    return templates.TemplateResponse(
        request,
        "live.html",
        {
            "engine_runs": engine_runs,
            "signals": signals,
            "trades": trades,
            "news_items": news_items,
            "latest_market": latest_market,
            "crypto_market": [row for row in latest_market if row["kind"] == AssetKind.CRYPTO.value],
            "etf_market": [row for row in latest_market if row["kind"] == AssetKind.ETF.value],
            "stock_market": [row for row in latest_market if row["kind"] == AssetKind.STOCK.value],
            "engine_timing": _engine_timing(latest_signal_at),
            "active_simulation": build_simulation_service().get_active(db),
            "active_simulations": build_simulation_service().list_active(db),
            "simulation_alerts": build_simulation_service().list_alerts(db, limit=8),
            "simulation_overview": build_simulation_service().scenario_overview(db),
            "state_events": _compact_state_events(build_state_event_service().list_recent(db, limit=30), limit=10),
            "simulation_trigger_status": simulation_trigger_status,
            "provider_warnings": _provider_warnings(engine_runs, latest_market, trades),
            "trade_story": _trade_story(trades),
            "provider_health": provider_health,
            "provider_audit": provider_audit,
            "strategy_diagnostics": board_focus["strategy_diagnostics"],
            "strategy_diagnostics_note": board_focus["strategy_diagnostics_note"],
            "signal_outcomes": _signal_outcome_summary(db),
            "pending_setups": pending_setups,
            "best_opportunity": best_opportunity,
            "setup_monitor": setup_monitor,
            "approval_focus": approval_focus,
            "launch_readiness": launch_readiness,
            "live_deployment": live_deployment,
            "operator_alert_policy": operator_alert_policy,
            "go_live_runbook": go_live_runbook,
            "setup_scorecards": setup_scorecards,
            "setup_walkforward": setup_walkforward,
            "benchmark_report": benchmark_report,
            "performance_report": performance_report,
            "risk_snapshot": risk_snapshot,
            "reconciliation_status": reconciliation_status,
            "research_connectors": _public_equity_connectors_status(),
            "autopilot_status": autopilot_status,
        },
    )


@app.get("/health")
def healthcheck():
    return {"status": "ok"}


@app.get("/api/assets", response_model=list[AssetOut])
def list_assets(db: Session = Depends(get_db)):
    return db.scalars(select(Asset).order_by(Asset.symbol)).all()


@app.get("/api/signals", response_model=list[SignalOut])
def list_signals(db: Session = Depends(get_db)):
    rows = _latest_signals(db, limit=50)
    return [
        SignalOut(
            id=row.id,
            asset_symbol=row.asset.symbol,
            asset_kind=row.asset.kind.value,
            setup_type=extract_setup_type(row.rationale),
            action=row.action.value,
            score=row.score,
            sentiment_score=row.sentiment_score,
            momentum_score=row.momentum_score,
            rationale=row.rationale,
            created_at=row.created_at,
        )
        for row in rows
    ]


@app.get("/api/news", response_model=list[NewsItemOut])
def list_news(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(NewsItem).options(joinedload(NewsItem.asset)).order_by(NewsItem.published_at.desc()).limit(50)
    ).all()
    return [
        NewsItemOut(
            id=row.id,
            asset_symbol=row.asset.symbol if row.asset else None,
            source=row.source,
            title=row.title,
            summary=row.summary,
            url=row.url,
            sentiment_score=row.sentiment_score,
            event_type=row.event_type,
            published_at=row.published_at,
        )
        for row in rows
    ]


@app.get("/api/trades", response_model=list[TradeOut])
def list_trades(db: Session = Depends(get_db)):
    rows = db.scalars(select(Trade).options(joinedload(Trade.asset)).order_by(Trade.executed_at.desc()).limit(50)).all()
    return [
        TradeOut(
            id=row.id,
            asset_symbol=row.asset.symbol,
            execution_target=row.execution_target,
            side=row.side.value,
            status=row.status.value,
            notional_eur=row.notional_eur,
            quantity=row.quantity,
            price=row.price,
            reason=row.reason,
            executed_at=row.executed_at,
        )
        for row in rows
    ]


@app.get("/api/execution/intents", response_model=list[ExecutionIntentOut])
def list_execution_intents(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(ExecutionIntent).options(joinedload(ExecutionIntent.asset)).order_by(ExecutionIntent.created_at.desc()).limit(50)
    ).all()
    return [
        ExecutionIntentOut(
            id=row.id,
            intent_key=row.intent_key,
            asset_symbol=row.asset.symbol,
            signal_id=row.signal_id,
            position_id=row.position_id,
            mode=row.mode,
            execution_target=row.execution_target,
            side=row.side.value,
            status=row.status.value,
            source=row.source,
            notional_eur=row.notional_eur,
            price_hint=row.price_hint,
            quantity=row.quantity,
            reason=row.reason,
            broker_provider=row.broker_provider,
            broker_order_id=row.broker_order_id,
            broker_status=row.broker_status,
            error_message=row.error_message,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


@app.get("/api/execution/reconciliation", response_model=ReconciliationStatusOut)
def get_reconciliation_status(db: Session = Depends(get_db)):
    return ReconciliationStatusOut(**build_reconciliation_service().snapshot(db).__dict__)


@app.get("/api/execution/reconciliation/details", response_model=ReconciliationDetailOut)
def get_reconciliation_detail(db: Session = Depends(get_db)):
    return ReconciliationDetailOut(**build_reconciliation_service().snapshot(db).__dict__)


@app.get("/api/positions", response_model=list[PositionOut])
def list_positions(db: Session = Depends(get_db)):
    rows = db.scalars(select(Position).options(joinedload(Position.asset)).order_by(Position.opened_at.desc()).limit(50)).all()
    return [
        PositionOut(
            id=row.id,
            asset_symbol=row.asset.symbol,
            status=row.status.value,
            quantity=row.quantity,
            entry_price=row.entry_price,
            stop_loss=row.stop_loss,
            take_profit=row.take_profit,
            opened_at=row.opened_at,
            closed_at=row.closed_at,
            exit_price=row.exit_price,
            pnl_eur=row.pnl_eur,
        )
        for row in rows
    ]


@app.get("/api/demo/active-position", response_model=ActiveDemoPositionOut | None)
def get_active_demo_position(db: Session = Depends(get_db)):
    position = db.scalar(
        select(Position)
        .options(joinedload(Position.asset))
        .where(Position.status == PositionStatus.OPEN)
        .order_by(Position.opened_at.desc())
        .limit(1)
    )
    snapshot = _active_demo_position_snapshot(db, position)
    if not snapshot:
        return None
    return ActiveDemoPositionOut(**snapshot)


@app.get("/api/summary", response_model=SummaryOut)
def get_summary(db: Session = Depends(get_db)):
    return build_portfolio_service().summary(db)


@app.get("/api/performance", response_model=PerformanceOut)
def get_performance(db: Session = Depends(get_db)):
    performance_report = _performance_report(db, build_portfolio_service().starting_capital_eur)
    performance_report["benchmark_alpha_summary"] = _benchmark_alpha_summary(
        _benchmark_report(db, performance_report["strategy_return_pct"])
    )
    return PerformanceOut(**performance_report)


@app.get("/api/benchmarks", response_model=BenchmarkReportOut)
def get_benchmarks(db: Session = Depends(get_db)):
    performance_report = _performance_report(db, build_portfolio_service().starting_capital_eur)
    return BenchmarkReportOut(**_benchmark_report(db, performance_report["strategy_return_pct"]))


@app.get("/api/setups/scorecards", response_model=SetupScorecardReportOut)
def get_setup_scorecards(db: Session = Depends(get_db)):
    return SetupScorecardReportOut(**build_strategy_proof_service().build_scorecard(db).to_dict())


@app.get("/api/setups/pending", response_model=PendingSetupReportOut)
def get_pending_setups(db: Session = Depends(get_db)):
    return PendingSetupReportOut(**_pending_setup_summary(db))


@app.get("/api/setups/monitor", response_model=SetupMonitorReportOut)
def get_setup_monitor(db: Session = Depends(get_db)):
    pending = _pending_setup_summary(db)
    walkforward = build_walkforward_service().build_report(db).to_dict()
    best_opportunity = build_opportunity_selector().summary(db)
    return SetupMonitorReportOut(**_setup_monitor_summary(walkforward, pending, best_opportunity))


@app.get("/api/setups/focus", response_model=ApprovalFocusReportOut)
def get_setup_focus(db: Session = Depends(get_db)):
    pending = _pending_setup_summary(db)
    scorecards = build_strategy_proof_service().build_scorecard(db).to_dict()
    walkforward = build_walkforward_service().build_report(db).to_dict()
    best_opportunity = build_opportunity_selector().summary(db)
    return ApprovalFocusReportOut(**_approval_focus_summary(scorecards, walkforward, pending, best_opportunity))


@app.get("/api/launch-readiness", response_model=LaunchReadinessReportOut)
def get_launch_readiness(db: Session = Depends(get_db)):
    assets = db.scalars(select(Asset).order_by(Asset.symbol)).all()
    signals = _latest_signals(db, limit=20)
    latest_market = _latest_market_rows(db, assets)
    provider_health = _provider_health_summary(db)
    pending_setups = _pending_setup_summary(db)
    best_opportunity = build_opportunity_selector().summary(db, signals=signals)
    setup_scorecards = _split_setup_rows(build_strategy_proof_service().build_scorecard(db).to_dict())
    setup_walkforward = _split_setup_rows(build_walkforward_service().build_report(db).to_dict())
    board_focus = _apply_etf_regime_focus(
        best_opportunity=best_opportunity,
        pending_setups=pending_setups,
        setup_scorecards=setup_scorecards,
        setup_walkforward=setup_walkforward,
        strategy_diagnostics=_strategy_diagnostics(signals, latest_market),
    )
    setup_monitor = _setup_monitor_summary(board_focus["setup_walkforward"], board_focus["pending_setups"], best_opportunity)
    approval_focus = _approval_focus_summary(
        board_focus["setup_scorecards"],
        board_focus["setup_walkforward"],
        board_focus["pending_setups"],
        best_opportunity,
    )
    reconciliation_status = build_reconciliation_service().snapshot(db)
    broker_status = build_broker_adapter(settings).status()
    risk_snapshot = build_risk_engine().control_snapshot(db)
    autopilot_status = _autopilot_status(signals, latest_market, provider_health, risk_snapshot)
    latest_engine_run = db.scalar(select(EngineRun).order_by(EngineRun.completed_at.desc()).limit(1))
    return LaunchReadinessReportOut(
        **_launch_readiness_summary(
            latest_engine_run=latest_engine_run,
            provider_health=provider_health,
            setup_monitor=setup_monitor,
            approval_focus=approval_focus,
            reconciliation_status=reconciliation_status,
            broker_status=broker_status,
            risk_snapshot=risk_snapshot,
            autopilot_status=autopilot_status,
        )
    )


@app.get("/api/live-deployment", response_model=LiveDeploymentReadinessOut)
def get_live_deployment_readiness(db: Session = Depends(get_db)):
    launch = get_launch_readiness(db)
    broker_status = build_broker_adapter(settings).status()
    reconciliation_status = build_reconciliation_service().snapshot(db)
    return LiveDeploymentReadinessOut(
        **_live_deployment_readiness(
            launch_readiness=launch.model_dump(),
            broker_status=broker_status,
            reconciliation_status=reconciliation_status,
        )
    )


@app.get("/api/operator-alerts", response_model=OperatorAlertPolicyOut)
def get_operator_alerts():
    return OperatorAlertPolicyOut(**_operator_alert_policy())


@app.get("/api/go-live-runbook", response_model=GoLiveRunbookOut)
def get_go_live_runbook():
    return GoLiveRunbookOut(**_go_live_runbook())


@app.get("/api/opportunity/best")
def get_best_opportunity(db: Session = Depends(get_db)):
    return build_opportunity_selector().summary(db)


@app.get("/api/setups/walk-forward", response_model=SetupWalkForwardReportOut)
def get_setup_walkforward(db: Session = Depends(get_db)):
    return SetupWalkForwardReportOut(**build_walkforward_service().build_report(db).to_dict())


@app.get("/api/simulation", response_model=SimulationOut | None)
def get_simulation(db: Session = Depends(get_db)):
    simulation = build_simulation_service().get_active(db)
    if not simulation:
        return None
    return SimulationOut(
        id=simulation.id,
        asset_symbol=simulation.asset.symbol,
        asset_kind=simulation.asset.kind.value,
        status=simulation.status.value,
        initial_notional_eur=simulation.initial_notional_eur,
        quantity=simulation.quantity,
        entry_price=simulation.entry_price,
        latest_price=simulation.latest_price,
        pnl_eur=simulation.pnl_eur,
        pnl_pct=simulation.pnl_pct,
        stop_price=simulation.stop_price,
        take_profit_price=simulation.take_profit_price,
        trailing_stop_price=simulation.trailing_stop_price,
        opened_reason=simulation.opened_reason,
        started_at=simulation.started_at,
        updated_at=simulation.updated_at,
        closed_at=simulation.closed_at,
    )


@app.get("/api/simulations")
def get_simulations(db: Session = Depends(get_db)):
    simulations = build_simulation_service().list_active(db)
    return [
        {
            "id": simulation.id,
            "scenario_key": simulation.scenario_key,
            "scenario_label": simulation.scenario_label,
            "asset_symbol": simulation.asset.symbol,
            "asset_kind": simulation.asset.kind.value,
            "setup_type": simulation.setup_type,
            "status": simulation.status.value,
            "initial_notional_eur": simulation.initial_notional_eur,
            "entry_price": simulation.entry_price,
            "latest_price": simulation.latest_price,
            "pnl_eur": simulation.pnl_eur,
            "pnl_pct": simulation.pnl_pct,
            "opened_signal_score": simulation.opened_signal_score,
            "started_at": simulation.started_at,
            "updated_at": simulation.updated_at,
        }
        for simulation in simulations
    ]


@app.get("/api/simulation/alerts", response_model=list[SimulationAlertOut])
def get_simulation_alerts(db: Session = Depends(get_db)):
    alerts = build_simulation_service().list_alerts(db)
    return [
        SimulationAlertOut(
            id=alert.id,
            level=alert.level,
            title=alert.title,
            message=alert.message,
            asset_symbol=alert.simulation.asset.symbol if alert.simulation and alert.simulation.asset else None,
            created_at=alert.created_at,
        )
        for alert in alerts
    ]


@app.get("/api/state-events", response_model=list[StateEventOut])
def get_state_events(db: Session = Depends(get_db)):
    events = build_state_event_service().list_recent(db, limit=30)
    return [
        StateEventOut(
            id=event.id,
            event_key=event.event_key,
            category=event.category,
            severity=event.severity,
            title=event.title,
            message=event.message,
            fingerprint=event.fingerprint,
            created_at=event.created_at,
        )
        for event in events
    ]


@app.get("/api/broker/status", response_model=BrokerStatusOut)
def broker_status():
    return BrokerStatusOut(**build_broker_adapter(settings).status().__dict__)


@app.get("/api/broker/capabilities", response_model=BrokerCapabilitiesOut)
def broker_capabilities():
    return BrokerCapabilitiesOut(**build_broker_adapter(settings).capabilities().__dict__)


@app.get("/api/broker/preview-order")
def broker_preview_order(symbol: str, side: str = "buy", notional: float = 5.0, client_order_id: str | None = None):
    preview = build_broker_adapter(settings).preview_order(symbol, side, notional, client_order_id=client_order_id)
    return preview.__dict__


@app.get("/api/broker/positions", response_model=list[BrokerPositionOut])
def broker_positions():
    return [BrokerPositionOut(**row.__dict__) for row in build_broker_adapter(settings).list_positions()]


@app.get("/api/broker/orders", response_model=list[BrokerOrderOut])
def broker_orders(status: str = "all", limit: int = 25):
    return [BrokerOrderOut(**row.__dict__) for row in build_broker_adapter(settings).list_orders(status=status, limit=limit)]


@app.post("/api/broker/submit-order", response_model=BrokerOrderResultOut)
def broker_submit_order(
    symbol: str = Form(...),
    side: str = Form(...),
    notional: float = Form(...),
    dry_run: bool = Form(True),
    client_order_id: str | None = Form(None),
    db: Session = Depends(get_db),
):
    asset = db.scalar(select(Asset).where(Asset.symbol == symbol.upper()))
    if not asset:
        result = build_broker_adapter(settings).submit_order(
            symbol=symbol.upper(),
            side=side.lower(),
            notional=notional,
            dry_run=dry_run,
            client_order_id=client_order_id,
        )
        return BrokerOrderResultOut(**result.__dict__)

    intent_service = build_execution_service()
    generated_client_order_id = client_order_id or f"broker-api:{symbol.upper()}:{side.lower()}:{uuid4().hex[:16]}"
    intent, _ = intent_service.get_or_create_intent(
        db,
        intent_key=generated_client_order_id,
        asset=asset,
        side=TradeSide.BUY if side.lower() == "buy" else TradeSide.SELL,
        reason=f"Broker API {side.lower()} request for {symbol.upper()}",
        source="broker_api",
        notional_eur=notional,
        price_hint=None,
    )
    result = build_broker_adapter(settings).submit_order(
        symbol=symbol.upper(),
        side=side.lower(),
        notional=notional,
        dry_run=dry_run,
        client_order_id=generated_client_order_id,
    )
    intent.broker_provider = result.provider
    intent.broker_order_id = result.broker_order_id
    intent.broker_status = result.broker_status
    intent.error_message = "" if result.submitted or result.dry_run else result.message
    intent.updated_at = datetime.utcnow()
    if result.submitted:
        intent.status = ExecutionIntentStatus.PENDING
    elif result.dry_run:
        intent.status = ExecutionIntentStatus.SKIPPED
    else:
        intent.status = ExecutionIntentStatus.FAILED
    db.commit()
    return BrokerOrderResultOut(**result.__dict__)


@app.get("/api/demo/preview", response_model=DemoPreviewOut)
def preview_demo(asset_symbol: str, notional_eur: float = 5.0, scenario_pct: float = 2.0, db: Session = Depends(get_db)):
    return DemoPreviewOut(**build_trader().preview_roundtrip(db, asset_symbol, notional_eur, scenario_pct))


@app.post("/api/engine/run-once")
def run_once(db: Session = Depends(get_db)):
    return run_engine_cycle(db, settings)


@app.post("/actions/run-engine")
def run_engine_action(db: Session = Depends(get_db)):
    result = run_engine_cycle(db, settings)
    return _redirect_with_message(f"Engine updated: {result['signals']} signals refreshed.")


@app.post("/actions/start-best-simulation")
def start_best_simulation(notional_eur: float = Form(100.0), db: Session = Depends(get_db)):
    try:
        simulation = build_simulation_service().start_best_asset(db, notional_eur=notional_eur)
        return _redirect_with_message(
            f"Best-asset simulation started on {simulation.asset.symbol} with EUR {simulation.initial_notional_eur:.2f}."
        )
    except ValueError as exc:
        return _redirect_with_message(str(exc))


@app.post("/actions/simulate-buy")
def simulate_buy(asset_symbol: str = Form(...), notional_eur: float = Form(5.0), db: Session = Depends(get_db)):
    try:
        position = build_trader().manual_buy(
            db,
            asset_symbol=asset_symbol,
            notional_eur=notional_eur,
            reason="Manual demo buy from the dashboard controls.",
        )
        return _redirect_with_message(f"Bought {position.asset.symbol if position.asset else asset_symbol.upper()} for demo.")
    except ValueError as exc:
        return _redirect_with_message(str(exc))


@app.post("/actions/simulate-sell")
def simulate_sell(asset_symbol: str = Form(...), outcome: str = Form("market"), db: Session = Depends(get_db)):
    try:
        asset = db.scalar(select(Asset).where(Asset.symbol == asset_symbol.upper()))
        position = db.scalar(
            select(Position).where(Position.asset_id == asset.id, Position.status == PositionStatus.OPEN)
        ) if asset else None
        exit_price = None
        reason = "Manual dashboard sell at current market price."
        if position:
            if outcome == "profit":
                exit_price = position.take_profit
                reason = "Manual dashboard close at simulated take profit."
            elif outcome == "loss":
                exit_price = position.stop_loss
                reason = "Manual dashboard close at simulated stop loss."
        build_trader().manual_sell(db, asset_symbol=asset_symbol, exit_price=exit_price, reason=reason)
        return _redirect_with_message(f"Closed {asset_symbol.upper()} with a demo sell.")
    except ValueError as exc:
        return _redirect_with_message(str(exc))


@app.post("/actions/demo-preview")
def demo_preview_action(
    asset_symbol: str = Form(...),
    notional_eur: float = Form(5.0),
    scenario_pct: float = Form(2.0),
    db: Session = Depends(get_db),
):
    try:
        preview = build_trader().preview_roundtrip(db, asset_symbol, notional_eur, scenario_pct)
    except ValueError as exc:
        return _redirect_with_message(str(exc))
    params = {
        "message": "Demo preview updated. No real paper trade was written.",
        "preview_asset": preview["asset_symbol"],
        "preview_notional": preview["notional_eur"],
        "preview_entry": preview["entry_price"],
        "preview_exit": preview["exit_price"],
        "preview_qty": preview["quantity"],
        "preview_pct": preview["scenario_pct"],
        "preview_pnl": preview["pnl_eur"],
        "preview_pnl_pct": preview["pnl_pct"],
    }
    return RedirectResponse(url=f"/?{urlencode(params)}", status_code=303)


def _redirect_with_message(message: str) -> RedirectResponse:
    return RedirectResponse(url=f"/?{urlencode({'message': message})}", status_code=303)


def _demo_preview_from_request(request: Request) -> dict | None:
    params = request.query_params
    if "preview_asset" not in params:
        return None
    return {
        "asset_symbol": params.get("preview_asset"),
        "notional_eur": float(params.get("preview_notional", "0")),
        "entry_price": float(params.get("preview_entry", "0")),
        "exit_price": float(params.get("preview_exit", "0")),
        "quantity": float(params.get("preview_qty", "0")),
        "scenario_pct": float(params.get("preview_pct", "0")),
        "pnl_eur": float(params.get("preview_pnl", "0")),
        "pnl_pct": float(params.get("preview_pnl_pct", "0")),
    }


def _latest_market_rows(db: Session, assets: list[Asset]) -> list[dict]:
    rows: list[dict] = []
    for asset in assets:
        tick = db.scalar(
            select(MarketTick).where(MarketTick.asset_id == asset.id).order_by(MarketTick.captured_at.desc()).limit(1)
        )
        age_seconds = None
        freshness = "missing"
        captured_at = None
        if tick:
            age_seconds = max(int((datetime.utcnow() - tick.captured_at).total_seconds()), 0)
            if age_seconds <= settings.max_tick_age_seconds:
                freshness = "fresh"
            elif tick.source == "alpaca" and age_seconds <= settings.alpaca_quote_cache_ttl_seconds:
                freshness = "recent"
            else:
                freshness = "stale"
            captured_at = tick.captured_at
        rows.append(
            {
                "symbol": asset.symbol,
                "kind": asset.kind.value,
                "price": tick.price if tick else None,
                "change_24h_pct": tick.change_24h_pct if tick else None,
                "source": tick.source if tick else "-",
                "captured_at": captured_at,
                "age_seconds": age_seconds,
                "freshness": freshness,
            }
        )
    return rows


def _performance_report(db: Session, starting_capital_eur: float) -> dict:
    realized_pnl = float(db.scalar(select(func.sum(Position.pnl_eur)).where(Position.pnl_eur.is_not(None))) or 0.0)
    closed_positions = db.scalars(
        select(Position).where(Position.status == PositionStatus.CLOSED).order_by(Position.closed_at.asc(), Position.opened_at.asc())
    ).all()
    open_positions = db.scalars(
        select(Position).options(joinedload(Position.asset)).where(Position.status == PositionStatus.OPEN)
    ).all()
    unrealized_pnl = 0.0
    for position in open_positions:
        latest_tick = db.scalar(
            select(MarketTick).where(MarketTick.asset_id == position.asset_id).order_by(MarketTick.captured_at.desc()).limit(1)
        )
        if not latest_tick:
            continue
        unrealized_pnl += (float(latest_tick.price) - position.entry_price) * position.quantity

    closed_trade_rows: list[dict] = []
    for position in closed_positions:
        if position.pnl_eur is None:
            continue
        entry_notional = float(position.entry_price * position.quantity)
        pnl_eur = float(position.pnl_eur)
        pnl_pct = round((pnl_eur / entry_notional) * 100, 2) if entry_notional else 0.0
        closed_trade_rows.append(
            {
                "pnl_eur": pnl_eur,
                "pnl_pct": pnl_pct,
                "closed_at": position.closed_at or position.opened_at,
            }
        )

    wins = [row for row in closed_trade_rows if row["pnl_eur"] > 0]
    losses = [row for row in closed_trade_rows if row["pnl_eur"] < 0]
    breakeven_positions = len([row for row in closed_trade_rows if row["pnl_eur"] == 0])
    closed_count = len(closed_trade_rows)
    winning_count = len(wins)
    losing_count = len(losses)

    current_equity_eur = float(starting_capital_eur + realized_pnl + unrealized_pnl)
    equity = float(starting_capital_eur)
    peak_equity = float(starting_capital_eur)
    max_drawdown_eur = 0.0
    for row in closed_trade_rows:
        equity += row["pnl_eur"]
        peak_equity = max(peak_equity, equity)
        max_drawdown_eur = max(max_drawdown_eur, peak_equity - equity)
    peak_equity = max(peak_equity, current_equity_eur)
    max_drawdown_eur = max(max_drawdown_eur, peak_equity - current_equity_eur)
    current_drawdown_eur = max(peak_equity - current_equity_eur, 0.0)
    strategy_return_pct = round(((realized_pnl + unrealized_pnl) / starting_capital_eur) * 100, 2) if starting_capital_eur else 0.0

    gross_profit = sum(row["pnl_eur"] for row in wins)
    gross_loss = abs(sum(row["pnl_eur"] for row in losses))
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss else None
    avg_closed_pnl_eur = round(sum(row["pnl_eur"] for row in closed_trade_rows) / closed_count, 4) if closed_count else 0.0
    avg_closed_pnl_pct = round(sum(row["pnl_pct"] for row in closed_trade_rows) / closed_count, 2) if closed_count else 0.0
    avg_win_eur = round(gross_profit / winning_count, 4) if winning_count else 0.0
    avg_loss_eur = round(sum(row["pnl_eur"] for row in losses) / losing_count, 4) if losing_count else 0.0
    expectancy_eur = avg_closed_pnl_eur
    expectancy_pct = avg_closed_pnl_pct
    win_rate_pct = round((winning_count / closed_count) * 100, 2) if closed_count else 0.0
    max_drawdown_pct = round((max_drawdown_eur / peak_equity) * 100, 2) if peak_equity else 0.0
    current_drawdown_pct = round((current_drawdown_eur / peak_equity) * 100, 2) if peak_equity else 0.0

    return {
        "closed_positions": closed_count,
        "winning_positions": winning_count,
        "losing_positions": losing_count,
        "breakeven_positions": breakeven_positions,
        "win_rate_pct": win_rate_pct,
        "realized_pnl_eur": round(realized_pnl, 4),
        "unrealized_pnl_eur": round(unrealized_pnl, 4),
        "net_pnl_eur": round(realized_pnl + unrealized_pnl, 4),
        "current_equity_eur": round(current_equity_eur, 4),
        "peak_equity_eur": round(peak_equity, 4),
        "strategy_return_pct": strategy_return_pct,
        "avg_closed_pnl_eur": avg_closed_pnl_eur,
        "avg_closed_pnl_pct": avg_closed_pnl_pct,
        "avg_win_eur": avg_win_eur,
        "avg_loss_eur": avg_loss_eur,
        "expectancy_eur": expectancy_eur,
        "expectancy_pct": expectancy_pct,
        "profit_factor": profit_factor,
        "max_drawdown_eur": round(max_drawdown_eur, 4),
        "max_drawdown_pct": max_drawdown_pct,
        "current_drawdown_eur": round(current_drawdown_eur, 4),
        "current_drawdown_pct": current_drawdown_pct,
        "benchmark_alpha_summary": "Benchmark comparison pending.",
    }


def _benchmark_report(db: Session, strategy_return_pct: float) -> dict:
    benchmark_symbols = ("SPY", "QQQ", "VTI")
    rows = []
    for symbol in benchmark_symbols:
        asset = db.scalar(select(Asset).where(Asset.symbol == symbol))
        if not asset:
            continue
        first_tick = db.scalar(
            select(MarketTick).where(MarketTick.asset_id == asset.id).order_by(MarketTick.captured_at.asc()).limit(1)
        )
        latest_tick = db.scalar(
            select(MarketTick).where(MarketTick.asset_id == asset.id).order_by(MarketTick.captured_at.desc()).limit(1)
        )
        if not first_tick or not latest_tick or not first_tick.price:
            continue
        return_pct = round(((float(latest_tick.price) / float(first_tick.price)) - 1) * 100, 2)
        rows.append(
            {
                "symbol": symbol,
                "return_pct": return_pct,
                "alpha_pct": round(strategy_return_pct - return_pct, 2),
                "start_price": float(first_tick.price),
                "latest_price": float(latest_tick.price),
            }
        )

    best = max(rows, key=lambda item: item["return_pct"], default=None)
    return {
        "strategy_return_pct": round(strategy_return_pct, 2),
        "rows": rows,
        "best_benchmark": best,
    }


def _benchmark_alpha_summary(benchmark_report: dict) -> str:
    rows = benchmark_report["rows"]
    if not rows:
        return "Benchmark comparison pending."
    best_alpha = max(rows, key=lambda item: item["alpha_pct"])
    worst_alpha = min(rows, key=lambda item: item["alpha_pct"])
    if best_alpha["alpha_pct"] >= 0:
        return f"Outperforming {best_alpha['symbol']} by {best_alpha['alpha_pct']:.2f}% at best."
    return f"Trailing {worst_alpha['symbol']} by {abs(worst_alpha['alpha_pct']):.2f}% at worst."


def _active_demo_position_snapshot(db: Session, position: Position | None) -> dict | None:
    if not position or not position.asset:
        return None
    invested_notional = round(position.entry_price * position.quantity, 4)
    latest_tick = db.scalar(
        select(MarketTick).where(MarketTick.asset_id == position.asset_id).order_by(MarketTick.captured_at.desc()).limit(1)
    )
    current_price = float(latest_tick.price) if latest_tick and latest_tick.price is not None else None
    current_value_eur = None
    unrealized_pnl_eur = None
    unrealized_pnl_pct = None
    updated_at = latest_tick.captured_at if latest_tick else None
    if current_price is not None:
        current_value_eur = round(current_price * position.quantity, 4)
        unrealized_pnl_eur = round((current_price - position.entry_price) * position.quantity, 4)
        unrealized_pnl_pct = round((unrealized_pnl_eur / invested_notional) * 100, 2) if invested_notional else 0.0
    return {
        "asset_symbol": position.asset.symbol,
        "asset_kind": position.asset.kind.value,
        "status": position.status.value,
        "quantity": round(position.quantity, 8),
        "invested_notional_eur": invested_notional,
        "entry_price": round(position.entry_price, 4),
        "current_price": round(current_price, 4) if current_price is not None else None,
        "current_value_eur": current_value_eur,
        "stop_loss": round(position.stop_loss, 4),
        "take_profit": round(position.take_profit, 4),
        "unrealized_pnl_eur": unrealized_pnl_eur,
        "unrealized_pnl_pct": unrealized_pnl_pct,
        "opened_at": position.opened_at,
        "updated_at": updated_at,
    }


def _provider_health_summary(db: Session) -> dict:
    rows = db.scalars(
        select(ProviderHealthSample).order_by(ProviderHealthSample.created_at.desc()).limit(20)
    ).all()
    latest_by_kind: dict[str, ProviderHealthSample] = {}
    for row in rows:
        latest_by_kind.setdefault(row.asset_kind, row)

    recent_failures = [row for row in rows if row.status in {"warn", "error"}][:6]
    return {
        "latest_by_kind": latest_by_kind,
        "recent_failures": recent_failures,
    }


def _provider_audit(provider_health: dict) -> list[dict]:
    audits: list[dict] = []
    preferred_map = {
        "crypto": settings.crypto_data_provider,
        "etf": settings.etf_data_provider,
        "stock": settings.etf_data_provider,
    }
    for kind, sample in provider_health.get("latest_by_kind", {}).items():
        provider_value = sample.provider or "none"
        actual_provider = provider_value
        if "+" in provider_value:
            actual_provider = provider_value
        preferred_provider = preferred_map.get(kind, "unknown")
        message = sample.message or ""
        fallback_used = "Fallback used." in message or (preferred_provider not in provider_value and provider_value != "none")
        audits.append(
            {
                "asset_kind": kind,
                "preferred_provider": preferred_provider,
                "actual_provider": actual_provider,
                "fallback_used": fallback_used,
                "status": sample.status,
                "message": (
                    f"{message} Cached Alpaca quotes supported this lane."
                    if getattr(sample, "cache_used", False)
                    else message
                ),
            }
        )
    audits.sort(key=lambda item: item["asset_kind"])
    return audits


def _strategy_diagnostics(signals: list[Signal], latest_market: list[dict]) -> list[dict]:
    tick_by_symbol = {row["symbol"]: row for row in latest_market}
    diagnostics: list[dict] = []
    strategy_engine = build_strategy_engine()
    for signal in signals[:10]:
        article_count = extract_news_count(signal.rationale)
        setup_type, failed_checks = strategy_engine.failed_checks_for_signal(
            signal.asset.kind.value,
            signal.score,
            signal.sentiment_score,
            signal.momentum_score,
            article_count,
        )
        if signal.action.value == "buy":
            failed_checks = []
        diagnostics.append(
            {
                "asset_symbol": signal.asset.symbol,
                "asset_kind": signal.asset.kind.value,
                "setup_type": setup_type,
                "action": signal.action.value,
                "score": signal.score,
                "sentiment_score": signal.sentiment_score,
                "momentum_score": signal.momentum_score,
                "news_count": article_count,
                "failed_checks": failed_checks,
                "freshness": tick_by_symbol.get(signal.asset.symbol, {}).get("freshness", "missing"),
                "rationale": signal.rationale,
            }
        )
    return diagnostics


def _signal_outcome_summary(db: Session) -> dict:
    rows = db.scalars(
        select(SignalOutcomeSnapshot)
        .options(joinedload(SignalOutcomeSnapshot.signal).joinedload(Signal.asset))
        .order_by(SignalOutcomeSnapshot.updated_at.desc())
        .limit(60)
    ).all()
    latest_resolved = [row for row in rows if row.outcome_status == "resolved"][:12]
    grouped: dict[int, list[SignalOutcomeSnapshot]] = {}
    for row in rows:
        grouped.setdefault(row.horizon_hours, []).append(row)

    summary_by_horizon = {}
    for horizon, horizon_rows in grouped.items():
        resolved = [row for row in horizon_rows if row.outcome_status == "resolved" and row.pnl_pct is not None]
        positive = [row for row in resolved if row.pnl_pct > 0]
        pending = [row for row in horizon_rows if row.outcome_status == "pending"]
        summary_by_horizon[horizon] = {
            "resolved_count": len(resolved),
            "pending_count": len(pending),
            "win_rate_pct": round((len(positive) / len(resolved)) * 100, 2) if resolved else 0.0,
            "avg_pnl_pct": round(sum(row.pnl_pct for row in resolved) / len(resolved), 3) if resolved else 0.0,
            "avg_market_move_pct": round(
                sum((row.market_move_pct or 0.0) for row in resolved) / len(resolved),
                3,
            ) if resolved else 0.0,
            "next_due_label": _next_due_label(pending, horizon),
        }

    return {
        "latest_resolved": latest_resolved,
        "summary_by_horizon": summary_by_horizon,
    }


def _pending_setup_summary(db: Session) -> dict:
    rows = db.scalars(
        select(SignalOutcomeSnapshot)
        .options(joinedload(SignalOutcomeSnapshot.signal).joinedload(Signal.asset))
        .where(SignalOutcomeSnapshot.outcome_status == "pending")
        .order_by(SignalOutcomeSnapshot.created_at.desc())
        .limit(300)
    ).all()
    grouped: dict[tuple[str, str, str], list[SignalOutcomeSnapshot]] = {}
    for row in rows:
        signal = row.signal
        asset = signal.asset if signal else None
        if not signal or not asset:
            continue
        setup_type = extract_setup_type(signal.rationale) or "unknown"
        grouped.setdefault((asset.kind.value, setup_type, signal.action.value), []).append(row)

    summary_rows = []
    for (asset_kind, setup_type, action), bucket in grouped.items():
        horizons = sorted({item.horizon_hours for item in bucket})
        latest_signal_at = max((item.signal.created_at for item in bucket if item.signal), default=None)
        next_due = _next_due_label(bucket, min(horizons) if horizons else 0)
        summary_rows.append(
            {
                "asset_kind": asset_kind,
                "setup_type": setup_type,
                "action": action,
                "pending_count": len(bucket),
                "horizons": horizons,
                "latest_signal_at": latest_signal_at,
                "next_due_label": next_due,
            }
        )

    action_rank = {"buy": 0, "sell": 1, "hold": 2}
    summary_rows.sort(
        key=lambda row: (
            action_rank.get(row["action"], 9),
            -row["pending_count"],
            row["asset_kind"],
            row["setup_type"],
        )
    )
    return {
        "generated_at": datetime.utcnow(),
        "total_pending": len(rows),
        "rows": summary_rows,
    }


def _split_setup_rows(report: dict) -> dict:
    rows = report.get("rows", [])
    entry_rows = [row for row in rows if not row["setup_type"].endswith("risk_off")]
    defensive_rows = [row for row in rows if row["setup_type"].endswith("risk_off")]
    promoted_statuses = {"approved", "watch"}
    promoted_entry_rows = [
        row
        for row in entry_rows
        if row.get("approval_status", row.get("recommendation")) in promoted_statuses
    ]
    blocked_entry_rows = [
        row
        for row in entry_rows
        if row.get("approval_status", row.get("recommendation")) == "disabled"
    ]
    return {
        **report,
        "entry_rows": entry_rows,
        "defensive_rows": defensive_rows,
        "promoted_entry_rows": promoted_entry_rows,
        "blocked_entry_rows": blocked_entry_rows,
        "entry_count": len(entry_rows),
        "defensive_count": len(defensive_rows),
        "promoted_entry_count": len(promoted_entry_rows),
        "blocked_entry_count": len(blocked_entry_rows),
    }


def _apply_etf_regime_focus(
    *,
    best_opportunity: dict,
    pending_setups: dict,
    setup_scorecards: dict,
    setup_walkforward: dict,
    strategy_diagnostics: list[dict],
) -> dict:
    regime_transition = (best_opportunity or {}).get("regime_transition") or {}
    if regime_transition.get("asset_kind") != "etf" or regime_transition.get("state") != "risk_off":
        return {
            "pending_setups": {**pending_setups, "board_note": None},
            "setup_scorecards": {
                **setup_scorecards,
                "board_note": None,
            },
            "setup_walkforward": {
                **setup_walkforward,
                "board_note": None,
            },
            "strategy_diagnostics": strategy_diagnostics,
            "strategy_diagnostics_note": None,
        }

    stale_etf_setups = {"etf_watch", "etf_risk_off"}
    leader_symbol = regime_transition.get("symbol", "ETF")

    def should_hide_row(row: dict) -> bool:
        return row.get("asset_kind") == "etf" and row.get("setup_type") in stale_etf_setups

    filtered_pending_rows = [row for row in pending_setups.get("rows", []) if not should_hide_row(row)]
    hidden_pending_count = len(pending_setups.get("rows", [])) - len(filtered_pending_rows)

    filtered_promoted_scorecards = [row for row in setup_scorecards.get("promoted_entry_rows", []) if not should_hide_row(row)]
    filtered_blocked_scorecards = [row for row in setup_scorecards.get("blocked_entry_rows", []) if not should_hide_row(row)]
    hidden_scorecard_count = (
        len(setup_scorecards.get("promoted_entry_rows", [])) - len(filtered_promoted_scorecards)
        + len(setup_scorecards.get("blocked_entry_rows", [])) - len(filtered_blocked_scorecards)
    )

    filtered_promoted_walkforward = [row for row in setup_walkforward.get("promoted_entry_rows", []) if not should_hide_row(row)]
    filtered_blocked_walkforward = [row for row in setup_walkforward.get("blocked_entry_rows", []) if not should_hide_row(row)]
    hidden_walkforward_count = (
        len(setup_walkforward.get("promoted_entry_rows", [])) - len(filtered_promoted_walkforward)
        + len(setup_walkforward.get("blocked_entry_rows", [])) - len(filtered_blocked_walkforward)
    )

    filtered_diagnostics = [
        item
        for item in strategy_diagnostics
        if not (item.get("asset_kind") == "etf" and item.get("setup_type") in stale_etf_setups)
    ]
    hidden_diagnostics_count = len(strategy_diagnostics) - len(filtered_diagnostics)

    focus_note = (
        f"ETF lane is currently risk-off around {leader_symbol}, so stale ETF watch and defensive rows are hidden here "
        "until leadership starts rebuilding."
    )

    return {
        "pending_setups": {
            **pending_setups,
            "rows": filtered_pending_rows,
            "board_note": focus_note if hidden_pending_count else None,
            "suppressed_rows_count": hidden_pending_count,
        },
        "setup_scorecards": {
            **setup_scorecards,
            "promoted_entry_rows": filtered_promoted_scorecards,
            "blocked_entry_rows": filtered_blocked_scorecards,
            "board_note": focus_note if hidden_scorecard_count else None,
            "suppressed_rows_count": hidden_scorecard_count,
            "promoted_entry_count": len(filtered_promoted_scorecards),
            "blocked_entry_count": len(filtered_blocked_scorecards),
        },
        "setup_walkforward": {
            **setup_walkforward,
            "promoted_entry_rows": filtered_promoted_walkforward,
            "blocked_entry_rows": filtered_blocked_walkforward,
            "board_note": focus_note if hidden_walkforward_count else None,
            "suppressed_rows_count": hidden_walkforward_count,
            "promoted_entry_count": len(filtered_promoted_walkforward),
            "blocked_entry_count": len(filtered_blocked_walkforward),
        },
        "strategy_diagnostics": filtered_diagnostics,
        "strategy_diagnostics_note": focus_note if hidden_diagnostics_count else None,
    }


def _setup_monitor_summary(setup_walkforward: dict, pending_setups: dict, best_opportunity: dict | None = None) -> dict:
    pending_lookup = {}
    pending_by_action = {}
    for row in pending_setups.get("rows", []):
        key = (row["asset_kind"], row["setup_type"])
        current = pending_lookup.get(key)
        if current is None or row["pending_count"] > current["pending_count"]:
            pending_lookup[key] = row
        pending_by_action[(row["asset_kind"], row["setup_type"], row["action"])] = row
    entry_rows = [
        row
        for row in setup_walkforward.get("rows", [])
        if not row["setup_type"].endswith("risk_off") and not row["setup_type"].endswith("watch")
    ]
    monitor_rows: list[dict] = []
    for row in entry_rows:
        pending = pending_lookup.get((row["asset_kind"], row["setup_type"]), {})
        monitor_rows.append(
            {
                "asset_symbol": None,
                "asset_kind": row["asset_kind"],
                "setup_type": row["setup_type"],
                "action": "buy",
                "recommendation": row["recommendation"],
                "live_proof_status": row["live_proof_status"],
                "eligible_for_unattended": row["eligible_for_unattended"],
                "live_sample_count": row["live_sample_count"],
                "replay_sample_count": row["replay_sample_count"],
                "pending_count": pending.get("pending_count", 0),
                "next_due_label": pending.get("next_due_label", "none pending"),
                "test_net_expectancy_pct": row["test"]["net_expectancy_pct"],
                "next_target": _next_proof_target(
                    row["live_proof_status"],
                    row["recommendation"],
                    row["eligible_for_unattended"],
                    pending.get("pending_count", 0),
                    row["live_sample_count"],
                ),
                "note": row["note"],
                "_test_net": row["test"]["net_expectancy_pct"],
            }
        )

    existing_keys = {(row["asset_kind"], row["setup_type"]) for row in monitor_rows}
    for row in pending_setups.get("rows", []):
        key = (row["asset_kind"], row["setup_type"])
        if key in existing_keys:
            continue
        if row["action"] != "buy":
            continue
        if row["setup_type"].endswith("risk_off") or row["setup_type"].endswith("watch"):
            continue
        monitor_rows.append(
            {
                "asset_symbol": None,
                "asset_kind": row["asset_kind"],
                "setup_type": row["setup_type"],
                "action": row["action"],
                "recommendation": "watch",
                "live_proof_status": "building_live",
                "eligible_for_unattended": False,
                "live_sample_count": 0,
                "replay_sample_count": 0,
                "pending_count": row["pending_count"],
                "next_due_label": row["next_due_label"],
                "test_net_expectancy_pct": 0.0,
                "next_target": _next_proof_target("building_live", "watch", False, row["pending_count"], 0),
                "note": "Live signal fired and is waiting for 1h / 4h / 24h outcomes to resolve.",
                "_test_net": 0.0,
            }
        )

    ready_rows = [row for row in monitor_rows if row["eligible_for_unattended"]]
    building_live_rows = [row for row in monitor_rows if row["live_proof_status"] == "building_live"]
    replay_only_rows = [row for row in monitor_rows if row["live_proof_status"] == "replay_only"]
    viable_rows = [row for row in monitor_rows if row["recommendation"] != "disabled"]
    status_rank = {"cleared": 0, "building_live": 1, "replay_only": 2, "research": 3, "exit_only": 4}
    recommendation_rank = {"approved": 0, "watch": 1, "disabled": 2}
    nearest_candidate = min(
        viable_rows,
        key=lambda row: (
            status_rank.get(row["live_proof_status"], 9),
            recommendation_rank.get(row["recommendation"], 9),
            -row["live_sample_count"],
            -row["pending_count"],
            -row["_test_net"],
        ),
        default=None,
    )
    if nearest_candidate:
        nearest_candidate = {key: value for key, value in nearest_candidate.items() if not key.startswith("_")}
    regime_transition = (best_opportunity or {}).get("regime_transition") if best_opportunity else None
    recovery_candidate = None
    if not nearest_candidate and regime_transition:
        recovery_candidate = dict(regime_transition.get("candidate") or {})
        if recovery_candidate:
            nearest_candidate = recovery_candidate

    active_candidate = None
    best = (best_opportunity or {}).get("best") if best_opportunity else None
    if best:
        pending = pending_by_action.get((best["asset_kind"], best["setup_type"], best["action"]))
        matching_row = next(
            (
                row for row in monitor_rows
                if row["asset_kind"] == best["asset_kind"] and row["setup_type"] == best["setup_type"]
            ),
            None,
        )
        if matching_row:
            active_candidate = {
                key: value for key, value in matching_row.items() if not key.startswith("_")
            }
            active_candidate["asset_symbol"] = best["symbol"]
            active_candidate["action"] = best["action"]
            if pending:
                active_candidate["pending_count"] = pending["pending_count"]
                active_candidate["next_due_label"] = pending["next_due_label"]
            active_candidate["note"] = best.get("blocked_reason") or matching_row["note"]
            active_candidate["next_target"] = _next_proof_target(
                active_candidate["live_proof_status"],
                active_candidate["recommendation"],
                active_candidate["eligible_for_unattended"],
                active_candidate["pending_count"],
                active_candidate["live_sample_count"],
            )

    alerts: list[dict] = []
    if ready_rows:
        alerts.append(
            {
                "severity": "ok",
                "title": "A setup is operationally ready",
                "message": f"{len(ready_rows)} entry setup(s) have cleared live-proof gates for unattended review.",
            }
        )
    else:
        alerts.append(
            {
                "severity": "warn",
                "title": "Not ready for unattended entries yet",
                "message": "No entry setup has enough live proof to justify low-attention deployment.",
            }
        )
    if nearest_candidate and nearest_candidate["pending_count"] > 0:
        alerts.append(
            {
                "severity": "ok" if nearest_candidate["live_proof_status"] == "building_live" else "warn",
                "title": f"{nearest_candidate['setup_type']} is the closest candidate",
                "message": (
                    f"{nearest_candidate['pending_count']} pending outcomes are still open for "
                    f"{nearest_candidate['asset_kind'].upper()} {nearest_candidate['setup_type']}. "
                    f"{nearest_candidate['next_due_label']}."
                ),
            }
        )
    elif recovery_candidate:
        alerts.append(
            {
                "severity": regime_transition.get("severity", "warn"),
                "title": regime_transition.get("title", "ETF recovery candidate is being tracked"),
                "message": recovery_candidate["note"],
            }
        )
    if replay_only_rows:
        alerts.append(
            {
                "severity": "warn",
                "title": "Replay-only ideas still need live proof",
                "message": f"{len(replay_only_rows)} setup(s) look interesting in replay but still have zero live resolved outcomes.",
            }
        )

    if ready_rows:
        overall_state = "ok"
        overall_message = f"{len(ready_rows)} setup(s) have cleared live-proof gates. Unattended mode can stay strict and still find candidates."
    elif nearest_candidate:
        overall_state = "warn"
        if recovery_candidate:
            overall_message = (
                f"Not ready yet. ETF recovery track: {nearest_candidate['asset_symbol']} "
                f"{nearest_candidate['setup_type']} is the current transition candidate. "
                f"{nearest_candidate['note']}"
            )
        else:
            overall_message = (
                f"Not ready yet. Closest candidate: {nearest_candidate['asset_kind'].upper()} {nearest_candidate['setup_type']} "
                f"with {nearest_candidate['live_sample_count']} live resolved and {nearest_candidate['pending_count']} pending outcomes."
            )
    else:
        overall_state = "warn"
        overall_message = "Not ready yet. No entry setup has enough live proof or pending evidence to justify unattended trust."

    return {
        "generated_at": datetime.utcnow(),
        "overall_state": overall_state,
        "overall_message": overall_message,
        "ready_setups_count": len(ready_rows),
        "building_live_count": len(building_live_rows),
        "replay_only_count": len(replay_only_rows),
        "nearest_candidate": nearest_candidate,
        "active_candidate": active_candidate,
        "recovery_candidate": recovery_candidate,
        "alerts": alerts,
    }


def _approval_focus_summary(
    setup_scorecards: dict,
    setup_walkforward: dict,
    pending_setups: dict,
    best_opportunity: dict | None = None,
) -> dict:
    def normalize_dt(value):
        if value is None or isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                return None
        return None

    scorecard_map = {
        (row["asset_kind"], row["setup_type"]): row
        for row in setup_scorecards.get("rows", [])
    }
    pending_map = {
        (row["asset_kind"], row["setup_type"], row["action"]): row
        for row in pending_setups.get("rows", [])
    }
    entry_rows = [
        row
        for row in setup_walkforward.get("rows", [])
        if not row["setup_type"].endswith("risk_off") and not row["setup_type"].endswith("watch")
    ]
    regime_transition = (best_opportunity or {}).get("regime_transition") or {}

    def build_gaps(row: dict, scorecard: dict | None, pending: dict | None) -> list[dict]:
        gaps: list[dict] = []
        sample_count = int(row.get("sample_count", 0) or 0)
        live_sample_count = int(row.get("live_sample_count", 0) or 0)
        test = row.get("test", {}) or {}
        train = row.get("train", {}) or {}
        test_expectancy = float(test.get("net_expectancy_pct", 0.0) or 0.0)
        test_win_rate = float(test.get("win_rate_pct", 0.0) or 0.0)
        test_edge = float(test.get("avg_decision_edge_pct", 0.0) or 0.0)
        test_drawdown = float(test.get("max_drawdown_pct", 0.0) or 0.0)
        train_expectancy = float(train.get("net_expectancy_pct", 0.0) or 0.0)
        scorecard_expectancy = float((scorecard or {}).get("net_expectancy_pct", 0.0) or 0.0)
        scorecard_win_rate = float((scorecard or {}).get("win_rate_pct", 0.0) or 0.0)
        false_positive_rate = float((scorecard or {}).get("false_positive_rate_pct", 0.0) or 0.0)
        pending_count = int((pending or {}).get("pending_count", 0) or 0)

        if scorecard is None:
            gaps.append(
                {
                    "label": "Scorecard evidence",
                    "status": "warn",
                    "detail": "No resolved scorecard row is available yet for this entry setup.",
                }
            )
        elif scorecard.get("approval_status") != "approved":
            if scorecard_expectancy < 0.15:
                gaps.append(
                    {
                        "label": "Scorecard expectancy",
                        "status": "warn",
                        "detail": f"Needs at least 0.15% net expectancy. Now {scorecard_expectancy:.2f}%.",
                    }
                )
            if scorecard_win_rate < 55.0:
                gaps.append(
                    {
                        "label": "Scorecard win rate",
                        "status": "warn",
                        "detail": f"Needs at least 55% win rate. Now {scorecard_win_rate:.0f}%.",
                    }
                )
            if false_positive_rate >= 35.0:
                gaps.append(
                    {
                        "label": "False positives",
                        "status": "warn",
                        "detail": f"Needs false positives below 35%. Now {false_positive_rate:.0f}%.",
                    }
                )

        if sample_count < 8:
            gaps.append(
                {
                    "label": "Walk-forward depth",
                    "status": "warn",
                    "detail": f"Needs at least 8 resolved rows across train/test. Now {sample_count}.",
                }
            )
        if train_expectancy < 0.15:
            gaps.append(
                {
                    "label": "Train expectancy",
                    "status": "warn",
                    "detail": f"Needs at least 0.15% in-sample expectancy. Now {train_expectancy:.2f}%.",
                }
            )
        if test_expectancy < 0.10:
            gaps.append(
                {
                    "label": "Test expectancy",
                    "status": "warn",
                    "detail": f"Needs at least 0.10% out-of-sample expectancy. Now {test_expectancy:.2f}%.",
                }
            )
        if test_win_rate < 50.0:
            gaps.append(
                {
                    "label": "Test win rate",
                    "status": "warn",
                    "detail": f"Needs at least 50% test win rate. Now {test_win_rate:.0f}%.",
                }
            )
        if test_edge < 0.05:
            gaps.append(
                {
                    "label": "Decision edge",
                    "status": "warn",
                    "detail": f"Needs at least 0.05% test decision edge. Now {test_edge:.2f}%.",
                }
            )
        if test_drawdown > 1.0:
            gaps.append(
                {
                    "label": "Test drawdown",
                    "status": "warn",
                    "detail": f"Needs max drawdown at or below 1.00%. Now {test_drawdown:.2f}%.",
                }
            )
        if live_sample_count < 4:
            gaps.append(
                {
                    "label": "Live proof",
                    "status": "warn",
                    "detail": f"Needs at least 4 live resolved outcomes. Now {live_sample_count}.",
                }
            )
        if pending_count > 0:
            gaps.append(
                {
                    "label": "Pending outcomes",
                    "status": "ok",
                    "detail": f"{pending_count} live outcomes are still open and can improve or weaken the case.",
                }
            )
        return gaps

    ranked_rows: list[tuple[tuple[int, int, float, float, float], dict, dict | None, dict | None]] = []
    for row in entry_rows:
        key = (row["asset_kind"], row["setup_type"])
        scorecard = scorecard_map.get(key)
        pending = pending_map.get((row["asset_kind"], row["setup_type"], "buy"))
        test = row.get("test", {}) or {}
        scorecard_status = (scorecard or {}).get("approval_status", "watch")
        walkforward_status = row.get("recommendation", "watch")
        live_status = row.get("live_proof_status", "research")
        gaps = build_gaps(row, scorecard, pending)
        warn_count = sum(1 for gap in gaps if gap["status"] == "warn")
        status_rank = {"approved": 0, "watch": 1, "disabled": 2}
        live_rank = {"cleared": 0, "building_live": 1, "research": 2, "replay_only": 3, "exit_only": 4}
        rank = (
            status_rank.get(walkforward_status, 9) + status_rank.get(scorecard_status, 9),
            warn_count,
            -float(test.get("net_expectancy_pct", -999.0) or -999.0),
            -float(test.get("avg_decision_edge_pct", -999.0) or -999.0),
            -float((scorecard or {}).get("net_expectancy_pct", -999.0) or -999.0),
        )
        ranked_rows.append((rank + (live_rank.get(live_status, 9),), row, scorecard, pending))

    if ranked_rows:
        _, target_row, target_scorecard, target_pending = sorted(ranked_rows, key=lambda item: item[0])[0]
        target_gaps = build_gaps(target_row, target_scorecard, target_pending)
        target_setup = target_row["setup_type"]
        target_asset_kind = target_row["asset_kind"]
        scorecard_status = (target_scorecard or {}).get("approval_status", "watch")
        walkforward_status = target_row.get("recommendation", "watch")
        live_proof_status = target_row.get("live_proof_status", "research")
        pending_count = int((target_pending or {}).get("pending_count", 0) or 0)
        next_due_label = (target_pending or {}).get("next_due_label", "none pending")
        latest_outcome_at = normalize_dt(target_row.get("latest_outcome_at"))
        evidence_status = "stale"
        evidence_message = "No fresh evidence is arriving yet for this target lane."
        if pending_count > 0:
            evidence_status = "building_live"
            evidence_message = (
                f"{pending_count} pending outcome window(s) are open now, so this lane is actively collecting fresh proof. "
                f"{next_due_label}."
            )
        elif latest_outcome_at:
            age_hours = max((datetime.utcnow() - latest_outcome_at).total_seconds() / 3600, 0.0)
            if age_hours <= 6:
                evidence_status = "building_live"
                evidence_message = f"Fresh resolved evidence landed recently, about {age_hours:.1f}h ago."
            elif age_hours <= 24:
                evidence_status = "watch"
                evidence_message = f"Recent evidence exists, but nothing new has resolved for about {age_hours:.1f}h."
            else:
                evidence_status = "warn"
                evidence_message = f"No new resolved evidence has arrived for about {age_hours:.1f}h."
        return {
            "generated_at": datetime.utcnow(),
            "objective": "Get the first truly approved entry lane.",
            "state": "watch" if walkforward_status != "approved" else "ok",
            "headline": f"Primary approval target: {target_asset_kind.upper()} {target_setup}",
            "message": (
                f"This is the nearest real entry lane to unattended approval right now. "
                f"Scorecard {scorecard_status}, walk-forward {walkforward_status}, live proof {live_proof_status}."
            ),
            "target_setup": target_setup,
            "target_asset_kind": target_asset_kind,
            "scorecard_status": scorecard_status,
            "walkforward_status": walkforward_status,
            "live_proof_status": live_proof_status,
            "pending_count": pending_count,
            "next_due_label": next_due_label,
            "latest_outcome_at": latest_outcome_at,
            "evidence_status": evidence_status,
            "evidence_message": evidence_message,
            "gaps": target_gaps[:6],
        }

    if regime_transition:
        candidate = regime_transition.get("candidate") or {}
        return {
            "generated_at": datetime.utcnow(),
            "objective": "Get the first truly approved entry lane.",
            "state": "warn",
            "headline": f"Market regime is blocking the next entry lane",
            "message": regime_transition.get("message", "No approval target is available yet."),
            "target_setup": candidate.get("setup_type"),
            "target_asset_kind": candidate.get("asset_kind"),
            "scorecard_status": None,
            "walkforward_status": candidate.get("recommendation"),
            "live_proof_status": candidate.get("live_proof_status"),
            "pending_count": candidate.get("pending_count", 0),
            "next_due_label": candidate.get("next_due_label"),
            "latest_outcome_at": None,
            "evidence_status": "warn",
            "evidence_message": "The lane is still waiting for a better market regime before fresh entry proof can accumulate.",
            "gaps": [
                {
                    "label": "Regime",
                    "status": "warn",
                    "detail": "A defensive market regime is still preventing clean entry proof collection.",
                },
                {
                    "label": "Leadership",
                    "status": "warn",
                    "detail": "The next requirement is a real leader or pullback pattern, not another defensive hold signal.",
                },
            ],
        }

    return {
        "generated_at": datetime.utcnow(),
        "objective": "Get the first truly approved entry lane.",
        "state": "warn",
        "headline": "No entry lane is close enough to promote yet",
        "message": "The engine still lacks a viable entry setup with enough walk-forward and live proof to focus promotion effort cleanly.",
        "target_setup": None,
        "target_asset_kind": None,
        "scorecard_status": None,
        "walkforward_status": None,
        "live_proof_status": None,
        "pending_count": 0,
        "next_due_label": None,
        "latest_outcome_at": None,
        "evidence_status": "warn",
        "evidence_message": "No focused entry lane is receiving meaningful new proof yet.",
        "gaps": [],
    }


def _next_proof_target(
    live_proof_status: str,
    recommendation: str,
    eligible_for_unattended: bool,
    pending_count: int,
    live_sample_count: int,
) -> str:
    if eligible_for_unattended:
        return "approved"
    if live_proof_status == "replay_only":
        return "building_live" if pending_count > 0 else "first live proof"
    if live_proof_status == "research":
        if live_sample_count > 0 or pending_count > 0:
            return "strengthen live proof"
        return "first live proof"
    if live_proof_status == "building_live":
        if live_sample_count == 0:
            return "first live proof"
        if live_sample_count < 2:
            return "strengthen live proof"
        if pending_count > 0:
            return "watch"
        return "strengthen live proof"
    if recommendation == "watch":
        return "approved"
    return "watch"


def _next_due_label(rows: list[SignalOutcomeSnapshot], horizon_hours: int) -> str:
    if not rows:
        return "none pending"
    due_times = [
        row.signal.created_at.timestamp() + (horizon_hours * 3600)
        for row in rows
        if row.signal is not None
    ]
    if not due_times:
        return "awaiting data"
    next_due_ts = min(due_times)
    remaining_seconds = max(int(next_due_ts - datetime.utcnow().timestamp()), 0)
    if remaining_seconds >= 3600:
        return f"next in {round(remaining_seconds / 3600)}h"
    if remaining_seconds >= 60:
        return f"next in {round(remaining_seconds / 60)}m"
    return f"next in {remaining_seconds}s"


def _provider_warnings(engine_runs: list[EngineRun], latest_market: list[dict], trades: list[Trade]) -> list[dict]:
    warnings: list[dict] = []
    recent_failures = [run for run in engine_runs[:5] if run.status.lower() != "ok"]
    for run in recent_failures:
        warnings.append(
            {
                "severity": "danger",
                "title": "Engine run failed",
                "message": f"{run.completed_at.strftime('%H:%M:%S UTC')} - {run.message}",
            }
        )

    for row in latest_market:
        if row["freshness"] == "missing":
            warnings.append(
                {
                    "severity": "danger",
                    "title": f"{row['symbol']} quote missing",
                    "message": f"No market tick stored yet for {row['symbol']}. Provider path cannot be trusted for execution.",
                }
            )
        elif row["freshness"] == "stale":
            warnings.append(
                {
                    "severity": "warn",
                    "title": f"{row['symbol']} quote stale",
                    "message": (
                        f"Last quote from {row['source']} is {_human_age(row['age_seconds'])} old, beyond the "
                        f"{settings.max_tick_age_seconds // 60} min freshness guard."
                    ),
                }
            )

    stale_skips = [
        trade
        for trade in trades
        if trade.status.value == "skipped" and "stale" in trade.reason.lower()
    ][:3]
    for trade in stale_skips:
        warnings.append(
            {
                "severity": "warn",
                "title": f"{trade.asset.symbol} execution skipped",
                "message": f"{trade.executed_at.strftime('%H:%M:%S UTC')} - {trade.reason}",
            }
        )

    return warnings[:8]


def _trade_story(trades: list[Trade]) -> list[dict]:
    stream: list[dict] = []
    pending_market_closed: list[Trade] = []

    def flush_market_closed_bucket() -> None:
        if not pending_market_closed:
            return
        latest = pending_market_closed[0]
        symbols = [trade.asset.symbol for trade in pending_market_closed if trade.asset]
        unique_symbols = list(dict.fromkeys(symbols))
        stream.append(
            {
                "time": latest.executed_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "asset_symbol": ", ".join(unique_symbols[:4]),
                "side": "mixed",
                "status": "skipped",
                "headline": f"{len(unique_symbols)} US-market trade(s) skipped",
                "reason": "Skipped because the US market session is closed.",
                "notional_eur": None,
                "price": None,
                "meta": f"{latest.executed_at.strftime('%Y-%m-%d %H:%M:%S UTC')} · {', '.join(unique_symbols[:6])}",
            }
        )
        pending_market_closed.clear()

    for trade in trades[:18]:
        reason = (trade.reason or "").strip()
        if trade.status.value == "skipped" and reason == "Skipped because the US market session is closed.":
            pending_market_closed.append(trade)
            continue

        flush_market_closed_bucket()
        if trade.status.value == "filled" and trade.side.value == "buy":
            headline = f"Opened {trade.asset.symbol}"
        elif trade.status.value == "filled" and trade.side.value == "sell":
            headline = f"Closed {trade.asset.symbol}"
        else:
            headline = f"{trade.asset.symbol} {trade.side.value} skipped"

        stream.append(
            {
                "time": trade.executed_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "asset_symbol": trade.asset.symbol,
                "side": trade.side.value,
                "status": trade.status.value,
                "headline": headline,
                "reason": trade.reason,
                "notional_eur": trade.notional_eur,
                "price": trade.price,
                "meta": f"{trade.executed_at.strftime('%Y-%m-%d %H:%M:%S UTC')} · {trade.side.value.upper()} · EUR {trade.price:.2f}",
            }
        )
    flush_market_closed_bucket()
    return stream[:10]


def _compact_state_events(events: list, limit: int = 10) -> list[dict]:
    compacted: list[dict] = []
    for event in events:
        fingerprint = (event.title, event.message, event.severity, event.category)
        current = compacted[-1] if compacted else None
        if current and current["_fingerprint"] == fingerprint:
            current["count"] += 1
            continue
        compacted.append(
            {
                "title": event.title,
                "message": event.message,
                "severity": event.severity,
                "category": event.category,
                "created_at": event.created_at,
                "count": 1,
                "_fingerprint": fingerprint,
            }
        )
    return compacted[:limit]


def _human_age(age_seconds: int | None) -> str:
    if age_seconds is None:
        return "unknown age"
    if age_seconds < 60:
        return f"{age_seconds}s"
    minutes, seconds = divmod(age_seconds, 60)
    if minutes < 60:
        return f"{minutes}m {seconds}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def _simulation_plan(active_simulation: StrategySimulation | None) -> dict | None:
    if not active_simulation:
        return None

    effective_stop = max(active_simulation.stop_price, active_simulation.trailing_stop_price)
    distance_to_stop_pct = ((active_simulation.latest_price / effective_stop) - 1) * 100 if effective_stop else 0.0
    distance_to_target_pct = ((active_simulation.take_profit_price / active_simulation.latest_price) - 1) * 100 if active_simulation.latest_price else 0.0

    if active_simulation.latest_price <= effective_stop:
        next_action = "Sell on the next scan because the protective stop has been hit."
    elif active_simulation.latest_price >= active_simulation.take_profit_price:
        next_action = "Sell on the next scan because the take-profit target has been reached."
    elif active_simulation.pnl_pct > 0:
        next_action = "Hold for now and keep raising the trailing stop while price stays favorable."
    else:
        next_action = "Hold for now and wait for either a rebound, a stop trigger, or a stronger new setup."

    return {
        "why_bought": active_simulation.opened_reason,
        "why_sell": (
            f"The simulation will exit if price falls to the active stop around EUR {effective_stop:.4f} "
            f"or rises to the take-profit target at EUR {active_simulation.take_profit_price:.4f}."
        ),
        "next_action": next_action,
        "distance_to_stop_pct": round(distance_to_stop_pct, 2),
        "distance_to_target_pct": round(distance_to_target_pct, 2),
    }


def _simulation_trigger_status(active_simulation: StrategySimulation | None, best_opportunity: dict, autopilot_status: dict) -> dict:
    if active_simulation:
        return {
            "state": "active",
            "headline": f"Simulation is running on {active_simulation.asset.symbol}.",
            "detail": active_simulation.opened_reason,
        }

    if not settings.simulation_enabled:
        return {
            "state": "disabled",
            "headline": "Automatic simulation is disabled.",
            "detail": "Turn SIMULATION_ENABLED back on to let the worker auto-start the next approved best-asset run.",
        }

    if autopilot_status["state"] != "ready":
        reason = autopilot_status["reasons"][0] if autopilot_status["reasons"] else "Autopilot guard is paused."
        return {
            "state": "warn",
            "headline": "Simulation trigger is armed but currently paused by guardrails.",
            "detail": reason,
        }

    best = best_opportunity.get("best")
    best_eligible = best_opportunity.get("best_eligible")
    best_building_live = best_opportunity.get("best_building_live")
    if best_eligible:
        return {
            "state": "ready",
            "headline": f"Simulation trigger is armed for {best_eligible['symbol']}.",
            "detail": f"The worker will auto-open the next best approved {best_eligible['asset_kind']} setup on its next cycle.",
        }
    if best_building_live:
        return {
            "state": "watch",
            "headline": f"Simulation trigger is tracking {best_building_live['symbol']}.",
            "detail": (
                f"{best_building_live['setup_type']} is currently the strongest cross-asset setup still building live proof. "
                f"Walk-forward is {best_building_live['walkforward_recommendation']} and live-proof is {best_building_live['live_proof_status']}."
            ),
        }
    if best:
        blocked_reason = best.get("blocked_reason") or "The current top setup is not yet eligible."
        return {
            "state": "watch",
            "headline": f"Simulation trigger is armed and waiting on {best['symbol']}.",
            "detail": blocked_reason,
        }
    return {
        "state": "watch",
        "headline": "Simulation trigger is armed and waiting for a fresh approved BUY.",
        "detail": "The worker is scanning crypto, ETF, and stock lanes every cycle, but no current setup is eligible yet.",
    }


def _launch_readiness_summary(
    *,
    latest_engine_run: EngineRun | None,
    provider_health: dict,
    setup_monitor: dict,
    approval_focus: dict,
    reconciliation_status,
    broker_status,
    risk_snapshot: dict,
    autopilot_status: dict,
) -> dict:
    gates: list[dict] = []

    def add_gate(
        key: str,
        title: str,
        status: str,
        summary: str,
        detail: str,
        next_step: str,
    ) -> None:
        gates.append(
            {
                "key": key,
                "title": title,
                "status": status,
                "summary": summary,
                "detail": detail,
                "next_step": next_step,
            }
        )

    ready_setups = int(setup_monitor.get("ready_setups_count", 0) or 0)
    building_live = int(setup_monitor.get("building_live_count", 0) or 0)
    pending_count = int(approval_focus.get("pending_count", 0) or 0)
    live_proof_status = (approval_focus.get("live_proof_status") or "").lower()
    evidence_status = (approval_focus.get("evidence_status") or "").lower()
    latest_by_kind = provider_health.get("latest_by_kind", {})
    relevant_kinds = sorted(settings.tradeable_asset_kinds | settings.simulation_asset_kinds)
    coverage = autopilot_status.get("coverage", {})
    min_coverage_pct = settings.min_data_coverage_ratio * 100

    if ready_setups > 0:
        add_gate(
            "strategy_proof",
            "Strategy proof",
            "ready",
            f"{ready_setups} lane(s) already cleared the proof gates.",
            "At least one setup has enough scorecard and walk-forward evidence to be considered for unattended paper deployment.",
            "Keep monitoring outcome quality and protect the approved lane from regression.",
        )
    elif building_live > 0 or approval_focus.get("target_setup"):
        add_gate(
            "strategy_proof",
            "Strategy proof",
            "watch",
            "The board has a nearest candidate, but it is not approved yet.",
            approval_focus.get("headline") or "A candidate lane exists, but it still needs stronger proof before promotion.",
            "Accumulate more resolved outcomes and improve expectancy until one entry lane moves from watch to approved.",
        )
    else:
        add_gate(
            "strategy_proof",
            "Strategy proof",
            "disabled",
            "No entry lane is close to approval right now.",
            "The strategy board does not currently show a near-term candidate that is close to unattended readiness.",
            "Focus the system on one lane and keep collecting cleaner resolved outcomes until a real candidate emerges.",
        )

    if live_proof_status in {"ready", "approved"}:
        add_gate(
            "live_evidence",
            "Live evidence",
            "ready",
            "The active candidate has enough fresh live proof.",
            approval_focus.get("evidence_message") or "Fresh live outcomes are flowing and the current candidate has passed the live-proof gate.",
            "Continue validating that live behavior remains stable across more market regimes.",
        )
    elif evidence_status == "building_live" or pending_count > 0:
        add_gate(
            "live_evidence",
            "Live evidence",
            "watch",
            f"{pending_count} outcome window(s) are still resolving.",
            approval_focus.get("evidence_message") or "The app is still waiting for open outcome windows to resolve before the lane can earn live approval.",
            "Leave the VM running continuously so pending outcome windows can resolve into fresh live proof.",
        )
    else:
        add_gate(
            "live_evidence",
            "Live evidence",
            "disabled",
            "No candidate currently has live proof in flight.",
            "The focused lane has neither approved live proof nor an active stream of pending outcomes building toward approval.",
            "Generate fresh signals in the focus lane and keep the worker online long enough to convert them into resolved evidence.",
        )

    provider_problems: list[str] = []
    weak_coverage: list[str] = []
    for kind in relevant_kinds:
        kind_coverage = float(coverage.get(kind, 0.0) or 0.0)
        sample = latest_by_kind.get(kind)
        if kind_coverage < min_coverage_pct:
            weak_coverage.append(f"{kind} coverage {kind_coverage:.0f}%")
        if sample and sample.status != "ok" and not (sample.cache_used and kind_coverage >= min_coverage_pct):
            provider_problems.append(f"{kind} provider {sample.status}")
        elif not sample:
            provider_problems.append(f"{kind} provider unknown")

    if not provider_problems and not weak_coverage:
        add_gate(
            "provider_reliability",
            "Provider reliability",
            "ready",
            "All active universes have clean provider health and full usable coverage.",
            "Quotes are arriving from the preferred provider path without stale-coverage issues across the configured trading and simulation universes.",
            "Keep this path stable and add alerting before any future provider changes.",
        )
    elif provider_problems:
        add_gate(
            "provider_reliability",
            "Provider reliability",
            "disabled",
            "A critical provider path is unhealthy.",
            "; ".join(provider_problems + weak_coverage) if weak_coverage else "; ".join(provider_problems),
            "Fix the failing provider path or reduce dependence on it before trusting unattended deployment.",
        )
    else:
        add_gate(
            "provider_reliability",
            "Provider reliability",
            "watch",
            "Providers are up, but usable market-data coverage is still thinner than policy allows.",
            "; ".join(weak_coverage),
            "Improve fresh quote coverage until every active universe stays at or above the configured minimum.",
        )

    if reconciliation_status.status == "ok" and reconciliation_status.pending_intents == 0 and reconciliation_status.failed_intents == 0:
        add_gate(
            "execution_safety",
            "Execution safety",
            "ready",
            "Ledger and execution plumbing are reconciled.",
            reconciliation_status.message,
            "Keep reconciliation checks green and investigate every mismatch immediately.",
        )
    elif reconciliation_status.status == "blocked" or reconciliation_status.failed_intents > 0:
        add_gate(
            "execution_safety",
            "Execution safety",
            "disabled",
            "Execution controls are not clean enough for trustable unattended use.",
            reconciliation_status.message,
            "Clear broker or ledger mismatches and remove failed intents before promoting the platform.",
        )
    else:
        add_gate(
            "execution_safety",
            "Execution safety",
            "watch",
            "Execution is mostly healthy, but there is still operational debt to clear.",
            reconciliation_status.message,
            "Wait for pending intents to settle and return reconciliation status to a clean ok state.",
        )

    interval_seconds = max(settings.worker_interval_seconds, 1)
    if latest_engine_run:
        age_seconds = max(int((datetime.utcnow() - latest_engine_run.completed_at).total_seconds()), 0)
        recent_enough = age_seconds <= max(interval_seconds * 2, 600)
    else:
        age_seconds = None
        recent_enough = False

    if latest_engine_run and latest_engine_run.status == "ok" and recent_enough:
        add_gate(
            "ops_health",
            "Ops health",
            "ready",
            "The engine is cycling normally on the VM.",
            f"Last engine cycle completed successfully at {latest_engine_run.completed_at.strftime('%Y-%m-%d %H:%M:%S UTC')}.",
            "Keep the stack supervised and add basic uptime + restart alerting around the worker and database.",
        )
    elif latest_engine_run and latest_engine_run.status != "ok":
        add_gate(
            "ops_health",
            "Ops health",
            "disabled",
            "The latest engine cycle failed.",
            latest_engine_run.message or "Engine cycle failed without a detailed message.",
            "Fix the worker/runtime failure before treating this VM as trustable for low-attention use.",
        )
    else:
        lag_note = (
            f"Last engine cycle is stale by about {round(age_seconds / 60)} min."
            if age_seconds is not None
            else "No engine cycle has been recorded yet."
        )
        add_gate(
            "ops_health",
            "Ops health",
            "watch",
            "The runtime is up, but recency is not yet convincing.",
            lag_note,
            "Keep the worker running continuously and verify recent successful engine cycles over time.",
        )

    drawdown_lock_active = bool(risk_snapshot.get("drawdown_lock_active"))
    drawdown_pct = float(risk_snapshot.get("drawdown_pct", 0.0) or 0.0)
    if drawdown_lock_active:
        add_gate(
            "capital_protection",
            "Capital protection",
            "disabled",
            "The drawdown lock is active.",
            (
                f"Current drawdown is {drawdown_pct:.2f}% and the portfolio protection layer has already locked new exposure."
            ),
            "Recover from the drawdown lock and keep risk controls green before adding unattended exposure.",
        )
    elif autopilot_status.get("state") == "ready":
        add_gate(
            "capital_protection",
            "Capital protection",
            "ready",
            "Risk guardrails currently allow autonomous paper entries.",
            autopilot_status.get("reasons", ["All guardrails passed."])[0],
            "Preserve these guardrails and keep position sizing conservative while proof is still maturing.",
        )
    else:
        add_gate(
            "capital_protection",
            "Capital protection",
            "watch",
            "Guardrails are doing their job, but they are still pausing new exposure.",
            autopilot_status.get("reasons", ["Autopilot is currently paused."])[0],
            "Clear the current guardrail blockers so the app can take approved entries without manual babysitting.",
        )

    broker_connected = bool(getattr(broker_status, "connected", False))
    live_guard_ok = settings.broker_mode != "live" or settings.broker_live_confirmed
    real_money_ready = (
        bool(getattr(broker_status, "enabled", False))
        and settings.broker_execution_target == "broker"
        and settings.broker_mode == "live"
        and settings.broker_live_confirmed
        and not settings.live_emergency_stop
        and settings.live_runbook_acknowledged
        and settings.live_alerts_configured
        and broker_connected
        and ready_setups > 0
        and not drawdown_lock_active
    )
    if real_money_ready:
        add_gate(
            "real_money",
            "Real-money eligibility",
            "ready",
            "The structure for real-money deployment is in place.",
            "Broker execution is enabled, live mode is explicitly confirmed, a lane is approved, and the risk lock is clear.",
            "Move to tiny-size capital only after a deliberate final review of fills, monitoring, and rollback handling.",
        )
    elif ready_setups > 0 and broker_connected and live_guard_ok:
        add_gate(
            "real_money",
            "Real-money eligibility",
            "watch",
            "The platform is structurally close, but not yet cleared for real capital.",
            (
                f"Broker mode={settings.broker_mode}, execution_target={settings.broker_execution_target}, "
                f"approved_lanes={ready_setups}, live_confirmed={settings.broker_live_confirmed}, "
                f"emergency_stop={settings.live_emergency_stop}, runbook_ack={settings.live_runbook_acknowledged}, "
                f"alerts_configured={settings.live_alerts_configured}."
            ),
            "Keep using paper mode until the approved lane remains stable and you explicitly switch into broker live execution.",
        )
    else:
        add_gate(
            "real_money",
            "Real-money eligibility",
            "disabled",
            "Real-money deployment is intentionally blocked.",
            (
                f"Broker connected={broker_connected}, execution_target={settings.broker_execution_target}, "
                f"mode={settings.broker_mode}, approved_lanes={ready_setups}."
            ),
            "Do not deploy real money until a lane is approved and the broker path is deliberately configured for live execution.",
        )

    approved_gates = len([gate for gate in gates if gate["status"] == "ready"])
    watch_gates = len([gate for gate in gates if gate["status"] == "watch"])
    blocked_gates = len([gate for gate in gates if gate["status"] == "disabled"])
    can_deploy_low_attention = ready_setups > 0 and blocked_gates == 0
    can_deploy_real_money = any(gate["key"] == "real_money" and gate["status"] == "ready" for gate in gates)

    if blocked_gates == 0 and watch_gates == 0:
        overall_state = "ready"
        current_tier = "live-capable" if can_deploy_real_money else "paper-on-vm"
        overall_message = (
            "All launch gates are green. The platform is structurally ready for low-attention operation, "
            "with real-money eligibility controlled separately by the broker gate."
        )
    elif blocked_gates == 0:
        overall_state = "watch"
        current_tier = "paper-on-vm"
        overall_message = (
            "The VM is usable for continuous paper trading, but at least one gate still needs more proof before this is trustable for unattended capital."
        )
    else:
        overall_state = "disabled"
        current_tier = "guarded-paper"
        overall_message = (
            "At least one critical gate is red, so the platform should stay in guarded paper mode until the blockers are removed."
        )

    next_unlock = next((gate["next_step"] for gate in gates if gate["status"] != "ready"), None)
    return {
        "generated_at": datetime.utcnow(),
        "objective": "Turn the VM system into a trustable low-attention investing platform.",
        "overall_state": overall_state,
        "overall_message": overall_message,
        "current_tier": current_tier,
        "approved_gates": approved_gates,
        "watch_gates": watch_gates,
        "blocked_gates": blocked_gates,
        "can_deploy_low_attention": can_deploy_low_attention,
        "can_deploy_real_money": can_deploy_real_money,
        "next_unlock": next_unlock,
        "gates": gates,
    }


def _live_deployment_readiness(*, launch_readiness: dict, broker_status, reconciliation_status) -> dict:
    checks: list[dict] = []

    def add_check(key: str, title: str, passed: bool, detail: str) -> None:
        checks.append(
            {
                "key": key,
                "title": title,
                "status": "ready" if passed else "disabled",
                "detail": detail,
            }
        )

    add_check(
        "approved_lane",
        "Approved entry lane",
        bool(launch_readiness.get("can_deploy_low_attention")),
        (
            "At least one lane must be approved for unattended paper use before real capital is even considered."
            if not launch_readiness.get("can_deploy_low_attention")
            else "A lane is approved for low-attention paper use."
        ),
    )
    add_check(
        "broker_connected",
        "Broker connected",
        bool(getattr(broker_status, "connected", False)),
        broker_status.message,
    )
    add_check(
        "execution_target_live",
        "Execution target switched to broker live",
        settings.broker_execution_target == "broker" and settings.broker_mode == "live",
        f"Current target={settings.broker_execution_target}, mode={settings.broker_mode}.",
    )
    add_check(
        "live_confirmed",
        "Explicit live confirmation",
        settings.broker_live_confirmed,
        "BROKER_LIVE_CONFIRMED must stay false until you intentionally approve first-capital deployment.",
    )
    add_check(
        "emergency_stop_released",
        "Emergency stop released",
        not settings.live_emergency_stop,
        "LIVE_EMERGENCY_STOP should stay true until the exact moment you intentionally allow live order submission.",
    )
    add_check(
        "runbook_acknowledged",
        "Runbook acknowledged",
        settings.live_runbook_acknowledged,
        "Require an explicit operator acknowledgement that the live runbook, rollback plan, and first-size limits were reviewed.",
    )
    add_check(
        "alerts_configured",
        "Alerts configured",
        settings.live_alerts_configured,
        "Phone/email alerts for fills, failures, and worker downtime should be configured before first live euro.",
    )
    add_check(
        "reconciliation_clean",
        "Reconciliation clean",
        reconciliation_status.status == "ok" and reconciliation_status.pending_intents == 0 and reconciliation_status.failed_intents == 0,
        reconciliation_status.message,
    )

    checks_passed = len([item for item in checks if item["status"] == "ready"])
    checks_total = len(checks)
    live_mode_enabled = settings.broker_execution_target == "broker" and settings.broker_mode == "live"
    emergency_stop_active = settings.live_emergency_stop
    overall_state = "ready" if checks_passed == checks_total else "disabled"
    overall_message = (
        "Live deployment checklist is fully green."
        if overall_state == "ready"
        else "Live deployment is still blocked by design. Keep the emergency stop active until every checklist item is green."
    )
    next_step = next((item["detail"] for item in checks if item["status"] != "ready"), None)
    return {
        "generated_at": datetime.utcnow(),
        "overall_state": overall_state,
        "overall_message": overall_message,
        "live_mode_enabled": live_mode_enabled,
        "emergency_stop_active": emergency_stop_active,
        "checks_passed": checks_passed,
        "checks_total": checks_total,
        "next_step": next_step,
        "checks": checks,
    }


def _operator_alert_policy() -> dict:
    status = build_operator_alerts().status()
    coverage = [
        "worker failure -> webhook event worker_failure",
        "trade fill -> webhook event trade_fill",
        "trade rejection -> webhook event trade_rejection",
    ]
    return {
        "generated_at": datetime.utcnow(),
        "configured": status.configured,
        "webhook_enabled": status.webhook_enabled,
        "transport": status.transport,
        "supported_transports": status.supported_transports,
        "events": status.events,
        "coverage": coverage,
        "message": status.message,
    }


def _go_live_runbook() -> dict:
    first_capital_eur = min(settings.max_notional_per_trade_eur, 25.0)
    return {
        "generated_at": datetime.utcnow(),
        "title": "Tiny live-capital go-live runbook",
        "objective": "Move from guarded paper into the smallest safe live deployment without releasing the whole system at once.",
        "first_capital_eur": round(first_capital_eur, 2),
        "max_positions": 1,
        "max_daily_loss_eur": round(min(settings.max_daily_loss_eur, max(first_capital_eur * 0.2, 5.0)), 2),
        "emergency_stop_active": settings.live_emergency_stop,
        "env_changes": [
            {"name": "BROKER_PROVIDER", "current": settings.broker_provider, "target": "alpaca"},
            {"name": "BROKER_ENABLED", "current": str(settings.broker_enabled).lower(), "target": "true"},
            {"name": "BROKER_EXECUTION_TARGET", "current": settings.broker_execution_target, "target": "broker"},
            {"name": "BROKER_MODE", "current": settings.broker_mode, "target": "live"},
            {"name": "BROKER_LIVE_CONFIRMED", "current": str(settings.broker_live_confirmed).lower(), "target": "true"},
            {"name": "LIVE_RUNBOOK_ACKNOWLEDGED", "current": str(settings.live_runbook_acknowledged).lower(), "target": "true"},
            {"name": "LIVE_ALERTS_CONFIGURED", "current": str(settings.live_alerts_configured).lower(), "target": "true"},
            {"name": "OPERATOR_ALERT_TRANSPORT", "current": settings.operator_alert_transport, "target": "telegram or another configured transport"},
            {"name": "LIVE_EMERGENCY_STOP", "current": str(settings.live_emergency_stop).lower(), "target": "false only at final release moment"},
            {"name": "MAX_OPEN_POSITIONS", "current": str(settings.max_open_positions), "target": "1"},
            {"name": "MAX_NOTIONAL_PER_TRADE_EUR", "current": str(settings.max_notional_per_trade_eur), "target": f"{first_capital_eur:.2f}"},
        ],
        "preflight_steps": [
            "Verify one entry lane is approved and stays stable for multiple worker cycles.",
            "Confirm broker connectivity, reconciliation clean state, and zero failed intents.",
            "Set a real operator webhook URL and validate worker_failure, trade_fill, and trade_rejection test deliveries.",
            "Keep LIVE_EMERGENCY_STOP=true while switching the rest of the live env flags into place.",
            "Restart the stack and confirm the dashboard still shows live deployment blocked only by the emergency stop.",
        ],
        "first_day_rules": [
            f"Start with no more than EUR {first_capital_eur:.2f} notional on the first live entry.",
            "Allow only one live position at a time for the first session.",
            "Watch the first fill, stop, and reconciliation cycle manually before leaving the system alone.",
            "If any rejection, mismatch, stale-data breach, or worker error occurs, stop immediately and return to paper mode.",
        ],
        "rollback_steps": [
            "Set LIVE_EMERGENCY_STOP=true immediately.",
            "Set BROKER_EXECUTION_TARGET=internal and BROKER_MODE=paper.",
            "Set BROKER_LIVE_CONFIRMED=false.",
            "Restart api and worker, then confirm the live deployment checklist is red again and broker live mode is off.",
            "Review the latest execution intents, broker orders, reconciliation snapshot, and worker logs before attempting another live session.",
        ],
    }


def _engine_timing(last_engine_at: datetime | None) -> dict:
    interval_seconds = settings.worker_interval_seconds
    if not last_engine_at:
        return {
            "last_decision_at": "No engine cycle yet.",
            "next_scan_in": f"about {max(round(interval_seconds / 60), 1)} min",
        }

    elapsed_seconds = max(int((datetime.utcnow() - last_engine_at).total_seconds()), 0)
    remaining_seconds = max(interval_seconds - elapsed_seconds, 0)
    if remaining_seconds >= 60:
        next_scan = f"about {round(remaining_seconds / 60)} min"
    else:
        next_scan = f"about {remaining_seconds} sec"

    return {
        "last_decision_at": last_engine_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "next_scan_in": next_scan,
    }


def _execution_guardrails(latest_engine_run: EngineRun | None, autopilot_status: dict, risk_snapshot: dict) -> dict:
    return {
        "trading_enabled": settings.trading_enabled,
        "simulation_enabled": settings.simulation_enabled,
        "tradeable_asset_kinds": sorted(settings.tradeable_asset_kinds),
        "simulation_asset_kinds": sorted(settings.simulation_asset_kinds),
        "min_data_coverage_ratio_pct": round(settings.min_data_coverage_ratio * 100, 0),
        "halt_on_provider_warnings": settings.halt_on_provider_warnings,
        "halt_on_stale_quotes": settings.halt_on_stale_quotes,
        "autopilot_state": autopilot_status["state"],
        "autopilot_reasons": autopilot_status["reasons"],
        "market_regime": autopilot_status.get("market_regime"),
        "max_tick_age_seconds": settings.max_tick_age_seconds,
        "min_minutes_between_trades": settings.min_minutes_between_trades,
        "max_gross_exposure_pct": round(settings.max_gross_exposure_pct * 100, 2),
        "max_symbol_exposure_pct": round(settings.max_symbol_exposure_pct * 100, 2),
        "max_portfolio_drawdown_pct": round(settings.max_portfolio_drawdown_pct, 2),
        "liquidate_on_drawdown_breach": settings.liquidate_on_drawdown_breach,
        "asset_kind_exposure_limits": risk_snapshot["asset_kind_exposure_limits"],
        "risk_snapshot": risk_snapshot,
        "last_engine_status": latest_engine_run.status if latest_engine_run else "unknown",
        "last_engine_completed_at": latest_engine_run.completed_at.strftime("%Y-%m-%d %H:%M:%S UTC") if latest_engine_run else "n/a",
        "last_engine_message": latest_engine_run.message if latest_engine_run else "No engine run recorded yet.",
    }


def _autopilot_status(signals: list[Signal], latest_market: list[dict], provider_health: dict, risk_snapshot: dict) -> dict:
    relevant_kinds = settings.tradeable_asset_kinds | settings.simulation_asset_kinds
    reasons: list[str] = []
    coverage: dict[str, float] = {}
    latest_by_kind = provider_health.get("latest_by_kind", {})
    market_regime = _market_regime(signals)

    for kind in sorted(relevant_kinds):
        rows = [row for row in latest_market if row["kind"] == kind]
        if not rows:
            coverage[kind] = 0.0
            reasons.append(f"{kind} has no tracked rows in the current market view")
            continue

        usable_rows = [row for row in rows if row["freshness"] in {"fresh", "recent"}]
        coverage[kind] = round((len(usable_rows) / len(rows)) * 100, 0)
        if coverage[kind] < settings.min_data_coverage_ratio * 100:
            reasons.append(
                f"{kind} usable quote coverage is {coverage[kind]:.0f}% "
                f"(min {settings.min_data_coverage_ratio * 100:.0f}%)"
            )

        if settings.halt_on_stale_quotes:
            stale_count = len([row for row in rows if row["freshness"] in {"stale", "missing"}])
            if stale_count:
                reasons.append(f"{kind} has {stale_count} stale or missing quote(s)")

        sample = latest_by_kind.get(kind)
        if (
            settings.halt_on_provider_warnings
            and sample
            and sample.status != "ok"
            and not (sample.cache_used and coverage[kind] >= settings.min_data_coverage_ratio * 100)
        ):
            reasons.append(f"{kind} provider reports {sample.status}")

    if risk_snapshot.get("drawdown_lock_active"):
        reasons.append(
            f"portfolio drawdown lock is active at {risk_snapshot['drawdown_pct']:.2f}% "
            f"(limit {risk_snapshot['max_portfolio_drawdown_pct']:.2f}%)"
        )
    if market_regime["state"] == "risk_off":
        reasons.append(market_regime["message"])

    return {
        "state": "paused" if reasons else "ready",
        "reasons": reasons or ["All configured universes passed freshness and provider-health checks."],
        "coverage": coverage,
        "market_regime": market_regime,
    }


def _latest_signals(db: Session, limit: int = 20) -> list[Signal]:
    rows = db.scalars(
        select(Signal)
        .options(joinedload(Signal.asset))
        .order_by(Signal.created_at.desc())
        .limit(max(limit * 8, 40))
    ).all()
    unique_rows: list[Signal] = []
    seen_asset_ids: set[int] = set()
    for row in rows:
        if not row.asset or row.asset_id in seen_asset_ids:
            continue
        seen_asset_ids.add(row.asset_id)
        unique_rows.append(row)
        if len(unique_rows) >= limit:
            break
    return unique_rows


def _market_regime(signals: list[Signal]) -> dict:
    if not signals:
        return {
            "state": "unknown",
            "message": "No recent signals yet to classify the market regime.",
            "kind_states": {},
        }

    per_kind: dict[str, dict] = {}
    for kind in sorted(settings.tradeable_asset_kinds | settings.simulation_asset_kinds):
        kind_rows = [signal for signal in signals if signal.asset and signal.asset.kind.value == kind]
        if not kind_rows:
            continue
        avg_momentum = round(sum(signal.momentum_score for signal in kind_rows) / len(kind_rows), 4)
        avg_score = round(sum(signal.score for signal in kind_rows) / len(kind_rows), 4)
        sell_count = sum(1 for signal in kind_rows if signal.action == SignalAction.SELL)
        buy_count = sum(1 for signal in kind_rows if signal.action == SignalAction.BUY)
        hold_count = sum(1 for signal in kind_rows if signal.action == SignalAction.HOLD)
        state = "neutral"
        if kind == "etf":
            if avg_momentum <= -0.04 or sell_count >= max(1, len(kind_rows) - 1):
                state = "risk_off"
            elif buy_count >= 1 and avg_momentum >= 0.04:
                state = "risk_on"
        else:
            if avg_momentum <= -0.10 or sell_count >= max(1, len(kind_rows) // 2):
                state = "risk_off"
            elif buy_count >= 1 and avg_momentum >= 0.08:
                state = "risk_on"
        per_kind[kind] = {
            "state": state,
            "avg_momentum": avg_momentum,
            "avg_score": avg_score,
            "buy_count": buy_count,
            "hold_count": hold_count,
            "sell_count": sell_count,
            "sample_count": len(kind_rows),
        }

    risk_off_kinds = [kind for kind, row in per_kind.items() if row["state"] == "risk_off"]
    if len(risk_off_kinds) >= 2:
        return {
            "state": "risk_off",
            "message": (
                "Broad market regime is risk-off across "
                f"{', '.join(risk_off_kinds)}. Autopilot stays in capital-preservation mode until momentum improves."
            ),
            "kind_states": per_kind,
        }
    if any(row["state"] == "risk_on" for row in per_kind.values()):
        return {
            "state": "mixed",
            "message": "Cross-asset regime is mixed. The engine can rank setups, but broad confirmation is still incomplete.",
            "kind_states": per_kind,
        }
    return {
        "state": "neutral",
        "message": "Cross-asset regime is mixed-to-neutral. The engine is waiting for a cleaner directional edge.",
        "kind_states": per_kind,
    }


def _public_equity_connectors_status() -> dict:
    default = {
        "available": False,
        "onboarding_status": "unavailable",
        "automation_status": "unavailable",
        "summary": "Public Equity Investing plugin state is not available on this machine.",
        "items": [],
    }
    if not PUBLIC_EQUITY_STATE_PATH.exists():
        return default

    try:
        payload = json.loads(PUBLIC_EQUITY_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            **default,
            "summary": "Public Equity Investing plugin state exists but could not be read safely.",
        }

    connector_confirmation = payload.get("connector_confirmation") or {}
    automations = payload.get("automations") or {}
    label_map = {
        "company_filings_ir": "Filings and IR",
        "earnings_transcripts_presentations": "Transcripts and events",
        "internal_research": "Internal research",
        "portfolio_models_trackers": "Models and trackers",
        "market_data_estimates": "Market data and estimates",
    }

    items = []
    for key, label in label_map.items():
        route = connector_confirmation.get(key) or {}
        items.append(
            {
                "label": label,
                "status": route.get("status", "unconfigured"),
                "source_kind": route.get("source_kind", "none"),
                "provider": route.get("plugin_name") or route.get("plugin_id") or "Not set",
            }
        )

    active_count = sum(1 for item in items if item["status"] == "active")
    summary = f"{active_count}/{len(items)} research routes active in Codex session state."
    if automations.get("status") == "completed":
        summary += " Weekday watchlist brief is configured."

    return {
        "available": True,
        "onboarding_status": payload.get("status") or "incomplete",
        "automation_status": automations.get("status") or "not_configured",
        "summary": summary,
        "items": items,
    }
