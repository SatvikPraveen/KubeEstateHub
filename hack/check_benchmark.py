#!/usr/bin/env python3
"""Fail if a benchmark run shows biased estimators or miscalibrated intervals.

Usage: check_benchmark.py benchmark.json
"""

import json
import math
import sys

with open(sys.argv[1]) as fh:
    result = json.load(fh)

reps = result["config"]["replications"]
problems = []
for name, metrics in result["cross_validation"].items():
    coverage = metrics["coverage"]["mean"]
    nominal = 1 - result["config"]["alpha"]
    if abs(coverage - nominal) > 0.03:
        problems.append(f"{name}: coverage {coverage:.3f} vs nominal {nominal:.2f}")
for feature, stats in result["parameter_recovery"].items():
    # |mean error| should be within ~3 standard errors of zero: SE(mean) ~ RMSE / sqrt(reps)
    limit = 3 * stats["rmse"] / math.sqrt(reps) + 1e-6
    if abs(stats["bias"]) > limit:
        problems.append(f"{feature}: bias {stats['bias']:+.5f} exceeds {limit:.5f}")

if problems:
    sys.exit("estimator checks failed:\n  " + "\n  ".join(problems))
print(f"estimator checks passed ({reps} replications)")
