import pandas as pd

from spain_power.risk import calculate_risk


def test_risk_calculation() -> None:
    prices = pd.Series(
        [50 + ((index % 7) - 3) * 2 for index in range(120)],
        dtype=float,
    )
    config = {
        "risk": {
            "paper_position_mwh": 100.0,
            "paper_capital_eur": 500000.0,
            "var_confidence_95_z": 1.6448536269514722,
            "var_confidence_99_z": 2.3263478740408408,
            "var_appetite_fraction": 0.02,
            "maximum_position_mwh": 2000.0,
            "volatility_window_days": 30,
            "stress_shocks_eur_mwh": [-100, 100],
        }
    }
    result = calculate_risk(prices, config)
    assert result.var_95 > 0
    assert result.binding_position_limit_mwh > 0
    assert len(result.stresses) == 2
