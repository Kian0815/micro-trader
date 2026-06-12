from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Asset, AssetKind, MarketTick, Position, PositionStatus, Signal, SignalAction
from app.services.backtesting import WalkForwardAnalysisService
from app.services.evaluation import StrategyProofService
from app.services.strategy import extract_setup_type


@dataclass
class OpportunityCandidate:
    asset_id: int
    symbol: str
    asset_kind: str
    action: str
    score: float
    setup_type: str
    approval_status: str
    approval_note: str
    proof_sample_count: int
    net_expectancy_pct: float
    walkforward_recommendation: str
    live_proof_status: str
    live_sample_count: int
    replay_sample_count: int
    test_net_expectancy_pct: float
    test_decision_edge_pct: float
    momentum_score: float
    sentiment_score: float
    signal_age_seconds: int
    tick_age_seconds: int | None
    price: float | None
    market_open: bool
    universe_enabled: bool
    setup_allowed: bool
    has_open_position: bool
    fresh_tick: bool
    eligible_for_unattended: bool
    blocked_reason: str | None
    setup_quality_score: float
    rank_score: float
    created_at: datetime
    rationale: str

    def to_dict(self) -> dict:
        return asdict(self)


class BestOpportunitySelector:
    def __init__(
        self,
        proof_service: StrategyProofService,
        walkforward_service: WalkForwardAnalysisService,
        max_signal_age_seconds: int = 900,
        max_tick_age_seconds: int = 900,
        allowed_asset_kinds: set[str] | None = None,
        allowed_setup_statuses: set[str] | None = None,
    ) -> None:
        self.proof_service = proof_service
        self.walkforward_service = walkforward_service
        self.max_signal_age_seconds = max_signal_age_seconds
        self.max_tick_age_seconds = max_tick_age_seconds
        self.allowed_asset_kinds = allowed_asset_kinds or {"etf", "stock", "crypto"}
        self.allowed_setup_statuses = allowed_setup_statuses or {"approved"}

    def best_candidate(self, db: Session, signals: list[Signal] | None = None) -> OpportunityCandidate | None:
        candidates = self.candidates(db, signals=signals)
        return candidates[0] if candidates else None

    def best_eligible_candidate(self, db: Session, signals: list[Signal] | None = None) -> OpportunityCandidate | None:
        for candidate in self.candidates(db, signals=signals):
            if candidate.eligible_for_unattended:
                return candidate
        return None

    def candidates(self, db: Session, signals: list[Signal] | None = None, limit: int = 12) -> list[OpportunityCandidate]:
        fresh_signals = self._recent_entry_signals(db, signals=signals, limit=limit)
        if not fresh_signals:
            return []

        approval_map = self.proof_service.approval_map(db)
        walkforward_report = self.walkforward_service.build_report(db)
        walkforward_map = {
            (row.asset_kind, row.setup_type): row
            for row in walkforward_report.rows
        }
        asset_ids = [signal.asset_id for signal in fresh_signals]
        latest_ticks = self._latest_ticks(db, asset_ids)
        open_positions = set(
            db.scalars(
                select(Position.asset_id).where(
                    Position.asset_id.in_(asset_ids),
                    Position.status == PositionStatus.OPEN,
                )
            ).all()
        )

        candidates: list[OpportunityCandidate] = []
        for signal in fresh_signals:
            asset = signal.asset
            if not asset:
                continue
            setup_type = extract_setup_type(signal.rationale) or "unknown"
            approval_row = approval_map.get((asset.kind.value, setup_type))
            approval_status = getattr(approval_row, "approval_status", "watch")
            approval_note = getattr(approval_row, "note", "No resolved setup evidence yet.")
            proof_sample_count = int(getattr(approval_row, "sample_count", 0) or 0)
            net_expectancy_pct = float(getattr(approval_row, "net_expectancy_pct", 0.0) or 0.0)
            walkforward_row = walkforward_map.get((asset.kind.value, setup_type))
            walkforward_recommendation = getattr(walkforward_row, "recommendation", "watch")
            live_proof_status = getattr(walkforward_row, "live_proof_status", "research")
            live_sample_count = int(getattr(walkforward_row, "live_sample_count", 0) or 0)
            replay_sample_count = int(getattr(walkforward_row, "replay_sample_count", 0) or 0)
            test_slice = getattr(walkforward_row, "test", None)
            test_net_expectancy_pct = float(getattr(test_slice, "net_expectancy_pct", 0.0) or 0.0)
            test_decision_edge_pct = float(getattr(test_slice, "avg_decision_edge_pct", 0.0) or 0.0)
            tick = latest_ticks.get(signal.asset_id)
            tick_age_seconds = self._tick_age_seconds(tick)
            fresh_tick = tick_age_seconds is not None and tick_age_seconds <= self.max_tick_age_seconds
            market_open = self._market_open(asset.kind)
            universe_enabled = asset.kind.value in self.allowed_asset_kinds
            setup_allowed = (
                approval_status in self.allowed_setup_statuses
                and walkforward_recommendation in self.allowed_setup_statuses
                and live_proof_status == "cleared"
            )
            has_open_position = signal.asset_id in open_positions
            setup_quality_score = self._setup_quality_score(
                approval_status=approval_status,
                walkforward_recommendation=walkforward_recommendation,
                live_proof_status=live_proof_status,
                proof_sample_count=proof_sample_count,
                live_sample_count=live_sample_count,
                net_expectancy_pct=net_expectancy_pct,
                test_net_expectancy_pct=test_net_expectancy_pct,
                test_decision_edge_pct=test_decision_edge_pct,
            )
            blocked_reason = self._blocked_reason(
                signal=signal,
                asset=asset,
                setup_type=setup_type,
                approval_status=approval_status,
                approval_note=approval_note,
                walkforward_recommendation=walkforward_recommendation,
                live_proof_status=live_proof_status,
                universe_enabled=universe_enabled,
                setup_allowed=setup_allowed,
                market_open=market_open,
                fresh_tick=fresh_tick,
                has_open_position=has_open_position,
            )
            eligible_for_unattended = blocked_reason is None
            candidates.append(
                OpportunityCandidate(
                    asset_id=signal.asset_id,
                    symbol=asset.symbol,
                    asset_kind=asset.kind.value,
                    action=signal.action.value,
                    score=float(signal.score),
                    setup_type=setup_type,
                    approval_status=approval_status,
                    approval_note=approval_note,
                    proof_sample_count=proof_sample_count,
                    net_expectancy_pct=net_expectancy_pct,
                    walkforward_recommendation=walkforward_recommendation,
                    live_proof_status=live_proof_status,
                    live_sample_count=live_sample_count,
                    replay_sample_count=replay_sample_count,
                    test_net_expectancy_pct=test_net_expectancy_pct,
                    test_decision_edge_pct=test_decision_edge_pct,
                    momentum_score=float(signal.momentum_score),
                    sentiment_score=float(signal.sentiment_score),
                    signal_age_seconds=int(max((datetime.utcnow() - signal.created_at).total_seconds(), 0)),
                    tick_age_seconds=tick_age_seconds,
                    price=float(tick.price) if tick else None,
                    market_open=market_open,
                    universe_enabled=universe_enabled,
                    setup_allowed=setup_allowed,
                    has_open_position=has_open_position,
                    fresh_tick=fresh_tick,
                    eligible_for_unattended=eligible_for_unattended,
                    blocked_reason=blocked_reason,
                    setup_quality_score=setup_quality_score,
                    rank_score=self._rank_score(
                        signal=signal,
                        setup_type=setup_type,
                        approval_status=approval_status,
                        walkforward_recommendation=walkforward_recommendation,
                        live_proof_status=live_proof_status,
                        net_expectancy_pct=net_expectancy_pct,
                        test_net_expectancy_pct=test_net_expectancy_pct,
                        test_decision_edge_pct=test_decision_edge_pct,
                        proof_sample_count=proof_sample_count,
                        live_sample_count=live_sample_count,
                        setup_quality_score=setup_quality_score,
                        eligible_for_unattended=eligible_for_unattended,
                    ),
                    created_at=signal.created_at,
                    rationale=signal.rationale,
                )
            )

        candidates.sort(
            key=lambda item: (
                0 if item.eligible_for_unattended else 1,
                -item.rank_score,
                -item.score,
                item.signal_age_seconds,
                item.symbol,
            )
        )
        return candidates

    def summary(self, db: Session, signals: list[Signal] | None = None) -> dict:
        candidates = self.candidates(db, signals=signals)
        regime_signals = self._recent_regime_signals(db, signals=signals, limit=12)
        best = candidates[0] if candidates else None
        best_eligible = next((item for item in candidates if item.eligible_for_unattended), None)
        best_building_live = next(
            (
                item for item in candidates
                if item.live_proof_status == "building_live"
            ),
            None,
        )
        regime_transition = self._etf_regime_transition(regime_signals)
        return {
            "allowed_asset_kinds": sorted(self.allowed_asset_kinds),
            "allowed_setup_statuses": sorted(self.allowed_setup_statuses),
            "best": best.to_dict() if best else None,
            "best_eligible": best_eligible.to_dict() if best_eligible else None,
            "best_building_live": best_building_live.to_dict() if best_building_live else None,
            "regime_transition": regime_transition,
            "candidate_count": len(candidates),
            "top_candidates": [item.to_dict() for item in candidates[:5]],
        }

    def _recent_entry_signals(self, db: Session, signals: list[Signal] | None, limit: int) -> list[Signal]:
        freshness_cutoff = datetime.utcnow() - timedelta(seconds=self.max_signal_age_seconds)
        if signals is not None:
            filtered = [
                signal
                for signal in signals
                if signal.created_at >= freshness_cutoff
                and signal.asset
                and (
                    signal.action == SignalAction.BUY
                    or (
                        signal.action == SignalAction.HOLD
                        and self._is_entry_setup(extract_setup_type(signal.rationale) or "")
                    )
                )
            ]
            filtered = self._dedupe_by_asset(filtered)
            filtered.sort(
                key=lambda item: (
                    0 if item.action == SignalAction.BUY else 1,
                    item.score,
                    item.created_at,
                ),
                reverse=True,
            )
            return filtered[:limit]
        rows = db.scalars(
            select(Signal)
            .options(joinedload(Signal.asset))
            .join(Asset, Asset.id == Signal.asset_id)
            .where(Signal.created_at >= freshness_cutoff)
            .order_by(Signal.created_at.desc())
            .limit(limit * 4)
        ).all()
        filtered = [
            signal
            for signal in rows
            if signal.action == SignalAction.BUY
            or (
                signal.action == SignalAction.HOLD
                and self._is_entry_setup(extract_setup_type(signal.rationale) or "")
            )
        ]
        filtered = self._dedupe_by_asset(filtered)
        filtered.sort(
            key=lambda item: (
                0 if item.action == SignalAction.BUY else 1,
                item.score,
                item.created_at,
            ),
            reverse=True,
        )
        return filtered[:limit]

    def _recent_regime_signals(self, db: Session, signals: list[Signal] | None, limit: int) -> list[Signal]:
        freshness_cutoff = datetime.utcnow() - timedelta(seconds=self.max_signal_age_seconds)
        if signals is not None:
            filtered = [
                signal
                for signal in signals
                if signal.created_at >= freshness_cutoff and signal.asset
            ]
            return self._dedupe_by_asset(filtered)[:limit]
        rows = db.scalars(
            select(Signal)
            .options(joinedload(Signal.asset))
            .join(Asset, Asset.id == Signal.asset_id)
            .where(Signal.created_at >= freshness_cutoff)
            .order_by(Signal.created_at.desc())
            .limit(limit * 4)
        ).all()
        return self._dedupe_by_asset([row for row in rows if row.asset])[:limit]

    def _dedupe_by_asset(self, signals: list[Signal]) -> list[Signal]:
        unique: list[Signal] = []
        seen_asset_ids: set[int] = set()
        for signal in sorted(signals, key=lambda item: item.created_at, reverse=True):
            if signal.asset_id in seen_asset_ids:
                continue
            seen_asset_ids.add(signal.asset_id)
            unique.append(signal)
        return unique

    def _etf_regime_transition(self, signals: list[Signal]) -> dict | None:
        etf_rows = [signal for signal in signals if signal.asset and signal.asset.kind == AssetKind.ETF]
        if not etf_rows:
            return None

        def setup(signal: Signal) -> str:
            return extract_setup_type(signal.rationale) or "unknown"

        ranked = sorted(
            etf_rows,
            key=lambda item: (
                item.score,
                item.momentum_score,
                item.sentiment_score,
                item.created_at,
            ),
            reverse=True,
        )
        leader = ranked[0]
        leader_setup = setup(leader)
        all_risk_off = all(setup(row) == "etf_risk_off" for row in etf_rows)
        any_leaderish = any(setup(row) in {"etf_leader", "etf_trend"} for row in etf_rows)

        def transition_payload(
            *,
            state: str,
            symbol: str,
            setup_type: str,
            title: str,
            severity: str,
            message: str,
            live_proof_status: str,
            next_target: str,
            next_due_label: str,
        ) -> dict:
            return {
                "state": state,
                "symbol": symbol,
                "asset_kind": "etf",
                "setup_type": setup_type,
                "title": title,
                "severity": severity,
                "message": message,
                "candidate": {
                    "asset_symbol": symbol,
                    "asset_kind": "etf",
                    "setup_type": setup_type,
                    "action": "hold",
                    "recommendation": "watch",
                    "live_proof_status": live_proof_status,
                    "eligible_for_unattended": False,
                    "live_sample_count": 0,
                    "replay_sample_count": 0,
                    "pending_count": 0,
                    "next_due_label": next_due_label,
                    "test_net_expectancy_pct": 0.0,
                    "next_target": next_target,
                    "note": message,
                },
            }

        if all_risk_off:
            message = (
                f"ETF lane is still defensive. {leader.asset.symbol} is the least-weak ETF, "
                "but no leadership recovery has started yet."
            )
            return transition_payload(
                state="risk_off",
                symbol=leader.asset.symbol,
                setup_type=leader_setup,
                title="ETF lane moved to risk-off",
                severity="warn",
                message=message,
                live_proof_status="research",
                next_target="wait for ETF regime improvement",
                next_due_label="waiting for regime improvement",
            )
        if any_leaderish:
            lead_candidate = next(row for row in ranked if setup(row) in {"etf_leader", "etf_trend"})
            candidate_setup = setup(lead_candidate)
            message = (
                f"ETF leadership is rebuilding around {lead_candidate.asset.symbol}. "
                f"{candidate_setup} is forming, but it is not tradable yet."
            )
            return transition_payload(
                state="rebuilding",
                symbol=lead_candidate.asset.symbol,
                setup_type=candidate_setup,
                title=f"ETF leadership is rebuilding around {lead_candidate.asset.symbol}",
                severity="ok",
                message=message,
                live_proof_status="building_live",
                next_target="confirm ETF leadership persistence",
                next_due_label="watch for repeated leader signals",
            )
        message = (
            f"ETF lane is off the lows but still generic. {leader.asset.symbol} is strongest for now, "
            "yet no distinct leadership pattern has emerged."
        )
        return transition_payload(
            state="watch",
            symbol=leader.asset.symbol,
            setup_type=leader_setup,
            title=f"ETF lane is stabilizing around {leader.asset.symbol}",
            severity="ok",
            message=message,
            live_proof_status="research",
            next_target="watch for ETF leadership separation",
            next_due_label="watch for a cleaner ETF leader",
        )

    def _latest_ticks(self, db: Session, asset_ids: list[int]) -> dict[int, MarketTick]:
        ticks: dict[int, MarketTick] = {}
        for asset_id in asset_ids:
            tick = db.scalar(
                select(MarketTick)
                .where(MarketTick.asset_id == asset_id)
                .order_by(MarketTick.captured_at.desc())
                .limit(1)
            )
            if tick:
                ticks[asset_id] = tick
        return ticks

    def _blocked_reason(
        self,
        *,
        signal: Signal,
        asset: Asset,
        setup_type: str,
        approval_status: str,
        approval_note: str,
        walkforward_recommendation: str,
        live_proof_status: str,
        universe_enabled: bool,
        setup_allowed: bool,
        market_open: bool,
        fresh_tick: bool,
        has_open_position: bool,
    ) -> str | None:
        if not universe_enabled:
            return f"{asset.kind.value.upper()} universe is disabled for unattended mode."
        if not fresh_tick:
            return "Market data is stale or missing."
        if asset.kind in {AssetKind.ETF, AssetKind.STOCK} and not market_open:
            return "US market session is closed."
        if has_open_position:
            return "A position is already open for this asset."
        if signal.action != SignalAction.BUY:
            return (
                f"Setup {setup_type} is forming, but it has not triggered a BUY yet. "
                f"Current action is {signal.action.value}."
            )
        if not setup_allowed:
            return (
                f"Setup {setup_type or 'unknown'} is "
                f"{approval_status} on scorecard, {walkforward_recommendation} on walk-forward, "
                f"and live-proof status is {live_proof_status}. {approval_note}"
            )
        return None

    def _rank_score(
        self,
        *,
        signal: Signal,
        setup_type: str,
        approval_status: str,
        walkforward_recommendation: str,
        live_proof_status: str,
        net_expectancy_pct: float,
        test_net_expectancy_pct: float,
        test_decision_edge_pct: float,
        proof_sample_count: int,
        live_sample_count: int,
        setup_quality_score: float,
        eligible_for_unattended: bool,
    ) -> float:
        action_boost = 0.16 if signal.action == SignalAction.BUY else -0.05
        entry_family_boost = 0.04 if self._is_entry_setup(setup_type) else -0.25
        approval_boost = {"approved": 0.22, "watch": 0.04, "disabled": -0.25}.get(approval_status, 0.0)
        walkforward_boost = {"approved": 0.22, "watch": 0.02, "disabled": -0.25}.get(walkforward_recommendation, 0.0)
        live_state_boost = {"cleared": 0.20, "building_live": 0.07, "replay_only": -0.03, "research": -0.06, "exit_only": -0.20}.get(live_proof_status, 0.0)
        live_confidence_boost = min(proof_sample_count, 12) * 0.008 + min(live_sample_count, 8) * 0.012
        expectancy_boost = max(net_expectancy_pct, -1.0) * 0.08
        test_expectancy_boost = max(test_net_expectancy_pct, -1.0) * 0.12
        edge_boost = max(test_decision_edge_pct, -1.0) * 0.10
        freshness_penalty = min((datetime.utcnow() - signal.created_at).total_seconds() / 3600, 1.0) * 0.05
        eligibility_boost = 0.20 if eligible_for_unattended else 0.0
        return round(
            (float(signal.score) * 0.55)
            + (float(signal.momentum_score) * 0.28)
            + (float(signal.sentiment_score) * 0.10)
            + (setup_quality_score * 0.20)
            + action_boost
            + entry_family_boost
            + approval_boost
            + walkforward_boost
            + live_state_boost
            + live_confidence_boost
            + expectancy_boost
            + test_expectancy_boost
            + edge_boost
            + eligibility_boost
            - freshness_penalty,
            4,
        )

    def _is_entry_setup(self, setup_type: str) -> bool:
        return bool(setup_type) and not setup_type.endswith("risk_off") and not setup_type.endswith("watch")

    def _setup_quality_score(
        self,
        *,
        approval_status: str,
        walkforward_recommendation: str,
        live_proof_status: str,
        proof_sample_count: int,
        live_sample_count: int,
        net_expectancy_pct: float,
        test_net_expectancy_pct: float,
        test_decision_edge_pct: float,
    ) -> float:
        approval_component = {"approved": 1.0, "watch": 0.45, "disabled": 0.0}.get(approval_status, 0.2)
        walkforward_component = {"approved": 1.0, "watch": 0.5, "disabled": 0.0}.get(walkforward_recommendation, 0.2)
        live_component = {"cleared": 1.0, "building_live": 0.7, "replay_only": 0.35, "research": 0.2, "exit_only": 0.0}.get(live_proof_status, 0.1)
        sample_component = min(proof_sample_count, 10) / 10
        live_sample_component = min(live_sample_count, 6) / 6
        expectancy_component = max(min((net_expectancy_pct + 0.25) / 0.5, 1.0), 0.0)
        walkforward_component_net = max(min((test_net_expectancy_pct + 0.20) / 0.4, 1.0), 0.0)
        edge_component = max(min((test_decision_edge_pct + 0.10) / 0.2, 1.0), 0.0)
        return round(
            (approval_component * 0.18)
            + (walkforward_component * 0.22)
            + (live_component * 0.18)
            + (sample_component * 0.10)
            + (live_sample_component * 0.10)
            + (expectancy_component * 0.10)
            + (walkforward_component_net * 0.08)
            + (edge_component * 0.04),
            4,
        )

    def _tick_age_seconds(self, tick: MarketTick | None) -> int | None:
        if not tick:
            return None
        return int(max((datetime.utcnow() - tick.captured_at).total_seconds(), 0))

    def _market_open(self, asset_kind: AssetKind) -> bool:
        if asset_kind not in {AssetKind.ETF, AssetKind.STOCK}:
            return True
        now_et = datetime.now(ZoneInfo("America/New_York"))
        if now_et.weekday() >= 5:
            return False
        open_time = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        close_time = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
        return open_time <= now_et <= close_time
