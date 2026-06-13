from datetime import datetime

from pydantic import BaseModel


class AssetOut(BaseModel):
    id: int
    symbol: str
    name: str
    external_id: str
    kind: str

    model_config = {"from_attributes": True}


class SignalOut(BaseModel):
    id: int
    asset_symbol: str
    asset_kind: str
    setup_type: str | None = None
    action: str
    score: float
    sentiment_score: float
    momentum_score: float
    rationale: str
    created_at: datetime


class TradeOut(BaseModel):
    id: int
    asset_symbol: str
    execution_target: str
    side: str
    status: str
    notional_eur: float
    quantity: float
    price: float
    reason: str
    executed_at: datetime


class PositionOut(BaseModel):
    id: int
    asset_symbol: str
    status: str
    quantity: float
    entry_price: float
    stop_loss: float
    take_profit: float
    opened_at: datetime
    closed_at: datetime | None
    exit_price: float | None
    pnl_eur: float | None


class NewsItemOut(BaseModel):
    id: int
    asset_symbol: str | None
    source: str
    title: str
    summary: str
    url: str
    sentiment_score: float
    event_type: str
    published_at: datetime


class SummaryOut(BaseModel):
    starting_capital_eur: float
    reserve_cash_eur: float
    available_cash_eur: float
    open_positions: int
    closed_positions: int
    realized_pnl_eur: float
    latest_signal_count: int
    stop_loss_pct: float
    take_profit_pct: float
    trailing_stop_pct: float


class BenchmarkRowOut(BaseModel):
    symbol: str
    return_pct: float
    alpha_pct: float
    start_price: float
    latest_price: float


class BenchmarkReportOut(BaseModel):
    strategy_return_pct: float
    rows: list[BenchmarkRowOut]
    best_benchmark: BenchmarkRowOut | None


class PerformanceOut(BaseModel):
    closed_positions: int
    winning_positions: int
    losing_positions: int
    breakeven_positions: int
    win_rate_pct: float
    realized_pnl_eur: float
    unrealized_pnl_eur: float
    net_pnl_eur: float
    current_equity_eur: float
    peak_equity_eur: float
    strategy_return_pct: float
    avg_closed_pnl_eur: float
    avg_closed_pnl_pct: float
    avg_win_eur: float
    avg_loss_eur: float
    expectancy_eur: float
    expectancy_pct: float
    profit_factor: float | None
    max_drawdown_eur: float
    max_drawdown_pct: float
    current_drawdown_eur: float
    current_drawdown_pct: float
    benchmark_alpha_summary: str


class SetupScorecardRowOut(BaseModel):
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


class SetupScorecardReportOut(BaseModel):
    generated_at: datetime
    total_resolved: int
    approved_count: int
    watch_count: int
    disabled_count: int
    rows: list[SetupScorecardRowOut]


class WalkForwardSliceOut(BaseModel):
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


class SetupWalkForwardRowOut(BaseModel):
    asset_kind: str
    setup_type: str
    recommendation: str
    live_proof_status: str
    eligible_for_unattended: bool
    sample_count: int
    live_sample_count: int
    replay_sample_count: int
    split_ratio_train_pct: int
    train: WalkForwardSliceOut
    test: WalkForwardSliceOut
    latest_outcome_at: datetime | None
    note: str


class SetupWalkForwardReportOut(BaseModel):
    generated_at: datetime
    total_resolved: int
    approved_count: int
    watch_count: int
    disabled_count: int
    replay_total_resolved: int
    earliest_signal_at: datetime | None
    latest_signal_at: datetime | None
    rows: list[SetupWalkForwardRowOut]


class PendingSetupRowOut(BaseModel):
    asset_kind: str
    setup_type: str
    action: str
    pending_count: int
    horizons: list[int]
    latest_signal_at: datetime | None
    next_due_label: str


class PendingSetupReportOut(BaseModel):
    generated_at: datetime
    total_pending: int
    rows: list[PendingSetupRowOut]


class SetupMonitorItemOut(BaseModel):
    asset_symbol: str | None = None
    asset_kind: str
    setup_type: str
    action: str | None = None
    recommendation: str
    live_proof_status: str
    eligible_for_unattended: bool
    live_sample_count: int
    replay_sample_count: int
    pending_count: int
    next_due_label: str
    test_net_expectancy_pct: float | None = None
    next_target: str | None = None
    note: str


class SetupMonitorAlertOut(BaseModel):
    severity: str
    title: str
    message: str


class SetupMonitorReportOut(BaseModel):
    generated_at: datetime
    overall_state: str
    overall_message: str
    ready_setups_count: int
    building_live_count: int
    replay_only_count: int
    nearest_candidate: SetupMonitorItemOut | None
    active_candidate: SetupMonitorItemOut | None
    recovery_candidate: SetupMonitorItemOut | None = None
    alerts: list[SetupMonitorAlertOut]


class ApprovalFocusGapOut(BaseModel):
    label: str
    status: str
    detail: str


class ApprovalFocusReportOut(BaseModel):
    generated_at: datetime
    objective: str
    state: str
    headline: str
    message: str
    target_setup: str | None = None
    target_asset_kind: str | None = None
    scorecard_status: str | None = None
    walkforward_status: str | None = None
    live_proof_status: str | None = None
    pending_count: int = 0
    next_due_label: str | None = None
    latest_outcome_at: datetime | None = None
    evidence_status: str | None = None
    evidence_message: str | None = None
    gaps: list[ApprovalFocusGapOut]


class LaunchReadinessGateOut(BaseModel):
    key: str
    title: str
    status: str
    summary: str
    detail: str
    next_step: str


class LaunchReadinessReportOut(BaseModel):
    generated_at: datetime
    objective: str
    overall_state: str
    overall_message: str
    current_tier: str
    approved_gates: int
    watch_gates: int
    blocked_gates: int
    can_deploy_low_attention: bool
    can_deploy_real_money: bool
    next_unlock: str | None = None
    gates: list[LaunchReadinessGateOut]


class LiveDeploymentCheckOut(BaseModel):
    key: str
    title: str
    status: str
    detail: str


class LiveDeploymentReadinessOut(BaseModel):
    generated_at: datetime
    overall_state: str
    overall_message: str
    live_mode_enabled: bool
    emergency_stop_active: bool
    checks_passed: int
    checks_total: int
    next_step: str | None = None
    checks: list[LiveDeploymentCheckOut]


class OperatorAlertPolicyOut(BaseModel):
    generated_at: datetime
    configured: bool
    webhook_enabled: bool
    transport: str
    supported_transports: list[str]
    events: list[str]
    coverage: list[str]
    interactive_commands: list[str]
    message: str


class ExecutionAuditTimelineItemOut(BaseModel):
    occurred_at: datetime
    source_type: str
    status: str
    title: str
    detail: str
    symbol: str | None = None


class ExecutionAuditOut(BaseModel):
    generated_at: datetime
    heartbeat_state: str
    heartbeat_message: str
    quote_safety_state: str
    quote_safety_message: str
    reconciliation_state: str
    reconciliation_message: str
    live_guard_state: str
    live_guard_message: str
    last_engine_completed_at: datetime | None
    last_engine_status: str
    pending_intents: int
    failed_intents: int
    fills_24h: int
    skips_24h: int
    failed_24h: int
    state_changes_24h: int
    timeline: list[ExecutionAuditTimelineItemOut]


class GoLiveRunbookOut(BaseModel):
    generated_at: datetime
    title: str
    objective: str
    first_capital_eur: float
    max_positions: int
    max_daily_loss_eur: float
    emergency_stop_active: bool
    env_changes: list[dict]
    preflight_steps: list[str]
    first_day_rules: list[str]
    rollback_steps: list[str]


class DemoPreviewOut(BaseModel):
    asset_symbol: str
    entry_price: float
    exit_price: float
    notional_eur: float
    quantity: float
    scenario_pct: float
    pnl_eur: float
    pnl_pct: float


class ActiveDemoPositionOut(BaseModel):
    asset_symbol: str
    asset_kind: str
    status: str
    quantity: float
    invested_notional_eur: float
    entry_price: float
    current_price: float | None
    current_value_eur: float | None
    stop_loss: float
    take_profit: float
    unrealized_pnl_eur: float | None
    unrealized_pnl_pct: float | None
    opened_at: datetime
    updated_at: datetime | None


class BrokerStatusOut(BaseModel):
    provider: str
    mode: str
    enabled: bool
    configured: bool
    connected: bool
    account_id: str | None
    account_status: str | None
    buying_power: str | None
    currency: str | None
    message: str


class BrokerCapabilitiesOut(BaseModel):
    provider: str
    mode: str
    execution_target: str
    enabled: bool
    supports_paper: bool
    supports_live: bool
    supported_asset_kinds: list[str]
    requires_usd_notional: bool
    submit_enabled: bool
    live_guard_enabled: bool
    notes: list[str]


class BrokerOrderResultOut(BaseModel):
    provider: str
    mode: str
    submitted: bool
    dry_run: bool
    endpoint: str
    payload: dict
    client_order_id: str | None
    broker_order_id: str | None
    broker_status: str | None
    message: str
    requested_notional_eur: float | None
    converted_notional_usd: float | None
    fx_rate_eur_usd: float | None
    fx_rate_provider: str | None
    fx_rate_as_of: str | None
    fx_buffer_pct: float | None


class BrokerPositionOut(BaseModel):
    symbol: str
    qty: float
    market_value: float
    side: str
    avg_entry_price: float | None
    current_price: float | None
    unrealized_pl: float | None
    currency: str | None


class BrokerOrderOut(BaseModel):
    broker_order_id: str
    client_order_id: str | None
    symbol: str
    side: str
    status: str
    notional: float | None
    qty: float | None
    filled_qty: float | None
    filled_avg_price: float | None
    created_at: str | None
    updated_at: str | None


class ExecutionIntentOut(BaseModel):
    id: int
    intent_key: str
    asset_symbol: str
    signal_id: int | None
    position_id: int | None
    mode: str
    execution_target: str
    side: str
    status: str
    source: str
    notional_eur: float
    price_hint: float | None
    quantity: float | None
    reason: str
    broker_provider: str | None
    broker_order_id: str | None
    broker_status: str | None
    error_message: str
    created_at: datetime
    updated_at: datetime


class StateEventOut(BaseModel):
    id: int
    event_key: str
    category: str
    severity: str
    title: str
    message: str
    fingerprint: str
    created_at: datetime


class ReconciliationStatusOut(BaseModel):
    status: str
    mode: str
    execution_target: str
    provider: str
    broker_connected: bool
    broker_account_id: str | None
    broker_buying_power: str | None
    ledger_open_positions: int
    ledger_closed_positions: int
    ledger_open_notional_eur: float
    ledger_realized_pnl_eur: float
    pending_intents: int
    failed_intents: int
    message: str


class ReconciliationDetailOut(BaseModel):
    status: str
    mode: str
    execution_target: str
    provider: str
    broker_connected: bool
    broker_account_id: str | None
    broker_buying_power: str | None
    ledger_open_positions: int
    ledger_closed_positions: int
    ledger_open_notional_eur: float
    ledger_realized_pnl_eur: float
    pending_intents: int
    failed_intents: int
    message: str
    broker_open_positions: int
    broker_open_orders: int
    broker_filled_orders: int
    position_mismatches: list[str]
    intent_mismatches: list[str]
    broker_positions: list[BrokerPositionOut]
    recent_broker_orders: list[BrokerOrderOut]


class SimulationOut(BaseModel):
    id: int
    asset_symbol: str
    asset_kind: str
    status: str
    initial_notional_eur: float
    quantity: float
    entry_price: float
    latest_price: float
    pnl_eur: float
    pnl_pct: float
    stop_price: float
    take_profit_price: float
    trailing_stop_price: float
    opened_reason: str
    started_at: datetime
    updated_at: datetime
    closed_at: datetime | None


class SimulationAlertOut(BaseModel):
    id: int
    level: str
    title: str
    message: str
    asset_symbol: str | None
    created_at: datetime
