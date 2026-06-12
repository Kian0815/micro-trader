from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import httpx

from app.config import Settings


@dataclass
class OperatorAlertStatus:
    configured: bool
    webhook_enabled: bool
    transport: str
    supported_transports: list[str]
    events: list[str]
    message: str


class OperatorAlertService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def status(self) -> OperatorAlertStatus:
        transport = self.settings.operator_alert_transport.strip().lower()
        events = sorted(self.settings.operator_alert_events)
        configured = self._transport_ready(transport)
        if configured:
            return OperatorAlertStatus(
                configured=True,
                webhook_enabled=transport != "none",
                transport=transport,
                supported_transports=self.settings.supported_operator_alert_transports,
                events=events,
                message=self._configured_message(transport),
            )
        return OperatorAlertStatus(
            configured=False,
            webhook_enabled=False,
            transport=transport,
            supported_transports=self.settings.supported_operator_alert_transports,
            events=events,
            message=self._missing_message(transport),
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
        transport = self.settings.operator_alert_transport.strip().lower()
        if not self._transport_ready(transport):
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
            if transport == "telegram":
                return self._send_telegram(payload)
            return self._send_webhook_like(transport, payload)
        except Exception:
            return False

    def _transport_ready(self, transport: str) -> bool:
        if transport == "telegram":
            return bool(self.settings.operator_alert_telegram_bot_token and self.settings.operator_alert_telegram_chat_id)
        if transport == "webhook":
            return bool(self.settings.operator_alert_webhook_url)
        if transport == "slack":
            return bool(self.settings.operator_alert_slack_webhook_url)
        if transport == "discord":
            return bool(self.settings.operator_alert_discord_webhook_url)
        if transport == "whatsapp_bridge":
            return bool(self.settings.operator_alert_whatsapp_bridge_url)
        if transport == "signal_bridge":
            return bool(self.settings.operator_alert_signal_bridge_url)
        return False

    def _configured_message(self, transport: str) -> str:
        messages = {
            "telegram": "Telegram alert transport is configured for operator notifications.",
            "webhook": "Generic webhook alert transport is configured for operator notifications.",
            "slack": "Slack webhook alert transport is configured for operator notifications.",
            "discord": "Discord webhook alert transport is configured for operator notifications.",
            "whatsapp_bridge": "WhatsApp bridge webhook is configured for operator notifications.",
            "signal_bridge": "Signal bridge webhook is configured for operator notifications.",
        }
        return messages.get(transport, "Operator alert transport is configured.")

    def _missing_message(self, transport: str) -> str:
        messages = {
            "telegram": "Telegram transport is selected but the bot token or chat id is missing.",
            "webhook": "Generic webhook transport is selected but OPERATOR_ALERT_WEBHOOK_URL is missing.",
            "slack": "Slack transport is selected but OPERATOR_ALERT_SLACK_WEBHOOK_URL is missing.",
            "discord": "Discord transport is selected but OPERATOR_ALERT_DISCORD_WEBHOOK_URL is missing.",
            "whatsapp_bridge": "WhatsApp bridge is selected but OPERATOR_ALERT_WHATSAPP_BRIDGE_URL is missing.",
            "signal_bridge": "Signal bridge is selected but OPERATOR_ALERT_SIGNAL_BRIDGE_URL is missing.",
        }
        return messages.get(transport, "No operator alert transport is configured yet.")

    def _send_webhook_like(self, transport: str, payload: dict) -> bool:
        url_map = {
            "webhook": self.settings.operator_alert_webhook_url,
            "slack": self.settings.operator_alert_slack_webhook_url,
            "discord": self.settings.operator_alert_discord_webhook_url,
            "whatsapp_bridge": self.settings.operator_alert_whatsapp_bridge_url,
            "signal_bridge": self.settings.operator_alert_signal_bridge_url,
        }
        url = url_map.get(transport, "")
        if not url:
            return False
        body = payload
        if transport == "slack":
            body = {"text": f"[{payload['severity']}] {payload['title']}\n{payload['message']}"}
        elif transport == "discord":
            body = {"content": f"**{payload['title']}**\n{payload['message']}"}
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=body)
            response.raise_for_status()
        return True

    def _send_telegram(self, payload: dict) -> bool:
        url = (
            f"https://api.telegram.org/bot{self.settings.operator_alert_telegram_bot_token}/sendMessage"
        )
        text = (
            f"[{payload['severity'].upper()}] {payload['title']}\n"
            f"{payload['message']}\n"
            f"event={payload['event_type']}"
        )
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                url,
                json={
                    "chat_id": self.settings.operator_alert_telegram_chat_id,
                    "text": text,
                },
            )
            response.raise_for_status()
        return True


def build_operator_alert_service(settings: Settings) -> OperatorAlertService:
    return OperatorAlertService(settings)
