"""KubeEstateHub analytics: reproducible real-estate market statistics and valuation models.

Modules
-------
stats        robust statistics: bootstrap CIs, Theil-Sen slope, Mann-Kendall trend test
market       market indicators (months of supply, absorption, days on market, trend)
hedonic      log-linear hedonic pricing model with HC1 errors and a time-dummy price index
conformal    split-conformal prediction intervals with finite-sample coverage guarantees
comparables  k-nearest-neighbour comparable-sales valuation
evaluation   k-fold cross-validation with AVM accuracy metrics
synthetic    synthetic market generator with known ground truth (for validation)
pipeline     end-to-end batch job that writes results with provenance
"""

__version__ = "2.0.0"
