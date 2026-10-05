// KubeEstateHub dashboard. Plain ES2022, no build step.
// All API data is rendered with textContent / DOM APIs, never innerHTML (XSS-safe).
"use strict";

const API = "/api/v1";
const state = { page: 1, perPage: 24, filters: {}, charts: {} };
const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const num = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });
const $ = (sel) => document.querySelector(sel);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "dataset") Object.assign(node.dataset, v);
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

const fmtMoney = (v) => (v === null || v === undefined ? "–" : money.format(v));
const fmtNum = (v, suffix = "") => (v === null || v === undefined ? "–" : `${num.format(v)}${suffix}`);

async function api(path, options = {}) {
  const headers = { Accept: "application/json", ...(options.headers || {}) };
  const token = sessionStorage.getItem("apiToken");
  if (token && options.method && options.method !== "GET") headers.Authorization = `Bearer ${token}`;
  if (options.body) headers["Content-Type"] = "application/json";
  const resp = await fetch(`${path.startsWith("/") ? "" : API + "/"}${path}`, { ...options, headers });
  if (resp.status === 204) return null;
  const body = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const detail = body.errors?.map((e) => `${e.field}: ${e.message}`).join("; ") || body.detail || body.title;
    throw new Error(detail || `HTTP ${resp.status}`);
  }
  return body;
}

function toast(message, kind = "info") {
  const t = $("#toast");
  t.textContent = message;
  t.className = `toast show ${kind}`;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => t.classList.remove("show"), 5000);
}

function chart(id, config) {
  if (!window.Chart) return;
  state.charts[id]?.destroy();
  state.charts[id] = new window.Chart(document.getElementById(id), config);
}

// ---------------------------------------------------------------- dashboard
async function loadDashboard() {
  const [{ summary }, index] = await Promise.all([api("market/summary"), api("market/price-index")]);
  $("#stat-active").textContent = fmtNum(summary.active_listings);
  $("#stat-median-price").textContent = fmtMoney(summary.median_list_price);
  $("#stat-dom").textContent = fmtNum(summary.median_days_on_market, " d");
  $("#stat-mos").textContent = fmtNum(summary.months_of_supply);

  const types = Object.entries(summary.by_property_type || {});
  chart("property-type-chart", {
    type: "doughnut",
    data: { labels: types.map(([t]) => t.replace("_", " ")), datasets: [{ data: types.map(([, n]) => n) }] },
    options: { maintainAspectRatio: false, plugins: { legend: { position: "bottom" } } },
  });

  const series = index.series || [];
  $("#index-caption").textContent = series.length ? `base ${series[0].period.slice(0, 7)} = 100` : "no model run yet";
  const upper = series.map((p) => p.index_value + 1.96 * (p.std_error || 0));
  const lower = series.map((p) => p.index_value - 1.96 * (p.std_error || 0));
  chart("price-index-chart", {
    type: "line",
    data: {
      labels: series.map((p) => p.period.slice(0, 7)),
      datasets: [
        { label: "95% CI upper", data: upper, pointRadius: 0, borderWidth: 0, fill: "+1", backgroundColor: "rgba(59,130,246,0.15)" },
        { label: "95% CI lower", data: lower, pointRadius: 0, borderWidth: 0, fill: false },
        { label: "Index", data: series.map((p) => p.index_value), borderColor: "#3b82f6", tension: 0.2 },
      ],
    },
    options: { maintainAspectRatio: false, plugins: { legend: { display: false } } },
  });
}

// ----------------------------------------------------------------- listings
function listingCard(l) {
  const details = [
    l.bedrooms !== null && `${l.bedrooms} bd`,
    l.bathrooms !== null && `${l.bathrooms} ba`,
    l.square_feet && `${num.format(l.square_feet)} sqft`,
  ].filter(Boolean);
  return el(
    "article",
    { class: "listing-card", tabindex: "0", onclick: () => showListing(l.id), onkeydown: (e) => e.key === "Enter" && showListing(l.id) },
    el("div", { class: "listing-content" },
      el("div", { class: `listing-status ${l.status}` }, l.status),
      el("h3", { class: "listing-title" }, l.title),
      el("p", { class: "listing-address" }, `${l.address}, ${l.city}, ${l.state} ${l.zip_code}`),
      el("div", { class: "listing-details" }, details.map((d) => el("span", { class: "detail-item" }, d))),
      el("div", { class: "listing-price" }, fmtMoney(l.price)),
      el("div", { class: "listing-meta" },
        el("span", { class: "listing-type" }, l.property_type.replace("_", " ")),
        el("span", {}, l.price_per_sqft ? `${fmtMoney(l.price_per_sqft)}/sqft` : ""),
        el("span", {}, `Listed ${l.listing_date}`))));
}

async function loadListings() {
  const params = new URLSearchParams({ page: state.page, per_page: state.perPage, ...state.filters });
  const grid = $("#listings-grid");
  try {
    const data = await api(`listings?${params}`);
    grid.replaceChildren(...(data.listings.length ? data.listings.map(listingCard) : [el("p", { class: "no-results" }, "No listings match these filters.")]));
    renderPagination(data.pagination);
  } catch (err) {
    grid.replaceChildren(el("p", { class: "no-results" }, `Could not load listings: ${err.message}`));
  }
}

function renderPagination({ page, pages, total }) {
  const nav = $("#pagination");
  if (pages <= 1) return nav.replaceChildren();
  const go = (p) => () => { state.page = p; loadListings(); window.scrollTo({ top: 0, behavior: "smooth" }); };
  nav.replaceChildren(
    el("span", { class: "pagination-info" }, `Page ${page} of ${pages} · ${num.format(total)} listings`),
    el("div", { class: "pagination-buttons" },
      el("button", { class: "pagination-btn", disabled: page <= 1, onclick: go(page - 1) }, "Previous"),
      el("button", { class: "pagination-btn", disabled: page >= pages, onclick: go(page + 1) }, "Next")));
}

async function showListing(id) {
  const dialog = $("#listing-dialog");
  const body = $("#dialog-body");
  body.replaceChildren(el("p", {}, "Loading…"));
  dialog.showModal();
  try {
    const { listing: l } = await api(`listings/${id}`);
    $("#dialog-title").textContent = l.title;
    const v = l.valuation;
    body.replaceChildren(
      el("p", {}, `${l.address}, ${l.city}, ${l.state} ${l.zip_code} · MLS ${l.mls_number}`),
      el("div", { class: "metric-row" }, el("span", { class: "metric-label" }, "List price"), el("span", { class: "metric-value" }, fmtMoney(l.price))),
      v
        ? el("div", {},
            el("div", { class: "metric-row" }, el("span", { class: "metric-label" }, "Model estimate"), el("span", { class: "metric-value" }, fmtMoney(v.estimated_value))),
            el("div", { class: "metric-row" }, el("span", { class: "metric-label" }, `${Math.round(v.confidence_level * 100)}% prediction interval`),
              el("span", { class: "metric-value" }, `${fmtMoney(v.interval_low)} – ${fmtMoney(v.interval_high)}`)),
            el("p", { class: "muted" }, `${v.valuation_method.replace("_", " + ")} · model run ${String(v.valuation_model_run_id).slice(0, 8)}`))
        : el("p", { class: "muted" }, "No model valuation yet (runs nightly for open listings)."),
      l.description ? el("p", {}, l.description) : null);
  } catch (err) {
    body.replaceChildren(el("p", {}, err.message));
  }
}

async function createListing(form) {
  const data = Object.fromEntries([...new FormData(form)].filter(([, v]) => v !== ""));
  for (const k of ["price", "square_feet", "bedrooms", "year_built"]) if (k in data) data[k] = Number(data[k]);
  if ("bathrooms" in data) data.bathrooms = Number(data.bathrooms);
  data.state = data.state.toUpperCase();
  try {
    await api("listings", { method: "POST", body: JSON.stringify(data) });
    $("#add-dialog").close();
    form.reset();
    toast("Listing created", "success");
    loadListings();
  } catch (err) {
    $("#form-error").textContent = err.message;
  }
}

// ---------------------------------------------------------------- analytics
async function loadAnalytics() {
  const [{ trends }, { summary }] = await Promise.all([api("market/trends"), api("market/summary")]);
  const tbody = $("#trends-table tbody");
  const pct = (v) => (v === null || v === undefined ? "–" : `${v >= 0 ? "+" : ""}${num.format(v)}`);
  tbody.replaceChildren(
    ...trends.map((t) =>
      el("tr", {},
        el("td", {}, `${t.city}, ${t.state}`),
        el("td", {}, t.property_type ?? "all"),
        el("td", {}, fmtNum(t.n_sales)),
        el("td", {}, fmtMoney(t.median_sale_price)),
        el("td", {}, fmtNum(t.months_of_supply)),
        el("td", {}, t.trend_slope_pct_per_month === null ? "–" : `${pct(t.trend_slope_pct_per_month)} [${pct(t.trend_slope_ci_low)}, ${pct(t.trend_slope_ci_high)}]`),
        el("td", {}, t.mann_kendall_p === null ? "–" : t.mann_kendall_p.toFixed(3)),
        el("td", {}, el("span", { class: `trend trend-${t.trend_direction}` }, t.trend_direction.replace("_", " "))))));

  $("#city-list").replaceChildren(
    ...(summary.by_city || []).map((c) =>
      el("div", { class: "city-item" },
        el("div", { class: "city-info" }, el("span", { class: "city-name" }, `${c.city}, ${c.state}`), el("span", { class: "city-sales" }, `${c.sales_90d} sales (90d)`)),
        el("span", { class: "city-growth" }, `${c.active} active`))));

  try {
    const { model_run: run } = await api("model-runs/latest");
    const cv = run.metrics.cross_validation?.hedonic_conformal;
    const rows = [
      ["Finished", new Date(run.finished_at).toLocaleString()],
      ["Code version / seed", `${run.code_version} / ${run.random_seed}`],
      ["Sales used", fmtNum(run.n_observations)],
      ["Hedonic R²", fmtNum(run.metrics.hedonic?.r_squared)],
      ["CV median APE", cv ? `${num.format(cv.median_ape * 100)}%` : "–"],
      ["Within ±10% (PPE10)", cv ? `${num.format(cv.ppe10 * 100)}%` : "–"],
      ["90% interval coverage", cv ? `${num.format(cv.coverage * 100)}%` : "–"],
    ];
    $("#model-card").replaceChildren(...rows.map(([k, v]) => el("div", { class: "metric-row" }, el("span", { class: "metric-label" }, k), el("span", { class: "metric-value" }, v))));
  } catch {
    /* no model run yet: keep placeholder */
  }
}

// ---------------------------------------------------------------- shell
// A Map, not an object literal: section comes from location.hash, and object lookup would
// also resolve inherited properties such as "constructor".
const loaders = new Map([
  ["dashboard", loadDashboard],
  ["listings", loadListings],
  ["analytics", loadAnalytics],
  ["settings", checkApi],
]);

function show(section) {
  if (!loaders.has(section)) section = "dashboard";
  document.querySelectorAll(".section").forEach((s) => s.classList.toggle("active", s.id === section));
  document.querySelectorAll(".nav-link").forEach((a) => a.classList.toggle("active", a.dataset.section === section));
  loaders.get(section)().catch((err) => toast(err.message, "error"));
}

async function checkApi() {
  const status = $("#api-status");
  try {
    const r = await fetch("/readyz");
    status.textContent = r.ok ? "Connected" : "Degraded";
    status.className = `status-indicator ${r.ok ? "connected" : "disconnected"}`;
  } catch {
    status.textContent = "Disconnected";
    status.className = "status-indicator disconnected";
  }
}

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("theme", theme);
  $("#theme-toggle i").className = theme === "dark" ? "fas fa-sun" : "fas fa-moon";
}

document.addEventListener("DOMContentLoaded", () => {
  setTheme(localStorage.getItem("theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
  state.perPage = Number(localStorage.getItem("perPage")) || state.perPage;
  $("#items-per-page").value = String(state.perPage);
  $("#api-token").value = sessionStorage.getItem("apiToken") || "";

  $("#theme-toggle").addEventListener("click", () => setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"));
  $("#items-per-page").addEventListener("change", (e) => { state.perPage = Number(e.target.value); localStorage.setItem("perPage", e.target.value); });
  $("#api-token").addEventListener("change", (e) => sessionStorage.setItem("apiToken", e.target.value));
  $("#filters").addEventListener("submit", (e) => {
    e.preventDefault();
    state.filters = Object.fromEntries([...new FormData(e.target)].filter(([, v]) => v !== "" && !(v === "-listing_date")));
    state.page = 1;
    loadListings();
  });
  $("#filters").addEventListener("reset", () => { state.filters = {}; state.page = 1; setTimeout(loadListings); });
  $("#add-listing-btn").addEventListener("click", () => { $("#form-error").textContent = ""; $("#add-dialog").showModal(); });
  $("#add-listing-form").addEventListener("submit", (e) => { e.preventDefault(); createListing(e.target); });
  document.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", () => b.closest("dialog").close()));
  window.addEventListener("hashchange", () => show(location.hash.slice(1)));
  show(location.hash.slice(1) || "dashboard");
});
