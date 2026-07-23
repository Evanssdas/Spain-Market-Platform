from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class RiskResult:
    latest_price: float
    volatility_30: float
    volatility_90: float
    var_95: float
    var_99: float
    var_limit: float
    var_position_limit_mwh: float
    binding_position_limit_mwh: float
    regime: str
    stresses: list[dict[str, float]]


def calculate_risk(daily_prices: pd.Series, config: dict) -> RiskResult:
    prices = pd.to_numeric(daily_prices, errors="coerce").dropna()
    if len(prices) < 31:
        raise ValueError(
            "At least 31 daily price observations are required for the risk report."
        )

    risk = config["risk"]
    position = float(risk["paper_position_mwh"])
    capital = float(risk["paper_capital_eur"])
    appetite = float(risk["var_appetite_fraction"])
    volume_limit = float(risk["maximum_position_mwh"])
    changes = prices.diff().dropna()

    window = int(risk.get("volatility_window_days", 30))
    volatility_30 = float(changes.tail(window).std(ddof=1))
    volatility_90 = float(changes.tail(90).std(ddof=1))
    z95 = float(risk["var_confidence_95_z"])
    z99 = float(risk["var_confidence_99_z"])

    var_95 = abs(position) * volatility_30 * z95
    var_99 = abs(position) * volatility_30 * z99
    var_limit = capital * appetite
    var_position_limit = (
        var_limit / (volatility_30 * z95)
        if volatility_30 > 0
        else volume_limit
    )
    binding = min(volume_limit, var_position_limit)

    if volatility_30 > 1.5 * volatility_90:
        regime = "ELEVATED"
    elif volatility_30 < 0.7 * volatility_90:
        regime = "CALM"
    else:
        regime = "NORMAL"

    stresses = [
        {
            "shock_eur_mwh": float(shock),
            "paper_pnl_eur": float(position * float(shock)),
        }
        for shock in risk["stress_shocks_eur_mwh"]
    ]
    return RiskResult(
        latest_price=float(prices.iloc[-1]),
        volatility_30=volatility_30,
        volatility_90=volatility_90,
        var_95=float(var_95),
        var_99=float(var_99),
        var_limit=float(var_limit),
        var_position_limit_mwh=float(var_position_limit),
        binding_position_limit_mwh=float(binding),
        regime=regime,
        stresses=stresses,
    )
