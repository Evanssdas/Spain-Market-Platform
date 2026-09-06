# Spain Daily Peak Price Risk Report

_Observed OMIE prices plus an illustrative paper position._

## Market data and assumptions

| Item | Value | Type |
|---|---:|---|
| Latest observed daily peak | €249.30/MWh | market data |
| 30-day volatility of daily changes | €26.40/MWh | calculated |
| Paper position | long 100 MWh | assumption |
| Paper capital | €500,000 | assumption |
| 95% VaR appetite | €10,000 | assumption |

## Parametric one-day VaR

| Position | VaR 95% | VaR 99% |
|---|---:|---:|
| Long 100 MWh | €4,343 | €6,143 |

VaR is not a maximum possible loss.

## Volatility regime

- 30-day volatility: **€26.40/MWh**
- 90-day volatility: **€31.41/MWh**
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

- VaR-derived maximum: **230 MWh**
- Separate volume maximum: **2,000 MWh**
- Binding maximum: **230 MWh**

## Latest model forecast

- Target date: **2026-09-07**
- Forecast daily peak: **€189.50/MWh**
- Forecast firm residual demand: **297,319 MWh**

## Limitations

Educational only. Excludes transaction costs, liquidity, basis, shape, collateral,
credit, imbalance and operational constraints.
