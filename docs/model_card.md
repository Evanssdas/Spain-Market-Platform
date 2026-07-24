# Model Card

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
