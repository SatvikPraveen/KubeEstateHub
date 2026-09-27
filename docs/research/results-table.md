Replications: 50, listings per market: 3000, folds: 5, nominal interval coverage: 90%, base seed: 42.

| Coefficient | True | Bias | RMSE | 95% Wald coverage |
|---|---:|---:|---:|---:|
| `log_sqft` | 0.8500 | -0.00131 | 0.01296 | 0.94 |
| `bedrooms` | -0.0200 | -0.00040 | 0.00491 | 0.88 |
| `bathrooms` | 0.0600 | +0.00091 | 0.00634 | 0.90 |
| `age` | -0.0040 | -0.00002 | 0.00013 | 0.94 |

Price index RMSE (index points, base = 100): 3.043 (sd 1.716).

| Model | Median APE | MAPE | PPE10 | PPE20 | Interval coverage | Relative width |
|---|---:|---:|---:|---:|---:|---:|
| hedonic_conformal | 8.20% | 9.81% | 58.92% | 89.79% | 0.902 ± 0.006 | 0.405 |
| comparables_conformal | 10.34% | 12.71% | 48.63% | 80.09% | 0.902 ± 0.008 | 0.530 |
