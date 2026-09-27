#!/usr/bin/env bash
# Install pinned Kubernetes validation tooling into ./bin so that local runs and CI
# use identical versions. Usage: hack/install-tools.sh [bin-dir]
set -euo pipefail

BIN_DIR="${1:-$(cd "$(dirname "$0")/.." && pwd)/bin}"
mkdir -p "$BIN_DIR"

HELM_VERSION="${HELM_VERSION:-v3.16.4}"
KUBECONFORM_VERSION="${KUBECONFORM_VERSION:-v0.6.7}"
CONFTEST_VERSION="${CONFTEST_VERSION:-0.56.0}"
KUBE_LINTER_VERSION="${KUBE_LINTER_VERSION:-v0.7.1}"
KIND_VERSION="${KIND_VERSION:-v0.24.0}"

os="$(uname -s | tr '[:upper:]' '[:lower:]')"
arch="$(uname -m)"
case "$arch" in
  x86_64 | amd64) goarch=amd64; ctarch=x86_64 ;;
  arm64 | aarch64) goarch=arm64; ctarch=arm64 ;;
  *) echo "unsupported architecture: $arch" >&2; exit 1 ;;
esac
ctos="$(uname -s)"

fetch() { curl -fsSL --retry 3 "$@"; }

if [[ ! -x "$BIN_DIR/helm" ]]; then
  fetch "https://get.helm.sh/helm-${HELM_VERSION}-${os}-${goarch}.tar.gz" |
    tar xz -C "$BIN_DIR" --strip-components=1 "${os}-${goarch}/helm"
fi
if [[ ! -x "$BIN_DIR/kubeconform" ]]; then
  fetch "https://github.com/yannh/kubeconform/releases/download/${KUBECONFORM_VERSION}/kubeconform-${os}-${goarch}.tar.gz" |
    tar xz -C "$BIN_DIR" kubeconform
fi
if [[ ! -x "$BIN_DIR/conftest" ]]; then
  fetch "https://github.com/open-policy-agent/conftest/releases/download/v${CONFTEST_VERSION}/conftest_${CONFTEST_VERSION}_${ctos}_${ctarch}.tar.gz" |
    tar xz -C "$BIN_DIR" conftest
fi
if [[ ! -x "$BIN_DIR/kube-linter" ]]; then
  suffix=""
  [[ "$os" == "linux" ]] && suffix="-linux"
  [[ "$os" == "darwin" ]] && suffix="-darwin"
  [[ "$os" == "linux" && "$goarch" == "arm64" ]] && suffix="-linux_arm64"
  fetch "https://github.com/stackrox/kube-linter/releases/download/${KUBE_LINTER_VERSION}/kube-linter${suffix}.tar.gz" |
    tar xz -C "$BIN_DIR" kube-linter
fi
if [[ ! -x "$BIN_DIR/kind" ]]; then
  fetch -o "$BIN_DIR/kind" "https://kind.sigs.k8s.io/dl/${KIND_VERSION}/kind-${os}-${goarch}"
  chmod +x "$BIN_DIR/kind"
fi

if ! command -v kubectl >/dev/null 2>&1 && [[ ! -x "$BIN_DIR/kubectl" ]]; then
  fetch -o "$BIN_DIR/kubectl" "https://dl.k8s.io/release/${KUBECTL_VERSION:-v1.31.2}/bin/${os}/${goarch}/kubectl"
  chmod +x "$BIN_DIR/kubectl"
fi

echo "tools installed in $BIN_DIR:"
"$BIN_DIR/helm" version --short
"$BIN_DIR/kubeconform" -v
"$BIN_DIR/conftest" --version | head -1
"$BIN_DIR/kube-linter" version
"$BIN_DIR/kind" version
