# 0007. Probe semantics and schema-version gating

* Status: accepted (2026-09)

## Context
v1's liveness probe queried the database. During a database outage, kubelet would
restart every API pod repeatedly, which turns a dependency failure into a crash loop and
slows recovery. Ordering between migrations and rollouts was also undefined.

## Decision
* `/livez` checks only that the process can serve.
* `/readyz` checks the database **and** that `schema_migrations` contains
  `REQUIRED_SCHEMA_VERSION`, the newest migration this build needs. A unit test enforces
  that the constant matches the newest migration file.

## Consequences
* A database outage removes pods from load balancing without restarting them.
* The migrate Job can run concurrently with a rollout. New pods receive traffic only
  after migration, and old pods keep serving because migrations are backward compatible
  by policy.
