# Model Card

## Intended use

Educational and portfolio-quality Spanish next-day power-market forecasting.

## Targets

- Daily maximum demand
- Daily mean wind, solar, nuclear and hydro generation
- Daily maximum Spanish day-ahead price

## Algorithms

LightGBM regressors. The price target uses an `arcsinh` transformation.

## Evaluation

Chronological holdout and persistence benchmarks. The second-stage price model is trained on time-series out-of-fold component forecasts.

## Limitations

- V1 predicts a daily peak, not every quarter-hour.
- Historical weather is a stitched forecast series, not a perfect fixed-vintage backtest.
- Public API schemas can change.
- Behind-the-meter solar is not fully visible as measured grid generation.
- Hydro is partly dispatchable and difficult to forecast.
- The model does not identify the marginal generating unit.
- VaR is illustrative and omits liquidity, credit, collateral, shape and imbalance risk.
