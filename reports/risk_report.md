# Spain Daily Peak Price Risk Report

_Observed OMIE prices plus an illustrative paper position._

## Market data and assumptions

| Item | Value | Type |
|---|---:|---|
| Latest observed daily peak | €225.57/MWh | market data |
| 30-day volatility of daily changes | €34.25/MWh | calculated |
| Paper position | long 100 MWh | assumption |
| Paper capital | €500,000 | assumption |
| 95% VaR appetite | €10,000 | assumption |

## Parametric one-day VaR

| Position | VaR 95% | VaR 99% |
|---|---:|---:|
| Long 100 MWh | €5,634 | €7,969 |

VaR is not a maximum possible loss.

## Volatility regime

- 30-day volatility: **€34.25/MWh**
- 90-day volatility: **€32.20/MWh**
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

- VaR-derived maximum: **177 MWh**
- Separate volume maximum: **2,000 MWh**
- Binding maximum: **177 MWh**

## Latest model forecast

- Target date: **2026-09-21**
- Forecast daily peak: **€153.79/MWh**
- Forecast firm residual demand: **192,234 MWh**

## Limitations

Educational only. Excludes transaction costs, liquidity, basis, shape, collateral,
credit, imbalance and operational constraints.
