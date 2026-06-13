from pathlib import Path
import logging
import time

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


def _reply_to_telegram_command(settings, operator_alerts, command: str, chat_id: str) -> None:
    normalized = command.split()[0].split("@")[0].lower()
    if normalized in {"/start", "/help"}:
        operator_alerts.send_message(
            "Micro Trader operator bot is live.\n"
            "Commands:\n"
            "/status - current operator snapshot\n"
            "/testalert - send a direct bot-path test reply\n"
            "/help - show this help",
            chat_id=chat_id,
        )
        return
    if normalized == "/status":
        operator_alerts.send_message(_build_status_reply(settings), chat_id=chat_id)
        return
    if normalized == "/testalert":
        operator_alerts.send_message(
            "Micro Trader Telegram command path is working from the VM.",
            chat_id=chat_id,
        )
        return
    operator_alerts.send_message(
        "Unknown command. Try /status, /testalert, or /help.",
        chat_id=chat_id,
    )


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
            continue
        _reply_to_telegram_command(settings, operator_alerts, text, chat_id)
    _store_telegram_offset(settings, latest_seen)


def main() -> None:
    settings = get_settings()
    operator_alerts = build_operator_alert_service(settings)
    Base.metadata.create_all(bind=engine)
    ensure_asset_kind_enum()
    ensure_signal_outcome_schema()
    ensure_simulation_schema()
    ensure_provider_health_schema()
    ensure_state_event_schema()
    while True:
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
        try:
            _process_telegram_commands(settings, operator_alerts)
        except Exception:
            logger.exception("Telegram operator command poll failed")
        time.sleep(settings.worker_interval_seconds)


if __name__ == "__main__":
    main()
