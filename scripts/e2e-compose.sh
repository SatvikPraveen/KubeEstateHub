#!/usr/bin/env bash
# End-to-end smoke test of the docker compose stack.
# Brings the stack up from scratch, waits for the analytics pipeline, then asserts on
# real HTTP responses from the dashboard proxy, the API and the metrics exporter.
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE=(docker compose -p kubeestatehub-e2e)
# non-default host ports so the test can run next to a developer's own stack
export POSTGRES_PORT=${POSTGRES_PORT:-55433} API_PORT=${API_PORT:-18080}
export METRICS_PORT=${METRICS_PORT:-19100} FRONTEND_PORT=${FRONTEND_PORT:-13000}
BASE="http://127.0.0.1:${FRONTEND_PORT}"
TOKEN=${API_WRITE_TOKEN:-local-dev-token}
export API_WRITE_TOKEN=$TOKEN

cleanup() { [[ "${KEEP:-0}" == 1 ]] || "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true; }
trap cleanup EXIT

fail() { echo "FAIL: $*" >&2; "${COMPOSE[@]}" logs --tail=50 >&2 || true; exit 1; }
check() { local desc=$1; shift; if "$@"; then echo "ok   $desc"; else fail "$desc"; fi; }
json() { python3 -c "import json,sys; d=json.load(sys.stdin); print(eval(sys.argv[1], {}, {'d': d}))" "$1"; }

"${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
"${COMPOSE[@]}" up -d --build --wait postgres redis listings-api metrics-service frontend
"${COMPOSE[@]}" up --exit-code-from pipeline seed pipeline >/dev/null 2>&1 || fail "seed/pipeline failed"

check "dashboard served"            test "$(curl -fsS -o /dev/null -w '%{http_code}' "$BASE/")" = 200
check "CSP header present"          bash -c "curl -fsSI '$BASE/' | grep -qi content-security-policy"
check "readiness through proxy"     test "$(curl -fsS "$BASE/readyz" | json 'd["status"]')" = ready

total=$(curl -fsS "$BASE/api/v1/listings?status=active&per_page=1" | json 'd["pagination"]["total"]')
check "active listings seeded ($total)" test "$total" -gt 100

summary=$(curl -fsS "$BASE/api/v1/market/summary")
check "months of supply computed"  test "$(echo "$summary" | json 'd["summary"]["months_of_supply"] is not None')" = True

run=$(curl -fsS "$BASE/api/v1/model-runs/latest")
coverage=$(echo "$run" | json 'd["model_run"]["metrics"]["cross_validation"]["hedonic_conformal"]["coverage"]')
check "conformal coverage near 90% ($coverage)" python3 -c "import sys; sys.exit(0 if 0.85 <= $coverage <= 0.95 else 1)"

index_len=$(curl -fsS "$BASE/api/v1/market/price-index" | json 'len(d["series"])')
check "price index published ($index_len periods)" test "$index_len" -gt 6

id=$(curl -fsS "$BASE/api/v1/listings?per_page=1" | json 'd["listings"][0]["id"]')
check "listing has a valuation interval" test "$(curl -fsS "$BASE/api/v1/listings/$id" | json 'd["listing"]["valuation"]["interval_low"] > 0')" = True

payload='{"mls_number":"E2E-1","title":"E2E home","property_type":"residential","price":350000,"address":"1 Test","city":"Austin","state":"TX","zip_code":"78701"}'
check "writes require token" test "$(curl -s -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' -d "$payload" "$BASE/api/v1/listings")" = 401
check "authorised create" test "$(curl -s -o /dev/null -w '%{http_code}' -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "$payload" "$BASE/api/v1/listings")" = 201
check "duplicate is 409" test "$(curl -s -o /dev/null -w '%{http_code}' -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "$payload" "$BASE/api/v1/listings")" = 409

check "business metrics exported" bash -c "curl -fsS http://127.0.0.1:${METRICS_PORT}/metrics | grep -q '^kubeestatehub_avm_coverage'"
check "api RED metrics exported"  bash -c "curl -fsS http://127.0.0.1:${API_PORT}/metrics | grep -q 'http_request_duration_seconds_bucket'"
echo "e2e: all checks passed"
