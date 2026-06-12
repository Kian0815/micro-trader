import logging
import time

from sqlalchemy.orm import Session

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
from app.models import EngineRun


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
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
        time.sleep(settings.worker_interval_seconds)


if __name__ == "__main__":
    main()
