from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Asset, MarketTick, NewsItem, Signal, SignalAction, SignalOutcomeSnapshot


def extract_news_count(rationale: str) -> int:
    marker = "news "
    if marker not in rationale:
        return 0
    tail = rationale.split(marker, 1)[1]
    digits: list[str] = []
    for char in tail:
        if char.isdigit():
            digits.append(char)
        elif digits:
            break
    return int("".join(digits)) if digits else 0


def extract_setup_type(rationale: str) -> str | None:
    prefix = "Setup "
    if not rationale.startswith(prefix):
        return None
    tail = rationale.split(prefix, 1)[1]
    return tail.split(":", 1)[0].strip() or None


@dataclass
class SignalDecision:
    action: SignalAction
    score: float
    sentiment_score: float
    momentum_score: float
    rationale: str


@dataclass
class LearningProfile:
    enabled: bool
    sample_count: int
    avg_market_move_pct: float
    positive_rate_pct: float
    score_relaxation: float
    sentiment_relaxation: float
    momentum_relaxation: float
    note: str


@dataclass
class OutcomeFeatureSet:
    setup_type: str
    sample_count: int
    avg_market_move_pct: float
    positive_rate_pct: float
    missed_upside_rate_pct: float
    safe_hold_rate_pct: float
    false_positive_rate_pct: float
    dominant_label: str
    promote: bool
    suppress: bool
    note: str


@dataclass
class StrategyProfile:
    asset_kind: str
    min_signal_score: float
    min_sentiment_score: float
    min_momentum_score: float
    min_news_items: int
    defensive_sell_sentiment: float
    defensive_sell_momentum: float
    allow_learning: bool
    label: str


@dataclass
class SetupEvaluation:
    setup_type: str
    min_score: float
    min_sentiment: float
    min_momentum: float
    min_news_items: int
    buy_ready: bool
    note: str


@dataclass
class AssetSnapshot:
    score: float
    sentiment_score: float
    momentum_score: float
    article_count: int
    event_article_count: int


@dataclass
class EtfMarketContext:
    positive_breadth: int
    negative_breadth: int
    leader_score: float
    leader_momentum: float
    runner_up_score: float
    runner_up_momentum: float
    score_spread: float
    momentum_spread: float
    average_score: float
    average_sentiment: float
    average_momentum: float
    regime_state: str
    regime_note: str


@dataclass
class StockMarketContext:
    positive_breadth: int
    negative_breadth: int
    leader_score: float
    leader_momentum: float
    average_score: float
    average_sentiment: float
    average_momentum: float


@dataclass
class CryptoMarketContext:
    positive_breadth: int
    negative_breadth: int
    leader_score: float
    leader_momentum: float
    average_score: float
    average_sentiment: float
    average_momentum: float


class StrategyEngine:
    def __init__(
        self,
        min_signal_score_to_buy: float,
        min_sentiment_score_to_buy: float = 0.12,
        min_momentum_score_to_buy: float = 0.03,
        min_news_items_to_buy: int = 1,
    ) -> None:
        self.min_signal_score_to_buy = min_signal_score_to_buy
        self.min_sentiment_score_to_buy = min_sentiment_score_to_buy
        self.min_momentum_score_to_buy = min_momentum_score_to_buy
        self.min_news_items_to_buy = min_news_items_to_buy
        self.profile_by_kind = {
            "etf": StrategyProfile(
                asset_kind="etf",
                min_signal_score=min_signal_score_to_buy,
                min_sentiment_score=max(min_sentiment_score_to_buy - 0.04, 0.05),
                min_momentum_score=max(min_momentum_score_to_buy - 0.01, 0.02),
                min_news_items=min_news_items_to_buy,
                defensive_sell_sentiment=-0.18,
                defensive_sell_momentum=-0.20,
                allow_learning=True,
                label="ETF",
            ),
            "stock": StrategyProfile(
                asset_kind="stock",
                min_signal_score=min(min_signal_score_to_buy + 0.03, 0.9),
                min_sentiment_score=max(min_sentiment_score_to_buy + 0.06, 0.18),
                min_momentum_score=max(min_momentum_score_to_buy + 0.01, 0.04),
                min_news_items=max(min_news_items_to_buy, 2),
                defensive_sell_sentiment=-0.16,
                defensive_sell_momentum=-0.22,
                allow_learning=False,
                label="Stock",
            ),
            "crypto": StrategyProfile(
                asset_kind="crypto",
                min_signal_score=min(min_signal_score_to_buy + 0.10, 0.95),
                min_sentiment_score=max(min_sentiment_score_to_buy + 0.10, 0.22),
                min_momentum_score=max(min_momentum_score_to_buy + 0.07, 0.10),
                min_news_items=max(min_news_items_to_buy, 2),
                defensive_sell_sentiment=-0.10,
                defensive_sell_momentum=-0.18,
                allow_learning=False,
                label="Crypto",
            ),
        }

    def build_signals(self, db: Session, assets: list[Asset]) -> list[Signal]:
        now = datetime.utcnow()
        results: list[Signal] = []
        learning_profiles = self._build_learning_profiles(db)
        outcome_features = self._build_outcome_features(db)
        snapshots: dict[int, AssetSnapshot] = {}

        for asset in assets:
            latest_tick = db.scalar(
                select(MarketTick)
                .where(MarketTick.asset_id == asset.id)
                .order_by(MarketTick.captured_at.desc())
                .limit(1)
            )
            if not latest_tick:
                continue

            sentiment_score = (
                db.scalar(
                    select(func.avg(NewsItem.sentiment_score))
                    .where(NewsItem.asset_id == asset.id, NewsItem.published_at >= now - timedelta(hours=24))
                )
                or 0.0
            )
            article_count = (
                db.scalar(
                    select(func.count(NewsItem.id))
                    .where(NewsItem.asset_id == asset.id, NewsItem.published_at >= now - timedelta(hours=24))
                )
                or 0
            )
            event_article_count = (
                db.scalar(
                    select(func.count(NewsItem.id))
                    .where(
                        NewsItem.asset_id == asset.id,
                        NewsItem.published_at >= now - timedelta(hours=24),
                        NewsItem.event_type != "general",
                    )
                )
                or 0
            )
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

        etf_context = self._build_etf_market_context(assets, snapshots)
        stock_context = self._build_stock_market_context(assets, snapshots)
        crypto_context = self._build_crypto_market_context(assets, snapshots)

        for asset in assets:
            snapshot = snapshots.get(asset.id)
            if not snapshot:
                continue

            sentiment_score = snapshot.sentiment_score
            article_count = snapshot.article_count
            event_article_count = snapshot.event_article_count
            momentum_score = snapshot.momentum_score
            combined_score = snapshot.score
            lane_profile = self._profile_for(asset.kind.value)
            evaluation = self._evaluate_setup(
                lane_profile,
                combined_score,
                sentiment_score,
                momentum_score,
                article_count,
                event_article_count=event_article_count,
                etf_context=etf_context if asset.kind.value == "etf" else None,
                stock_context=stock_context if asset.kind.value == "stock" else None,
                crypto_context=crypto_context if asset.kind.value == "crypto" else None,
            )
            setup_type = evaluation.setup_type
            learning_profile = learning_profiles.get(asset.symbol) or learning_profiles.get(asset.kind.value) or LearningProfile(
                enabled=False,
                sample_count=0,
                avg_market_move_pct=0.0,
                positive_rate_pct=0.0,
                score_relaxation=0.0,
                sentiment_relaxation=0.0,
                momentum_relaxation=0.0,
                note="No resolved near-miss learning profile yet.",
            )
            features = (
                outcome_features.get(f"{asset.symbol}:{setup_type}")
                or outcome_features.get(f"{asset.kind.value}:{setup_type}")
                or OutcomeFeatureSet(
                    setup_type=setup_type,
                    sample_count=0,
                    avg_market_move_pct=0.0,
                    positive_rate_pct=0.0,
                    missed_upside_rate_pct=0.0,
                    safe_hold_rate_pct=0.0,
                    false_positive_rate_pct=0.0,
                    dominant_label="none",
                    promote=False,
                    suppress=False,
                    note="No resolved setup-pattern history yet.",
                )
            )

            conservative_buy = evaluation.buy_ready
            etf_pullback_learning_ok = not (
                asset.kind.value == "etf"
                and setup_type == "etf_pullback"
                and (
                    not etf_context
                    or etf_context.regime_state == "risk_off"
                    or etf_context.positive_breadth < 2
                    or etf_context.negative_breadth > 0
                    or etf_context.average_sentiment < 0.08
                    or etf_context.average_momentum < 0.03
                    or etf_context.leader_score < 0.64
                    or etf_context.score_spread < 0.02
                    or combined_score < 0.64
                    or sentiment_score < 0.28
                    or momentum_score < 0.0
                    or momentum_score > 0.05
                    or article_count < 4
                )
            )
            learned_buy = (
                lane_profile.allow_learning
                and learning_profile.enabled
                and features.promote
                and not features.suppress
                and etf_pullback_learning_ok
                and combined_score >= evaluation.min_score - learning_profile.score_relaxation
                and sentiment_score >= evaluation.min_sentiment - learning_profile.sentiment_relaxation
                and momentum_score >= evaluation.min_momentum - learning_profile.momentum_relaxation
                and sentiment_score >= -0.02
                and momentum_score > -0.03
                and article_count >= max(evaluation.min_news_items, 2)
            )
            false_positive_news_spike = (
                setup_type in {"etf_pullback", "stock_event"}
                and features.false_positive_rate_pct >= 45.0
                and features.sample_count >= 4
            )
            safe_hold_bias = (
                lane_profile.allow_learning
                and setup_type in {"etf_watch", "etf_pullback", "etf_trend"}
                and features.safe_hold_rate_pct >= 65.0
                and features.sample_count >= 6
                and not (
                    asset.kind.value == "etf"
                    and etf_context
                    and etf_context.regime_state == "risk_off"
                )
            )

            if conservative_buy:
                action = SignalAction.BUY
                rationale = (
                    f"Setup {setup_type}: {lane_profile.label} lane passed. Score {combined_score:.2f}, "
                    f"sentiment {sentiment_score:.2f}, momentum {momentum_score:.2f}, news {article_count}. "
                    f"{evaluation.note}"
                )
            elif learned_buy:
                action = SignalAction.BUY
                rationale = (
                    f"Setup {setup_type}: promoted from resolved {lane_profile.label.lower()} holds. Similar {asset.kind.value} {setup_type} holds averaged "
                    f"{learning_profile.avg_market_move_pct:.2f}% over {learning_profile.sample_count} resolved rows, with "
                    f"{features.missed_upside_rate_pct:.0f}% missed-upside labels. "
                    f"Relaxed gates to score {evaluation.min_score - learning_profile.score_relaxation:.2f}, "
                    f"sentiment {evaluation.min_sentiment - learning_profile.sentiment_relaxation:.2f}, "
                    f"momentum {evaluation.min_momentum - learning_profile.momentum_relaxation:.2f}. "
                    f"Current setup is score {combined_score:.2f}, sentiment {sentiment_score:.2f}, "
                    f"momentum {momentum_score:.2f}, news {article_count}."
                )
            elif false_positive_news_spike:
                action = SignalAction.HOLD
                rationale = (
                    f"Setup {setup_type}: suppressed as a false-positive pattern. Similar {asset.kind.value} {setup_type} setups "
                    f"showed {features.false_positive_rate_pct:.0f}% weak follow-through and only "
                    f"{features.avg_market_move_pct:.2f}% average move across {features.sample_count} resolved rows."
                )
            elif safe_hold_bias:
                action = SignalAction.HOLD
                rationale = (
                    f"Setup {setup_type}: safe-hold bias. Similar {asset.kind.value} {setup_type} setups were defensive winners "
                    f"{features.safe_hold_rate_pct:.0f}% of the time, so capital stays protected."
                )
            elif sentiment_score < lane_profile.defensive_sell_sentiment or momentum_score < lane_profile.defensive_sell_momentum:
                action = SignalAction.SELL
                rationale = (
                    f"Setup {setup_type}: defensive sell. Sentiment {sentiment_score:.2f} or momentum {momentum_score:.2f} "
                    "fell below the lane risk threshold."
                )
            else:
                action = SignalAction.HOLD
                rationale = (
                    f"Setup {setup_type}: no clean edge yet. Score {combined_score:.2f}, sentiment {sentiment_score:.2f}, "
                    f"momentum {momentum_score:.2f}, news {article_count}. {evaluation.note}"
                )

            signal = Signal(
                asset_id=asset.id,
                action=action,
                score=combined_score,
                sentiment_score=round(sentiment_score, 4),
                momentum_score=round(momentum_score, 4),
                rationale=rationale,
            )
            db.add(signal)
            results.append(signal)

        db.commit()
        return results

    def failed_checks_for_signal(
        self,
        asset_kind: str,
        score: float,
        sentiment_score: float,
        momentum_score: float,
        article_count: int,
    ) -> tuple[str, list[str]]:
        profile = self._profile_for(asset_kind)
        evaluation = self._evaluate_setup(profile, score, sentiment_score, momentum_score, article_count)
        checks: list[str] = []
        if score < evaluation.min_score:
            checks.append(f"score {score:.2f} < {evaluation.min_score:.2f}")
        if sentiment_score < evaluation.min_sentiment:
            checks.append(f"sentiment {sentiment_score:.2f} < {evaluation.min_sentiment:.2f}")
        if momentum_score < evaluation.min_momentum:
            checks.append(f"momentum {momentum_score:.2f} < {evaluation.min_momentum:.2f}")
        if article_count < evaluation.min_news_items:
            checks.append(f"news {article_count} < {evaluation.min_news_items}")
        return evaluation.setup_type, checks

    def classify_setup_type_for_signal(
        self,
        asset_kind: str,
        score: float,
        sentiment_score: float,
        momentum_score: float,
        article_count: int,
    ) -> str:
        return self._classify_setup_type(asset_kind, score, sentiment_score, momentum_score, article_count)

    def _classify_setup_type(
        self,
        asset_kind: str,
        combined_score: float,
        sentiment_score: float,
        momentum_score: float,
        article_count: int,
        event_article_count: int = 0,
    ) -> str:
        if asset_kind == "etf":
            if combined_score >= 0.58 and momentum_score >= 0.12 and sentiment_score >= -0.05:
                return "etf_leader"
            if combined_score >= 0.62 and momentum_score >= 0.06 and sentiment_score >= 0.04:
                return "etf_trend"
            if combined_score >= 0.64 and sentiment_score >= 0.30 and article_count >= 4 and 0.0 <= momentum_score <= 0.05:
                return "etf_pullback"
            if momentum_score <= -0.14 or sentiment_score <= -0.10:
                return "etf_risk_off"
            return "etf_watch"
        if asset_kind == "stock":
            if (
                article_count >= 4
                and combined_score >= 0.60
                and sentiment_score >= 0.04
                and momentum_score >= 0.01
                and (
                    event_article_count >= 2
                    or (
                        event_article_count >= 1
                        and article_count >= 6
                        and sentiment_score >= 0.12
                        and momentum_score >= 0.08
                    )
                )
            ):
                return "stock_event"
            if combined_score >= 0.52 and momentum_score >= 0.14 and sentiment_score >= 0.03:
                return "stock_momentum"
            if momentum_score <= -0.16 or sentiment_score <= -0.12:
                return "stock_risk_off"
            return "stock_watch"
        if combined_score >= 0.60 and momentum_score >= 0.18 and (sentiment_score >= 0.03 or article_count >= 1):
            return "crypto_breakout"
        if momentum_score <= -0.12 or sentiment_score <= -0.10:
            return "crypto_risk_off"
        return "crypto_watch"

    def _profile_for(self, asset_kind: str) -> StrategyProfile:
        return self.profile_by_kind.get(asset_kind, self.profile_by_kind["etf"])

    def _evaluate_setup(
        self,
        profile: StrategyProfile,
        combined_score: float,
        sentiment_score: float,
        momentum_score: float,
        article_count: int,
        event_article_count: int = 0,
        etf_context: EtfMarketContext | None = None,
        stock_context: StockMarketContext | None = None,
        crypto_context: CryptoMarketContext | None = None,
    ) -> SetupEvaluation:
        setup_type = self._classify_setup_type(
            profile.asset_kind,
            combined_score,
            sentiment_score,
            momentum_score,
            article_count,
            event_article_count,
        )
        if (
            profile.asset_kind == "etf"
            and setup_type == "etf_watch"
            and etf_context
            and etf_context.regime_state == "risk_off"
            and momentum_score <= 0.0
        ):
            setup_type = "etf_risk_off"
        min_score = profile.min_signal_score
        min_sentiment = profile.min_sentiment_score
        min_momentum = profile.min_momentum_score
        min_news_items = profile.min_news_items
        note = f"{profile.label} lane is waiting for cleaner confirmation."

        if setup_type == "etf_leader":
            min_score = max(profile.min_signal_score - 0.01, 0.58)
            min_sentiment = -0.04
            min_momentum = max(profile.min_momentum_score + 0.10, 0.12)
            min_news_items = 0
            note = "ETF leader lane trusts clean relative strength more than generic ETF headline flow, but only when one symbol is clearly pulling away from peers."
            if etf_context:
                note = (
                    f"ETF leader lane wants one clean leader over the pack. Breadth {etf_context.positive_breadth} positive / "
                    f"{etf_context.negative_breadth} negative, leader momentum {etf_context.leader_momentum:.2f}, "
                    f"score spread {etf_context.score_spread:.2f}."
                )
        elif setup_type == "etf_trend":
            min_score = max(profile.min_signal_score, 0.62)
            min_sentiment = 0.04
            min_momentum = max(profile.min_momentum_score + 0.01, 0.06)
            min_news_items = 0
            note = "ETF trend lane now wants cleaner tape leadership. Mild upward drift is no longer enough to count as trend."
            if etf_context:
                note = (
                    f"ETF trend lane wants market confirmation. Breadth {etf_context.positive_breadth} positive / "
                    f"{etf_context.negative_breadth} negative, average momentum {etf_context.average_momentum:.2f}."
                )
        elif setup_type == "etf_pullback":
            min_score = max(profile.min_signal_score + 0.06, 0.68)
            min_sentiment = max(profile.min_sentiment_score + 0.06, 0.28)
            min_momentum = 0.0
            min_news_items = 4
            note = "ETF pullback lane now only counts disciplined buy-the-dip attempts inside a still-healthy tape, so weak headline dips stop polluting the lane."
            if etf_context:
                note = (
                    f"ETF pullback lane needs a still-healthy tape behind the dip. Breadth {etf_context.positive_breadth} positive / "
                    f"{etf_context.negative_breadth} negative, average sentiment {etf_context.average_sentiment:.2f}, "
                    f"average momentum {etf_context.average_momentum:.2f}, score spread {etf_context.score_spread:.2f}."
                )
        elif setup_type == "etf_watch":
            min_score = max(profile.min_signal_score + 0.10, 0.72)
            min_sentiment = max(profile.min_sentiment_score + 0.08, 0.18)
            min_momentum = max(profile.min_momentum_score, 0.05)
            min_news_items = max(profile.min_news_items, 2)
            note = "ETF watch is observation-only now. It can inform monitoring, but it does not earn unattended entries."
            if etf_context and etf_context.regime_state == "risk_off":
                note = (
                    f"ETF lane is in capital-preservation mode. {etf_context.regime_note} "
                    "New ETF entries stay on hold until breadth and momentum improve."
                )
        elif setup_type == "stock_event":
            min_score = max(profile.min_signal_score - 0.02, 0.60)
            min_sentiment = 0.04
            min_momentum = 0.01
            min_news_items = max(profile.min_news_items + 2, 4)
            note = "Stock event lane now demands multi-article catalyst coverage plus constructive tape, so generic headline noise stops looking actionable."
            if stock_context:
                note = (
                    f"Stock event lane wants real catalyst coverage with constructive tape. Event articles {event_article_count}, "
                    f"breadth {stock_context.positive_breadth} positive / {stock_context.negative_breadth} negative, "
                    f"leader momentum {stock_context.leader_momentum:.2f}."
                )
        elif setup_type == "stock_momentum":
            min_score = max(profile.min_signal_score - 0.05, 0.52)
            min_sentiment = 0.03
            min_momentum = max(profile.min_momentum_score + 0.10, 0.14)
            min_news_items = 0
            note = "Stock momentum lane now only counts clean relative-strength breakouts. It can work without fresh headlines, but weak or mixed tape no longer qualifies."
            if stock_context:
                note = (
                    f"Stock momentum lane wants broad tape confirmation. Breadth {stock_context.positive_breadth} positive / "
                    f"{stock_context.negative_breadth} negative, average momentum {stock_context.average_momentum:.2f}, "
                    f"leader momentum {stock_context.leader_momentum:.2f}."
                )
        elif setup_type == "stock_watch":
            min_score = max(profile.min_signal_score + 0.06, 0.60)
            min_sentiment = max(profile.min_sentiment_score, 0.10)
            min_momentum = max(profile.min_momentum_score + 0.02, 0.06)
            min_news_items = 1
            note = "Stock watch is observation-only until momentum or catalyst quality gets much cleaner."
        elif setup_type == "crypto_breakout":
            min_score = max(profile.min_signal_score - 0.12, 0.60)
            min_sentiment = max(profile.min_sentiment_score - 0.19, 0.03)
            min_momentum = max(profile.min_momentum_score, 0.18)
            min_news_items = 0
            note = "Crypto breakout lane can trust tape more than headlines, but only when market breadth confirms the move."
            if crypto_context:
                note = (
                    f"Crypto breakout lane wants tape confirmation. Breadth {crypto_context.positive_breadth} positive / "
                    f"{crypto_context.negative_breadth} negative, average momentum {crypto_context.average_momentum:.2f}, "
                    f"leader momentum {crypto_context.leader_momentum:.2f}."
                )
        elif setup_type.endswith("risk_off"):
            note = f"{profile.label} lane is risk-off here, so new buys stay disabled."

        buy_ready = (
            not setup_type.endswith("risk_off")
            and setup_type not in {"etf_watch", "stock_watch"}
            and combined_score >= min_score
            and sentiment_score >= min_sentiment
            and momentum_score >= min_momentum
            and article_count >= min_news_items
        )
        if buy_ready and setup_type == "etf_trend" and etf_context:
            buy_ready = (
                etf_context.positive_breadth >= 2
                and etf_context.negative_breadth == 0
                and etf_context.average_momentum >= 0.04
                and combined_score >= max(etf_context.average_score + 0.02, 0.62)
            )
        if buy_ready and setup_type == "etf_leader" and etf_context:
            buy_ready = (
                etf_context.positive_breadth >= 1
                and etf_context.negative_breadth == 0
                and combined_score >= max(etf_context.average_score + 0.03, 0.58)
                and momentum_score >= max(etf_context.average_momentum + 0.08, 0.12)
                and momentum_score >= max(etf_context.leader_momentum - 0.03, 0.12)
                and (
                    etf_context.score_spread >= 0.02
                    or etf_context.momentum_spread >= 0.06
                )
            )
        if buy_ready and setup_type == "etf_pullback" and etf_context:
            buy_ready = (
                etf_context.regime_state != "risk_off"
                and
                etf_context.positive_breadth >= 2
                and etf_context.negative_breadth == 0
                and etf_context.average_sentiment >= 0.08
                and etf_context.average_momentum >= 0.03
                and etf_context.leader_score >= 0.64
                and etf_context.leader_momentum >= 0.08
                and etf_context.score_spread >= 0.02
                and combined_score >= max(etf_context.average_score + 0.04, 0.68)
                and 0.0 <= momentum_score <= 0.05
            )
        if buy_ready and setup_type == "stock_momentum" and stock_context:
            buy_ready = (
                stock_context.positive_breadth >= 2
                and stock_context.negative_breadth == 0
                and stock_context.average_momentum >= 0.08
                and combined_score >= max(stock_context.average_score + 0.03, 0.52)
                and sentiment_score >= max(stock_context.average_sentiment, 0.03)
                and momentum_score >= max(stock_context.leader_momentum - 0.03, 0.14)
            )
        if buy_ready and setup_type == "stock_event" and stock_context:
            buy_ready = (
                stock_context.negative_breadth == 0
                and stock_context.average_momentum >= 0.0
                and combined_score >= max(stock_context.average_score + 0.02, 0.60)
                and (
                    event_article_count >= 2
                    or (
                        event_article_count >= 1
                        and article_count >= 6
                        and sentiment_score >= 0.12
                        and momentum_score >= max(stock_context.average_momentum + 0.04, 0.08)
                    )
                )
            )
        if buy_ready and setup_type == "crypto_breakout" and crypto_context:
            buy_ready = (
                crypto_context.positive_breadth >= 2
                and crypto_context.negative_breadth <= 1
                and crypto_context.average_momentum >= 0.10
                and combined_score >= max(crypto_context.average_score, 0.58)
                and combined_score >= max(crypto_context.leader_score - 0.03, 0.60)
                and momentum_score >= max(crypto_context.average_momentum - 0.18, 0.18)
            )
        return SetupEvaluation(
            setup_type=setup_type,
            min_score=round(min_score, 3),
            min_sentiment=round(min_sentiment, 3),
            min_momentum=round(min_momentum, 3),
            min_news_items=min_news_items,
            buy_ready=buy_ready,
            note=note,
        )

    def _build_etf_market_context(
        self,
        assets: list[Asset],
        snapshots: dict[int, AssetSnapshot],
    ) -> EtfMarketContext | None:
        etf_rows = [
            snapshots[asset.id]
            for asset in assets
            if asset.kind.value == "etf" and asset.id in snapshots
        ]
        if not etf_rows:
            return None
        positive_breadth = sum(
            1 for row in etf_rows if row.score >= 0.55 and row.momentum_score >= 0.03 and row.sentiment_score >= -0.02
        )
        negative_breadth = sum(1 for row in etf_rows if row.momentum_score <= -0.05 or row.sentiment_score <= -0.08)
        ranked_by_score = sorted(
            etf_rows,
            key=lambda row: (row.score, row.momentum_score, row.sentiment_score),
            reverse=True,
        )
        leader = ranked_by_score[0]
        runner_up = ranked_by_score[1] if len(ranked_by_score) > 1 else leader
        average_score = round(sum(row.score for row in etf_rows) / len(etf_rows), 4)
        average_sentiment = round(sum(row.sentiment_score for row in etf_rows) / len(etf_rows), 4)
        average_momentum = round(sum(row.momentum_score for row in etf_rows) / len(etf_rows), 4)
        regime_state = "neutral"
        regime_note = "ETF breadth is mixed."
        if negative_breadth >= max(2, len(etf_rows) - 1) or average_momentum <= -0.04:
            regime_state = "risk_off"
            regime_note = (
                f"Average ETF momentum is {average_momentum:.2f} with {negative_breadth} weak symbol(s), "
                "so leadership is too fragile for new ETF entries."
            )
        elif positive_breadth >= 2 and leader.momentum_score >= 0.10 and average_momentum >= 0.03:
            regime_state = "risk_on"
            regime_note = (
                f"Average ETF momentum is {average_momentum:.2f} with {positive_breadth} constructive symbol(s), "
                "so leader-style entries can be evaluated."
            )
        return EtfMarketContext(
            positive_breadth=positive_breadth,
            negative_breadth=negative_breadth,
            leader_score=leader.score,
            leader_momentum=leader.momentum_score,
            runner_up_score=runner_up.score,
            runner_up_momentum=runner_up.momentum_score,
            score_spread=round(leader.score - runner_up.score, 4),
            momentum_spread=round(leader.momentum_score - runner_up.momentum_score, 4),
            average_score=average_score,
            average_sentiment=average_sentiment,
            average_momentum=average_momentum,
            regime_state=regime_state,
            regime_note=regime_note,
        )

    def _build_stock_market_context(
        self,
        assets: list[Asset],
        snapshots: dict[int, AssetSnapshot],
    ) -> StockMarketContext | None:
        stock_rows = [
            snapshots[asset.id]
            for asset in assets
            if asset.kind.value == "stock" and asset.id in snapshots
        ]
        if not stock_rows:
            return None
        positive_breadth = sum(
            1 for row in stock_rows if row.score >= 0.45 and row.momentum_score >= 0.08 and row.sentiment_score >= -0.03
        )
        negative_breadth = sum(1 for row in stock_rows if row.momentum_score <= -0.08 or row.sentiment_score <= -0.10)
        return StockMarketContext(
            positive_breadth=positive_breadth,
            negative_breadth=negative_breadth,
            leader_score=max(row.score for row in stock_rows),
            leader_momentum=max(row.momentum_score for row in stock_rows),
            average_score=round(sum(row.score for row in stock_rows) / len(stock_rows), 4),
            average_sentiment=round(sum(row.sentiment_score for row in stock_rows) / len(stock_rows), 4),
            average_momentum=round(sum(row.momentum_score for row in stock_rows) / len(stock_rows), 4),
        )

    def _build_crypto_market_context(
        self,
        assets: list[Asset],
        snapshots: dict[int, AssetSnapshot],
    ) -> CryptoMarketContext | None:
        crypto_rows = [
            snapshots[asset.id]
            for asset in assets
            if asset.kind.value == "crypto" and asset.id in snapshots
        ]
        if not crypto_rows:
            return None
        positive_breadth = sum(
            1 for row in crypto_rows if row.score >= 0.54 and row.momentum_score >= 0.16 and row.sentiment_score >= -0.02
        )
        negative_breadth = sum(1 for row in crypto_rows if row.momentum_score <= -0.10 or row.sentiment_score <= -0.08)
        return CryptoMarketContext(
            positive_breadth=positive_breadth,
            negative_breadth=negative_breadth,
            leader_score=max(row.score for row in crypto_rows),
            leader_momentum=max(row.momentum_score for row in crypto_rows),
            average_score=round(sum(row.score for row in crypto_rows) / len(crypto_rows), 4),
            average_sentiment=round(sum(row.sentiment_score for row in crypto_rows) / len(crypto_rows), 4),
            average_momentum=round(sum(row.momentum_score for row in crypto_rows) / len(crypto_rows), 4),
        )

    def _build_learning_profiles(self, db: Session) -> dict[str, LearningProfile]:
        rows = db.scalars(
            select(SignalOutcomeSnapshot)
            .join(Signal, Signal.id == SignalOutcomeSnapshot.signal_id)
            .join(Asset, Asset.id == Signal.asset_id)
            .where(
                SignalOutcomeSnapshot.outcome_status == "resolved",
                Signal.action == SignalAction.HOLD,
                SignalOutcomeSnapshot.market_move_pct.is_not(None),
                SignalOutcomeSnapshot.horizon_hours.in_((4, 24)),
            )
            .order_by(SignalOutcomeSnapshot.updated_at.desc())
            .limit(600)
        ).all()

        grouped: dict[str, list[SignalOutcomeSnapshot]] = {}
        for row in rows:
            if not row.signal or not row.signal.asset:
                continue
            profile = self._profile_for(row.signal.asset.kind.value)
            if not profile.allow_learning:
                continue
            if row.signal.score < profile.min_signal_score - 0.10:
                continue
            if row.signal.sentiment_score < -0.05:
                continue
            if row.signal.momentum_score < profile.min_momentum_score - 0.08:
                continue
            grouped.setdefault(row.signal.asset.symbol, []).append(row)
            grouped.setdefault(row.signal.asset.kind.value, []).append(row)

        profiles: dict[str, LearningProfile] = {}
        for key, bucket in grouped.items():
            profile = self._summarize_learning_bucket(bucket)
            if profile.sample_count:
                profiles[key] = profile
        return profiles

    def _build_outcome_features(self, db: Session) -> dict[str, OutcomeFeatureSet]:
        rows = db.scalars(
            select(SignalOutcomeSnapshot)
            .join(Signal, Signal.id == SignalOutcomeSnapshot.signal_id)
            .join(Asset, Asset.id == Signal.asset_id)
            .where(
                SignalOutcomeSnapshot.outcome_status == "resolved",
                SignalOutcomeSnapshot.market_move_pct.is_not(None),
                SignalOutcomeSnapshot.horizon_hours.in_((4, 24)),
            )
            .order_by(SignalOutcomeSnapshot.updated_at.desc())
            .limit(800)
        ).all()

        grouped: dict[str, list[SignalOutcomeSnapshot]] = {}
        for row in rows:
            signal = row.signal
            asset = signal.asset if signal else None
            if not signal or not asset:
                continue
            setup_type = extract_setup_type(signal.rationale) or self._classify_setup_type(
                asset.kind.value,
                signal.score,
                signal.sentiment_score,
                signal.momentum_score,
                extract_news_count(signal.rationale),
            )
            grouped.setdefault(f"{asset.symbol}:{setup_type}", []).append(row)
            grouped.setdefault(f"{asset.kind.value}:{setup_type}", []).append(row)

        features: dict[str, OutcomeFeatureSet] = {}
        for key, bucket in grouped.items():
            features[key] = self._summarize_outcome_features(bucket)
        return features

    def _summarize_learning_bucket(self, rows: list[SignalOutcomeSnapshot]) -> LearningProfile:
        weighted_count = 0.0
        weighted_positive = 0.0
        weighted_market_move = 0.0

        for row in rows:
            if row.market_move_pct is None:
                continue
            weight = {4: 1.0, 24: 1.35}.get(row.horizon_hours, 0.0)
            if weight <= 0:
                continue
            weighted_count += weight
            weighted_market_move += row.market_move_pct * weight
            if row.market_move_pct >= 0.25:
                weighted_positive += weight

        sample_count = int(round(weighted_count))
        avg_market_move_pct = round(weighted_market_move / weighted_count, 3) if weighted_count else 0.0
        positive_rate_pct = round((weighted_positive / weighted_count) * 100, 2) if weighted_count else 0.0

        enabled = weighted_count >= 6 and avg_market_move_pct >= 0.20 and positive_rate_pct >= 60.0
        score_relaxation = 0.0
        sentiment_relaxation = 0.0
        momentum_relaxation = 0.0
        note = "History not strong enough to relax buy thresholds."
        if enabled:
            score_relaxation = min(0.06, 0.03 + max(avg_market_move_pct, 0.0) / 20)
            sentiment_relaxation = 0.12 if avg_market_move_pct >= 0.40 else 0.07
            momentum_relaxation = 0.05 if positive_rate_pct >= 70 else 0.04
            note = (
                f"Enabled from {sample_count} weighted resolved near-miss rows with "
                f"{avg_market_move_pct:.2f}% average upside and {positive_rate_pct:.1f}% positive rate."
            )

        return LearningProfile(
            enabled=enabled,
            sample_count=sample_count,
            avg_market_move_pct=avg_market_move_pct,
            positive_rate_pct=positive_rate_pct,
            score_relaxation=round(score_relaxation, 3),
            sentiment_relaxation=round(sentiment_relaxation, 3),
            momentum_relaxation=round(momentum_relaxation, 3),
            note=note,
        )

    def _summarize_outcome_features(self, rows: list[SignalOutcomeSnapshot]) -> OutcomeFeatureSet:
        weighted_count = 0.0
        weighted_move = 0.0
        missed_upside = 0.0
        safe_hold = 0.0
        false_positive = 0.0
        positive = 0.0
        label_weights: dict[str, float] = {}
        setup_type = "balanced"

        for row in rows:
            signal = row.signal
            if row.market_move_pct is None or not signal:
                continue
            weight = {4: 1.0, 24: 1.35}.get(row.horizon_hours, 0.0)
            if weight <= 0:
                continue
            setup_type = self._classify_setup_type(
                signal.asset.kind.value,
                signal.score,
                signal.sentiment_score,
                signal.momentum_score,
                extract_news_count(signal.rationale),
            )
            weighted_count += weight
            weighted_move += row.market_move_pct * weight
            label = row.outcome_label or "none"
            label_weights[label] = label_weights.get(label, 0.0) + weight
            if row.market_move_pct >= 0.25:
                positive += weight
            if label == "missed-upside":
                missed_upside += weight
            if label in {"protected-downside", "flat-safe"}:
                safe_hold += weight
            if setup_type in {"etf_pullback", "stock_event"} and row.market_move_pct <= 0.10:
                false_positive += weight

        avg_market_move_pct = round(weighted_move / weighted_count, 3) if weighted_count else 0.0
        positive_rate_pct = round((positive / weighted_count) * 100, 2) if weighted_count else 0.0
        missed_upside_rate_pct = round((missed_upside / weighted_count) * 100, 2) if weighted_count else 0.0
        safe_hold_rate_pct = round((safe_hold / weighted_count) * 100, 2) if weighted_count else 0.0
        false_positive_rate_pct = round((false_positive / weighted_count) * 100, 2) if weighted_count else 0.0
        dominant_label = max(label_weights.items(), key=lambda item: item[1])[0] if label_weights else "none"

        promote = weighted_count >= 6 and missed_upside_rate_pct >= 22.0 and avg_market_move_pct >= 0.18
        suppress = (
            (safe_hold_rate_pct >= 72.0 and avg_market_move_pct <= 0.12)
            or (setup_type in {"etf_pullback", "stock_event"} and false_positive_rate_pct >= 45.0)
        ) and weighted_count >= 5
        note = (
            f"{setup_type} pattern: {dominant_label}, avg move {avg_market_move_pct:.2f}%, "
            f"missed upside {missed_upside_rate_pct:.0f}%, safe hold {safe_hold_rate_pct:.0f}%."
        )

        return OutcomeFeatureSet(
            setup_type=setup_type,
            sample_count=int(round(weighted_count)),
            avg_market_move_pct=avg_market_move_pct,
            positive_rate_pct=positive_rate_pct,
            missed_upside_rate_pct=missed_upside_rate_pct,
            safe_hold_rate_pct=safe_hold_rate_pct,
            false_positive_rate_pct=false_positive_rate_pct,
            dominant_label=dominant_label,
            promote=promote,
            suppress=suppress,
            note=note,
        )
