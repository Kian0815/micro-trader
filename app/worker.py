from pathlib import Path
import logging
import time
from datetime import datetime

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
from app.models import EngineRun, ExecutionIntent, ExecutionIntentStatus, Position, PositionStatus, Signal
from app.services.operator_alerts import build_operator_alert_service


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _telegram_offset_path(settings) -> Path:
    return Path(settings.operator_alert_telegram_offset_path)


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
