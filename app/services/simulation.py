from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import Asset, MarketTick, Signal, SignalAction, SimulationAlert, SimulationStatus, StrategySimulation
from app.services.evaluation import StrategyProofService
from app.services.opportunity import BestOpportunitySelector
from app.services.strategy import extract_setup_type


class BestAssetSimulationService:
    def __init__(
        self,
        stop_loss_pct: float,
        take_profit_pct: float,
        trailing_stop_pct: float,
        proof_service: StrategyProofService,
        opportunity_selector: BestOpportunitySelector,
        simulation_budgets: list[float] | None = None,
        max_signal_age_seconds: int = 900,
        allowed_asset_kinds: set[str] | None = None,
        allowed_setup_statuses: set[str] | None = None,
    ) -> None:
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.trailing_stop_pct = trailing_stop_pct
        self.proof_service = proof_service
        self.opportunity_selector = opportunity_selector
        self.simulation_budgets = simulation_budgets or [100.0]
        self.max_signal_age_seconds = max_signal_age_seconds
        self.allowed_asset_kinds = allowed_asset_kinds or {"etf"}
        self.allowed_setup_statuses = allowed_setup_statuses or {"approved"}

    def get_active(self, db: Session) -> StrategySimulation | None:
        preferred_key = self._scenario_key(100.0)
        preferred = db.scalar(
            select(StrategySimulation)
            .options(joinedload(StrategySimulation.asset))
            .where(
                StrategySimulation.status == SimulationStatus.ACTIVE,
                StrategySimulation.scenario_key == preferred_key,
            )
            .order_by(StrategySimulation.started_at.desc())
            .limit(1)
        )
        if preferred:
            return preferred
        return db.scalar(
            select(StrategySimulation)
            .options(joinedload(StrategySimulation.asset))
            .where(StrategySimulation.status == SimulationStatus.ACTIVE)
            .order_by(StrategySimulation.started_at.desc())
            .limit(1)
        )

    def list_active(self, db: Session) -> list[StrategySimulation]:
        return db.scalars(
            select(StrategySimulation)
            .options(joinedload(StrategySimulation.asset))
            .where(StrategySimulation.status == SimulationStatus.ACTIVE)
            .order_by(StrategySimulation.initial_notional_eur.asc(), StrategySimulation.started_at.desc())
        ).all()

    def list_alerts(self, db: Session, limit: int = 12) -> list[SimulationAlert]:
        return db.scalars(
            select(SimulationAlert)
            .options(joinedload(SimulationAlert.simulation).joinedload(StrategySimulation.asset))
            .order_by(SimulationAlert.created_at.desc())
            .limit(limit)
        ).all()

    def performance_summary(self, db: Session) -> dict:
        simulations = db.scalars(
            select(StrategySimulation)
            .options(joinedload(StrategySimulation.asset))
            .order_by(StrategySimulation.started_at.desc())
        ).all()

        closed = [simulation for simulation in simulations if simulation.status == SimulationStatus.CLOSED]
        total_pnl = round(sum(simulation.pnl_eur for simulation in simulations), 4)
        wins = [simulation for simulation in closed if simulation.pnl_eur > 0]
        losses = [simulation for simulation in closed if simulation.pnl_eur < 0]
        best = max(closed, key=lambda simulation: simulation.pnl_eur, default=None)
        worst = min(closed, key=lambda simulation: simulation.pnl_eur, default=None)
        by_scenario: dict[str, dict] = {}
        by_setup: dict[str, dict] = {}

        for simulation in simulations:
            scenario = by_scenario.setdefault(
                simulation.scenario_label,
                {"label": simulation.scenario_label, "runs": 0, "active": 0, "closed": 0, "pnl": 0.0, "wins": 0, "losses": 0},
            )
            scenario["runs"] += 1
            scenario["pnl"] += simulation.pnl_eur
            if simulation.status == SimulationStatus.ACTIVE:
                scenario["active"] += 1
            else:
                scenario["closed"] += 1
                if simulation.pnl_eur > 0:
                    scenario["wins"] += 1
                elif simulation.pnl_eur < 0:
                    scenario["losses"] += 1

            setup = by_setup.setdefault(
                simulation.setup_type or "balanced",
                {"setup_type": simulation.setup_type or "balanced", "runs": 0, "closed": 0, "pnl": 0.0, "wins": 0, "losses": 0},
            )
            setup["runs"] += 1
            setup["pnl"] += simulation.pnl_eur
            if simulation.status == SimulationStatus.CLOSED:
                setup["closed"] += 1
                if simulation.pnl_eur > 0:
                    setup["wins"] += 1
                elif simulation.pnl_eur < 0:
                    setup["losses"] += 1

        return {
            "total_runs": len(simulations),
            "closed_runs": len(closed),
            "active_runs": len([simulation for simulation in simulations if simulation.status == SimulationStatus.ACTIVE]),
            "total_pnl_eur": total_pnl,
            "win_rate_pct": round((len(wins) / len(closed)) * 100, 2) if closed else 0.0,
            "avg_closed_pnl_pct": round(sum(simulation.pnl_pct for simulation in closed) / len(closed), 2) if closed else 0.0,
            "best_run": best,
            "worst_run": worst,
            "wins": len(wins),
            "losses": len(losses),
            "scenario_summaries": sorted(by_scenario.values(), key=lambda item: item["label"]),
            "setup_summaries": sorted(by_setup.values(), key=lambda item: item["pnl"], reverse=True),
        }

    def start_best_asset(self, db: Session, notional_eur: float = 100.0) -> StrategySimulation:
        signal = self._best_signal(db)
        if not signal:
            raise ValueError(
                "No fresh BUY signal is available yet. Wait for a current entry setup before starting a simulation."
            )

        scenario_key = self._scenario_key(notional_eur)
        active = db.scalar(
            select(StrategySimulation)
            .where(
                StrategySimulation.status == SimulationStatus.ACTIVE,
                StrategySimulation.scenario_key == scenario_key,
            )
            .order_by(StrategySimulation.started_at.desc())
            .limit(1)
        )
        if active:
            self._close_simulation(db, active, "Replaced by a newer best-asset simulation.")

        simulation = self._open_simulation(
            db,
            signal=signal,
            notional_eur=notional_eur,
            scenario_key=scenario_key,
            scenario_label=self._scenario_label(notional_eur),
        )
        db.commit()
        db.refresh(simulation)
        return simulation

    def ensure_scenarios(self, db: Session) -> list[StrategySimulation]:
        created: list[StrategySimulation] = []
        signal = self._best_signal(db)
        if not signal:
            return created

        active_keys = {
            row.scenario_key
            for row in db.scalars(
                select(StrategySimulation).where(StrategySimulation.status == SimulationStatus.ACTIVE)
            ).all()
        }
        for budget in self.simulation_budgets:
            scenario_key = self._scenario_key(budget)
            if scenario_key in active_keys:
                continue
            created.append(
                self._open_simulation(
                    db,
                    signal=signal,
                    notional_eur=budget,
                    scenario_key=scenario_key,
                    scenario_label=self._scenario_label(budget),
                )
            )
            active_keys.add(scenario_key)
        db.commit()
        return created

    def update_active(self, db: Session) -> list[StrategySimulation]:
        simulations = self.list_active(db)
        if not simulations:
            return []

        updated: list[StrategySimulation] = []
        for simulation in simulations:
            tick = self._latest_tick(db, simulation.asset_id)
            if not tick:
                updated.append(simulation)
                continue

            current_price = float(tick.price)
            simulation.latest_price = current_price
            simulation.updated_at = datetime.utcnow()
            simulation.pnl_eur = round((current_price - simulation.entry_price) * simulation.quantity, 4)
            simulation.pnl_pct = round((simulation.pnl_eur / simulation.initial_notional_eur) * 100, 2)

            if current_price > simulation.entry_price:
                simulation.trailing_stop_price = round(
                    max(simulation.trailing_stop_price, current_price * (1 - self.trailing_stop_pct)),
                    4,
                )

            self._emit_threshold_alerts(db, simulation)

            if current_price <= max(simulation.stop_price, simulation.trailing_stop_price):
                self._alert(
                    db,
                    simulation,
                    level="loss",
                    title="Stop loss triggered",
                    message=(
                        f"{simulation.scenario_label}: {simulation.asset.symbol} hit the protective stop. "
                        f"Simulated PnL: EUR {simulation.pnl_eur:.2f}."
                    ),
                )
                self._close_simulation(db, simulation, "Closed automatically by stop loss protection.")
            elif current_price >= simulation.take_profit_price:
                self._alert(
                    db,
                    simulation,
                    level="profit",
                    title="Take profit reached",
                    message=(
                        f"{simulation.scenario_label}: {simulation.asset.symbol} reached the profit target. "
                        f"Simulated PnL: EUR {simulation.pnl_eur:.2f}."
                    ),
                )
                self._close_simulation(db, simulation, "Closed automatically after take profit.")

            updated.append(simulation)

        db.commit()
        return updated

    def scenario_overview(self, db: Session) -> dict:
        active = self.list_active(db)
        return {
            "active": active,
            "configured_budgets": [round(budget, 2) for budget in self.simulation_budgets],
        }

    def _open_simulation(
        self,
        db: Session,
        signal: Signal,
        notional_eur: float,
        scenario_key: str,
        scenario_label: str,
    ) -> StrategySimulation:
        tick = self._latest_tick(db, signal.asset_id)
        if not tick:
            raise ValueError("No current market price available for the selected asset.")

        quantity = round(notional_eur / float(tick.price), 8)
        simulation = StrategySimulation(
            asset_id=signal.asset_id,
            scenario_key=scenario_key,
            scenario_label=scenario_label,
            setup_type=self._infer_setup_type(signal),
            opened_signal_score=signal.score,
            initial_notional_eur=round(notional_eur, 2),
            quantity=quantity,
            entry_price=float(tick.price),
            latest_price=float(tick.price),
            pnl_eur=0.0,
            pnl_pct=0.0,
            stop_price=round(float(tick.price) * (1 - self.stop_loss_pct), 4),
            take_profit_price=round(float(tick.price) * (1 + self.take_profit_pct), 4),
            trailing_stop_price=round(float(tick.price) * (1 - self.trailing_stop_pct), 4),
            opened_reason=(
                f"{scenario_label} started on best signal: {signal.asset.symbol} with score {signal.score:.2f}. "
                f"Setup {self._infer_setup_type(signal)}. {signal.rationale}"
            ),
        )
        db.add(simulation)
        db.flush()
        self._alert(
            db,
            simulation,
            level="info",
            title="Simulation started",
            message=(
                f"{scenario_label}: allocated EUR {notional_eur:.2f} to {signal.asset.symbol} "
                f"at EUR {float(tick.price):.4f}."
            ),
        )
        return simulation

    def _best_signal(self, db: Session) -> Signal | None:
        candidate = self.opportunity_selector.best_eligible_candidate(db)
        if not candidate:
            return None
        return db.scalar(
            select(Signal)
            .options(joinedload(Signal.asset))
            .where(Signal.asset_id == candidate.asset_id, Signal.action == SignalAction.BUY)
            .order_by(Signal.created_at.desc())
            .limit(1)
        )

    def _latest_tick(self, db: Session, asset_id: int) -> MarketTick | None:
        return db.scalar(
            select(MarketTick).where(MarketTick.asset_id == asset_id).order_by(MarketTick.captured_at.desc()).limit(1)
        )

    def _emit_threshold_alerts(self, db: Session, simulation: StrategySimulation) -> None:
        checkpoints = [
            ("profit_2", simulation.pnl_pct >= 2.0, "profit", "Profit alert", f"{simulation.asset.symbol} is up {simulation.pnl_pct:.2f}%."),
            ("profit_5", simulation.pnl_pct >= 5.0, "profit", "Strong profit", f"{simulation.asset.symbol} is up {simulation.pnl_pct:.2f}%."),
            ("loss_2", simulation.pnl_pct <= -2.0, "loss", "Loss alert", f"{simulation.asset.symbol} is down {simulation.pnl_pct:.2f}%."),
            ("loss_5", simulation.pnl_pct <= -5.0, "loss", "Strong loss", f"{simulation.asset.symbol} is down {simulation.pnl_pct:.2f}%."),
        ]
        flags = {flag for flag in simulation.alert_flags.split(",") if flag}
        for flag, triggered, level, title, message in checkpoints:
            if triggered and flag not in flags:
                self._alert(db, simulation, level=level, title=title, message=message)
                flags.add(flag)
        simulation.alert_flags = ",".join(sorted(flags))

    def _close_simulation(self, db: Session, simulation: StrategySimulation, reason: str) -> None:
        simulation.status = SimulationStatus.CLOSED
        simulation.closed_at = datetime.utcnow()
        simulation.updated_at = datetime.utcnow()
        self._alert(db, simulation, level="info", title="Simulation closed", message=reason)

    def _alert(self, db: Session, simulation: StrategySimulation, level: str, title: str, message: str) -> None:
        db.add(
            SimulationAlert(
                simulation_id=simulation.id,
                level=level,
                title=title,
                message=message,
            )
        )

    def _scenario_key(self, notional_eur: float) -> str:
        return f"sim_{int(round(notional_eur))}"

    def _scenario_label(self, notional_eur: float) -> str:
        return f"EUR {round(notional_eur, 2):.2f}"

    def _infer_setup_type(self, signal: Signal) -> str:
        rationale = signal.rationale.lower()
        if rationale.startswith("setup "):
            tail = rationale.split("setup ", 1)[1]
            return tail.split(":", 1)[0].strip()
        if "safe-hold bias" in rationale:
            return "safe_hold"
        if "promoted" in rationale or "near-miss" in rationale:
            return "near_miss"
        if signal.momentum_score >= 0.08 and signal.sentiment_score >= 0:
            return "trend_follow"
        if signal.sentiment_score < 0 and signal.momentum_score < 0:
            return "risk_off"
        return "balanced"
