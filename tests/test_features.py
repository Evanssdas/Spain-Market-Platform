import pandas as pd

from spain_power.features import aggregate_omie_daily


def test_daily_price_aggregation() -> None:
    frame = pd.DataFrame(
        {
            "delivery_date": pd.to_datetime(["2026-01-01"] * 4),
            "period": [1, 2, 3, 4],
            "price_spain_eur_mwh": [10.0, -2.0, 30.0, 20.0],
            "price_portugal_eur_mwh": [9.0, -1.0, 25.0, 19.0],
        }
    )
    daily = aggregate_omie_daily(frame)
    assert daily.loc[0, "price_peak_eur_mwh"] == 30.0
    assert daily.loc[0, "price_minimum_eur_mwh"] == -2.0
    assert daily.loc[0, "negative_price_periods"] == 1
