# Security findings that block going live

Every deploy to `dev` is scanned by Substrait (code, secrets, dependencies, container image,
and the running app). Findings the organisation's policy marks as **blocking** stop the app
going live: a promotion to production is refused until `dev` is clean. Which findings block
is the server's decision — never argue with the list, re-rank it, or decide a finding
"doesn't really block". Fix it, file a false-positive claim with Infosec, or report it as
still blocking.

This is the starter's version of Substrait's `/substrait:fix`. Do it only when the user asks
whether the app can go live, asks to fix its security findings, or a promotion was refused
for blocking findings.

```bash
bash substrait.sh security status                        # summary, one key=value per line
bash substrait.sh security findings                      # the full blocking set (JSON)
bash substrait.sh security submit-fp --file .substrait/fp-claims.json   # file claims
```

## 1. Preflight — stop at the first check that fails, and say why

- **Where `dev` stands:** `bash substrait.sh security status` prints `blocking_total`,
  `scans_running`, `scans_errored`, `commit_sha`, `source_hash`.
  - `scans_running` not empty → the scan isn't finished. Name the scanners, tell the user to
    ask again in a few minutes, and stop.
  - `scans_errored` not empty → name them. The user must retry them on the app's
    **Security** tab in the portal first. Stop.
- **Is the scanned code the code on disk?** The findings belong to what is deployed.
  `git rev-parse HEAD` must equal `commit_sha`, and `git status --porcelain` must print
  nothing. If not, say: "Deploy your changes first, then I'll check the security findings"
  — and stop. Don't deploy from here without the user's go-ahead.
- **`blocking_total` is 0** → "Nothing is blocking — the app is clear to go live." Stop.

## 2. Summarise

`bash substrait.sh security findings` returns `scanners[]`, each with a `display_name`, a
`blocking_count` and its `findings[]`. For a long list, redirect it to
`.substrait/findings.json` and read that file instead. Each finding carries `finding_id`,
`name`, `severity`, `file`/`line` (or `file_path`), `description`, scanner-specific fields
(`rule_id`, `credential`, `engine`, `solution`, `cve_id`, `pkg_name`, `installed_version`,
`fixed_version`, `container_target`, `dockerfile_path`, `no_fix`) and `fp` — Infosec's
false-positive state (`status`, `decision_note`, `reviewer_name`, `locked`).

Tell the user in plain language, grouped by scanner `display_name`, what blocks and where.
Then list separately:

- **Awaiting Infosec** — `fp.status` is `pending`. Leave these alone.
- **Infosec asked a question** — `fp.status` is `info_requested`. Quote `fp.decision_note`;
  answer it by filing a claim on that finding again (step 4) whose reason answers it.
- **Rejected** — `fp.status` is `rejected`. Quote `fp.decision_note`; it is the brief for the fix.
- **Locked** — `fp.locked` is true. It can only be fixed, never claimed.
- **No fix available** — `no_fix` is true. No upstream release fixes it yet.

## 3. Fix every actionable finding in one pass — from its fields, never the scanner's name

- **`no_fix: true`** → no workaround. Don't remove, pin around or vendor the component to
  dodge the scanner. Report it as **still blocking**.
- **A hardcoded credential** (the finding has a `credential`) → read the value from an
  environment variable instead, and store it as a secret for `dev`:
  `read -rsp "NAME: " NAME; printf '%s' "$NAME" | bash substrait.sh env --env dev set NAME --secret; unset NAME`
  — give the user that command to run themselves; **never print the secret**. Tell them
  plainly the credential **must still be rotated**: it was exposed in the code and the git
  history, so moving it is not enough. Production gets its own copy at go-live.
- **Found on the running app** (the finding has an `engine`, or its `file` is a URL) → fix
  the cause in code or configuration and label it **"verified after deploy"** — only the next
  scan of the running app can confirm it.
- **A vulnerable package with a `fixed_version`** → raise `pkg_name` to at least
  `fixed_version` in the file it came from (`file_path`, e.g. `backend/requirements.txt`),
  keeping the pin exact. If it names a `container_target`/`dockerfile_path`, fix the base
  image or the upgrade line in that Dockerfile (see *Every Dockerfile you write* in AGENTS.md).
  Keep the change as small as the fix needs.
- **Code findings** → fix the code at `file:line` the way `description` (and `rule_id`) call
  for — the real fix, not a rewrite that merely stops the pattern matching.
- **Never** add suppression comments or ignore files (`nosemgrep`, `gitleaks:allow`,
  `.trivyignore`, …) and never delete a file to make a finding disappear. Suppression is
  Infosec's decision, through a claim.
- Then run the app locally (`docs/running-locally.md`) and fix anything you broke.

## 4. False-positive claims — only on the user's "y"

Only for **unlocked** findings you did not fix and are confident are not real problems (test
fixtures, example values, unreachable code, a scanner misreading the code). Infosec reviews
each claim, so each needs a concrete, checkable reason.

1. Show the user every claim — scanner, `name`, `file:line`, your reason — and ask whether to
   file them. **File only if they type "y".**
2. A previously rejected finding may be claimed again only if the new reason directly answers
   the reviewer's `decision_note`; otherwise fix it.
3. Write `.substrait/fp-claims.json` (that folder is never committed or deployed):
   `{"items":[{"finding_id":123,"agent_reason":"…"}],"user_note":null}`
   then run `bash substrait.sh security submit-fp --file .substrait/fp-claims.json` and delete
   the file. `"duplicate": true` = a claim was already open (tell the user, not an error);
   `"answered": true` = their answer went onto the claim Infosec asked about.
4. Filing needs the **account** link. On "not signed in to an account", run
   `bash substrait.sh link account`. Relay any refusal as is; never retry it.

## 5. Close out

Report four short lists: **fixed** (marking "verified after deploy" where it applies),
**filed with Infosec**, **not fixable** (still blocking, and why), **secrets to rotate**.
Nothing counts until it is deployed and re-scanned, so ask "Deploy now?". On "y": commit →
push → `bash substrait.sh deploy`, then tell the user the scans take a few minutes and offer
to run `bash substrait.sh security status` again afterwards.
