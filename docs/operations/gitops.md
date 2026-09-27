# GitOps with Argo CD

Each overlay is a plain kustomize directory, so Argo CD can deploy it directly:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: kubeestatehub-staging
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/SatvikPraveen/KubeEstateHub
    targetRevision: main
    path: kustomize/overlays/staging
  destination:
    server: https://kubernetes.default.svc
    namespace: kubeestatehub
  syncPolicy:
    automated: {prune: true, selfHeal: true}
    syncOptions:
      - ServerSideApply=true
      - RespectIgnoreDifferences=true
  ignoreDifferences:
    - group: apps
      kind: Deployment
      jsonPointers: [/spec/replicas]   # owned by the HPA
```

**Promotion.** Bump image tags in `kustomize/overlays/<env>/kustomization.yaml`
(`images:`), preferably by digest, through a pull request. The `db-migrate` Job has
`ttlSecondsAfterFinished`, so Argo CD recreates it on the next sync after it has been
cleaned up. To run it on every sync, annotate it with
`argocd.argoproj.io/hook: Sync` and `argocd.argoproj.io/hook-delete-policy: BeforeHookCreation`.
