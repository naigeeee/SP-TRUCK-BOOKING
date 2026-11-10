# If you add a frontend later

Only when the user asks. Then: `cicd/Dockerfile.frontend` serving the built site on **port
80**; call the backend same-origin via relative `/api` paths; **never hardcode an API URL
and never set `VITE_API_URL`**. Public build-time values go in a committed
`frontend/.env.production` (already un-ignored in `.gitignore`).

**Base image for the frontend's final stage: `FROM nginx:stable-alpine`, then
`RUN apk upgrade --no-cache` directly under it.** Never a pinned minor like
`nginx:1.27-alpine` — pinned tags stop being rebuilt and collect OS security flaws that
have published fixes, and those BLOCK promotion to production. Only the final stage is
scanned; the `node:22-bookworm-slim` build stage needs no upgrade line.

**Never proxy `/api` from the frontend's nginx config.** `/api` is routed by the ingress and
never reaches nginx. Adding a compose-style `proxy_pass http://backend:8000` is fatal on the
platform: nginx resolves upstream hostnames at startup, `backend` doesn't exist in the app's
namespace, and nginx refuses to start — the frontend crash-loops with `host not found in
upstream "backend"` and the deploy fails. The deploy rejects this at VALIDATING when it
detects a dot-less hostname in the nginx config. Keep the scaffold's `cicd/nginx.conf`
proxy-free; for local docker-compose use `npm run dev` (Vite proxies `/api`) or a separate
compose-only nginx config that the Dockerfile never copies.
