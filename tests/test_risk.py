from app.services.risk import RiskEngine


def test_risk_engine_placeholder():
    engine = RiskEngine(
        starting_capital_eur=30,
        reserve_cash_eur=10,
        max_notional_per_trade_eur=5,
        max_open_positions=1,
        max_daily_loss_eur=3,
    )
    assert engine.reserve_cash_eur == 10
