# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [2.0.0] - 2026-09-27

A ground-up rework. Version 1.0.0 described itself as production-ready, but it could not
be deployed:

* No kustomize overlay built.
* The Helm chart failed lint and depended on unvendored subcharts.
* The API crashed at import (Flask-Limiter signature).
* The frontend image could not build.
* The schema job was invalid YAML and invalid SQL.
* The manifests used removed or invented APIs.
* The CI workflows skipped their checks.

### Added
* Analytics methods:
  * a hedonic price model with HC1 errors, Duan smearing and a Kennedy-corrected
    time-dummy price index
  * Theil–Sen and Mann–Kendall trend classification
  * split-conformal valuation intervals and a comparable-sales AVM
  * k-fold AVM evaluation with IAAO metrics
* A synthetic market generator with ground truth, a Monte Carlo validation study
  (`python -m analytics_worker benchmark`), trend size and power studies and
  `docs/research/`.
* Provenance: the `model_runs` table referenced by every derived row, and the
  `/api/v1/model-runs/latest` endpoint.
* The RealEstateSync operator (kopf): CronJob reconciliation, status subresource, drift
  repair and garbage collection.
* Versioned, checksummed SQL migrations with a POSIX runner, and readiness gated on the
  schema version.
* Listings API v2:
  * pydantic contracts that also generate the OpenAPI 3.1 spec
  * RFC 9457 errors, PATCH and soft DELETE
  * bearer-token writes and a separate write rate limit
  * market summary, trends and price index endpoints
  * generation-based cache invalidation and multiprocess Prometheus metrics
* A scrape-time metrics exporter with model-quality gauges (conformal coverage, median
  APE, pipeline freshness).
* SLOs (99.5% availability, 99% ≤ 500 ms), multi-window burn-rate alerts, model-quality
  alerts, promtool tests, a Grafana dashboard as code and runbooks.
* A Kubernetes base with PSA `restricted` and default-deny NetworkPolicies, plus these
  components: monitoring, operator, admission policy (CEL) and backup. Overlays for
  development, staging, production (External Secrets, TLS) and e2e.
* A self-contained Helm chart with a values schema, migration hook, `helm test` and CI
  parity with kustomize.
* Validation tooling: kubeconform, kube-linter and conftest (Rego v1, with unit tests and
  cross-resource invariants).
* Testing: a docker compose stack with an end-to-end test, a kind end-to-end test, a k6
  SLO load test and Chaos Mesh experiments.
* CI/CD:
  * gating lint and typing, unit tests on 3.12 and 3.13, PostgreSQL integration and an
    estimator benchmark
  * multi-arch images with Trivy gate, SBOM, SLSA provenance and cosign signatures
  * CodeQL, gitleaks, Trivy IaC scanning, dependency review and an OCI chart
    release
* ADRs, a threat model, `CITATION.cff` and `SECURITY.md`.

### Changed
* Analytics runs as a batch CronJob instead of an idle Celery worker.
* The frontend is served by nginx-unprivileged and shows only live data. It renders
  without innerHTML, so it is XSS-safe, and uses CSP and SRI.
* The liveness probe no longer depends on the database.
* The minimum Kubernetes version is now 1.30 and the minimum Python version 3.12.

### Removed
* Hand-maintained copies of platform software: the ingress controller, Prometheus,
  Grafana, Alertmanager, cluster-autoscaler, Falco and fluent-bit. Use the pinned
  upstream charts in `platform/` instead.
* PodSecurityPolicies, fake admission webhooks, AWS-only PersistentVolumes and deployment
  scripts that referenced non-existent files.

### Security
* Removed plaintext `apiKey` and `connectionString` fields from the CRD. No credentials
  are committed.
* Two demo defaults found in the 1.0.0 history are listed in `.gitleaksignore`. Rotate
  anything that ever reused them.

## [1.0.0] - 2025-11-26

### Added

#### Core Features
- ✅ Complete microservices architecture with Kubernetes orchestration
- ✅ Real estate property listing management system
- ✅ Analytics worker for market trend analysis
- ✅ Metrics export and monitoring infrastructure
- ✅ Frontend dashboard with real-time visualizations

#### Kubernetes Support
- ✅ Multi-environment deployment configurations (development, staging, production)
- ✅ Helm charts with environment-specific values files
- ✅ Kustomize overlays for configuration management
- ✅ Direct Kubernetes manifest deployments
- ✅ Automated database initialization job
- ✅ Health checks and probes (liveness, readiness, startup)
- ✅ Pod security policies and network policies
- ✅ Resource quotas and limits

#### Database
- ✅ PostgreSQL database with schema initialization
- ✅ Complete database schema with extensions (uuid-ossp, pg_trgm, btree_gist)
- ✅ Materialized views for analytics
- ✅ Automatic timestamp triggers
- ✅ Comprehensive indexes for performance
- ✅ Sample data for testing

#### API
- ✅ RESTful API for listing management
- ✅ CORS support for frontend integration
- ✅ Rate limiting (1000 per hour)
- ✅ Prometheus metrics export
- ✅ Request/response logging
- ✅ Error handling and validation

#### Observability
- ✅ Prometheus metrics collection
- ✅ Grafana dashboard configuration
- ✅ Service health endpoints
- ✅ Pod metrics collection
- ✅ Application performance monitoring

#### Deployment
- ✅ Automated deployment script (deploy-all.sh)
- ✅ Docker containerization for all services
- ✅ Image build automation
- ✅ Multi-phase deployment with dependency management
- ✅ Port forwarding utilities

#### Documentation
- ✅ Architecture overview
- ✅ Quick start guide
- ✅ Troubleshooting guide
- ✅ Security best practices
- ✅ Scaling guide
- ✅ Monitoring guide
- ✅ Advanced features guide
- ✅ FAQ with common solutions

### Fixed

#### Critical Issues
- ✅ Fixed database connection string handling and defaults
- ✅ Fixed Redis connection retry logic
- ✅ Fixed missing database schema initialization
- ✅ Fixed API endpoint consistency (listings vs properties)
- ✅ Fixed Kubernetes service naming and discovery
- ✅ Fixed storage class compatibility (fast-ssd → standard)
- ✅ Fixed relative paths in deployment scripts
- ✅ Fixed missing Python dependencies (requests module)

#### Manifest Issues
- ✅ Created missing secret files (db-secret.yaml, global-env-secret.yaml)
- ✅ Fixed database StatefulSet configuration
- ✅ Added headless service for StatefulSet
- ✅ Fixed ingress configuration
- ✅ Fixed resource requests and limits

#### Configuration Issues
- ✅ Created environment-specific Helm values files
  - values-development.yaml
  - values-staging.yaml
  - values-production.yaml
- ✅ Fixed database credentials and environment variables
- ✅ Fixed external service endpoints
- ✅ Fixed Redis service URLs

#### Frontend Issues
- ✅ Fixed API endpoint references
- ✅ Fixed CORS handling
- ✅ Updated API paths to match backend

#### Deployment Script Issues
- ✅ Fixed relative path handling in build_images()
- ✅ Fixed deploy_with_manifests() to use absolute paths
- ✅ Fixed deploy_with_kustomize() path resolution
- ✅ Fixed deploy_with_helm() path resolution
- ✅ Fixed service port forwarding with proper namespace handling

### Security Enhancements
- ✅ Pod security context with non-root users
- ✅ Read-only root filesystems where applicable
- ✅ Capability dropping (CAP_ALL dropped)
- ✅ Network policies for traffic segmentation
- ✅ RBAC configurations with service accounts
- ✅ Secret management with proper defaults
- ✅ Container image security best practices

### Performance Improvements
- ✅ Connection pooling configurations
- ✅ Caching strategy with Redis
- ✅ Query optimization with indexes
- ✅ Materialized views for analytics
- ✅ Rate limiting to prevent abuse
- ✅ Horizontal pod autoscaling configuration

### Infrastructure
- ✅ Database initialization job for automatic schema setup
- ✅ Postgres exporter for metrics collection
- ✅ Multi-replica deployments for HA
- ✅ Pod anti-affinity for distribution
- ✅ PersistentVolume and PersistentVolumeClaim templates
- ✅ EmptyDir volumes for temporary storage

### Documentation
- ✅ Complete issues and fixes documentation
- ✅ Quick start guide for new users
- ✅ Advanced features guide for scaling
- ✅ CHANGELOG for version tracking

## Known Limitations

- Images not yet pushed to GitHub Container Registry (build locally first)
- SSL certificates need to be configured manually for ingress
- S3 backup integration needs AWS credentials
- ML models for property valuation not included (template provided)

## Roadmap for Future Versions

### v1.1.0
- [ ] GitHub Actions CI/CD pipeline
- [ ] Automated image builds and pushes
- [ ] Integration tests in CI/CD
- [ ] Helm chart dependencies (PostgreSQL, Redis)

### v1.2.0
- [ ] Service mesh integration (Istio)
- [ ] Distributed tracing (Jaeger)
- [ ] GraphQL API layer
- [ ] WebSocket support for real-time updates

### v1.3.0
- [ ] ML-based property valuation models
- [ ] Advanced analytics with Pandas/Numpy
- [ ] Blue-green deployment automation
- [ ] Cost optimization recommendations

### v2.0.0
- [ ] Multi-cluster deployment support
- [ ] Federation and cross-cluster failover
- [ ] Complete disaster recovery automation
- [ ] Enterprise features and SLA monitoring

## Contributing

Contributions are welcome! Please follow the guidelines:

1. Create a feature branch from `develop`
2. Make atomic, well-documented commits
3. Add/update tests as needed
4. Update documentation
5. Submit a pull request with detailed description

## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Support

For issues, questions, or suggestions:

1. Check the FAQ (removed in 2.0.0)
2. Review the Debugging Guide (removed in 2.0.0)
3. Open a GitHub issue with detailed information
4. Provide relevant logs and configuration details

## Acknowledgments

- Kubernetes best practices from the official documentation
- Real estate industry standards and patterns
- Open source community for inspiration and tools
