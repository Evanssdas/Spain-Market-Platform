# Spain Daily Peak Price Risk Report

_Observed OMIE prices plus an illustrative paper position._

## Market data and assumptions

| Item | Value | Type |
|---|---:|---|
| Latest observed daily peak | €310.44/MWh | market data |
| 30-day volatility of daily changes | €34.92/MWh | calculated |
| Paper position | long 100 MWh | assumption |
| Paper capital | €500,000 | assumption |
| 95% VaR appetite | €10,000 | assumption |

## Parametric one-day VaR

| Position | VaR 95% | VaR 99% |
|---|---:|---:|
| Long 100 MWh | €5,744 | €8,123 |

VaR is not a maximum possible loss.

## Volatility regime

- 30-day volatility: **€34.92/MWh**
- 90-day volatility: **€36.00/MWh**
- Regime: **NORMAL**

## Absolute price-shock stresses

| Price shock | Paper P&L |
|---:|---:|
| -100 €/MWh | -10,000 € |
| -50 €/MWh | -5,000 € |
| +50 €/MWh | +5,000 € |
| +100 €/MWh | +10,000 € |
| +200 €/MWh | +20,000 € |

## Position sizing

- VaR-derived maximum: **174 MWh**
- Separate volume maximum: **2,000 MWh**
- Binding maximum: **174 MWh**

## Latest model forecast

- Target date: **2026-11-07**
- Forecast daily peak: **€158.01/MWh**
- Forecast firm residual demand: **265,314 MWh**

## Limitations

Educational only. Excludes transaction costs, liquidity, basis, shape, collateral,
credit, imbalance and operational constraints.
