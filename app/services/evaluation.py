from dataclasses import asdict, dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Signal, SignalOutcomeSnapshot
from app.services.strategy import StrategyEngine, extract_news_count, extract_setup_type


@dataclass
class SetupScorecardRow:
    asset_kind: str
    setup_type: str
    approval_status: str
    sample_count: int
    resolved_4h: int
    resolved_24h: int
    win_rate_pct: float
    avg_pnl_pct: float
    net_expectancy_pct: float
    avg_market_move_pct: float
    avg_decision_edge_pct: float
    false_positive_rate_pct: float
    missed_upside_rate_pct: float
    safe_hold_rate_pct: float
    dominant_label: str
    note: str
    latest_outcome_at: datetime | None


@dataclass
class SetupScorecardReport:
    generated_at: datetime
    total_resolved: int
    approved_count: int
    watch_count: int
    disabled_count: int
    rows: list[SetupScorecardRow]

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "total_resolved": self.total_resolved,
            "approved_count": self.approved_count,
            "watch_count": self.watch_count,
            "disabled_count": self.disabled_count,
            "rows": [asdict(row) for row in self.rows],
        }


class StrategyProofService:
    def __init__(self, strategy_engine: StrategyEngine) -> None:
        self.strategy_engine = strategy_engine
        self.cost_haircut_pct = {
            "etf": 0.08,
            "stock": 0.12,
            "crypto": 0.20,
        }

    def build_scorecard(self, db: Session) -> SetupScorecardReport:
        rows = db.scalars(
            select(SignalOutcomeSnapshot)
            .options(joinedload(SignalOutcomeSnapshot.signal).joinedload(Signal.asset))
            .where(
                SignalOutcomeSnapshot.outcome_status == "resolved",
                SignalOutcomeSnapshot.pnl_pct.is_not(None),
                SignalOutcomeSnapshot.horizon_hours.in_((4, 24)),
            )
            .order_by(SignalOutcomeSnapshot.updated_at.desc())
            .limit(5000)
        ).all()

        grouped: dict[tuple[str, str], list[SignalOutcomeSnapshot]] = {}
        for row in rows:
            signal = row.signal
            asset = signal.asset if signal else None
            if not signal or not asset:
                continue
            setup_type = extract_setup_type(signal.rationale) or self.strategy_engine.classify_setup_type_for_signal(
                asset.kind.value,
                signal.score,
                signal.sentiment_score,
                signal.momentum_score,
                extract_news_count(signal.rationale),
            )
            if not self._signal_matches_setup(signal.action.value, setup_type):
                continue
            grouped.setdefault((asset.kind.value, setup_type), []).append(row)

        scorecards = [
            self._summarize_bucket(asset_kind, setup_type, bucket)
            for (asset_kind, setup_type), bucket in grouped.items()
        ]
        scorecards.sort(
            key=lambda row: (
                self._status_rank(row.approval_status),
                -row.net_expectancy_pct,
                -row.sample_count,
                row.asset_kind,
                row.setup_type,
            )
        )
        return SetupScorecardReport(
            generated_at=datetime.utcnow(),
            total_resolved=len(rows),
            approved_count=sum(1 for row in scorecards if row.approval_status == "approved"),
            watch_count=sum(1 for row in scorecards if row.approval_status == "watch"),
            disabled_count=sum(1 for row in scorecards if row.approval_status == "disabled"),
            rows=scorecards,
        )

    def approval_map(self, db: Session) -> dict[tuple[str, str], SetupScorecardRow]:
        report = self.build_scorecard(db)
        return {
            (row.asset_kind, row.setup_type): row
            for row in report.rows
        }

    def evaluate_signal(self, db: Session, signal: Signal) -> tuple[str, str, str]:
        asset = signal.asset
        if not asset:
            return "disabled", extract_setup_type(signal.rationale) or "unknown", "Signal has no linked asset."
        setup_type = extract_setup_type(signal.rationale) or self.strategy_engine.classify_setup_type_for_signal(
            asset.kind.value,
            signal.score,
            signal.sentiment_score,
            signal.momentum_score,
            extract_news_count(signal.rationale),
        )
        row = self.approval_map(db).get((asset.kind.value, setup_type))
        if not row:
            return "watch", setup_type, "No resolved setup evidence yet."
        return row.approval_status, setup_type, row.note

    def _summarize_bucket(
        self,
        asset_kind: str,
        setup_type: str,
        rows: list[SignalOutcomeSnapshot],
    ) -> SetupScorecardRow:
        weighted_count = 0.0
        weighted_wins = 0.0
        weighted_pnl = 0.0
        weighted_net_pnl = 0.0
        weighted_market_move = 0.0
        weighted_decision_edge = 0.0
        false_positive = 0.0
        missed_upside = 0.0
        safe_hold = 0.0
        label_weights: dict[str, float] = {}
        resolved_4h = 0
        resolved_24h = 0
        latest_outcome_at: datetime | None = None
        cost_haircut_pct = self.cost_haircut_pct.get(asset_kind, 0.10)

        for row in rows:
            if row.pnl_pct is None:
                continue
            weight = {4: 1.0, 24: 1.35}.get(row.horizon_hours, 0.0)
            if weight <= 0:
                continue
            weighted_count += weight
            weighted_pnl += row.pnl_pct * weight
            net_pnl = row.pnl_pct - cost_haircut_pct
            weighted_net_pnl += net_pnl * weight
            if net_pnl > 0:
                weighted_wins += weight
            weighted_market_move += (row.market_move_pct or 0.0) * weight
            weighted_decision_edge += (row.decision_edge_pct or 0.0) * weight
            if row.horizon_hours == 4:
                resolved_4h += 1
            elif row.horizon_hours == 24:
                resolved_24h += 1
            if row.updated_at and (latest_outcome_at is None or row.updated_at > latest_outcome_at):
                latest_outcome_at = row.updated_at

            label = row.outcome_label or "none"
            label_weights[label] = label_weights.get(label, 0.0) + weight
            if label == "missed-upside":
                missed_upside += weight
            if label in {"protected-downside", "flat-safe"}:
                safe_hold += weight
            if setup_type in {"etf_pullback", "stock_event"} and (row.market_move_pct or 0.0) <= 0.10:
                false_positive += weight

        sample_count = int(round(weighted_count))
        avg_pnl_pct = round(weighted_pnl / weighted_count, 3) if weighted_count else 0.0
        net_expectancy_pct = round(weighted_net_pnl / weighted_count, 3) if weighted_count else 0.0
        win_rate_pct = round((weighted_wins / weighted_count) * 100, 2) if weighted_count else 0.0
        avg_market_move_pct = round(weighted_market_move / weighted_count, 3) if weighted_count else 0.0
        avg_decision_edge_pct = round(weighted_decision_edge / weighted_count, 3) if weighted_count else 0.0
        false_positive_rate_pct = round((false_positive / weighted_count) * 100, 2) if weighted_count else 0.0
        missed_upside_rate_pct = round((missed_upside / weighted_count) * 100, 2) if weighted_count else 0.0
        safe_hold_rate_pct = round((safe_hold / weighted_count) * 100, 2) if weighted_count else 0.0
        dominant_label = max(label_weights.items(), key=lambda item: item[1])[0] if label_weights else "none"

        approval_status, note = self._approval_decision(
            asset_kind=asset_kind,
            setup_type=setup_type,
            sample_count=sample_count,
            win_rate_pct=win_rate_pct,
            net_expectancy_pct=net_expectancy_pct,
            avg_market_move_pct=avg_market_move_pct,
            false_positive_rate_pct=false_positive_rate_pct,
            safe_hold_rate_pct=safe_hold_rate_pct,
            missed_upside_rate_pct=missed_upside_rate_pct,
            dominant_label=dominant_label,
        )

        return SetupScorecardRow(
            asset_kind=asset_kind,
            setup_type=setup_type,
            approval_status=approval_status,
            sample_count=sample_count,
            resolved_4h=resolved_4h,
            resolved_24h=resolved_24h,
            win_rate_pct=win_rate_pct,
            avg_pnl_pct=avg_pnl_pct,
            net_expectancy_pct=net_expectancy_pct,
            avg_market_move_pct=avg_market_move_pct,
            avg_decision_edge_pct=avg_decision_edge_pct,
            false_positive_rate_pct=false_positive_rate_pct,
            missed_upside_rate_pct=missed_upside_rate_pct,
            safe_hold_rate_pct=safe_hold_rate_pct,
            dominant_label=dominant_label,
            note=note,
            latest_outcome_at=latest_outcome_at,
        )

    def _approval_decision(
        self,
        *,
        asset_kind: str,
        setup_type: str,
        sample_count: int,
        win_rate_pct: float,
        net_expectancy_pct: float,
        avg_market_move_pct: float,
        false_positive_rate_pct: float,
        safe_hold_rate_pct: float,
        missed_upside_rate_pct: float,
        dominant_label: str,
    ) -> tuple[str, str]:
        if setup_type.endswith("risk_off"):
            return "disabled", "Defensive risk-off setup. Useful for exits, not for unattended new entries."
        if sample_count < 4:
            return "watch", f"Too little resolved evidence yet ({sample_count} weighted samples)."
        if net_expectancy_pct < 0 or false_positive_rate_pct >= 45.0:
            return "disabled", (
                f"Negative net expectancy ({net_expectancy_pct:.2f}%) or too many weak follow-through outcomes "
                f"({false_positive_rate_pct:.0f}% false positives)."
            )
        if safe_hold_rate_pct >= 70.0 and avg_market_move_pct <= 0.12:
            return "disabled", "History says this setup protects capital better than it creates upside."
        if (
            sample_count >= 6
            and win_rate_pct >= 55.0
            and net_expectancy_pct >= 0.15
            and false_positive_rate_pct < 35.0
        ):
            return "approved", (
                f"Cleared unattended thresholds with {win_rate_pct:.0f}% win rate and "
                f"{net_expectancy_pct:.2f}% net expectancy."
            )
        return "watch", (
            f"Mixed evidence so far. Dominant label {dominant_label}, missed upside {missed_upside_rate_pct:.0f}%, "
            f"net expectancy {net_expectancy_pct:.2f}%."
        )

    def _status_rank(self, status: str) -> int:
        return {"approved": 0, "watch": 1, "disabled": 2}.get(status, 3)

    def _signal_matches_setup(self, action: str, setup_type: str) -> bool:
        if setup_type.endswith("risk_off"):
            return action == "sell"
        return action == "buy"
