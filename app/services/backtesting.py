from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from bisect import bisect_right

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Asset, AssetKind, MarketTick, NewsItem, Signal, SignalAction, SignalOutcomeSnapshot
from app.services.strategy import AssetSnapshot, StrategyEngine, extract_news_count, extract_setup_type


@dataclass
class WalkForwardSlice:
    sample_count: int
    weighted_count: float
    win_rate_pct: float
    avg_pnl_pct: float
    net_expectancy_pct: float
    profit_factor: float | None
    max_drawdown_pct: float
    avg_market_move_pct: float
    avg_decision_edge_pct: float
    first_at: datetime | None
    last_at: datetime | None


@dataclass
class ReplayOutcomeObservation:
    asset_kind: str
    setup_type: str
    action: str
    horizon_hours: int
    signal_at: datetime
    outcome_at: datetime
    market_move_pct: float
    decision_edge_pct: float
    pnl_pct: float
    source: str


@dataclass
class SetupWalkForwardRow:
    asset_kind: str
    setup_type: str
    recommendation: str
    live_proof_status: str
    eligible_for_unattended: bool
    sample_count: int
    live_sample_count: int
    replay_sample_count: int
    split_ratio_train_pct: int
    train: WalkForwardSlice
    test: WalkForwardSlice
    latest_outcome_at: datetime | None
    note: str


@dataclass
class SetupWalkForwardReport:
    generated_at: datetime
    total_resolved: int
    approved_count: int
    watch_count: int
    disabled_count: int
    replay_total_resolved: int
    earliest_signal_at: datetime | None
    latest_signal_at: datetime | None
    rows: list[SetupWalkForwardRow]

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "total_resolved": self.total_resolved,
            "approved_count": self.approved_count,
            "watch_count": self.watch_count,
            "disabled_count": self.disabled_count,
            "replay_total_resolved": self.replay_total_resolved,
            "earliest_signal_at": self.earliest_signal_at,
            "latest_signal_at": self.latest_signal_at,
            "rows": [
                {
                    **asdict(row),
                    "train": asdict(row.train),
                    "test": asdict(row.test),
                }
                for row in self.rows
            ],
        }


class WalkForwardAnalysisService:
    def __init__(self, strategy_engine: StrategyEngine) -> None:
        self.strategy_engine = strategy_engine
        self.cost_haircut_pct = {
            "etf": 0.08,
            "stock": 0.12,
            "crypto": 0.20,
        }
        self.replay_interval_minutes = {
            "etf": 60,
            "stock": 60,
            "crypto": 120,
        }
        self.replay_kinds = {"etf", "stock"}

    def build_report(self, db: Session) -> SetupWalkForwardReport:
        live_rows = db.scalars(
            select(SignalOutcomeSnapshot)
            .options(joinedload(SignalOutcomeSnapshot.signal).joinedload(Signal.asset))
            .where(
                SignalOutcomeSnapshot.outcome_status == "resolved",
                SignalOutcomeSnapshot.pnl_pct.is_not(None),
                SignalOutcomeSnapshot.horizon_hours.in_((4, 24)),
            )
            .order_by(SignalOutcomeSnapshot.updated_at.asc())
            .limit(5000)
        ).all()

        grouped: dict[tuple[str, str], list[ReplayOutcomeObservation]] = {}
        earliest_signal_at: datetime | None = None
        latest_signal_at: datetime | None = None

        for row in live_rows:
            observation = self._observation_from_live_row(row)
            if not observation:
                continue
            if earliest_signal_at is None or observation.signal_at < earliest_signal_at:
                earliest_signal_at = observation.signal_at
            if latest_signal_at is None or observation.signal_at > latest_signal_at:
                latest_signal_at = observation.signal_at
            grouped.setdefault((observation.asset_kind, observation.setup_type), []).append(observation)

        replay_rows = self._build_replay_observations(db)
        for observation in replay_rows:
            if earliest_signal_at is None or observation.signal_at < earliest_signal_at:
                earliest_signal_at = observation.signal_at
            if latest_signal_at is None or observation.signal_at > latest_signal_at:
                latest_signal_at = observation.signal_at
            grouped.setdefault((observation.asset_kind, observation.setup_type), []).append(observation)

        report_rows = [
            self._summarize_bucket(asset_kind, setup_type, bucket)
            for (asset_kind, setup_type), bucket in grouped.items()
        ]
        report_rows.sort(
            key=lambda row: (
                self._status_rank(row.recommendation),
                -(row.test.net_expectancy_pct or 0.0),
                -row.sample_count,
                row.asset_kind,
                row.setup_type,
            )
        )
        return SetupWalkForwardReport(
            generated_at=datetime.utcnow(),
            total_resolved=len(live_rows),
            approved_count=sum(1 for row in report_rows if row.recommendation == "approved"),
            watch_count=sum(1 for row in report_rows if row.recommendation == "watch"),
            disabled_count=sum(1 for row in report_rows if row.recommendation == "disabled"),
            replay_total_resolved=len(replay_rows),
            earliest_signal_at=earliest_signal_at,
            latest_signal_at=latest_signal_at,
            rows=report_rows,
        )

    def _observation_from_live_row(self, row: SignalOutcomeSnapshot) -> ReplayOutcomeObservation | None:
        signal = row.signal
        asset = signal.asset if signal else None
        if not signal or not asset or row.pnl_pct is None:
            return None
        setup_type = extract_setup_type(signal.rationale) or self.strategy_engine.classify_setup_type_for_signal(
            asset.kind.value,
            signal.score,
            signal.sentiment_score,
            signal.momentum_score,
            extract_news_count(signal.rationale),
        )
        if not self._signal_matches_setup(signal.action.value, setup_type):
            return None
        return ReplayOutcomeObservation(
            asset_kind=asset.kind.value,
            setup_type=setup_type,
            action=signal.action.value,
            horizon_hours=row.horizon_hours,
            signal_at=signal.created_at,
            outcome_at=row.updated_at or signal.created_at,
            market_move_pct=row.market_move_pct or 0.0,
            decision_edge_pct=row.decision_edge_pct or 0.0,
            pnl_pct=row.pnl_pct,
            source="live",
        )

    def _build_replay_observations(self, db: Session) -> list[ReplayOutcomeObservation]:
        assets = db.scalars(
            select(Asset).where(Asset.is_active.is_(True)).order_by(Asset.kind.asc(), Asset.symbol.asc())
        ).all()
        if not assets:
            return []

        news_items = db.scalars(
            select(NewsItem)
            .where(NewsItem.asset_id.is_not(None))
            .order_by(NewsItem.published_at.asc())
        ).all()
        news_by_asset: dict[int, list[NewsItem]] = {}
        for item in news_items:
            if item.asset_id is not None:
                news_by_asset.setdefault(item.asset_id, []).append(item)

        ticks = db.scalars(
            select(MarketTick)
            .where(MarketTick.asset_id.in_([asset.id for asset in assets]))
            .order_by(MarketTick.asset_id.asc(), MarketTick.captured_at.asc())
        ).all()
        ticks_by_asset: dict[int, list[MarketTick]] = {}
        for tick in ticks:
            ticks_by_asset.setdefault(tick.asset_id, []).append(tick)

        observations: list[ReplayOutcomeObservation] = []
        for kind in self.replay_kinds:
            kind_assets = [asset for asset in assets if asset.kind.value == kind]
            if not kind_assets:
                continue
            sampled_times = self._sample_kind_timestamps(kind_assets, ticks_by_asset, self.replay_interval_minutes.get(kind, 60))
            for timestamp in sampled_times:
                snapshots = self._build_snapshots_at(timestamp, kind_assets, ticks_by_asset, news_by_asset)
                if len(snapshots) < len(kind_assets):
                    continue
                etf_context = (
                    self.strategy_engine._build_etf_market_context(kind_assets, snapshots)  # noqa: SLF001
                    if kind == "etf"
                    else None
                )
                stock_context = (
                    self.strategy_engine._build_stock_market_context(kind_assets, snapshots)  # noqa: SLF001
                    if kind == "stock"
                    else None
                )
                for asset in kind_assets:
                    snapshot = snapshots.get(asset.id)
                    if not snapshot:
                        continue
                    profile = self.strategy_engine._profile_for(asset.kind.value)  # noqa: SLF001
                    evaluation = self.strategy_engine._evaluate_setup(  # noqa: SLF001
                        profile,
                        snapshot.score,
                        snapshot.sentiment_score,
                        snapshot.momentum_score,
                        snapshot.article_count,
                        event_article_count=snapshot.event_article_count,
                        etf_context=etf_context,
                        stock_context=stock_context,
                    )
                    action = self._research_action(profile, snapshot, evaluation.setup_type, evaluation.buy_ready)
                    if not self._signal_matches_setup(action, evaluation.setup_type):
                        continue
                    asset_ticks = ticks_by_asset.get(asset.id, [])
                    for horizon_hours in (4, 24):
                        future_tick = self._future_tick(asset_ticks, timestamp, horizon_hours)
                        current_tick = self._latest_tick_before(asset_ticks, timestamp)
                        if not future_tick or not current_tick or current_tick.price <= 0:
                            continue
                        market_move_pct = round(((future_tick.price / current_tick.price) - 1) * 100, 4)
                        decision_direction = 1.0 if action == "buy" else -1.0
                        decision_edge_pct = round(market_move_pct * decision_direction, 4)
                        observations.append(
                            ReplayOutcomeObservation(
                                asset_kind=asset.kind.value,
                                setup_type=evaluation.setup_type,
                                action=action,
                                horizon_hours=horizon_hours,
                                signal_at=timestamp,
                                outcome_at=future_tick.captured_at,
                                market_move_pct=market_move_pct,
                                decision_edge_pct=decision_edge_pct,
                                pnl_pct=decision_edge_pct,
                                source="replay",
                            )
                        )
        return observations

    def _sample_kind_timestamps(
        self,
        assets: list[Asset],
        ticks_by_asset: dict[int, list[MarketTick]],
        interval_minutes: int,
    ) -> list[datetime]:
        timestamps = sorted(
            {
                tick.captured_at
                for asset in assets
                for tick in ticks_by_asset.get(asset.id, [])
            }
        )
        sampled: list[datetime] = []
        minimum_gap = timedelta(minutes=interval_minutes)
        for timestamp in timestamps:
            if not sampled or timestamp - sampled[-1] >= minimum_gap:
                sampled.append(timestamp)
        return sampled

    def _build_snapshots_at(
        self,
        timestamp: datetime,
        assets: list[Asset],
        ticks_by_asset: dict[int, list[MarketTick]],
        news_by_asset: dict[int, list[NewsItem]],
    ) -> dict[int, AssetSnapshot]:
        snapshots: dict[int, AssetSnapshot] = {}
        for asset in assets:
            latest_tick = self._latest_tick_before(ticks_by_asset.get(asset.id, []), timestamp)
            if not latest_tick:
                continue
            sentiment_score, article_count, event_article_count = self._news_snapshot(news_by_asset.get(asset.id, []), timestamp)
            momentum_score = max(min(latest_tick.change_24h_pct / 10, 1.0), -1.0)
            coverage_score = min(article_count / 3, 1.0)
            sentiment_component = (sentiment_score + 1) / 2
            momentum_component = (momentum_score + 1) / 2
            combined_score = round(
                (0.5 * sentiment_component) + (0.35 * momentum_component) + (0.15 * coverage_score),
                4,
            )
            snapshots[asset.id] = AssetSnapshot(
                score=combined_score,
                sentiment_score=sentiment_score,
                momentum_score=momentum_score,
                article_count=article_count,
                event_article_count=event_article_count,
            )
        return snapshots

    def _news_snapshot(self, items: list[NewsItem], timestamp: datetime) -> tuple[float, int, int]:
        window_start = timestamp - timedelta(hours=24)
        relevant = [
            item
            for item in items
            if window_start <= item.published_at <= timestamp
        ]
        if not relevant:
            return 0.0, 0, 0
        sentiment = round(sum(item.sentiment_score for item in relevant) / len(relevant), 4)
        event_count = sum(1 for item in relevant if item.event_type != "general")
        return sentiment, len(relevant), event_count

    def _latest_tick_before(self, ticks: list[MarketTick], timestamp: datetime) -> MarketTick | None:
        if not ticks:
            return None
        times = [tick.captured_at for tick in ticks]
        idx = bisect_right(times, timestamp) - 1
        if idx < 0:
            return None
        return ticks[idx]

    def _future_tick(self, ticks: list[MarketTick], timestamp: datetime, horizon_hours: int) -> MarketTick | None:
        if not ticks:
            return None
        target = timestamp + timedelta(hours=horizon_hours)
        times = [tick.captured_at for tick in ticks]
        idx = bisect_right(times, target - timedelta(microseconds=1))
        if idx >= len(ticks):
            return None
        return ticks[idx]

    def _research_action(self, profile, snapshot: AssetSnapshot, setup_type: str, buy_ready: bool) -> str:
        if buy_ready:
            return SignalAction.BUY.value
        if (
            snapshot.sentiment_score < profile.defensive_sell_sentiment
            or snapshot.momentum_score < profile.defensive_sell_momentum
        ):
            return SignalAction.SELL.value
        return SignalAction.HOLD.value

    def _summarize_bucket(
        self,
        asset_kind: str,
        setup_type: str,
        rows: list[ReplayOutcomeObservation],
    ) -> SetupWalkForwardRow:
        ordered = sorted(rows, key=lambda row: (row.signal_at, row.outcome_at))
        sample_count = len(ordered)
        split_index = self._split_index(sample_count)
        train_rows = ordered[:split_index]
        test_rows = ordered[split_index:]
        train = self._slice_metrics(asset_kind, train_rows)
        test = self._slice_metrics(asset_kind, test_rows)
        latest_outcome_at = max((row.outcome_at for row in ordered), default=None)
        live_rows = [row for row in ordered if row.source == "live"]
        live_sample_count = sum(1 for row in ordered if row.source == "live")
        replay_sample_count = sum(1 for row in ordered if row.source == "replay")
        live_metrics = self._slice_metrics(asset_kind, live_rows)
        recommendation, note = self._recommendation(
            asset_kind=asset_kind,
            setup_type=setup_type,
            sample_count=sample_count,
            train=train,
            test=test,
            live_sample_count=live_sample_count,
            replay_sample_count=replay_sample_count,
        )
        eligible_for_unattended = recommendation == "approved" and live_sample_count >= 4
        live_proof_status = self._live_proof_status(
            asset_kind=asset_kind,
            setup_type=setup_type,
            live_sample_count=live_sample_count,
            live_metrics=live_metrics,
            recommendation=recommendation,
        )
        return SetupWalkForwardRow(
            asset_kind=asset_kind,
            setup_type=setup_type,
            recommendation=recommendation,
            live_proof_status=live_proof_status,
            eligible_for_unattended=eligible_for_unattended,
            sample_count=sample_count,
            live_sample_count=live_sample_count,
            replay_sample_count=replay_sample_count,
            split_ratio_train_pct=70,
            train=train,
            test=test,
            latest_outcome_at=latest_outcome_at,
            note=note,
        )

    def _slice_metrics(self, asset_kind: str, rows: list[ReplayOutcomeObservation]) -> WalkForwardSlice:
        cost_haircut_pct = self.cost_haircut_pct.get(asset_kind, 0.10)
        weighted_count = 0.0
        weighted_wins = 0.0
        weighted_pnl = 0.0
        weighted_net = 0.0
        weighted_market_move = 0.0
        weighted_edge = 0.0
        gross_profit = 0.0
        gross_loss = 0.0
        cumulative = 0.0
        peak = 0.0
        max_drawdown = 0.0
        first_at: datetime | None = None
        last_at: datetime | None = None

        for row in rows:
            weight = {4: 1.0, 24: 1.35}.get(row.horizon_hours, 0.0)
            if weight <= 0:
                continue
            net_pnl = row.pnl_pct - cost_haircut_pct
            weighted_count += weight
            weighted_pnl += row.pnl_pct * weight
            weighted_net += net_pnl * weight
            weighted_market_move += row.market_move_pct * weight
            weighted_edge += row.decision_edge_pct * weight
            if net_pnl > 0:
                weighted_wins += weight
                gross_profit += net_pnl
            elif net_pnl < 0:
                gross_loss += abs(net_pnl)
            cumulative += net_pnl
            peak = max(peak, cumulative)
            max_drawdown = max(max_drawdown, peak - cumulative)
            if first_at is None or row.signal_at < first_at:
                first_at = row.signal_at
            if last_at is None or row.signal_at > last_at:
                last_at = row.signal_at

        profit_factor = round(gross_profit / gross_loss, 3) if gross_loss > 0 else (round(gross_profit, 3) if gross_profit > 0 else None)
        return WalkForwardSlice(
            sample_count=len(rows),
            weighted_count=round(weighted_count, 2),
            win_rate_pct=round((weighted_wins / weighted_count) * 100, 2) if weighted_count else 0.0,
            avg_pnl_pct=round(weighted_pnl / weighted_count, 3) if weighted_count else 0.0,
            net_expectancy_pct=round(weighted_net / weighted_count, 3) if weighted_count else 0.0,
            profit_factor=profit_factor,
            max_drawdown_pct=round(max_drawdown, 3),
            avg_market_move_pct=round(weighted_market_move / weighted_count, 3) if weighted_count else 0.0,
            avg_decision_edge_pct=round(weighted_edge / weighted_count, 3) if weighted_count else 0.0,
            first_at=first_at,
            last_at=last_at,
        )

    def _recommendation(
        self,
        *,
        asset_kind: str,
        setup_type: str,
        sample_count: int,
        train: WalkForwardSlice,
        test: WalkForwardSlice,
        live_sample_count: int,
        replay_sample_count: int,
    ) -> tuple[str, str]:
        sample_note = f"Sources: live {live_sample_count}, replay {replay_sample_count}."
        if setup_type.endswith("risk_off"):
            return "disabled", f"Risk-off setups are exit tools, so they stay out of unattended entry promotion. {sample_note}"
        if asset_kind in {"stock", "etf"} and live_sample_count == 0:
            return "watch", f"Research-only evidence so far. Replay can rank ideas, but this setup still has no live resolved proof. {sample_note}"
        if asset_kind in {"stock", "etf"} and live_sample_count < 2:
            return "watch", f"Too little live proof yet. Replay is useful, but unattended trust still needs real resolved outcomes. {sample_note}"
        if sample_count < 8 or train.sample_count < 4 or test.sample_count < 2:
            return "watch", f"Too little walk-forward evidence yet ({sample_count} resolved rows across train/test). {sample_note}"
        if test.net_expectancy_pct < 0 or test.avg_decision_edge_pct < 0 or (test.profit_factor is not None and test.profit_factor < 1.0):
            return "disabled", (
                f"Out-of-sample evidence is weak: test net expectancy {test.net_expectancy_pct:.2f}%, "
                f"edge {test.avg_decision_edge_pct:.2f}%, profit factor {self._format_profit_factor(test.profit_factor)}. {sample_note}"
            )
        if train.net_expectancy_pct < 0:
            return "disabled", f"In-sample evidence is already negative at {train.net_expectancy_pct:.2f}%. {sample_note}"
        if (
            train.net_expectancy_pct >= 0.15
            and test.net_expectancy_pct >= 0.10
            and test.win_rate_pct >= 50.0
            and test.avg_decision_edge_pct >= 0.05
            and test.max_drawdown_pct <= 1.0
            and live_sample_count >= 4
        ):
            return "approved", (
                f"Walk-forward cleared: train {train.net_expectancy_pct:.2f}% and test {test.net_expectancy_pct:.2f}% "
                f"net expectancy with {test.win_rate_pct:.0f}% test win rate. {sample_note}"
            )
        return "watch", (
            f"Promising but not ready: train {train.net_expectancy_pct:.2f}% vs test {test.net_expectancy_pct:.2f}% "
            f"net expectancy, test drawdown {test.max_drawdown_pct:.2f}%. {sample_note}"
        )

    def _live_proof_status(
        self,
        *,
        asset_kind: str,
        setup_type: str,
        live_sample_count: int,
        live_metrics: WalkForwardSlice,
        recommendation: str,
    ) -> str:
        if setup_type.endswith("risk_off"):
            return "exit_only"
        if recommendation == "approved" and live_sample_count >= 4:
            return "cleared"
        if asset_kind in {"stock", "etf"} and live_sample_count == 0:
            return "replay_only"
        if live_sample_count == 0:
            return "research"
        if live_sample_count < 2:
            if live_metrics.net_expectancy_pct >= 0 and live_metrics.avg_decision_edge_pct >= 0:
                return "building_live"
            return "research"
        if live_sample_count < 4:
            early_live_ok = (
                live_metrics.net_expectancy_pct >= 0.05
                and live_metrics.avg_decision_edge_pct >= 0.03
                and live_metrics.win_rate_pct >= 50.0
                and live_metrics.max_drawdown_pct <= 1.0
            )
            return "building_live" if early_live_ok else "research"
        return "research"

    def _split_index(self, sample_count: int) -> int:
        if sample_count <= 2:
            return max(sample_count - 1, 0)
        split_index = int(sample_count * 0.7)
        split_index = max(split_index, min(4, sample_count - 1))
        split_index = min(split_index, sample_count - 2)
        return split_index

    def _signal_matches_setup(self, action: str, setup_type: str) -> bool:
        if setup_type.endswith("risk_off"):
            return action == SignalAction.SELL.value
        return action == SignalAction.BUY.value

    def _status_rank(self, status: str) -> int:
        return {"approved": 0, "watch": 1, "disabled": 2}.get(status, 3)

    def _format_profit_factor(self, value: float | None) -> str:
        if value is None:
            return "n/a"
        return f"{value:.2f}"
