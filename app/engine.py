from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Asset, AssetKind, EngineRun, MarketTick, ProviderHealthSample, Signal, SignalOutcomeSnapshot
from app.services.market_data import MarketDataRouter
from app.services.backtesting import WalkForwardAnalysisService
from app.services.news import NewsService
from app.services.evaluation import StrategyProofService
from app.services.events import StateEventService
from app.services.execution import ExecutionIntentService
from app.services.opportunity import BestOpportunitySelector
from app.services.operator_alerts import build_operator_alert_service
from app.services.reconciliation import ReconciliationService
from app.services.risk import RiskEngine
from app.services.simulation import BestAssetSimulationService
from app.services.strategy import StrategyEngine, extract_setup_type
from app.services.trading import PaperTrader


def run_engine_cycle(db: Session, settings: Settings) -> dict[str, int]:
    started_at = datetime.utcnow()
    latest_previous_engine_run = db.scalar(select(EngineRun).order_by(EngineRun.completed_at.desc()).limit(1))
    assets = db.scalars(select(Asset).where(Asset.is_active.is_(True))).all()
    assets = _select_runtime_assets(settings, assets)

    market_service = MarketDataRouter(
        alphavantage_api_key=settings.alphavantage_api_key,
        crypto_data_provider=settings.crypto_data_provider,
        etf_data_provider=settings.etf_data_provider,
        finimpulse_api_token=settings.finimpulse_api_token,
        twelvedata_api_key=settings.twelvedata_api_key,
        alpaca_api_key=settings.alpaca_api_key,
        alpaca_api_secret=settings.alpaca_api_secret,
        provider_rate_limit_cooldown_seconds=settings.provider_rate_limit_cooldown_seconds,
        provider_error_cooldown_seconds=settings.provider_error_cooldown_seconds,
        alpaca_quote_cache_ttl_seconds=settings.alpaca_quote_cache_ttl_seconds,
    )
    news_service = NewsService(settings.news_feeds)
    strategy_engine = StrategyEngine(
        settings.min_signal_score_to_buy,
        min_sentiment_score_to_buy=settings.min_sentiment_score_to_buy,
        min_momentum_score_to_buy=settings.min_momentum_score_to_buy,
        min_news_items_to_buy=settings.min_news_items_to_buy,
    )
    proof_service = StrategyProofService(
        strategy_engine,
        stop_loss_pct=settings.stop_loss_pct,
        take_profit_pct=settings.take_profit_pct,
        trailing_stop_pct=settings.trailing_stop_pct,
    )
    walkforward_service = WalkForwardAnalysisService(
        strategy_engine,
        stop_loss_pct=settings.stop_loss_pct,
        take_profit_pct=settings.take_profit_pct,
        trailing_stop_pct=settings.trailing_stop_pct,
    )
    risk_engine = RiskEngine(
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
    execution_service = ExecutionIntentService(settings)
    opportunity_selector = BestOpportunitySelector(
        proof_service,
        walkforward_service,
        max_signal_age_seconds=settings.max_tick_age_seconds,
        max_tick_age_seconds=settings.max_tick_age_seconds,
        allowed_asset_kinds=settings.tradeable_asset_kinds,
        allowed_setup_statuses=settings.unattended_setup_statuses,
    )
    trader = PaperTrader(
        risk_engine,
        execution_service,
        proof_service,
        opportunity_selector,
        allowed_asset_kinds=settings.tradeable_asset_kinds,
        allowed_setup_statuses=settings.unattended_setup_statuses,
    )
    reconciliation_service = ReconciliationService(settings, risk_engine)
    simulation_service = BestAssetSimulationService(
        stop_loss_pct=settings.stop_loss_pct,
        take_profit_pct=settings.take_profit_pct,
        trailing_stop_pct=settings.trailing_stop_pct,
        proof_service=proof_service,
        opportunity_selector=opportunity_selector,
        simulation_budgets=settings.simulation_budgets,
        max_signal_age_seconds=settings.max_tick_age_seconds,
        allowed_asset_kinds=settings.simulation_asset_kinds,
        allowed_setup_statuses=settings.unattended_setup_statuses,
    )
    operator_alerts = build_operator_alert_service(settings)

    latest_ticks = market_service.persist(db, assets)
    news_count = news_service.ingest(db, assets)
    refreshed_news_count = news_service.refresh_recent(db, assets)
    signals = strategy_engine.build_signals(db, assets)
    autopilot_guard = _autopilot_guard(settings, assets, latest_ticks, market_service.last_provider_report)
    best_opportunity = opportunity_selector.summary(db, signals=signals)
    scorecard = proof_service.build_scorecard(db)
    walkforward_report = walkforward_service.build_report(db)
    event_service = StateEventService()
    if settings.trading_enabled and autopilot_guard["trading_allowed"]:
        trader.execute(db, signals)
    if settings.simulation_enabled and autopilot_guard["simulation_allowed"]:
        simulation_service.ensure_scenarios(db)
        simulation_service.update_active(db)
    _record_provider_health(db, market_service.last_provider_report, assets, latest_ticks, settings.max_tick_age_seconds)
    _update_signal_outcomes(db, signals)
    _record_state_events(
        db,
        event_service=event_service,
        best_opportunity=best_opportunity,
        autopilot_guard=autopilot_guard,
        scorecard=scorecard,
        walkforward_report=walkforward_report,
        active_simulation=simulation_service.get_active(db),
    )
    _record_setup_approval_alerts(
        db,
        event_service=event_service,
        operator_alerts=operator_alerts,
        walkforward_report=walkforward_report,
    )
    reconciliation_snapshot = reconciliation_service.record_snapshot(db)
    _record_heartbeat_alerts(
        db,
        settings=settings,
        event_service=event_service,
        operator_alerts=operator_alerts,
        latest_previous_engine_run=latest_previous_engine_run,
    )
    _record_quote_safety_alerts(
        db,
        settings=settings,
        event_service=event_service,
        operator_alerts=operator_alerts,
        provider_report=market_service.last_provider_report,
    )
    _record_reconciliation_alerts(
        db,
        event_service=event_service,
        operator_alerts=operator_alerts,
        reconciliation_snapshot=reconciliation_snapshot,
    )

    result = {"assets": len(assets), "news_items": news_count, "signals": len(signals)}
    safety_message = ""
    if not autopilot_guard["trading_allowed"] or not autopilot_guard["simulation_allowed"]:
        safety_message = f" Autopilot guard: {'; '.join(autopilot_guard['reasons'])}."
    db.add(
        EngineRun(
            status="ok",
            assets_count=result["assets"],
            news_items_count=result["news_items"] + refreshed_news_count,
            signals_count=result["signals"],
            message=(
                f"Engine cycle completed successfully. News ingested {news_count}, rescored {refreshed_news_count}."
                f"{safety_message}"
            ),
            started_at=started_at,
            completed_at=datetime.utcnow(),
        )
    )
    db.commit()
    return result


def _select_runtime_assets(settings: Settings, assets: list[Asset]) -> list[Asset]:
    if not settings.proof_focus_enabled:
        return assets

    focused_assets = [asset for asset in assets if asset.kind.value in settings.proof_focus_asset_kinds]
    if settings.proof_focus_symbols:
        focused_assets = [asset for asset in focused_assets if asset.symbol.upper() in settings.proof_focus_symbols]

    return focused_assets or assets


def _record_setup_approval_alerts(
    db: Session,
    *,
    event_service: StateEventService,
    operator_alerts,
    walkforward_report,
) -> None:
    """Flag when an entry lane first clears the (honest) approval gate.

    Records an in-app state event every time the approved-lane set changes, and
    additionally pushes an operator alert (e.g. Telegram) when the set becomes
    non-empty. The operator-alert send is gated by OPERATOR_ALERT_EVENTS and is a
    no-op unless `setup_approved` is enabled there.
    """
    approved_lanes = sorted(
        f"{row.asset_kind}:{row.setup_type}"
        for row in walkforward_report.rows
        if row.recommendation == "approved"
    )
    fingerprint = "|".join(approved_lanes) if approved_lanes else "none"
    event = event_service.record_change(
        db,
        event_key="setup-approval-alert",
        category="proof",
        severity="ok" if approved_lanes else "warn",
        title=(
            f"{len(approved_lanes)} setup lane(s) cleared the approval gate"
            if approved_lanes
            else "No setup lane is approved yet"
        ),
        message=(
            "Approved lanes: " + ", ".join(approved_lanes) + ". "
            "These cleared realized-exit expectancy across multiple independent sessions."
            if approved_lanes
            else "No entry lane currently clears the honest approval gate."
        ),
        fingerprint=fingerprint,
    )
    if event and approved_lanes:
        operator_alerts.emit(
            event_type="setup_approved",
            severity="ok",
            title=f"Micro Trader: {len(approved_lanes)} lane(s) now APPROVED",
            message=(
                "Approved: " + ", ".join(approved_lanes) + ". "
                "Cleared the honest harness (realized exits + multiple independent sessions). "
                "Stage 0 milestone — review before considering anything live."
            ),
            details={"approved_lanes": approved_lanes},
        )


def _record_heartbeat_alerts(
    db: Session,
    *,
    settings: Settings,
    event_service: StateEventService,
    operator_alerts,
    latest_previous_engine_run: EngineRun | None,
) -> None:
    threshold_seconds = max(settings.heartbeat_max_gap_seconds, settings.worker_interval_seconds * 2)
    latest_heartbeat_event = event_service.latest_for_key(db, "worker-heartbeat")
    if not latest_previous_engine_run:
        return
    gap_seconds = max(int((datetime.utcnow() - latest_previous_engine_run.completed_at).total_seconds()), 0)
    if gap_seconds > threshold_seconds:
        lag_event = event_service.record_change(
            db,
            event_key="worker-heartbeat",
            category="ops",
            severity="warn",
            title="Worker heartbeat lagged",
            message=(
                f"No completed engine cycle landed for about {round(gap_seconds / 60)} min, above the "
                f"{round(threshold_seconds / 60)} min threshold."
            ),
            fingerprint=f"lag|{latest_previous_engine_run.id}",
        )
        if lag_event:
            operator_alerts.emit(
                event_type="heartbeat_lag",
                severity="warn",
                title=lag_event.title,
                message=lag_event.message,
                details={"last_engine_run_id": latest_previous_engine_run.id, "gap_seconds": gap_seconds},
            )
    else:
        recovered = bool(latest_heartbeat_event and latest_heartbeat_event.fingerprint != "ok")
        healthy_event = event_service.record_change(
            db,
            event_key="worker-heartbeat",
            category="ops",
            severity="ok",
            title="Worker heartbeat recovered" if recovered else "Worker heartbeat healthy",
            message=(
                "A fresh engine cycle completed and the heartbeat is back inside the configured threshold."
                if recovered
                else "Fresh engine cycles are arriving inside the configured heartbeat threshold."
            ),
            fingerprint="ok",
        )
        if healthy_event and recovered:
            operator_alerts.emit(
                event_type="heartbeat_recovered",
                severity="ok",
                title=healthy_event.title,
                message=healthy_event.message,
                details={"threshold_seconds": threshold_seconds},
            )


def _record_quote_safety_alerts(
    db: Session,
    *,
    settings: Settings,
    event_service: StateEventService,
    operator_alerts,
    provider_report: dict[str, dict],
) -> None:
    for kind, report in provider_report.items():
        stale_assets = int(report.get("stale_assets") or 0)
        failed_assets = int(report.get("failed_assets") or 0)
        provider_status = str(report.get("status") or "ok")
        if stale_assets >= settings.stale_quote_alert_threshold or failed_assets > 0 or provider_status != "ok":
            warn_event = event_service.record_change(
                db,
                event_key=f"quote-safety-{kind}",
                category="data",
                severity="warn",
                title=f"{kind.upper()} quote safety degraded",
                message=(
                    f"{kind.upper()} provider path reports status {provider_status}, "
                    f"{stale_assets} stale quote(s), and {failed_assets} failed quote(s)."
                ),
                fingerprint=f"warn|{provider_status}|{stale_assets}|{failed_assets}",
            )
            if warn_event:
                operator_alerts.emit(
                    event_type="stale_quotes",
                    severity="warn",
                    title=warn_event.title,
                    message=warn_event.message,
                    details={"asset_kind": kind, "provider_status": provider_status},
                )
        else:
            event_service.record_change(
                db,
                event_key=f"quote-safety-{kind}",
                category="data",
                severity="ok",
                title=f"{kind.upper()} quote safety healthy",
                message=f"{kind.upper()} quote freshness and provider health are inside the configured threshold.",
                fingerprint="ok",
            )


def _record_reconciliation_alerts(
    db: Session,
    *,
    event_service: StateEventService,
    operator_alerts,
    reconciliation_snapshot,
) -> None:
    if reconciliation_snapshot.status != "ok":
        drift_event = event_service.record_change(
            db,
            event_key="execution-reconciliation",
            category="execution",
            severity="warn",
            title="Execution reconciliation needs attention",
            message=reconciliation_snapshot.message,
            fingerprint=(
                f"{reconciliation_snapshot.status}|{reconciliation_snapshot.pending_intents}|"
                f"{reconciliation_snapshot.failed_intents}|{reconciliation_snapshot.execution_target}"
            ),
        )
        if drift_event:
            operator_alerts.emit(
                event_type="reconciliation_drift",
                severity="warn",
                title=drift_event.title,
                message=drift_event.message,
                details={
                    "status": reconciliation_snapshot.status,
                    "pending_intents": reconciliation_snapshot.pending_intents,
                    "failed_intents": reconciliation_snapshot.failed_intents,
                },
            )
    else:
        event_service.record_change(
            db,
            event_key="execution-reconciliation",
            category="execution",
            severity="ok",
            title="Execution reconciliation clean",
            message=reconciliation_snapshot.message,
            fingerprint="ok",
        )


def _record_state_events(
    db: Session,
    *,
    event_service: StateEventService,
    best_opportunity: dict,
    autopilot_guard: dict,
    scorecard,
    walkforward_report,
    active_simulation,
) -> None:
    state = "ready" if autopilot_guard["trading_allowed"] and autopilot_guard["simulation_allowed"] else "paused"
    reasons = "; ".join(autopilot_guard["reasons"]) if autopilot_guard["reasons"] else "All guardrails are currently satisfied."
    event_service.record_change(
        db,
        event_key="autopilot-state",
        category="autopilot",
        severity="ok" if state == "ready" else "warn",
        title=f"Autopilot is {state}",
        message=reasons,
        fingerprint=f"{state}|{reasons}",
    )

    best = best_opportunity.get("best")
    best_eligible = best_opportunity.get("best_eligible")
    if best_eligible:
        title = f"Best opportunity is now tradable: {best_eligible['symbol']}"
        message = (
            f"{best_eligible['asset_kind'].upper()} {best_eligible['setup_type']} cleared the unattended gate "
            f"with score {best_eligible['score']:.2f}."
        )
        fingerprint = f"eligible|{best_eligible['symbol']}|{best_eligible['setup_type']}|{best_eligible['approval_status']}"
        severity = "ok"
    elif best:
        title = f"Best opportunity shifted to {best['symbol']}"
        message = best.get("blocked_reason") or f"{best['asset_kind'].upper()} {best['setup_type']} is leading but still blocked."
        fingerprint = f"blocked|{best['symbol']}|{best['setup_type']}|{best.get('blocked_reason', '')}"
        severity = "warn"
    else:
        title = "No fresh BUY opportunity is available"
        message = "The cross-asset selector does not see a fresh eligible BUY setup right now."
        fingerprint = "none"
        severity = "warn"
    event_service.record_change(
        db,
        event_key="best-opportunity",
        category="opportunity",
        severity=severity,
        title=title,
        message=message,
        fingerprint=fingerprint,
    )
    _record_etf_regime_event(
        db,
        event_service=event_service,
        regime_transition=best_opportunity.get("regime_transition"),
    )

    simulation_state = "active" if active_simulation else "waiting"
    if active_simulation:
        sim_title = f"Simulation active on {active_simulation.asset.symbol}"
        sim_message = active_simulation.opened_reason
        sim_fingerprint = f"active|{active_simulation.asset.symbol}|{active_simulation.setup_type}|{active_simulation.started_at.isoformat()}"
        sim_severity = "ok"
    else:
        sim_title = "Simulation trigger is waiting"
        sim_message = "The worker will start the next best approved cross-asset simulation automatically when a fresh BUY appears."
        sim_fingerprint = f"waiting|{best_eligible['symbol'] if best_eligible else 'none'}"
        sim_severity = "warn"
    event_service.record_change(
        db,
        event_key="simulation-trigger",
        category="simulation",
        severity=sim_severity,
        title=sim_title,
        message=sim_message,
        fingerprint=sim_fingerprint,
    )

    approval_counts = f"{scorecard.approved_count}|{scorecard.watch_count}|{scorecard.disabled_count}"
    event_service.record_change(
        db,
        event_key="setup-proof-counts",
        category="proof",
        severity="ok" if scorecard.approved_count else "warn",
        title=f"Setup proof board: {scorecard.approved_count} approved / {scorecard.watch_count} watch",
        message=(
            f"Current setup evidence totals: {scorecard.approved_count} approved, "
            f"{scorecard.watch_count} watch, {scorecard.disabled_count} disabled."
        ),
        fingerprint=approval_counts,
    )
    _record_approval_focus_event(
        db,
        event_service=event_service,
        scorecard=scorecard,
        walkforward_report=walkforward_report,
        regime_transition=best_opportunity.get("regime_transition"),
    )
    _record_active_proof_runway_event(
        db,
        event_service=event_service,
        best_opportunity=best_opportunity,
        walkforward_report=walkforward_report,
    )


def _record_active_proof_runway_event(
    db: Session,
    *,
    event_service: StateEventService,
    best_opportunity: dict,
    walkforward_report,
) -> None:
    best = best_opportunity.get("best") or {}
    if not best or not best.get("setup_type") or best["setup_type"].endswith("risk_off") or best["setup_type"].endswith("watch"):
        event_service.record_change(
            db,
            event_key="active-proof-runway",
            category="proof",
            severity="warn",
            title="No active proof candidate",
            message="No current entry setup is far enough along to deserve a live-proof runway.",
            fingerprint="inactive",
        )
        return

    pending_rows = db.scalars(
        select(SignalOutcomeSnapshot)
        .join(Signal, SignalOutcomeSnapshot.signal_id == Signal.id)
        .where(
            SignalOutcomeSnapshot.outcome_status == "pending",
            Signal.asset_id == best["asset_id"],
        )
    ).all()
    pending_rows = [
        row for row in pending_rows
        if row.signal is not None and extract_setup_type(row.signal.rationale) == best["setup_type"]
    ]
    pending_count = len(pending_rows)
    walkforward_row = next(
        (
            row for row in walkforward_report.rows
            if row.asset_kind == best["asset_kind"] and row.setup_type == best["setup_type"]
        ),
        None,
    )
    recommendation = getattr(walkforward_row, "recommendation", best.get("walkforward_recommendation", "watch"))
    live_sample_count = int(getattr(walkforward_row, "live_sample_count", best.get("live_sample_count", 0)) or 0)
    live_proof_status = getattr(walkforward_row, "live_proof_status", best.get("live_proof_status", "research"))
    test_net_expectancy_pct = float(
        getattr(getattr(walkforward_row, "test", None), "net_expectancy_pct", best.get("test_net_expectancy_pct", 0.0)) or 0.0
    )
    phase = _active_proof_phase(
        eligible_for_unattended=bool(best.get("eligible_for_unattended")),
        live_proof_status=live_proof_status,
        live_sample_count=live_sample_count,
        pending_count=pending_count,
        recommendation=recommendation,
    )
    previous = event_service.latest_for_key(db, "active-proof-runway")
    previous_phase = ""
    if previous and previous.fingerprint:
        previous_phase = previous.fingerprint.split("|", 1)[0]
    title, message, severity = _active_proof_event_payload(
        symbol=best["symbol"],
        asset_kind=best["asset_kind"],
        setup_type=best["setup_type"],
        phase=phase,
        previous_phase=previous_phase,
        live_sample_count=live_sample_count,
        pending_count=pending_count,
        recommendation=recommendation,
        test_net_expectancy_pct=test_net_expectancy_pct,
    )
    fingerprint = (
        f"{phase}|{best['symbol']}|{best['setup_type']}|{recommendation}|"
        f"{live_proof_status}|{live_sample_count}|{pending_count}|{test_net_expectancy_pct:.3f}"
    )
    event_service.record_change(
        db,
        event_key="active-proof-runway",
        category="proof",
        severity=severity,
        title=title,
        message=message,
        fingerprint=fingerprint,
    )


def _record_etf_regime_event(
    db: Session,
    *,
    event_service: StateEventService,
    regime_transition: dict | None,
) -> None:
    if not regime_transition:
        return

    state = regime_transition.get("state", "watch")
    symbol = regime_transition.get("symbol", "ETF")
    setup_type = regime_transition.get("setup_type", "unknown")
    title = regime_transition.get("title")
    severity = regime_transition.get("severity")
    message = regime_transition.get("message", "ETF regime is unchanged.")
    if not title or not severity:
        if state == "risk_off":
            title = "ETF lane moved to risk-off"
            severity = "warn"
        elif state == "rebuilding":
            title = f"ETF leadership is rebuilding around {symbol}"
            severity = "ok"
        else:
            title = f"ETF lane is stabilizing around {symbol}"
            severity = "ok"

    event_service.record_change(
        db,
        event_key="etf-regime",
        category="opportunity",
        severity=severity,
        title=title,
        message=message,
        fingerprint=f"{state}|{symbol}|{setup_type}|{message}",
    )


def _record_approval_focus_event(
    db: Session,
    *,
    event_service: StateEventService,
    scorecard,
    walkforward_report,
    regime_transition: dict | None,
) -> None:
    scorecard_map = {
        (row.asset_kind, row.setup_type): row
        for row in scorecard.rows
    }
    entry_rows = [
        row
        for row in walkforward_report.rows
        if not row.setup_type.endswith("risk_off") and not row.setup_type.endswith("watch")
    ]
    if not entry_rows:
        event_service.record_change(
            db,
            event_key="approval-focus",
            category="proof",
            severity="warn",
            title="No entry lane is close enough to promote",
            message="The proof engine still lacks any entry setup with enough evidence to become the primary approval candidate.",
            fingerprint="none",
        )
        return

    def target_rank(row) -> tuple[int, int, float, float, float]:
        scorecard_row = scorecard_map.get((row.asset_kind, row.setup_type))
        scorecard_status = getattr(scorecard_row, "approval_status", "watch")
        walkforward_status = getattr(row, "recommendation", "watch")
        live_status = getattr(row, "live_proof_status", "research")
        status_rank = {"approved": 0, "watch": 1, "disabled": 2}
        live_rank = {"cleared": 0, "building_live": 1, "research": 2, "replay_only": 3, "exit_only": 4}
        return (
            status_rank.get(walkforward_status, 9) + status_rank.get(scorecard_status, 9),
            live_rank.get(live_status, 9),
            -float(getattr(getattr(row, "test", None), "net_expectancy_pct", -999.0) or -999.0),
            -float(getattr(getattr(row, "test", None), "avg_decision_edge_pct", -999.0) or -999.0),
            -float(getattr(scorecard_row, "net_expectancy_pct", -999.0) or -999.0),
        )

    target_row = min(entry_rows, key=target_rank)
    target_scorecard = scorecard_map.get((target_row.asset_kind, target_row.setup_type))
    scorecard_status = getattr(target_scorecard, "approval_status", "watch")
    walkforward_status = getattr(target_row, "recommendation", "watch")
    live_status = getattr(target_row, "live_proof_status", "research")
    scorecard_expectancy = float(getattr(target_scorecard, "net_expectancy_pct", 0.0) or 0.0)
    test_expectancy = float(getattr(target_row.test, "net_expectancy_pct", 0.0) or 0.0)
    test_edge = float(getattr(target_row.test, "avg_decision_edge_pct", 0.0) or 0.0)
    test_win_rate = float(getattr(target_row.test, "win_rate_pct", 0.0) or 0.0)
    live_sample_count = int(getattr(target_row, "live_sample_count", 0) or 0)

    blockers: list[str] = []
    if scorecard_status != "approved":
        if target_scorecard is None:
            blockers.append("scorecard evidence is still missing")
        elif scorecard_expectancy < 0.15:
            blockers.append(f"scorecard expectancy is {scorecard_expectancy:.2f}%")
    if test_expectancy < 0.10:
        blockers.append(f"test expectancy is {test_expectancy:.2f}%")
    if test_edge < 0.05:
        blockers.append(f"decision edge is {test_edge:.2f}%")
    if test_win_rate < 50.0:
        blockers.append(f"test win rate is {test_win_rate:.0f}%")
    if live_sample_count < 4:
        blockers.append(f"live proof is only {live_sample_count} resolved outcome(s)")
    if regime_transition and regime_transition.get("state") == "risk_off" and target_row.asset_kind == "etf":
        blockers.append("ETF regime is still risk-off")

    if walkforward_status == "approved" and scorecard_status == "approved" and live_status == "cleared":
        severity = "ok"
        title = f"{target_row.setup_type} cleared the approval focus"
        message = (
            f"{target_row.asset_kind.upper()} {target_row.setup_type} has cleared scorecard, walk-forward, and live-proof gates "
            "and is now the first unattended-ready entry lane."
        )
    else:
        severity = "warn"
        title = f"Approval focus remains {target_row.setup_type}"
        message = (
            f"{target_row.asset_kind.upper()} {target_row.setup_type} is still the nearest entry lane, "
            f"but {', '.join(blockers[:3]) or 'it still lacks enough proof'}."
        )

    fingerprint = (
        f"{target_row.asset_kind}|{target_row.setup_type}|{scorecard_status}|{walkforward_status}|"
        f"{live_status}|{scorecard_expectancy:.3f}|{test_expectancy:.3f}|{test_edge:.3f}|{live_sample_count}"
    )
    event_service.record_change(
        db,
        event_key="approval-focus",
        category="proof",
        severity=severity,
        title=title,
        message=message,
        fingerprint=fingerprint,
    )


def _active_proof_phase(
    *,
    eligible_for_unattended: bool,
    live_proof_status: str,
    live_sample_count: int,
    pending_count: int,
    recommendation: str,
) -> str:
    if eligible_for_unattended:
        return "approved"
    if live_proof_status == "replay_only":
        return "replay_only"
    if pending_count > 0 and live_sample_count == 0:
        return "first_live_proof"
    if live_proof_status == "building_live":
        if live_sample_count < 2:
            return "strengthen_live_proof"
        return "watch_candidate"
    if live_proof_status == "research" and live_sample_count > 0:
        return "weakened"
    if recommendation == "watch":
        return "research"
    return live_proof_status or "research"


def _active_proof_event_payload(
    *,
    symbol: str,
    asset_kind: str,
    setup_type: str,
    phase: str,
    previous_phase: str,
    live_sample_count: int,
    pending_count: int,
    recommendation: str,
    test_net_expectancy_pct: float,
) -> tuple[str, str, str]:
    label = f"{asset_kind.upper()} {symbol} {setup_type}"
    if phase == "approved":
        return (
            f"{symbol} cleared the proof runway",
            f"{label} is now unattended-eligible after clearing live-proof and walk-forward gates.",
            "ok",
        )
    if phase == "first_live_proof":
        return (
            f"{symbol} entered first live proof",
            f"{label} has {pending_count} pending outcome windows and is now collecting its first real live evidence.",
            "ok",
        )
    if phase == "strengthen_live_proof":
        return (
            f"{symbol} is strengthening live proof",
            f"{label} has {live_sample_count} live resolved outcome(s) and {pending_count} pending. It still needs stronger confirmation before watch status.",
            "ok",
        )
    if phase == "watch_candidate":
        return (
            f"{symbol} is approaching watch status",
            f"{label} has {live_sample_count} live resolved outcome(s). Walk-forward remains {recommendation} with test expectancy {test_net_expectancy_pct:.2f}%.",
            "ok",
        )
    if phase == "weakened":
        transition_note = " Early live proof weakened the setup." if previous_phase in {"first_live_proof", "strengthen_live_proof", "watch_candidate"} else ""
        return (
            f"{symbol} live proof weakened",
            f"{label} fell back to research after early live results failed to support promotion.{transition_note} Test expectancy is {test_net_expectancy_pct:.2f}%.",
            "warn",
        )
    if phase == "replay_only":
        return (
            f"{symbol} is replay-only for now",
            f"{label} still has no live resolved outcomes, so replay can rank it but not promote it.",
            "warn",
        )
    return (
        f"{symbol} remains under research",
        f"{label} is still blocked at the {phase} stage. Walk-forward is {recommendation} with {live_sample_count} live resolved outcome(s).",
        "warn",
    )


def _record_provider_health(
    db: Session,
    provider_report: dict[str, dict],
    assets: list[Asset],
    latest_ticks: dict[str, MarketTick],
    max_tick_age_seconds: int,
) -> None:
    assets_by_kind = {
        "crypto": [asset for asset in assets if asset.kind == AssetKind.CRYPTO],
        "etf": [asset for asset in assets if asset.kind == AssetKind.ETF],
        "stock": [asset for asset in assets if asset.kind == AssetKind.STOCK],
    }
    for key, report in provider_report.items():
        tracked_assets = assets_by_kind.get(key, [])
        stale_assets = 0
        for asset in tracked_assets:
            tick = latest_ticks.get(asset.symbol)
            if not tick:
                continue
            age_seconds = max(int((datetime.utcnow() - tick.captured_at).total_seconds()), 0)
            if age_seconds > max_tick_age_seconds:
                stale_assets += 1
        report["stale_assets"] = stale_assets
        db.add(
            ProviderHealthSample(
                provider=report["provider"],
                asset_kind=report["asset_kind"],
                status=report["status"],
                attempted_assets=report["attempted_assets"],
                successful_assets=report["successful_assets"],
                failed_assets=report["failed_assets"],
                stale_assets=stale_assets,
                cache_used=bool(report.get("cache_used")),
                message=report["message"],
            )
        )


def _autopilot_guard(settings: Settings, assets: list[Asset], latest_ticks: dict[str, MarketTick], provider_report: dict[str, dict]) -> dict:
    coverage_by_kind: dict[str, float] = {}
    stale_by_kind: dict[str, int] = {}
    relevant_kinds = settings.tradeable_asset_kinds | settings.simulation_asset_kinds

    for kind in relevant_kinds:
        kind_assets = [asset for asset in assets if asset.kind.value == kind]
        attempted = len(kind_assets)
        successful = len([asset for asset in kind_assets if asset.symbol in latest_ticks])
        coverage_by_kind[kind] = round((successful / attempted), 4) if attempted else 1.0
        stale_by_kind[kind] = 0
        for asset in kind_assets:
            tick = latest_ticks.get(asset.symbol)
            if not tick:
                continue
            age_seconds = max(int((datetime.utcnow() - tick.captured_at).total_seconds()), 0)
            if age_seconds > settings.max_tick_age_seconds:
                stale_by_kind[kind] += 1

    reasons: list[str] = []
    for kind in relevant_kinds:
        report = provider_report.get(kind)
        if settings.halt_on_provider_warnings and report and report.get("status") != "ok":
            reasons.append(f"{kind} provider status is {report.get('status')}")
        if coverage_by_kind.get(kind, 0.0) < settings.min_data_coverage_ratio:
            reasons.append(
                f"{kind} data coverage is {coverage_by_kind.get(kind, 0.0) * 100:.0f}% "
                f"(min {settings.min_data_coverage_ratio * 100:.0f}%)"
            )
        if settings.halt_on_stale_quotes and stale_by_kind.get(kind, 0) > 0:
            reasons.append(f"{kind} has {stale_by_kind[kind]} stale quote(s)")

    trading_allowed = settings.trading_enabled and not reasons
    simulation_allowed = settings.simulation_enabled and not reasons
    return {
        "trading_allowed": trading_allowed,
        "simulation_allowed": simulation_allowed,
        "reasons": reasons or ["all active universes passed autopilot safety checks"],
        "coverage_by_kind": coverage_by_kind,
    }


def _update_signal_outcomes(db: Session, new_signals: list[Signal]) -> None:
    horizons = (1, 4, 24)
    if new_signals:
        for signal in new_signals:
            signal_tick = db.scalar(
                select(MarketTick)
                .where(MarketTick.asset_id == signal.asset_id, MarketTick.captured_at <= signal.created_at)
                .order_by(MarketTick.captured_at.desc())
                .limit(1)
            )
            if not signal_tick:
                continue
            existing_horizons = {
                row.horizon_hours
                for row in db.scalars(select(SignalOutcomeSnapshot).where(SignalOutcomeSnapshot.signal_id == signal.id)).all()
            }
            for horizon in horizons:
                if horizon in existing_horizons:
                    continue
                db.add(
                    SignalOutcomeSnapshot(
                        signal_id=signal.id,
                        horizon_hours=horizon,
                        signal_price=float(signal_tick.price),
                        outcome_status="pending",
                    )
                )

    pending = db.scalars(
        select(SignalOutcomeSnapshot)
        .where(SignalOutcomeSnapshot.outcome_status == "pending")
        .order_by(SignalOutcomeSnapshot.created_at.asc())
        .limit(300)
    ).all()
    now = datetime.utcnow()
    for outcome in pending:
        signal = outcome.signal
        if not signal:
            continue
        elapsed_hours = (now - signal.created_at).total_seconds() / 3600
        if elapsed_hours < outcome.horizon_hours:
            continue
        candidate_tick = None
        target_cutoff = signal.created_at.timestamp() + (outcome.horizon_hours * 3600)
        ticks = db.scalars(
            select(MarketTick)
            .where(
                MarketTick.asset_id == signal.asset_id,
                MarketTick.captured_at >= signal.created_at,
                MarketTick.captured_at <= now,
            )
            .order_by(MarketTick.captured_at.asc())
        ).all()
        for tick in ticks:
            if tick.captured_at.timestamp() >= target_cutoff:
                candidate_tick = tick
                break
        if candidate_tick is None and ticks:
            candidate_tick = ticks[-1]
        if not candidate_tick:
            outcome.outcome_status = "missing"
            outcome.updated_at = now
            continue
        observed_price = float(candidate_tick.price)
        outcome.observed_price = observed_price
        if outcome.signal_price > 0:
            market_move_pct = round(((observed_price / outcome.signal_price) - 1) * 100, 4)
            decision_direction = 1.0 if signal.action.value == "buy" else -1.0
            decision_edge_pct = round(market_move_pct * decision_direction, 4)
            outcome.market_move_pct = market_move_pct
            outcome.decision_edge_pct = decision_edge_pct
            outcome.pnl_pct = decision_edge_pct
            outcome.outcome_label = _label_outcome(signal.action.value, market_move_pct, decision_edge_pct)
        else:
            outcome.market_move_pct = None
            outcome.decision_edge_pct = None
            outcome.pnl_pct = None
            outcome.outcome_label = "missing-price"
        outcome.outcome_status = "resolved"
        outcome.updated_at = now
    _backfill_resolved_signal_outcomes(db)


def _backfill_resolved_signal_outcomes(db: Session) -> None:
    rows = db.scalars(
        select(SignalOutcomeSnapshot)
        .where(SignalOutcomeSnapshot.outcome_status == "resolved")
        .order_by(SignalOutcomeSnapshot.updated_at.desc())
        .limit(600)
    ).all()
    for row in rows:
        if not row.signal or not row.signal_price or not row.observed_price:
            continue
        market_move_pct = round(((row.observed_price / row.signal_price) - 1) * 100, 4)
        decision_direction = 1.0 if row.signal.action.value == "buy" else -1.0
        decision_edge_pct = round(market_move_pct * decision_direction, 4)
        row.market_move_pct = market_move_pct
        row.decision_edge_pct = decision_edge_pct
        row.pnl_pct = decision_edge_pct
        row.outcome_label = _label_outcome(row.signal.action.value, market_move_pct, decision_edge_pct)


def _label_outcome(action: str, market_move_pct: float, decision_edge_pct: float) -> str:
    if action == "hold":
        if market_move_pct >= 0.75:
            return "missed-upside"
        if market_move_pct <= -0.75:
            return "protected-downside"
        return "flat-safe"
    if decision_edge_pct >= 1.0:
        return "strong-win"
    if decision_edge_pct > 0:
        return "small-win"
    if decision_edge_pct <= -1.0:
        return "strong-loss"
    return "small-loss"
