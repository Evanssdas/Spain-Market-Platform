# Spain Model Performance

- Model version: `20260724T013523Z`
- Training period: **2025-01-01 to 2026-07-23**
- Chronological holdout begins: **2026-04-30**

| Model | MAE | RMSE | Persistence MAE | Improvement vs persistence |
|---|---:|---:|---:|---:|
| demand | 19777.14 | 26141.23 | 65515.61 | 69.8% |
| wind | 13169.00 | 15858.17 | 42778.27 | 69.2% |
| solar | 36443.49 | 39850.16 | 28145.96 | -29.5% |
| nuclear | 8908.17 | 11049.78 | 6761.45 | -31.7% |
| hydro | 7414.46 | 9212.17 | 16947.54 | 56.3% |
| price_peak | 23.03 | 32.91 | 19.78 | -16.4% |

Negative improvement means the model lost to persistence on the chronological holdout and must be reported honestly.

Component errors are in MWh; peak-price errors are in €/MWh.
