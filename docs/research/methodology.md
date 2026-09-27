# Statistical methodology

This document specifies every estimator the analytics pipeline uses, the assumptions
behind it, and how it is validated. The implementation lives in
`src/analytics-worker/analytics_worker/`. The validation study is in
[results.md](results.md).

## 1. Data and notation

A listing *i* has a list price $L_i$, and, if closed, a sale price $P_i$, listing date
$t^{\text{list}}_i$ and sale date $t^{\text{sold}}_i$. It also has structural attributes:
living area $s_i$ (sqft), bedrooms $b_i$, bathrooms $h_i$ and year built $y_i$. Its
categorical attributes are city $c_i$ and property type $k_i$. The period $p_i$ is the
calendar month of the reference date: the sale date for sales, the listing date for open
listings.

Market snapshots condition on an as-of date $T$ and a window $W$ (default 90 days).

## 2. Market indicators (`market.py`)

| Indicator | Definition |
|---|---|
| Closed sales $n_s$ | $\lvert\{i: T-W < t^{\text{sold}}_i \le T\}\rvert$ |
| Active inventory $n_a$ | Listings with $t^{\text{list}}_i \le T$ that are active/pending, or sold after $T$ |
| Median sale price | $\operatorname{med}(P_i)$ over closed sales, with a 95% percentile-bootstrap CI (2,000 resamples) |
| Days on market | $\operatorname{med}(t^{\text{sold}}_i - t^{\text{list}}_i)$ |
| Sale-to-list ratio | $\operatorname{med}(P_i / L_i)$ |
| Monthly sales rate | $r = n_s / (W / 30.4375)$ |
| Months of supply | $n_a / r$ (undefined if $r = 0$) |
| Absorption rate | $r / n_a$ |

Medians are used throughout because house prices are right-skewed and contain data-entry
outliers.

### 2.1 Trend detection

The original implementation labelled a market "up" or "down" when the latest two weekly
means differed by more than ±5%. Such a rule has no error control: with about 40 sales a
week it fires on sampling noise alone. It is replaced by the following procedure.

1. **Series.** For each month in the last 12 with at least 3 sales, take
   $z_m = \log \operatorname{med}(P_i / s_i)$. This is the log median price per square
   foot, a simple composition adjustment against months that happen to sell larger homes.
   At least 4 such months are required. Otherwise the segment is `insufficient_data`.
2. **Magnitude:** the Theil–Sen slope (Theil, 1950; Sen, 1968) of $z_m$ on the month
   index, $\hat\beta = \operatorname{med}_{j<k} (z_k - z_j)/(m_k - m_j)$. It is reported
   as $100(e^{\hat\beta}-1)$ % per month, with Sen's distribution-free 95% CI. The
   estimator's breakdown point is about 29%, so a few bad months cannot swing it.
3. **Significance:** the two-sided Mann–Kendall test (Mann, 1945; Kendall, 1975) on
   $z_m$. It uses the tie-corrected variance
   $\operatorname{Var}(S) = [n(n-1)(2n+5) - \sum_t t(t-1)(2t+5)]/18$ and the continuity
   correction $Z = (S - \operatorname{sgn} S)/\sqrt{\operatorname{Var}(S)}$.
4. **Classification:** `up` or `down` only if $p < \alpha = 0.05$. Otherwise `flat`.

Under the null of no trend the false-positive rate is therefore at most about 5%. It is
slightly below because the continuity correction makes the test conservative. The unit
tests check this rate empirically (2,000 null series), and they check that a true
±1.2%/month drift is detected and covered by the slope CI.

**Validation.** `stats.theil_sen` reproduces `scipy.stats.theilslopes` exactly, including
the CI order statistics. `stats.mann_kendall` reproduces Kendall's τ from SciPy.

## 3. Hedonic price model (`hedonic.py`)

The log-linear hedonic model (Rosen, 1974) with a time-dummy index (de Haan & Diewert,
2013, *Handbook on Residential Property Price Indices*, ch. 5):

$$
\log P_i = \beta_0 + \beta_1 \log s_i + \beta_2 b_i + \beta_3 h_i + \beta_4 a_i
+ \sum_{c} \alpha_c \mathbb 1[c_i=c] + \sum_{k} \tau_k \mathbb 1[k_i=k]
+ \sum_{p} \gamma_p \mathbb 1[p_i=p] + \varepsilon_i ,
$$

Here $a_i$ is the age at sale. Categorical effects use treatment coding: the
alphabetically first city and type, and the earliest month, are the reference levels. The
model is estimated by OLS on complete-case closed sales.

* **Standard errors** are heteroskedasticity-robust, HC1 (White, 1980; MacKinnon & White,
  1985): $\widehat{\operatorname{Var}}(\hat\beta) = \frac{n}{n-k}(X^\top X)^{-1} X^\top
  \operatorname{diag}(\hat e^2) X (X^\top X)^{-1}$. Rank-deficient designs are rejected
  instead of silently regularised.
* **Retransformation.** $\exp(\hat\mu)$ estimates the conditional *median* price. The
  point estimate therefore uses Duan's (1983) smearing factor, $\hat P = e^{\hat\mu} \cdot
  n^{-1}\sum_i e^{\hat e_i}$.
* **Price index.** $I_p = 100\exp(\hat\gamma_p - \tfrac12\widehat{\operatorname{Var}}(\hat\gamma_p))$.
  This is Kennedy's (1981) correction for the bias of exponentiating an estimated dummy
  coefficient. The delta-method standard error is $I_p \cdot \operatorname{se}(\hat\gamma_p)$.
* **Unseen levels.** A city, type or month not present in the training data makes the
  prediction invalid (`NaN`) rather than silently extrapolated.

## 4. Comparable-sales model (`comparables.py`)

This is a k-nearest-neighbour automated valuation model (AVM), mirroring appraisal
practice:

1. Candidates are restricted to the same city and property type.
2. Features are $(\log s, b, h, a)$, z-standardised on the training set, compared with
   Euclidean distance.
3. **Time adjustment.** Sale prices are deflated by the hedonic index to base-period
   prices and re-inflated to the target's valuation period:
   $P^\ast_j = P_j \cdot I_{p^\ast}/I_{p_j}$.
4. The estimate is $\exp\big(\sum_j w_j \log P^\ast_j / \sum_j w_j\big)$ over the $k = 8$
   nearest comparables, with $w_j = 1/(d_j + \epsilon)$.

## 5. Prediction intervals: split conformal (`conformal.py`)

Parametric log-normal intervals depend on correct model specification. The platform
instead reports **split-conformal** intervals (Vovk et al., 2005; Lei et al., 2018), which
wrap any point predictor:

1. Split the training sales into a proper-training set (80%) and a calibration set (20%),
   using a seeded split.
2. Fit on the proper-training set and compute scores
   $R_j = \lvert \log P_j - \log \hat P_j \rvert$ on the calibration set.
3. Let $\hat q$ be the $\lceil (n+1)(1-\alpha)\rceil$-th smallest score. If that rank
   exceeds $n$, the interval is unbounded.
4. The interval is $[\hat P e^{-\hat q},\ \hat P e^{\hat q}]$.

If calibration and test points are exchangeable, this interval has **finite-sample
marginal coverage of at least $1-\alpha$**, whatever the data distribution or model
misspecification. The unit tests verify coverage under heavy-tailed (Student-*t*, 2 df)
errors for α ∈ {0.05, 0.10, 0.20}. The guarantee is *marginal*, not conditional on
segment, and it fails under distribution shift. That is why coverage is monitored in
production and alerts below 85% (see [slo.md](slo.md)).

## 6. Evaluation protocol (`evaluation.py`)

Models are compared with seeded k-fold cross-validation (k = 5), using pooled
out-of-fold predictions. The calibration split is nested inside each training fold, so
the test fold is never used for fitting or calibration. The metrics follow the IAAO
*Standard on Automated Valuation Models* (2018):

| Metric | Definition |
|---|---|
| Median APE | $\operatorname{med}\lvert\hat P - P\rvert/P$, the headline accuracy |
| MAPE | mean absolute percentage error |
| PPE10 / PPE20 | share of estimates within ±10% / ±20% |
| Coverage | share of sale prices inside the conformal interval |
| Relative width | mean $(\text{high}-\text{low})/\hat P$ |

## 7. Reproducibility and provenance

* **Determinism.** Every stochastic step draws from `numpy.random.Generator` instances
  seeded from `PipelineConfig.seed`: bootstrap, CV folds and calibration splits. Two runs
  with the same data and seed produce identical metrics, and a unit test enforces this.
* **Provenance.** Each run writes a `model_runs` row with the code version (image build
  arg), seed, full parameter set, sample size and all evaluation metrics. Every derived
  row (`market_trends`, `price_index`, `property_valuations`) references it. The API
  exposes it at `/api/v1/model-runs/latest`, and the dashboard shows it next to each
  valuation.
* **Immutable schema history.** Migrations are checksummed (see `db/README.md`).
* **Synthetic ground truth.** `synthetic.py` implements exactly the data-generating
  process of §3, with city-specific growth. The Monte Carlo study compares estimates
  against true parameters.

## 8. Limitations

* **Omitted variables.** The hedonic specification leaves out location within a city,
  condition and lot quality. On real data this adds omitted-variable bias to $\hat\beta$
  and widens intervals. Conformal coverage remains valid, but the intervals get wider.
* **Pooled time dummies.** They assume a common appreciation path across cities. When
  cities diverge, $\alpha_c$ absorbs the average level difference over the window (see
  results.md §2). A city × period interaction or per-city index fixes this, at a cost in
  variance.
* **Marginal coverage only.** Segments with unusual properties can be under-covered even
  when overall coverage is nominal. Mondrian (group-conditional) conformal prediction is
  the natural extension.
* **Composition adjustment.** Trends use price per square foot, a partial adjustment. A
  per-segment hedonic or repeat-sales index would be stronger.

## References

* Duan, N. (1983). Smearing estimate: a nonparametric retransformation method. *JASA* 78(383).
* de Haan, J. & Diewert, W. E. (eds.) (2013). *Handbook on Residential Property Price Indices*. Eurostat.
* Efron, B. & Tibshirani, R. (1993). *An Introduction to the Bootstrap*. Chapman & Hall.
* IAAO (2018). *Standard on Automated Valuation Models*.
* Kendall, M. G. (1975). *Rank Correlation Methods*. Griffin.
* Kennedy, P. (1981). Estimation with correctly interpreted dummy variables in semilogarithmic equations. *AER* 71(4).
* Lei, J., G'Sell, M., Rinaldo, A., Tibshirani, R. & Wasserman, L. (2018). Distribution-free predictive inference for regression. *JASA* 113(523).
* MacKinnon, J. & White, H. (1985). Some heteroskedasticity-consistent covariance matrix estimators. *J. Econometrics* 29(3).
* Mann, H. B. (1945). Nonparametric tests against trend. *Econometrica* 13(3).
* Rosen, S. (1974). Hedonic prices and implicit markets. *J. Political Economy* 82(1).
* Sen, P. K. (1968). Estimates of the regression coefficient based on Kendall's tau. *JASA* 63(324).
* Theil, H. (1950). A rank-invariant method of linear and polynomial regression analysis. *Indagationes Mathematicae* 12.
* Vovk, V., Gammerman, A. & Shafer, G. (2005). *Algorithmic Learning in a Random World*. Springer.
* White, H. (1980). A heteroskedasticity-consistent covariance matrix estimator. *Econometrica* 48(4).
