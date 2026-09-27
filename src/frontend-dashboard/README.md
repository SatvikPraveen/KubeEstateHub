# Frontend dashboard

A static, dependency-free (no build step) dashboard served by `nginx-unprivileged` on
port 8080 as UID 101.

* **Data:** the dashboard reads the market summary, the hedonic price index with its
  95% confidence band, statistical segment trends and model-run provenance from the
  listings API. Nothing on screen is hard-coded.
* **Security:**
  * API data is rendered only through `textContent` and DOM APIs.
  * A strict Content-Security-Policy is set, and CDN assets are pinned with Subresource
    Integrity hashes.
  * The write token is kept in `sessionStorage` for the current tab only.
* **Routing:** the browser always calls same-origin `/api/v1`. In Kubernetes the Ingress
  routes `/api` to the listings API. Under docker compose, nginx proxies it to
  `listings-api:8080`.
