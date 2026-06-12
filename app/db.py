from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_asset_kind_enum() -> None:
    with engine.begin() as connection:
        connection.execute(text("ALTER TYPE assetkind ADD VALUE IF NOT EXISTS 'ETF'"))
        connection.execute(text("ALTER TYPE assetkind ADD VALUE IF NOT EXISTS 'STOCK'"))


def ensure_signal_outcome_schema() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE signal_outcome_snapshots "
                "ADD COLUMN IF NOT EXISTS market_move_pct DOUBLE PRECISION"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE signal_outcome_snapshots "
                "ADD COLUMN IF NOT EXISTS decision_edge_pct DOUBLE PRECISION"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE signal_outcome_snapshots "
                "ADD COLUMN IF NOT EXISTS outcome_label VARCHAR(32) DEFAULT ''"
            )
        )


def ensure_simulation_schema() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE strategy_simulations "
                "ADD COLUMN IF NOT EXISTS scenario_key VARCHAR(32) DEFAULT 'sim_100'"
            )
        )


def ensure_execution_audit_schema() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE trades "
                "ADD COLUMN IF NOT EXISTS execution_target VARCHAR(16) DEFAULT 'internal'"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE strategy_simulations "
                "ADD COLUMN IF NOT EXISTS scenario_label VARCHAR(64) DEFAULT 'EUR 100'"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE strategy_simulations "
                "ADD COLUMN IF NOT EXISTS setup_type VARCHAR(32) DEFAULT 'balanced'"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE strategy_simulations "
                "ADD COLUMN IF NOT EXISTS opened_signal_score DOUBLE PRECISION DEFAULT 0"
            )
        )


def ensure_provider_health_schema() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE provider_health_samples "
                "ALTER COLUMN provider TYPE VARCHAR(128)"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE provider_health_samples "
                "ADD COLUMN IF NOT EXISTS cache_used BOOLEAN DEFAULT FALSE"
            )
        )


def ensure_state_event_schema() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE state_events "
                "ALTER COLUMN fingerprint TYPE VARCHAR(255)"
            )
        )
