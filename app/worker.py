from pathlib import Path
import json
import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.bootstrap import seed_assets
from app.config import get_settings
from app.db import (
    Base,
    engine,
    ensure_asset_kind_enum,
    ensure_provider_health_schema,
    ensure_signal_outcome_schema,
    ensure_simulation_schema,
    ensure_state_event_schema,
)
from app.engine import run_engine_cycle
from app.models import Asset, EngineRun, ExecutionIntent, ExecutionIntentStatus, Position, PositionStatus, Signal
from app.services.brokers import build_broker_adapter
from app.services.operator_alerts import build_operator_alert_service


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _telegram_offset_path(settings) -> Path:
    return Path(settings.operator_alert_telegram_offset_path)


def _runtime_state_path(raw_path: str) -> Path:
    return Path(raw_path)


def _load_telegram_offset(settings) -> int | None:
    path = _telegram_offset_path(settings)
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _store_telegram_offset(settings, offset: int) -> None:
    path = _telegram_offset_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(offset), encoding="utf-8")


def _load_runtime_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _store_runtime_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _safe_local_now(settings) -> datetime:
    try:
        return datetime.now(ZoneInfo(settings.operator_alert_digest_timezone))
    except Exception:
        return datetime.utcnow()


def _operator_snapshot(settings) -> dict:
    import app.main as app_main

    with Session(engine) as db:
        latest_engine_run = db.scalar(select(EngineRun).order_by(EngineRun.completed_at.desc()).limit(1))
        pending_intents = int(
            db.scalar(select(func.count()).select_from(ExecutionIntent).where(ExecutionIntent.status == ExecutionIntentStatus.PENDING))
            or 0
        )
        failed_intents = int(
            db.scalar(select(func.count()).select_from(ExecutionIntent).where(ExecutionIntent.status == ExecutionIntentStatus.FAILED))
            or 0
        )
        open_positions = int(
            db.scalar(select(func.count()).select_from(Position).where(Position.status == PositionStatus.OPEN))
            or 0
        )
        latest_signal = db.scalar(select(Signal).options(joinedload(Signal.asset)).order_by(Signal.created_at.desc()).limit(1))
        assets = db.scalars(select(Asset).where(Asset.is_active.is_(True)).order_by(Asset.kind.asc(), Asset.symbol.asc())).all()
        recent_signals = db.scalars(select(Signal).options(joinedload(Signal.asset)).order_by(Signal.created_at.desc()).limit(40)).all()

        provider_health = app_main._provider_health_summary(db)
        latest_market = app_main._latest_market_rows(db, assets)
        risk_snapshot = app_main.build_risk_engine().control_snapshot(db)
        autopilot_status = app_main._autopilot_status(recent_signals, latest_market, provider_health, risk_snapshot)
        pending_setups = app_main._pending_setup_summary(db)
        best_opportunity = app_main.build_opportunity_selector().summary(db)
        setup_scorecards = app_main._split_setup_rows(app_main.build_strategy_proof_service().build_scorecard(db).to_dict())
        setup_walkforward = app_main._split_setup_rows(app_main.build_walkforward_service().build_report(db).to_dict())
        setup_monitor = app_main._setup_monitor_summary(setup_walkforward, pending_setups, best_opportunity)
        approval_focus = app_main._approval_focus_summary(setup_scorecards, setup_walkforward, pending_setups, best_opportunity)
        reconciliation_status = app_main.build_reconciliation_service().snapshot(db)
        launch_readiness = app_main._launch_readiness_summary(
            setup_monitor=setup_monitor,
            approval_focus=approval_focus,
            provider_health=provider_health,
            reconciliation_status=reconciliation_status,
            latest_engine_run=latest_engine_run,
            autopilot_status=autopilot_status,
            risk_snapshot=risk_snapshot,
            broker_status=build_broker_adapter(settings).status(),
        )

    latest_signal_line = "none yet"
    if latest_signal and latest_signal.asset:
        latest_signal_line = f"{latest_signal.asset.symbol} {latest_signal.action.value.upper()} score {latest_signal.score:.2f}"
    return {
        "engine_status": latest_engine_run.status if latest_engine_run else "unknown",
        "engine_completed_at": latest_engine_run.completed_at.isoformat(timespec="seconds") if latest_engine_run else None,
        "pending_intents": pending_intents,
        "failed_intents": failed_intents,
        "open_positions": open_positions,
        "latest_signal": latest_signal_line,
        "launch_readiness": launch_readiness,
        "setup_monitor": setup_monitor,
        "approval_focus": approval_focus,
        "best_opportunity": best_opportunity,
    }


def _build_daily_summary_message(settings) -> str:
    snapshot = _operator_snapshot(settings)
    launch = snapshot["launch_readiness"]
    focus = snapshot["approval_focus"]
    nearest = snapshot["setup_monitor"].get("nearest_candidate") or {}
    local_now = _safe_local_now(settings)
    closest_lane = "none"
    if focus.get("target_asset_kind") and focus.get("target_setup"):
        closest_lane = f"{focus['target_asset_kind'].upper()} {focus['target_setup']}"
    nearest_line = "none"
    if nearest:
        nearest_line = (
            f"{nearest.get('asset_kind', '').upper()} {nearest.get('setup_type')} "
            f"({nearest.get('live_sample_count', 0)} live / {nearest.get('pending_count', 0)} pending)"
        )
    return "\n".join(
        [
            "Micro Trader daily summary",
            f"local time: {local_now.strftime('%Y-%m-%d %H:%M %Z')}",
            f"readiness: {launch['overall_state']} ({launch['current_tier']})",
            f"approved gates: {launch['approved_gates']} / watch: {launch['watch_gates']} / blocked: {launch['blocked_gates']}",
            f"open positions: {snapshot['open_positions']}",
            f"pending intents: {snapshot['pending_intents']} / failed intents: {snapshot['failed_intents']}",
            f"closest lane: {closest_lane}",
            f"lead evidence: {focus.get('walkforward_status') or 'n/a'} / {focus.get('live_proof_status') or 'n/a'}",
            f"nearest candidate: {nearest_line}",
            f"latest signal: {snapshot['latest_signal']}",
            f"next unlock: {launch['next_unlock']}",
        ]
    )


def _emit_daily_summary_if_due(settings, operator_alerts) -> None:
    if settings.operator_alert_transport.strip().lower() != "telegram" or not settings.operator_alert_daily_summary_enabled:
        return
    local_now = _safe_local_now(settings)
    if local_now.hour < max(0, min(23, settings.operator_alert_daily_summary_hour_local)):
        return
    state_path = _runtime_state_path(settings.operator_alert_daily_summary_state_path)
    state = _load_runtime_json(state_path)
    current_day = local_now.date().isoformat()
    if state.get("last_sent_day") == current_day:
        return
    if operator_alerts.send_message(_build_daily_summary_message(settings)):
        _store_runtime_json(
            state_path,
            {
                "last_sent_day": current_day,
                "last_sent_at": local_now.isoformat(),
            },
        )


def _current_strategy_state(settings) -> dict:
    snapshot = _operator_snapshot(settings)
    focus = snapshot["approval_focus"]
    best = snapshot["best_opportunity"].get("best") or {}
    setup_monitor = snapshot["setup_monitor"] or {}
    nearest = setup_monitor.get("nearest_candidate") or {}
    return {
        "overall_state": snapshot["launch_readiness"]["overall_state"],
        "ready_setups_count": int(setup_monitor.get("ready_setups_count", 0) or 0),
        "target_asset_kind": focus.get("target_asset_kind"),
        "target_setup": focus.get("target_setup"),
        "walkforward_status": focus.get("walkforward_status"),
        "live_proof_status": focus.get("live_proof_status"),
        "pending_count": int(focus.get("pending_count", 0) or 0),
        "best_symbol": best.get("symbol"),
        "best_setup_type": best.get("setup_type"),
        "best_action": best.get("action"),
        "nearest_asset_kind": nearest.get("asset_kind"),
        "nearest_setup_type": nearest.get("setup_type"),
        "nearest_pending_count": int(nearest.get("pending_count", 0) or 0),
        "nearest_live_sample_count": int(nearest.get("live_sample_count", 0) or 0),
        "headline": focus.get("headline"),
        "message": focus.get("message"),
        "evidence_message": focus.get("evidence_message"),
    }


def _build_approved_lane_message(previous: dict, current: dict) -> str:
    previous_count = int(previous.get("ready_setups_count", 0) or 0)
    current_count = int(current.get("ready_setups_count", 0) or 0)
    if current_count > previous_count:
        title = "Micro Trader approved lane gained"
        detail = f"approved lanes: {previous_count} -> {current_count}"
    else:
        title = "Micro Trader approved lane lost"
        detail = f"approved lanes: {previous_count} -> {current_count}"
    current_lane = "none"
    if current.get("target_asset_kind") and current.get("target_setup"):
        current_lane = f"{str(current['target_asset_kind']).upper()} {current['target_setup']}"
    return "\n".join(
        [
            title,
            detail,
            f"focus lane: {current_lane}",
            f"proof state: {current.get('walkforward_status', 'n/a')}/{current.get('live_proof_status', 'n/a')}",
            current.get("evidence_message") or current.get("message") or "Approval board changed.",
        ]
    )


def _build_etf_trend_pending_message(previous: dict, current: dict) -> str:
    previous_pending = int(previous.get("pending_count", 0) or 0)
    current_pending = int(current.get("pending_count", 0) or 0)
    live_count = int(current.get("nearest_live_sample_count", 0) or 0)
    return "\n".join(
        [
            "Micro Trader etf_trend proof started",
            f"pending outcome windows: {previous_pending} -> {current_pending}",
            f"live resolved so far: {live_count}",
            "focus lane: ETF etf_trend",
            current.get("evidence_message") or "Fresh ETF trend proof is now building.",
        ]
    )


def _build_state_change_message(previous: dict, current: dict) -> str:
    previous_lane = "none"
    if previous.get("target_asset_kind") and previous.get("target_setup"):
        previous_lane = f"{str(previous['target_asset_kind']).upper()} {previous['target_setup']}"
    current_lane = "none"
    if current.get("target_asset_kind") and current.get("target_setup"):
        current_lane = f"{str(current['target_asset_kind']).upper()} {current['target_setup']}"
    return "\n".join(
        [
            "Micro Trader state change",
            f"readiness: {previous.get('overall_state', 'unknown')} -> {current.get('overall_state', 'unknown')}",
            f"focus lane: {previous_lane} -> {current_lane}",
            (
                f"proof state: {previous.get('walkforward_status', 'n/a')}/{previous.get('live_proof_status', 'n/a')} -> "
                f"{current.get('walkforward_status', 'n/a')}/{current.get('live_proof_status', 'n/a')}"
            ),
            f"best symbol: {previous.get('best_symbol') or 'none'} -> {current.get('best_symbol') or 'none'}",
            current.get("headline") or "Strategy focus updated.",
            current.get("evidence_message") or current.get("message") or "No extra evidence note available.",
        ]
    )


def _emit_strategy_state_change_if_needed(settings, operator_alerts) -> None:
    if settings.operator_alert_transport.strip().lower() != "telegram":
        return
    state_path = _runtime_state_path(settings.operator_alert_strategy_state_path)
    previous = _load_runtime_json(state_path)
    current = _current_strategy_state(settings)
    watched_keys = [
        "overall_state",
        "target_asset_kind",
        "target_setup",
        "walkforward_status",
        "live_proof_status",
        "best_symbol",
        "best_setup_type",
        "best_action",
    ]
    if not previous:
        _store_runtime_json(state_path, current)
        return
    previous_ready = int(previous.get("ready_setups_count", 0) or 0)
    current_ready = int(current.get("ready_setups_count", 0) or 0)
    if previous_ready != current_ready:
        operator_alerts.send_message(_build_approved_lane_message(previous, current))
    previous_is_etf_trend = previous.get("target_asset_kind") == "etf" and previous.get("target_setup") == "etf_trend"
    current_is_etf_trend = current.get("target_asset_kind") == "etf" and current.get("target_setup") == "etf_trend"
    previous_pending = int(previous.get("pending_count", 0) or 0)
    current_pending = int(current.get("pending_count", 0) or 0)
    if current_is_etf_trend and current_pending > 0 and (not previous_is_etf_trend or previous_pending == 0):
        operator_alerts.send_message(_build_etf_trend_pending_message(previous, current))
    if any(previous.get(key) != current.get(key) for key in watched_keys):
        if operator_alerts.send_message(_build_state_change_message(previous, current)):
            _store_runtime_json(state_path, current)
        return
    _store_runtime_json(state_path, current)


def _build_status_reply(settings) -> str:
    with Session(engine) as db:
        latest_engine_run = db.scalar(select(EngineRun).order_by(EngineRun.completed_at.desc()).limit(1))
        pending_intents = db.scalar(
            select(func.count()).select_from(ExecutionIntent).where(ExecutionIntent.status == ExecutionIntentStatus.PENDING)
        )
        failed_intents = db.scalar(
            select(func.count()).select_from(ExecutionIntent).where(ExecutionIntent.status == ExecutionIntentStatus.FAILED)
        )
        open_positions = db.scalar(
            select(func.count()).select_from(Position).where(Position.status == PositionStatus.OPEN)
        )
        latest_signal = db.scalar(select(Signal).options(joinedload(Signal.asset)).order_by(Signal.created_at.desc()).limit(1))
    engine_status = latest_engine_run.status if latest_engine_run else "unknown"
    engine_time = latest_engine_run.completed_at.isoformat(timespec="seconds") if latest_engine_run else "n/a"
    latest_signal_line = "none yet"
    if latest_signal:
        latest_signal_line = (
            f"{latest_signal.asset.symbol} {latest_signal.action.value.upper()} "
            f"score {latest_signal.score:.2f}"
        )
    return "\n".join(
        [
            "Micro Trader status",
            f"engine: {engine_status} at {engine_time}",
            f"broker mode: {settings.broker_mode} / target: {settings.broker_execution_target}",
            f"live emergency stop: {'on' if settings.live_emergency_stop else 'off'}",
            f"open positions: {open_positions or 0}",
            f"pending intents: {pending_intents or 0} / failed intents: {failed_intents or 0}",
            f"latest signal: {latest_signal_line}",
        ]
    )


def _build_ping_reply(settings) -> str:
    with Session(engine) as db:
        latest_engine_run = db.scalar(select(EngineRun).order_by(EngineRun.completed_at.desc()).limit(1))
    if not latest_engine_run:
        return "pong\nengine: no completed cycle yet"
    return "\n".join(
        [
            "pong",
            f"engine: {latest_engine_run.status}",
            f"completed_at: {latest_engine_run.completed_at.isoformat(timespec='seconds')}",
            f"broker mode: {settings.broker_mode} / target: {settings.broker_execution_target}",
        ]
    )


def _build_last_error_reply() -> str:
    with Session(engine) as db:
        latest_engine_error = db.scalar(
            select(EngineRun).where(EngineRun.status == "error").order_by(EngineRun.completed_at.desc()).limit(1)
        )
        latest_failed_intent = db.scalar(
            select(ExecutionIntent)
            .options(joinedload(ExecutionIntent.asset))
            .where(ExecutionIntent.status == ExecutionIntentStatus.FAILED)
            .order_by(ExecutionIntent.updated_at.desc())
            .limit(1)
        )
    candidates: list[tuple[datetime, str]] = []
    if latest_engine_error:
        candidates.append(
            (
                latest_engine_error.completed_at,
                "\n".join(
                    [
                        "Latest operator error",
                        "source: engine_run",
                        f"at: {latest_engine_error.completed_at.isoformat(timespec='seconds')}",
                        f"status: {latest_engine_error.status}",
                        f"message: {latest_engine_error.message or 'Engine cycle failed without a saved message.'}",
                    ]
                ),
            )
        )
    if latest_failed_intent:
        asset_symbol = latest_failed_intent.asset.symbol if latest_failed_intent.asset else "unknown"
        candidates.append(
            (
                latest_failed_intent.updated_at,
                "\n".join(
                    [
                        "Latest operator error",
                        "source: execution_intent",
                        f"at: {latest_failed_intent.updated_at.isoformat(timespec='seconds')}",
                        f"asset: {asset_symbol}",
                        f"side: {latest_failed_intent.side.value}",
                        f"mode: {latest_failed_intent.mode} / target: {latest_failed_intent.execution_target}",
                        f"message: {latest_failed_intent.error_message or latest_failed_intent.reason}",
                    ]
                ),
            )
        )
    if not candidates:
        return "Latest operator error\nnone recorded yet"
    happened_at, message = max(candidates, key=lambda item: item[0])
    age_seconds = max(int((datetime.utcnow() - happened_at).total_seconds()), 0)
    age_hours = round(age_seconds / 3600, 1)
    if age_seconds >= 86400:
        age_days = round(age_seconds / 86400, 1)
        prefix = (
            "Latest operator error\n"
            f"stale historical error: {age_days} day(s) old\n"
            "no newer operator error has been recorded in the last 24h\n"
        )
        return prefix + message.removeprefix("Latest operator error\n")
    prefix = (
        "Latest operator error\n"
        f"recent error: {age_hours} hour(s) old\n"
    )
    return prefix + message.removeprefix("Latest operator error\n")


def _reply_to_telegram_command(settings, operator_alerts, command: str, chat_id: str) -> None:
    normalized = command.split()[0].split("@")[0].lower()
    logger.info("Processing Telegram command %s for chat %s", normalized, chat_id)
    if normalized in {"/start", "/help"}:
        sent = operator_alerts.send_message(
            "Micro Trader operator bot is live.\n"
            "Commands:\n"
            "/ping - lightweight worker heartbeat\n"
            "/status - current operator snapshot\n"
            "/lasterror - latest worker or execution failure\n"
            "/testalert - send a direct bot-path test reply\n"
            "/help - show this help",
            chat_id=chat_id,
        )
        if not sent:
            logger.warning("Telegram reply failed for %s to chat %s", normalized, chat_id)
        return
    if normalized == "/ping":
        sent = operator_alerts.send_message(_build_ping_reply(settings), chat_id=chat_id)
        if not sent:
            logger.warning("Telegram reply failed for %s to chat %s", normalized, chat_id)
        return
    if normalized == "/status":
        sent = operator_alerts.send_message(_build_status_reply(settings), chat_id=chat_id)
        if not sent:
            logger.warning("Telegram reply failed for %s to chat %s", normalized, chat_id)
        return
    if normalized == "/lasterror":
        sent = operator_alerts.send_message(_build_last_error_reply(), chat_id=chat_id)
        if not sent:
            logger.warning("Telegram reply failed for %s to chat %s", normalized, chat_id)
        return
    if normalized == "/testalert":
        sent = operator_alerts.send_message(
            "Micro Trader Telegram command path is working from the VM.",
            chat_id=chat_id,
        )
        if not sent:
            logger.warning("Telegram reply failed for %s to chat %s", normalized, chat_id)
        return
    sent = operator_alerts.send_message(
        "Unknown command. Try /ping, /status, /lasterror, /testalert, or /help.",
        chat_id=chat_id,
    )
    if not sent:
        logger.warning("Telegram reply failed for %s to chat %s", normalized, chat_id)


def _process_telegram_commands(settings, operator_alerts) -> None:
    if (
        settings.operator_alert_transport.strip().lower() != "telegram"
        or not settings.operator_alert_telegram_poll_enabled
        or not settings.operator_alert_telegram_bot_token
    ):
        return
    last_offset = _load_telegram_offset(settings)
    if last_offset is None:
        backlog = operator_alerts.fetch_telegram_updates(limit=25)
        if backlog:
            latest_seen = max(int(item.get("update_id", 0)) for item in backlog)
            if latest_seen:
                _store_telegram_offset(settings, latest_seen)
        return
    updates = operator_alerts.fetch_telegram_updates(offset=last_offset + 1, limit=25)
    if not updates:
        return
    logger.info("Fetched %s Telegram update(s) starting at offset %s", len(updates), last_offset + 1)
    latest_seen = last_offset
    for update in updates:
        update_id = int(update.get("update_id", 0))
        latest_seen = max(latest_seen, update_id)
        message = update.get("message") or update.get("edited_message") or {}
        text = (message.get("text") or "").strip()
        chat_id = str(message.get("chat", {}).get("id") or "").strip()
        if not text.startswith("/") or not chat_id:
            continue
        if settings.operator_alert_telegram_chat_id and chat_id != settings.operator_alert_telegram_chat_id:
            logger.info("Ignoring Telegram command from unauthorized chat %s", chat_id)
            continue
        _reply_to_telegram_command(settings, operator_alerts, text, chat_id)
    _store_telegram_offset(settings, latest_seen)
    logger.info("Stored Telegram offset %s", latest_seen)


def main() -> None:
    settings = get_settings()
    operator_alerts = build_operator_alert_service(settings)
    Base.metadata.create_all(bind=engine)
    ensure_asset_kind_enum()
    ensure_signal_outcome_schema()
    ensure_simulation_schema()
    ensure_provider_health_schema()
    ensure_state_event_schema()
    next_engine_run_at = 0.0
    next_telegram_poll_at = 0.0
    telegram_poll_interval = max(5, settings.operator_alert_telegram_poll_interval_seconds)
    while True:
        now = time.monotonic()
        if now >= next_engine_run_at:
            try:
                with Session(engine) as db:
                    seed_assets(db, settings.watchlist, settings.etf_watchlist, settings.stock_watchlist)
                    result = run_engine_cycle(db, settings)
                    logger.info("Engine cycle complete: %s", result)
                _emit_daily_summary_if_due(settings, operator_alerts)
                _emit_strategy_state_change_if_needed(settings, operator_alerts)
            except Exception:
                logger.exception("Engine cycle failed")
                operator_alerts.emit(
                    event_type="worker_failure",
                    severity="danger",
                    title="Worker cycle failed",
                    message="Micro Trader worker cycle failed. Check VM logs and the latest engine run traceback immediately.",
                    details={
                        "mode": settings.broker_mode,
                        "execution_target": settings.broker_execution_target,
                    },
                )
                with Session(engine) as db:
                    db.add(
                        EngineRun(
                            status="error",
                            assets_count=0,
                            news_items_count=0,
                            signals_count=0,
                            message="Engine cycle failed. Check worker logs for traceback.",
                        )
                    )
                    db.commit()
            next_engine_run_at = time.monotonic() + settings.worker_interval_seconds
        now = time.monotonic()
        if now >= next_telegram_poll_at:
            try:
                _process_telegram_commands(settings, operator_alerts)
            except Exception:
                logger.exception("Telegram operator command poll failed")
            next_telegram_poll_at = time.monotonic() + telegram_poll_interval
        sleep_for = min(
            max(0.5, next_engine_run_at - time.monotonic()),
            max(0.5, next_telegram_poll_at - time.monotonic()),
        )
        time.sleep(sleep_for)


if __name__ == "__main__":
    main()
