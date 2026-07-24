from __future__ import annotations

import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def write(relative: str, content: str) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def replace_function_block(
    text: str,
    start_name: str,
    next_name: str,
    replacement: str,
) -> str:
    start = text.index(f"def {start_name}")
    end = text.index(f"\ndef {next_name}", start)
    return text[:start] + replacement.rstrip() + "\n\n" + text[end + 1 :]


def rename_daily_energy_units() -> None:
    candidates = [
        ROOT / "config.yaml",
        ROOT / "README.md",
        *(ROOT / "src").rglob("*.py"),
        *(ROOT / "tests").rglob("*.py"),
        *(ROOT / "docs").rglob("*.md"),
    ]
    for path in candidates:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"_mw\b", "_mwh", text)
        text = re.sub(r"\bMW\b", "MWh", text)
        path.write_text(text, encoding="utf-8")


def repair_config() -> None:
    path = ROOT / "config.yaml"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))

    source = config["sources"]["redata"]
    source["base_url"] = "https://apidatos.ree.es/es/datos"
    source["time_trunc"] = "day"
    source["chunk_days"] = 31

    aliases = config["columns"]["redata_aliases"]
    aliases.clear()
    aliases.update(
        {
            "demand_mwh": [
                "Demand",
                "Demand at busbars",
                "Demand at transmission busbars",
                "Transport demand (b.c.)",
                "Demanda",
                "Demanda transporte (b.c.)",
                "Demanda en b.c.",
                "Demanda en barras de central",
            ],
            "wind_mwh": ["Wind", "Eólica", "Eolica"],
            "solar_pv_mwh": [
                "Solar photovoltaic",
                "Solar fotovoltaica",
            ],
            "solar_thermal_mwh": [
                "Solar thermal",
                "Solar térmica",
                "Solar termica",
            ],
            "nuclear_mwh": ["Nuclear"],
            "hydro_mwh": [
                "Hydro",
                "Hydraulic",
                "Hydroelectric",
                "Hidráulica",
                "Hidraulica",
            ],
            "pumped_storage_mwh": [
                "Pumped storage",
                "Pumped-storage generation",
                "Turbinación bombeo",
                "Turbinacion bombeo",
            ],
            "pumped_consumption_mwh": [
                "Pumped storage consumption",
                "Pumping consumption",
                "Consumos en bombeo",
                "Consumo en bombeo",
            ],
            "combined_cycle_mwh": [
                "Combined cycle",
                "Ciclo combinado",
            ],
            "net_imports_mwh": [
                "International exchanges balance",
                "Cross-border exchange balance",
                "Saldo intercambios internacionales",
                "Saldo de intercambios",
            ],
        }
    )

    path.write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def repair_http_headers() -> None:
    path = ROOT / "src/spain_power/io_utils.py"
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r"session\.headers\.update\(.*?\)\n    return session", re.S)
    replacement = '''session.headers.update(
        {
            "User-Agent": "Spain-Power-Market-Platform/0.1",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
    )
    return session'''
    text = pattern.sub(replacement, text, count=1)
    path.write_text(text, encoding="utf-8")


def repair_redata_default() -> None:
    path = ROOT / "src/spain_power/data/redata.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        'source.get("time_trunc", "hour")',
        'source.get("time_trunc", "day")',
    )
    path.write_text(text, encoding="utf-8")


def repair_features() -> None:
    path = ROOT / "src/spain_power/features.py"
    text = path.read_text(encoding="utf-8")

    aggregate = '''def aggregate_redata_daily(balance: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Convert the REData daily balance into one energy row per delivery date."""
    frame = balance.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    timezone = config["project"]["timezone"]
    frame["delivery_date"] = (
        frame["timestamp"]
        .dt.tz_convert(timezone)
        .dt.tz_localize(None)
        .dt.normalize()
    )

    aliases = config["columns"]["redata_aliases"]
    selected = {
        canonical: _find_column(frame.columns, alias_list)
        for canonical, alias_list in aliases.items()
    }
    required = [
        "demand_mwh",
        "wind_mwh",
        "solar_pv_mwh",
        "solar_thermal_mwh",
        "nuclear_mwh",
        "hydro_mwh",
    ]
    missing = [name for name in required if selected.get(name) is None]
    if missing:
        available = sorted(
            column
            for column in frame.columns
            if column not in {"timestamp", "delivery_date"}
        )
        raise ValueError(
            "REData aliases did not match the live response. "
            f"Missing: {missing}. Available series: {available}"
        )

    output = pd.DataFrame(
        {"delivery_date": sorted(frame["delivery_date"].unique())}
    )
    for canonical, source_column in selected.items():
        if source_column is None:
            output[canonical] = np.nan
            continue
        values = frame.groupby("delivery_date")[source_column].last()
        output = output.merge(
            values.rename(canonical),
            on="delivery_date",
            how="left",
        )

    output["solar_mwh"] = output[
        ["solar_pv_mwh", "solar_thermal_mwh"]
    ].sum(axis=1, min_count=1)
    return output'''

    build = '''def build_model_frame(
    system_daily: pd.DataFrame,
    prices_daily: pd.DataFrame,
    weather_daily: pd.DataFrame,
) -> pd.DataFrame:
    frame = weather_daily.merge(system_daily, on="delivery_date", how="outer")
    frame = frame.merge(prices_daily, on="delivery_date", how="outer")
    frame["delivery_date"] = pd.to_datetime(frame["delivery_date"]).dt.normalize()

    # Preserve calendar-day spacing even when today's physical balance is not yet
    # published. This keeps a two-day system lag equal to target_date minus 2 days.
    calendar = pd.DataFrame(
        {
            "delivery_date": pd.date_range(
                frame["delivery_date"].min(),
                frame["delivery_date"].max(),
                freq="D",
            )
        }
    )
    frame = calendar.merge(frame, on="delivery_date", how="left")
    frame = frame.sort_values("delivery_date").reset_index(drop=True)
    frame = add_calendar_features(frame)

    component_targets = {
        "demand": "demand_mwh",
        "wind": "wind_mwh",
        "solar": "solar_mwh",
        "nuclear": "nuclear_mwh",
        "hydro": "hydro_mwh",
    }
    for name, source in component_targets.items():
        if source not in frame.columns:
            frame[source] = np.nan
        frame[f"target_{source}"] = frame[source]
        frame[f"lag_{name}_2"] = frame[source].shift(2)
        frame[f"lag_{name}_7"] = frame[source].shift(7)
        frame[f"roll_{name}_7"] = (
            frame[source].shift(2).rolling(7, min_periods=3).mean()
        )
        frame[f"roll_{name}_28"] = (
            frame[source].shift(2).rolling(28, min_periods=7).mean()
        )

    price_source = "price_peak_eur_mwh"
    if price_source not in frame.columns:
        frame[price_source] = np.nan
    frame["target_price_peak_eur_mwh"] = frame[price_source]
    frame["lag_price_1"] = frame[price_source].shift(1)
    frame["lag_price_2"] = frame[price_source].shift(2)
    frame["lag_price_7"] = frame[price_source].shift(7)
    frame["roll_price_7"] = (
        frame[price_source].shift(1).rolling(7, min_periods=3).mean()
    )
    frame["roll_price_28"] = (
        frame[price_source].shift(1).rolling(28, min_periods=7).mean()
    )
    frame["roll_price_change_vol30"] = (
        frame[price_source].diff().shift(1).rolling(30, min_periods=10).std()
    )

    spread = (
        frame["spain_portugal_peak_spread"]
        if "spain_portugal_peak_spread" in frame
        else pd.Series(index=frame.index, dtype=float)
    )
    frame["lag_spain_portugal_spread_1"] = spread.shift(1)
    return frame'''

    text = replace_function_block(
        text,
        "aggregate_redata_daily",
        "_weighted_group_daily",
        aggregate,
    )
    text = replace_function_block(
        text,
        "build_model_frame",
        "base_feature_columns",
        build,
    )
    path.write_text(text, encoding="utf-8")


def repair_modeling() -> None:
    path = ROOT / "src/spain_power/modeling.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace('f"lag_{component}_1"', 'f"lag_{component}_2"')
    path.write_text(text, encoding="utf-8")


def repair_pipeline() -> None:
    path = ROOT / "src/spain_power/pipeline.py"
    text = path.read_text(encoding="utf-8")
    start = text.index("def daily_forecast")
    tail = '''def daily_forecast(config: dict) -> dict[str, Any]:
    """Refresh known data and forecast tomorrow without using future outturns."""
    today = pd.Timestamp.now(tz=config["project"]["timezone"]).date()
    yesterday = today - timedelta(days=1)
    lookback_start = today - timedelta(days=60)
    raw = Path(config["paths"]["raw_dir"])

    collect_omie_range(
        lookback_start,
        today,
        output_path=raw / "omie_prices.parquet",
        config=config,
        timezone=config["project"]["timezone"],
    )
    collect_redata_range(
        lookback_start,
        yesterday,
        output_path=raw / "redata_balance.parquet",
        config=config,
    )
    collect_weather_range(
        lookback_start,
        yesterday,
        output_path=raw / "weather_historical.parquet",
        config=config,
        historical=True,
    )
    process_all(config)
    return forecast(today + timedelta(days=1), config)


def daily_grade(config: dict) -> pd.DataFrame:
    today = pd.Timestamp.now(tz=config["project"]["timezone"]).date()
    refresh_actuals(
        today - timedelta(days=60),
        today - timedelta(days=1),
        config,
    )
    grades = grade_available_forecasts(config)
    write_grading_summary(config)
    write_risk_report(config)
    return grades
'''
    path.write_text(text[:start] + tail, encoding="utf-8")


def repair_documentation() -> None:
    write(
        "docs/model_card.md",
        """# Model Card

## Intended use

Educational and portfolio-quality Spanish next-day power-market forecasting.

## Targets

- Daily peninsular demand energy in MWh
- Daily wind, solar, nuclear and hydro energy in MWh
- Daily maximum Spanish day-ahead price in €/MWh

## Evaluation

Chronological holdout and persistence benchmarks. The second-stage price model uses time-series out-of-fold component forecasts.

## Information timing

For a tomorrow forecast, component actuals use a two-calendar-day lag because today's complete physical balance is not available before the day-ahead auction. Today's published day-ahead price can be used as a one-day price lag.

## Limitations

- V1 predicts a daily peak price, not every quarter-hour.
- Historical weather is not a perfect fixed-vintage backtest.
- Public API schemas can change.
- Behind-the-meter solar is not fully visible.
- Hydro is partly dispatchable and difficult to forecast.
- VaR is illustrative and omits liquidity, credit, collateral, shape and imbalance risk.
""",
    )
    write(
        "docs/data_dictionary.md",
        """# Data Dictionary

## Daily REData energy targets

| Column | Meaning |
|---|---|
| `demand_mwh` | Daily peninsular demand energy |
| `wind_mwh` | Daily wind energy |
| `solar_mwh` | Daily photovoltaic plus solar-thermal energy |
| `nuclear_mwh` | Daily nuclear energy |
| `hydro_mwh` | Daily hydro energy |

## OMIE price data

Prices are stored in €/MWh at the market-period level and aggregated into daily peak, average and minimum features.
""",
    )


def write_timing_test() -> None:
    write(
        "tests/test_realtime_features.py",
        '''import pandas as pd

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
''',
    )


def ensure_pytest() -> None:
    path = ROOT / "requirements.txt"
    text = path.read_text(encoding="utf-8")
    if "pytest" not in text:
        path.write_text(text.rstrip() + "\npytest>=8,<9\n", encoding="utf-8")


def main() -> None:
    rename_daily_energy_units()
    repair_config()
    repair_http_headers()
    repair_redata_default()
    repair_features()
    repair_modeling()
    repair_pipeline()
    repair_documentation()
    write_timing_test()
    ensure_pytest()
    print("Repository repaired successfully.")


if __name__ == "__main__":
    main()
