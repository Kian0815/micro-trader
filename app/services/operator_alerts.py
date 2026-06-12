from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import httpx

from app.config import Settings


@dataclass
class OperatorAlertStatus:
    configured: bool
    webhook_enabled: bool
    events: list[str]
    message: str


class OperatorAlertService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def status(self) -> OperatorAlertStatus:
        configured = bool(self.settings.operator_alert_webhook_url)
        events = sorted(self.settings.operator_alert_events)
        if configured:
            return OperatorAlertStatus(
                configured=True,
                webhook_enabled=True,
                events=events,
                message="Webhook alert transport is configured for operator notifications.",
            )
        return OperatorAlertStatus(
            configured=False,
            webhook_enabled=False,
            events=events,
            message="No operator alert webhook is configured yet.",
        )

    def emit(
        self,
        *,
        event_type: str,
        severity: str,
        title: str,
        message: str,
        details: dict | None = None,
    ) -> bool:
        if event_type not in self.settings.operator_alert_events:
            return False
        if not self.settings.operator_alert_webhook_url:
            return False

        payload = {
            "source": "micro-trader",
            "event_type": event_type,
            "severity": severity,
            "title": title,
            "message": message,
            "details": details or {},
            "sent_at": datetime.utcnow().isoformat() + "Z",
        }
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(self.settings.operator_alert_webhook_url, json=payload)
                response.raise_for_status()
            return True
        except Exception:
            return False


def build_operator_alert_service(settings: Settings) -> OperatorAlertService:
    return OperatorAlertService(settings)
