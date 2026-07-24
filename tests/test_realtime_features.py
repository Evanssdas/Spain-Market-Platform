import pandas as pd

from spain_power.features import build_model_frame


def test_component_lags_use_calendar_day_spacing() -> None:
    dates = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-04"])
    system = pd.DataFrame(
        {
            "delivery_date": dates[:2],
            "demand_mwh": [100.0, 110.0],
            "wind_mwh": [20.0, 21.0],
            "solar_mwh": [10.0, 11.0],
            "nuclear_mwh": [30.0, 31.0],
            "hydro_mwh": [5.0, 6.0],
        }
    )
    prices = pd.DataFrame(
        {
            "delivery_date": dates,
            "price_peak_eur_mwh": [50.0, 51.0, None],
            "spain_portugal_peak_spread": [0.0, 0.0, None],
        }
    )
    weather = pd.DataFrame({"delivery_date": dates})
    frame = build_model_frame(system, prices, weather)

    target_row = frame.loc[frame["delivery_date"] == pd.Timestamp("2026-01-04")].iloc[0]
    assert "lag_demand_1" not in frame.columns
    assert target_row["lag_demand_2"] == 110.0
