import hashlib
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StateEvent


class StateEventService:
    def _compact_fingerprint(self, fingerprint: str) -> str:
        if len(fingerprint) <= 255:
            return fingerprint
        digest = hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()[:12]
        return f"{fingerprint[:242]}:{digest}"

    def list_recent(self, db: Session, limit: int = 20) -> list[StateEvent]:
        return db.scalars(
            select(StateEvent)
            .order_by(StateEvent.created_at.desc())
            .limit(limit)
        ).all()

    def latest_for_key(self, db: Session, event_key: str) -> StateEvent | None:
        return db.scalar(
            select(StateEvent)
            .where(StateEvent.event_key == event_key)
            .order_by(StateEvent.created_at.desc())
            .limit(1)
        )

    def record_change(
        self,
        db: Session,
        *,
        event_key: str,
        category: str,
        severity: str,
        title: str,
        message: str,
        fingerprint: str,
    ) -> StateEvent | None:
        fingerprint = self._compact_fingerprint(fingerprint)
        latest = db.scalar(
            select(StateEvent)
            .where(StateEvent.event_key == event_key)
            .order_by(StateEvent.created_at.desc())
            .limit(1)
        )
        if latest and latest.fingerprint == fingerprint:
            return None

        event = StateEvent(
            event_key=event_key,
            category=category,
            severity=severity,
            title=title,
            message=message,
            fingerprint=fingerprint,
            created_at=datetime.utcnow(),
        )
        db.add(event)
        db.flush()
        return event
