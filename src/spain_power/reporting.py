from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from spain_power.io_utils import read_table
from spain_power.risk import calculate_risk


def _money(value: float) -> str:
    return f"€{value:,.0f}"


def write_model_performance(bundle: dict[str, Any], config: dict) -> Path:
    path = Path(config["paths"]["reports_dir"]) / "model_performance.md"
    lines = [
        "# Spain Model Performance",
        "",
        f"- Model version: `{bundle['model_version']}`",
        f"- Training period: **{bundle['training_start']} to {bundle['training_end']}**",
        f"- Chronological holdout begins: **{bundle['holdout_start']}**",
        "",
        "| Model | MAE | RMSE | Persistence MAE | Improvement vs persistence |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, metrics in bundle["metrics"].items():
        lines.append(
            f"| {name} | {metrics['mae']:.2f} | {metrics['rmse']:.2f} | "
            f"{metrics['persistence_mae']:.2f} | "
            f"{metrics['improvement_vs_persistence_pct']:.1f}% |"
        )

    lines.extend(
        [
            "",
            "Negative improvement means the model lost to persistence on the "
            "chronological holdout and must be reported honestly.",
            "",
            "Component errors are in MW; peak-price errors are in €/MWh.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_latest_forecast(prediction: dict[str, Any], config: dict) -> Path:
    path = Path(config["paths"]["reports_dir"]) / "latest_forecast.md"
    content = f"""# Spain Next-Day Forecast

_Generated {prediction['issued_at_utc']}. Forecasts are model outputs, not market observations._

| Item | Forecast |
|---|---:|
| Target date | **{prediction['target_date']}** |
| Issue timing | **{prediction['issue_timing']}** |
| Demand | {prediction['forecast_demand_mw']:,.0f} MW |
| Wind | {prediction['forecast_wind_mw']:,.0f} MW |
| Solar | {prediction['forecast_solar_mw']:,.0f} MW |
| Nuclear | {prediction['forecast_nuclear_mw']:,.0f} MW |
| Hydro | {prediction['forecast_hydro_mw']:,.0f} MW |
| Variable residual demand | {prediction['forecast_variable_residual_mw']:,.0f} MW |
| Firm residual demand | {prediction['forecast_firm_residual_mw']:,.0f} MW |
| Daily peak price | **€{prediction['forecast_peak_price_eur_mwh']:,.2f}/MWh** |

## Model identity

- Forecast ID: `{prediction['forecast_id']}`
- Model version: `{prediction['model_version']}`
- Training data end: `{prediction['training_end']}`

## Scope

V1 predicts the next-day maximum Spanish day-ahead price. It does not yet predict
every quarter-hour or identify the marginal generating unit.
"""
    path.write_text(content, encoding="utf-8")
    return path


def write_risk_report(
    config: dict,
    prediction: dict[str, Any] | None = None,
) -> Path:
    processed = Path(config["paths"]["processed_dir"])
    prices = read_table(processed / "prices_daily.parquet")
    result = calculate_risk(prices["price_peak_eur_mwh"], config)
    risk_config = config["risk"]
    path = Path(config["paths"]["reports_dir"]) / "risk_report.md"

    stress_rows = "\n".join(
        f"| {row['shock_eur_mwh']:+.0f} €/MWh | "
        f"{row['paper_pnl_eur']:+,.0f} € |"
        for row in result.stresses
    )
    forecast_section = ""
    if prediction is not None:
        forecast_section = f"""
## Latest model forecast

- Target date: **{prediction['target_date']}**
- Forecast daily peak: **€{prediction['forecast_peak_price_eur_mwh']:,.2f}/MWh**
- Forecast firm residual demand: **{prediction['forecast_firm_residual_mw']:,.0f} MW**
"""

    content = f"""# Spain Daily Peak Price Risk Report

_Observed OMIE prices plus an illustrative paper position._

## Market data and assumptions

| Item | Value | Type |
|---|---:|---|
| Latest observed daily peak | €{result.latest_price:,.2f}/MWh | market data |
| 30-day volatility of daily changes | €{result.volatility_30:,.2f}/MWh | calculated |
| Paper position | long {float(risk_config['paper_position_mwh']):,.0f} MWh | assumption |
| Paper capital | {_money(float(risk_config['paper_capital_eur']))} | assumption |
| 95% VaR appetite | {_money(result.var_limit)} | assumption |

## Parametric one-day VaR

| Position | VaR 95% | VaR 99% |
|---|---:|---:|
| Long {float(risk_config['paper_position_mwh']):,.0f} MWh | {_money(result.var_95)} | {_money(result.var_99)} |

VaR is not a maximum possible loss.

## Volatility regime

- 30-day volatility: **€{result.volatility_30:,.2f}/MWh**
- 90-day volatility: **€{result.volatility_90:,.2f}/MWh**
- Regime: **{result.regime}**

## Absolute price-shock stresses

| Price shock | Paper P&L |
|---:|---:|
{stress_rows}

## Position sizing

- VaR-derived maximum: **{result.var_position_limit_mwh:,.0f} MWh**
- Separate volume maximum: **{float(risk_config['maximum_position_mwh']):,.0f} MWh**
- Binding maximum: **{result.binding_position_limit_mwh:,.0f} MWh**
{forecast_section}
## Limitations

Educational only. Excludes transaction costs, liquidity, basis, shape, collateral,
credit, imbalance and operational constraints.
"""
    path.write_text(content, encoding="utf-8")
    return path


def write_grading_summary(config: dict) -> Path | None:
    grades_path = Path(config["paths"]["logs_dir"]) / "forecast_grades.csv"
    if not grades_path.exists():
        return None
    grades = pd.read_csv(grades_path)
    if grades.empty:
        return None

    recent = grades.tail(30)
    path = Path(config["paths"]["reports_dir"]) / "forecast_grading.md"
    content = f"""# Forecast Grading

- Fully graded forecasts: **{len(grades)}**
- Recent 30 price MAE: **€{recent['price_absolute_error_eur_mwh'].mean():,.2f}/MWh**
- Latest graded target: **{grades['target_date'].max()}**

The prediction log remains separate and append-only.
"""
    path.write_text(content, encoding="utf-8")
    return path
