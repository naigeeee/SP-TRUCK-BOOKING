# Deploying — commit, push, THEN deploy

**If the deploy reports this folder isn't linked to an app**, fix it yourself before
asking anything: run `bash substrait.sh link status`, then `bash substrait.sh link apps`.
If exactly one listed app matches this project's repo, bind it
(`bash substrait.sh link use --app <slug>`) and continue the deploy. If none or several
match, show the user the list and ask which one — never guess between two apps.

Substrait builds the **pushed** branch, but it does not notice the push by itself. Three
steps, every time, in this order:

```bash
git add -A && git commit -m "describe the change" && git push
bash substrait.sh deploy
```

**Never stop after the push.** The portal's "auto-redeploys on push" label is misleading —
the deploy command is what triggers the build. Reporting "deployed" after only pushing is
the single worst mistake you can make here, because the user reloads their app, sees no
change, and has no idea why.

**Expect the deploy to refuse the first time with "uncommitted changes … scaffold_version".**
The deploy stamps `substrait.yaml` itself *before* it checks the tree was clean, so its own
edit dirties it. This is normal. Recover without asking:

```bash
git add substrait.yaml && git commit -m "stamp scaffold version" && git push
bash substrait.sh deploy
```

**Keep `openapi.json` current.** The deploy warns when it is older than your latest
`backend/` change. It is only a warning, but the file ships as the app's published API
description — so when you add, remove or rename a route, update `openapi.json` in the same
edit.

**Fallback with no terminal:** the user can open the app in the portal and click
**Redeploy** in the header.

## Checking it worked

The user can see build state in the portal under the app's **Overview → Recent
deployments**. You can confirm the push landed with:

```bash
git ls-remote origin main
git rev-parse HEAD
```

If those two SHAs match, Substrait has what it needs.

## Optional: watching the build from here

Only if the user wants live build logs in this conversation. It requires the one-time
machine link described in `docs/linking.md`, which is genuinely optional:

```bash
bash substrait.sh deploy
```

Don't set this up unless asked — pushing is enough.

## How it refuses, and what to do

| Message | Cause | Fix |
|---|---|---|
| "uncommitted changes ... scaffold_version stamp" | The deploy stamped `substrait.yaml` itself, before checking the tree was clean | Commit and push it, deploy again. Expected once after any tooling update. |
| "uncommitted changes" after linking | `SUBSTRAIT-CONTRACT.md` / `.gitignore` were just written | Commit and push, deploy again |
| "deploys from branch 'X' but you're on 'Y'" | Branch name must match exactly | `git branch -M X` or `git checkout X` |
| "local HEAD doesn't match the pushed tip" | Unpushed commits | `git push`, deploy again |
| "isn't a git checkout" | Wrong folder | Run from the repo root |
| "chose GitHub deploys but the app isn't connected" | Recorded mode vs server disagree | `bash substrait.sh link set-mode --mode connect --repo OWNER/REPO` (needs the account link) |
| HTTP 409 "deploy refused" naming production | Deploying straight to production on an app that has `dev` | Deploy to `dev` (drop `--env production`); production changes only by promotion — and only if the user asks |
| HTTP 409 (other) | Server-side SHA mismatch | Push, then deploy again |

A sign-in window during **deploy** (not push) is the `git fetch` the freshness check runs.

## After changing any API route

Update `openapi.json` in the same edit, to match what `backend/main.py` now serves. The
deploy warns when it's older than your latest `backend/` change, and warns if it's missing —
currently advisory, but slated to become a hard requirement.

### OpenAPI as the published API description

`openapi.json` at the repo root is the app's **published** API description — shown on the
portal's API tab and in the API Library. It takes precedence over the runtime harvest of the
app's own `/openapi.json`. Author it from the code; never list endpoints or fields the code
doesn't serve. Must be valid JSON with a top-level `paths` key, ≤ 1 MB.

## Deploy-mode switching

There are two deploy modes:

- **Upload** (zip) — the deploy command packages and uploads the code. The default for apps
  created without `--repo`.
- **Connect** (GitHub) — the deploy command tells the portal to pull from the pushed branch.
  Required when the workspace has zip uploads disabled.

If you hit the error **"chose GitHub deploys but the app isn't connected"**, the recorded mode
doesn't match the server. Fix it:

```bash
bash substrait.sh link set-mode --mode connect --repo OWNER/REPO
```

To create an app that is GitHub-connected from birth (required in some workspaces):

```bash
bash substrait.sh link create --name <app-name> --repo OWNER/REPO
```

See `docs/linking.md` for the full creation ladder.

## Deploy environments

An app has at most two **deploy environments**: `dev` and `production`. Each is a full,
separate instance with its own database, bucket, URL, variables and secrets.

| | `dev` | `production` |
|---|---|---|
| URL | `https://<slug>--dev.ninjavan.apps.substrait.build` | `https://<slug>.ninjavan.apps.substrait.build` |
| Access | Always behind Ninja Van sign-in — can never be made public | Set on the app's Access tab |
| Created | When the app is created (new apps) | When the app **goes live** |
| Data | Can be seeded from `backend/db/seed.sql` | Starts EMPTY; never seeded |

- **New apps start in `dev`** and have no production until the owner goes live. Apps created
  before this change keep production as their default and can add a `dev` from the
  environment switcher on the app's page.
- **A bare deploy goes to the app's default environment** — `dev` for an app that started
  there, *even after it goes live*. The deploy prints `Target environment: <name>`; always
  tell the user which environment it landed in and give them that environment's URL.
- `--env <name>` picks one explicitly (`bash substrait.sh deploy --env dev`). A deploy aimed
  straight at production (`--env production`) is **refused (HTTP 409)** for an app that has
  a `dev` environment — production changes only by promotion.
- The same folder deploys to either environment — nothing in the code changes. The app can
  read `SUBSTRAIT_ENV` (`production` | `preview`), `SUBSTRAIT_ENV_NAME` (`dev` | `production`)
  and `APP_URL` at runtime. Build absolute links from `APP_URL`, never a hard-coded hostname.
- Each environment has its **own** env vars and secrets: `bash substrait.sh env --env production list`.
  Going live copies NO variables; adding `dev` to an older app copies production's non-secret
  ones. Secrets are never copied — set them per environment.
- To pin a folder to an environment for every command, add `"environment": "production"` to
  `.substrait/config.json`. `--env` always wins.

### Going live / promoting to production — gated, and only when the user asks

Promotion into production does **not** deploy right away. It starts the production
**security check** (Layer 1 scans → Layer 2 classification → Layer 3 human review →
Layer 4) on the build that is live in `dev` at that moment. When the check reaches Layer 4,
that exact build is promoted automatically (database migrated, images copied, no rebuild).
If the check does not clear — a scan fails, a reviewer rejects — nothing is deployed; fix
the issue, deploy to `dev` again, and promote again (a new check starts from Layer 1).

```bash
bash substrait.sh deploy promote --to production   # request it (going live, if no production yet)
bash substrait.sh deploy promotion                 # where it is: the check's layer, or why it was blocked
```

- **Never request this on your own initiative.** Confirm with the user first, and tell them
  that production starts with an **empty** database — nothing is copied from `dev`.
- A review can take a while. Tell the user; do **not** poll `promotion` in a loop.
- Anyone with write access to the app can request it; the security check is the gate.
- **The promotion is refused up front** (nothing starts) while `dev` is not clean: it still
  has blocking security findings, a `dev` scan is still running (wait, then promote again),
  or a scan didn't complete (the user retries it on the app's **Security** tab). If the
  refusal says to run `/substrait:fix`, follow `docs/security.md` instead.
- **Every deploy to `dev` is scanned automatically.** `bash substrait.sh deploy` returns as
  soon as the app is live and does not wait for the scans (the plugin would wait up to 10
  minutes, longer than editor runners allow). `bash substrait.sh security status` shows the
  result at any time. To wait for the verdict in a real terminal instead:
  `SUBSTRAIT_WAIT_FOR_SCANS=1 bash substrait.sh deploy`.
- The container scan blocks on OS CVEs that have a published fix. `cicd/Dockerfile.backend`
  already applies `apt-get upgrade` under its `FROM` — keep that line in every Dockerfile
  you write, in the **final** stage, directly under the `FROM`.

### Seed SQL

`backend/db/seed.sql` (optional) gives a **non-production** database starter rows. It runs
after the Flyway migrations: on the environment's first deploy, again whenever the file
changes, and again after a database reset. **Production is never seeded**, so the app must
work with no rows. Write it to be re-runnable (`INSERT IGNORE` or
`ON DUPLICATE KEY UPDATE` on OceanBase), keep schema changes in `V__` migrations, never in
the seed, and never put real data in it — the file is committed.

## `bash substrait.sh check`

Run before every deploy. Exit 0 = compliant, exit 1 = problems. It reports all of these:

- no backend Dockerfile
- `frontend/` exists but ships no frontend Dockerfile
- no `substrait.yaml`, or no `description:`, or the placeholder description
- Flyway migrations exist but no `database:` declared
- a `k8s/` directory is present

**A green check is not a deploy guarantee.** The server runs additional checks: an nginx
backend base image, unresolvable `COPY` paths, the two banned DDL shapes, a changed
database engine, and a frontend nginx config that proxies to a compose-style hostname (see
`docs/frontend.md`) are all rejected server-side.

---

## Run everything inside this editor. A separate window is a last resort.

**Run every command here, in your own command runner.** Not because it looks tidier —
because **a separate window blinds you.** You cannot read its output, so you cannot see
`! [rejected] ... fetch first`, a merge conflict, or a failed build, and you cannot recover
from any of them. The user ends up relaying error text they don't understand, badly. Run it
here and you read the error yourself and fix it.

**These NEVER need a separate window** — no exceptions:

| Command | Why it's fine here |
|---|---|
| `bash substrait.sh doctor` | prints and exits |
| `bash substrait.sh check` | prints and exits |
| `bash substrait.sh deploy` | streams the build log for ~40s, then exits |
| `bash substrait.sh link` | opens the browser itself; you relay the code |
| `git add` / `commit` / `push` | no interaction once signed in — and you need to see the errors |

### Push failures you should fix yourself, here, without asking

| Git says | What it means | Do this |
|---|---|---|
| `! [rejected] ... (fetch first)` or `(non-fast-forward)` | GitHub has commits you don't | `git pull --rebase origin main` then push again |
| `Updates were rejected because the remote contains work` | same | as above |
| `divergent branches` / `need to specify how to reconcile` | no pull strategy set | `git config pull.rebase true`, then pull and push |
| a rebase stops on a conflict | two edits to the same lines | resolve it properly (below), `git add` the file, `git rebase --continue` |

**Never leave conflict markers in a file.** If you see `<<<<<<< HEAD`, `=======` or
`>>>>>>> origin/main`, the file is broken until you remove them and the unwanted side.
`substrait.sh`, `AGENTS.md` and `SETUP.md` are tooling, not the user's work — when they
conflict, take the newer copy wholesale rather than merging line by line:

```bash
git checkout --theirs substrait.sh   # during a rebase this is the incoming version
git add substrait.sh
```

`bash substrait.sh doctor` reports any file still containing markers.

**Never `git push --force`.** If a rebase can't resolve, stop and explain — force-pushing
can destroy work that someone else, or another copy of this folder, already pushed.

### Interactive steps — when a separate window IS needed

**The one case that may need a window:** the very first `git push` on a machine that has
never signed in to GitHub. Git Credential Manager tries to show a sign-in window and cannot
do so from a sandboxed runner, so the push fails silently with no prompt.

**Escalate only after an in-editor attempt has actually failed.** Do not pre-emptively open
a window because you think one might be needed. The sequence is:

1. Run the command here.
2. If it succeeds — and it usually will, because the credential is cached after the first
   time — you are done. Say nothing about windows.
3. Only if it fails with `Repository not found` or `could not read Username` — the two
   errors that mean a credential prompt could not be shown — and you have already checked
   the four causes in `docs/github-pushing.md`, open a window. **Then immediately re-run the
   command here** so you can see the result yourself rather than relying on what the user
   reports:

```powershell
Start-Process powershell -WorkingDirectory '<FULL PATH TO THIS FOLDER>' -ArgumentList '-NoExit','-Command','git push -u origin main'
```

Use `-WorkingDirectory` rather than building a `cd '<path>';` string — a folder name with an
apostrophe, `&` or `$` breaks the quoting and the window opens on a syntax error.

**Never promise a browser window.** It only appears if they aren't already signed in. Say
what done looks like instead:

> I've opened a window. Either a sign-in page opens in your browser — approve it — or it
> just finishes, meaning you were already signed in. Either way, when the window shows
> `main -> main` it's done.

**Verify it yourself** with `git ls-remote origin` rather than waiting to be told.
