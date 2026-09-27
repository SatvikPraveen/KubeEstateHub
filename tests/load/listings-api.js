// k6 load test for the read path. Thresholds encode the SLOs (docs/research/slo.md),
// so a run fails exactly when the service would burn error budget.
//   docker run --rm -i -e BASE_URL=http://host:3000 -v $PWD/tests/load:/s grafana/k6 run /s/listings-api.js
import http from "k6/http";
import { check } from "k6";
import { Trend } from "k6/metrics";

const BASE = __ENV.BASE_URL || "http://127.0.0.1:3000";
const RATE = Number(__ENV.RATE || 200);           // target requests per second
const DURATION = __ENV.DURATION || "2m";
const cities = ["Austin", "Dallas", "Houston", "San Antonio", "Tampa"];
const sorts = ["-listing_date", "price", "-price"];
const listLatency = new Trend("latency_list", true);
const detailLatency = new Trend("latency_detail", true);

export const options = {
  discardResponseBodies: false,
  scenarios: {
    steady: {
      executor: "ramping-arrival-rate",   // open model: arrivals do not wait for responses
      startRate: 10,
      timeUnit: "1s",
      preAllocatedVUs: 50,
      maxVUs: 400,
      stages: [
        { target: RATE, duration: "30s" },
        { target: RATE, duration: DURATION },
        { target: 0, duration: "10s" },
      ],
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.005"],                       // availability SLO 99.5%
    "http_req_duration{expected_response:true}": ["p(99)<500"], // latency SLO
    checks: ["rate>0.995"],
  },
  summaryTrendStats: ["avg", "med", "p(90)", "p(95)", "p(99)", "max"],
};

let knownIds = [];

export function setup() {
  const res = http.get(`${BASE}/api/v1/listings?per_page=100`);
  return { ids: res.json("listings").map((l) => l.id) };
}

export default function (data) {
  knownIds = data.ids;
  const r = Math.random();
  if (r < 0.6) {
    const city = cities[Math.floor(Math.random() * cities.length)];
    const page = 1 + Math.floor(Math.random() * 5);
    const sort = sorts[Math.floor(Math.random() * sorts.length)];
    const res = http.get(`${BASE}/api/v1/listings?city=${encodeURIComponent(city)}&page=${page}&sort=${sort}`,
      { tags: { endpoint: "list" } });
    listLatency.add(res.timings.duration);
    check(res, { "list 200": (x) => x.status === 200 });
  } else if (r < 0.85) {
    const id = knownIds[Math.floor(Math.random() * knownIds.length)];
    const res = http.get(`${BASE}/api/v1/listings/${id}`, { tags: { endpoint: "detail" } });
    detailLatency.add(res.timings.duration);
    check(res, { "detail 200": (x) => x.status === 200 });
  } else if (r < 0.95) {
    const res = http.get(`${BASE}/api/v1/market/summary`, { tags: { endpoint: "summary" } });
    check(res, { "summary 200": (x) => x.status === 200 });
  } else {
    const res = http.get(`${BASE}/api/v1/market/trends`, { tags: { endpoint: "trends" } });
    check(res, { "trends 200": (x) => x.status === 200 });
  }
}
