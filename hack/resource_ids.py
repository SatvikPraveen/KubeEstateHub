#!/usr/bin/env python3
"""Print sorted Kind/name identifiers of a multi-document manifest (used for parity checks)."""

import sys

import yaml

with open(sys.argv[1]) as fh:
    docs = [d for d in yaml.safe_load_all(fh) if d]
if not docs:
    sys.exit(f"no resources in {sys.argv[1]}")
print("\n".join(sorted(f"{d['kind']}/{d['metadata']['name']}" for d in docs)))
