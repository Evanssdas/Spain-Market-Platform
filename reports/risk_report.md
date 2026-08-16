# Spain Daily Peak Price Risk Report

_Observed OMIE prices plus an illustrative paper position._

## Market data and assumptions

| Item | Value | Type |
|---|---:|---|
| Latest observed daily peak | €215.04/MWh | market data |
| 30-day volatility of daily changes | €36.12/MWh | calculated |
| Paper position | long 100 MWh | assumption |
| Paper capital | €500,000 | assumption |
| 95% VaR appetite | €10,000 | assumption |

## Parametric one-day VaR

| Position | VaR 95% | VaR 99% |
|---|---:|---:|
| Long 100 MWh | €5,941 | €8,403 |

VaR is not a maximum possible loss.

## Volatility regime

- 30-day volatility: **€36.12/MWh**
- 90-day volatility: **€29.51/MWh**
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

- VaR-derived maximum: **168 MWh**
- Separate volume maximum: **2,000 MWh**
- Binding maximum: **168 MWh**

## Latest model forecast

- Target date: **2026-08-17**
- Forecast daily peak: **€214.99/MWh**
- Forecast firm residual demand: **275,935 MWh**

## Limitations

Educational only. Excludes transaction costs, liquidity, basis, shape, collateral,
credit, imbalance and operational constraints.
