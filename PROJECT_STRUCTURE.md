.
├── .dockerignore
├── .DS_Store
├── .github
│   └── workflows
│       ├── k8s-deploy.yaml
│       ├── manifest-validation.yaml
│       └── security-scan.yaml
├── .gitignore
├── .kubeignore
├── create_kube_estate_verse_structure.sh
├── docs
│   ├── architecture-diagram.svg
│   ├── architecture-overview.md
│   ├── debugging-guide.md
│   ├── faq.md
│   ├── gitops-with-argocd.md
│   ├── kubectl-cheatsheet.md
│   ├── monitoring-guide.md
│   ├── operators-guide.md
│   ├── scaling-guide.md
│   ├── security-best-practices.md
│   └── storage-deep-dive.md
├── helm-charts
│   ├── kubeestatehub
│   │   ├── Chart.yaml
│   │   ├── charts
│   │   │   └── .gitkeep
│   │   ├── templates
│   │   │   ├── _helpers.tpl
│   │   │   ├── configmaps.yaml
│   │   │   ├── deployments.yaml
│   │   │   ├── grafana.yaml
│   │   │   ├── hpa.yaml
│   │   │   ├── ingress.yaml
│   │   │   ├── NOTES.txt
│   │   │   ├── prometheus.yaml
│   │   │   ├── pvc.yaml
│   │   │   ├── rbac.yaml
│   │   │   ├── secrets.yaml
│   │   │   ├── serviceaccounts.yaml
│   │   │   ├── services.yaml
│   │   │   └── tests
│   │   │       └── tests.yaml
│   │   └── values.yaml
│   └── README.md
├── kustomize
│   ├── base
│   │   └── kustomization.yaml
│   ├── overlays
│   │   ├── development
│   │   │   └── kustomization.yaml
│   │   ├── production
│   │   │   └── kustomization.yaml
│   │   └── staging
│   │       └── kustomization.yaml
│   └── README.md
├── LICENSE
├── manifests
│   ├── autoscaling
│   │   ├── cluster-autoscaler.yaml
│   │   ├── hpa-frontend-dashboard.yaml
│   │   ├── hpa-listings-api.yaml
│   │   ├── resource-quotas.yaml
│   │   └── vpa-listings-api.yaml
│   ├── base
│   │   ├── analytics-worker-cronjob.yaml
│   │   ├── analytics-worker-deployment.yaml
│   │   ├── db-service.yaml
│   │   ├── db-statefulset.yaml
│   │   ├── frontend-dashboard-deployment.yaml
│   │   ├── frontend-dashboard-service.yaml
│   │   ├── image-store-deployment.yaml
│   │   ├── image-store-service.yaml
│   │   ├── ingress.yaml
│   │   ├── listings-api-deployment.yaml
│   │   ├── listings-api-service.yaml
│   │   └── namespace.yaml
│   ├── configs
│   │   ├── analytics-configmap.yaml
│   │   ├── db-configmap.yaml
│   │   ├── db-secret.yaml
│   │   ├── frontend-configmap.yaml
│   │   ├── global-env-secret.yaml
│   │   ├── listings-configmap.yaml
│   │   ├── rbac-admin.yaml
│   │   ├── rbac-readonly.yaml
│   │   └── service-accounts.yaml
│   ├── daemonsets
│   │   ├── log-collector-daemonset.yaml
│   │   ├── node-exporter-daemonset.yaml
│   │   └── security-scanner-daemonset.yaml
│   ├── jobs
│   │   ├── db-backup-cronjob.yaml
│   │   ├── db-migration-job.yaml
│   │   └── image-cleanup-job.yaml
│   ├── monitoring
│   │   ├── alertmanager-config.yaml
│   │   ├── grafana-dashboard-configmap.yaml
│   │   ├── grafana-deployment.yaml
│   │   ├── grafana-service.yaml
│   │   ├── prometheus-deployment.yaml
│   │   ├── prometheus-service.yaml
│   │   └── service-monitor-listings.yaml
│   ├── network
│   │   ├── dns-configmap.yaml
│   │   ├── ingress-controller.yaml
│   │   ├── network-policy-db.yaml
│   │   └── network-policy-frontend.yaml
│   ├── operators
│   │   ├── operator-rbac.yaml
│   │   ├── realestate-sync-cr.yaml
│   │   ├── realestate-sync-crd.yaml
│   │   └── realestate-sync-operator-deployment.yaml
│   ├── security
│   │   ├── admission-controllers.yaml
│   │   ├── pod-security-policy.yaml
│   │   ├── pod-security-standards.yaml
│   │   └── security-contexts.yaml
│   └── storage
│       ├── db-persistent-volume-claim.yaml
│       ├── db-persistent-volume.yaml
│       ├── image-store-pv.yaml
│       ├── image-store-pvc.yaml
│       └── storage-class.yaml
├── PROJECT_STRUCTURE.md
├── README.md
├── scripts
│   ├── backup-db.sh
│   ├── cluster-setup.sh
│   ├── deploy-all.sh
│   ├── grafana-dashboard-import.sh
│   ├── kubectl-aliases.sh
│   ├── port-forwarding.sh
│   └── teardown-all.sh
├── src
│   ├── analytics-worker
│   │   ├── Dockerfile
│   │   ├── README.md
│   │   ├── requirements.txt
│   │   └── worker.py
│   ├── frontend-dashboard
│   │   ├── app.js
│   │   ├── Dockerfile
│   │   ├── index.html
│   │   ├── README.md
│   │   └── styles.css
│   ├── listings-api
│   │   ├── app.py
│   │   ├── Dockerfile
│   │   ├── k8s_health.py
│   │   ├── README.md
│   │   └── requirements.txt
│   └── metrics-service
│       ├── Dockerfile
│       ├── metrics_exporter.py
│       ├── README.md
│       └── requirements.txt
└── tests
    ├── integration-tests
    │   ├── db-connection-test.py
    │   ├── ingress-routing-test.py
    │   └── listings-api-test.py
    ├── k8s-lint-tests
    │   ├── conftest
    │   │   ├── deployment.rego
    │   │   └── security.rego
    │   ├── kube-score.yaml
    │   └── kubeval.yaml
    └── README.md

36 directories, 134 files
