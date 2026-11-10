#!/usr/bin/env bash
# Wrapper around Substrait's official tooling. Clones their plugin on first use and
# refreshes it after, so you always run their current scripts — nothing is forked.
#
#   bash substrait.sh doctor    check this machine and this project, change nothing
#   bash substrait.sh check     audit the project against Substrait's deploy contract
#   bash substrait.sh link      authorise this machine (opens your browser)
#   bash substrait.sh deploy    build and ship, streaming the log; returns once the app is live
#   bash substrait.sh security  Dev security findings that block going live (status|findings|submit-fp)
#   bash substrait.sh env ...   manage the app's env vars and secrets
#   bash substrait.sh library   browse the internal API catalogue (needs the account link)
#   bash substrait.sh logs      read the deployed app's runtime logs (needs the account link)
#   bash substrait.sh logout    sign this machine out of Substrait (revokes the token)
#   bash substrait.sh update    pull latest scaffolding (AGENTS.md, docs/, substrait.sh, SETUP.md)
set -uo pipefail

# ── Always run from the project root, whatever the caller's working directory ─────
cd "$(dirname "$0")" 2>/dev/null || { echo "Error: cannot enter the script's folder." >&2; exit 1; }
if [ ! -f substrait.yaml ] || [ ! -d backend ]; then
  echo "Error: this doesn't look like the project folder (no substrait.yaml / backend/)." >&2
  echo "       I am in: $(pwd)" >&2
  echo "       Open the folder that contains substrait.yaml and try again." >&2
  exit 1
fi

# ── Pipe-safe output ────────────────────────────────────────────────────────────
# IDE runners (TraeWork, OpenCode) sometimes close stdout before the script
# finishes, causing "echo: write error: Bad file descriptor". We capture all
# output to a log file so nothing is lost even when the pipe breaks. The AI
# reads the log file; the user sees live output in a real terminal.
_SUBSTRAIT_LOG="$(pwd)/.substrait-last-run.log"
if [ "${_SUBSTRAIT_INNER:-}" != "1" ]; then
  export _SUBSTRAIT_INNER=1
  if [ -t 1 ]; then
    # Real terminal — stream live AND keep a log
    "$0" "$@" 2>&1 | tee "$_SUBSTRAIT_LOG"
    exit ${PIPESTATUS[0]}
  else
    # Piped (IDE runner) — capture to file, immune to broken pipes
    "$0" "$@" > "$_SUBSTRAIT_LOG" 2>&1
    _rc=$?
    cat "$_SUBSTRAIT_LOG" 2>/dev/null
    exit $_rc
  fi
fi

# ── Where the tooling lives ──────────────────────────────────────────────────────
# Prefer LOCALAPPDATA on Windows: $HOME can be a redirected or mapped network drive on
# corporate images, which makes the clone fail or crawl.
TOOLS="${SUBSTRAIT_TOOLS:-}"
if [ -z "$TOOLS" ] && [ -n "${LOCALAPPDATA:-}" ] && command -v cygpath >/dev/null 2>&1; then
  TOOLS="$(cygpath -u "$LOCALAPPDATA")/substrait-tools"
fi
TOOLS="${TOOLS:-$HOME/.substrait-tools}"
SCRIPTS="$TOOLS/substrait-plugin/scripts"
REPO="https://github.com/substrait-build/substrait-claudecode-plugin.git"

# Some editor sandboxes (TraeWork) block writes to ~/.substrait, which silently breaks
# saving the account link: the browser OAuth succeeds but the credential can't be stored,
# and the link reports failure. Probe writability; if blocked, keep the credential in the
# tooling directory instead — the same location the sandbox already allows us to clone into.
# Machine-level either way, so one link covers every project. An existing ~/.substrait link
# is left alone, and a pre-set SUBSTRAIT_GLOBAL_CONFIG always wins.
if [ -z "${SUBSTRAIT_GLOBAL_CONFIG:-}" ] && [ ! -f "$HOME/.substrait/config.json" ]; then
  if ! ( mkdir -p "$HOME/.substrait" && : > "$HOME/.substrait/.wtest" && rm -f "$HOME/.substrait/.wtest" ) 2>/dev/null; then
    mkdir -p "$TOOLS" 2>/dev/null
    export SUBSTRAIT_GLOBAL_CONFIG="$TOOLS/account-config.json"
    echo "Note: this editor blocks ~/.substrait — keeping the Substrait account link in"
    echo "      $SUBSTRAIT_GLOBAL_CONFIG instead. This is normal and machine-wide."
  fi
fi

# Substrait ships no default portal URL. Since plugin v2026.11.05 the saved login follows the
# installation when its API address moves — but only when the URL comes from the saved login,
# never from $SUBSTRAIT_PORTAL_URL. So read the saved address first and export the hosted
# default ONLY when nothing is saved yet (a machine that has never linked). Logins get the
# address passed explicitly (see `link` below).
_SUBSTRAIT_DEFAULT_PORTAL="https://api.substrait.build"
_saved_portal() {
  local f gc="${SUBSTRAIT_GLOBAL_CONFIG:-$HOME/.substrait/config.json}" v
  for f in .substrait/config.json "$gc" "$(dirname "$gc")"/profiles/*.json; do
    [ -f "$f" ] || continue
    v="$(sed -n 's/.*"portal_url"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$f" 2>/dev/null | head -1)"
    [ -n "$v" ] && { printf '%s' "${v%/}"; return 0; }
  done
  return 1
}
SUBSTRAIT_LOGIN_PORTAL="${SUBSTRAIT_PORTAL_URL:-$(_saved_portal || printf '%s' "$_SUBSTRAIT_DEFAULT_PORTAL")}"
if [ -z "${SUBSTRAIT_PORTAL_URL:-}" ] && ! _saved_portal >/dev/null; then
  export SUBSTRAIT_PORTAL_URL="$_SUBSTRAIT_DEFAULT_PORTAL"
fi
# Linking appends the platform's own contract block to a memory file. Keep it out of
# AGENTS.md — its text describes the zip-upload path and would contradict ours.
export SUBSTRAIT_MEMO_FILE="${SUBSTRAIT_MEMO_FILE:-SUBSTRAIT-CONTRACT.md}"
# On a network that intercepts TLS, point this at the corporate root CA .pem and curl/git
# will trust it, instead of anyone reaching for --insecure.
if [ -n "${SUBSTRAIT_CA_BUNDLE:-}" ] && [ -f "${SUBSTRAIT_CA_BUNDLE}" ]; then
  export CURL_CA_BUNDLE="$SUBSTRAIT_CA_BUNDLE" SSL_CERT_FILE="$SUBSTRAIT_CA_BUNDLE" \
         GIT_SSL_CAINFO="$SUBSTRAIT_CA_BUNDLE"
fi

# ── Fetch / refresh the tooling ──────────────────────────────────────────────────
fetch_tools() {
  if [ ! -d "$TOOLS/.git" ]; then
    # A part-finished clone leaves a non-repo directory that blocks every future attempt.
    rm -rf "$TOOLS"
    echo "First run: downloading Substrait's tooling (this can take a few minutes behind"
    echo "corporate antivirus). Please wait…"
    # autocrlf=false is essential: with Git for Windows' default, every .sh below is
    # checked out with CRLF and dies with "$'\r': command not found".
    if ! git clone --depth 1 --config core.autocrlf=false --config core.eol=lf \
         "$REPO" "$TOOLS" 2>&1; then
      rm -rf "$TOOLS"
      echo "Error: could not download the Substrait tooling from GitHub." >&2
      echo "       Usually a proxy, firewall or VPN issue rather than a broken repo." >&2
      echo "       Check that github.com opens in your browser, then try again." >&2
      exit 1
    fi
    echo "Tooling ready."
  else
    # The plugin moved from the developer's personal account to substrait-build.
    # A clone made before the move still pulls from the old URL; re-point it so
    # refreshes keep tracking the maintained repo.
    if [ "$(git -C "$TOOLS" remote get-url origin 2>/dev/null)" != "$REPO" ]; then
      git -C "$TOOLS" remote set-url origin "$REPO" 2>/dev/null || true
    fi
    git -C "$TOOLS" pull --ff-only --quiet 2>/dev/null \
      || git -C "$TOOLS" fetch --depth 1 -q origin 2>/dev/null \
      && git -C "$TOOLS" reset --hard -q '@{u}' 2>/dev/null || true
  fi
  if [ ! -d "$SCRIPTS" ]; then
    rm -rf "$TOOLS"
    echo "Error: the tooling download was incomplete. Run this command again." >&2
    exit 1
  fi
  # An older clone (made before we forced LF) can hold CRLF scripts that fail with
  # "$'"'"'\r'"'"': command not found". Detect and re-clone rather than hand-patching.
  if LC_ALL=C grep -qU $'"'"'\r'"'"' "$SCRIPTS/substrait-deploy.sh" 2>/dev/null; then
    echo "Tooling had Windows line endings — re-downloading it cleanly…"
    rm -rf "$TOOLS"
    git clone --depth 1 --config core.autocrlf=false --config core.eol=lf "$REPO" "$TOOLS" >/dev/null 2>&1 \
      || { echo "Error: re-download failed." >&2; exit 1; }
  fi
}

# (Browser opening: the plugin's own opener has used rundll32 on Git Bash since v2026.11.05,
# which fixed the "opens File Explorer / Documents" bug this wrapper used to patch around.)

# ── doctor: one command that tells you whether anything here can work ────────────
doctor() {
  local fail=0 warn=0
  echo "Substrait project doctor"
  echo "------------------------"
  printf 'folder          : %s\n' "$(pwd)"

  case "$(pwd)" in
    *OneDrive*|*SharePoint*)
      echo "  PROBLEM: this folder is inside OneDrive. Sync locks files while git is using"
      echo "           them, which corrupts the repository. Move it to C:\\dev first."
      fail=1 ;;
  esac
  if [ "$(pwd | LC_ALL=C wc -c)" -gt 120 ]; then
    echo "  WARNING: long path — Windows breaks at 260 characters. Prefer C:\\dev."
    warn=1
  fi
  if LC_ALL=C printf '%s' "$(pwd)" | LC_ALL=C grep -q '[^ -~]'; then
    echo "  WARNING: the path contains non-English characters, which some tools mishandle."
    warn=1
  fi

  # Unresolved merge conflict markers left in a file by a bad pull. Very common when an
  # AI resolves a conflict badly, and it silently breaks whatever file it lands in.
  local conflicted
  conflicted="$(LC_ALL=C grep -rlE '^<{7} |^>{7} ' --exclude-dir=.git . 2>/dev/null | head -5)"
  if [ -n "$conflicted" ]; then
    echo "merge conflicts : FOUND"
    printf '  PROBLEM: these files still contain unresolved conflict markers:\n'
    printf '           %s\n' $conflicted
    echo "           Fix them before anything else — the files are broken as they stand."
    fail=1
  else
    echo "merge conflicts : none"
  fi

  # CRLF is the single most common Windows breakage.
  if LC_ALL=C grep -qU $'\r' substrait.sh 2>/dev/null; then
    echo "line endings    : BROKEN (Windows CRLF)"
    echo "  FIX: sed -i 's/\r$//' substrait.sh   then run this again"
    fail=1
  else
    echo "line endings    : ok (LF)"
  fi

  printf 'bash            : %s\n' "${BASH_VERSION:-unknown}"
  if command -v git >/dev/null 2>&1; then printf 'git             : %s\n' "$(git --version)"
  else echo "git             : MISSING"; fail=1; fi
  if command -v curl >/dev/null 2>&1; then printf 'curl            : %s\n' "$(curl --version | head -1)"
  else echo "curl            : MISSING"; fail=1; fi

  printf 'autocrlf        : %s\n' "$(git config --get core.autocrlf 2>/dev/null || echo '(unset)')"
  printf 'longpaths       : %s\n' "$(git config --get core.longpaths 2>/dev/null || echo '(unset)')"
  printf 'credential help : %s\n' "$(git config --get credential.helper 2>/dev/null || echo '(unset)')"
  printf 'git remote      : %s\n' "$(git remote get-url origin 2>/dev/null || echo '(none)')"
  printf 'git branch      : %s\n' "$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '(no commits)')"

  local code
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
          "$SUBSTRAIT_LOGIN_PORTAL/api/link/start" 2>/dev/null)" || code=""
  if [ -n "$code" ] && [ "$code" != "000" ]; then
    echo "substrait api   : reachable (HTTP $code)"
  else
    echo "substrait api   : UNREACHABLE"
    echo "  Usually a proxy, VPN or TLS-interception issue. Do NOT disable certificate"
    echo "  checks. Try: git config --global http.sslBackend schannel"
    fail=1
  fi

  echo "------------------------"
  if [ "$fail" -ne 0 ]; then echo "RESULT: BLOCKED — fix the PROBLEM lines above."; return 1
  elif [ "$warn" -ne 0 ]; then echo "RESULT: OK WITH WARNINGS"; return 0
  else echo "RESULT: READY"; return 0; fi
}

# ── update: pull the latest scaffolding files from the starter repo ─────────
# Replaces ONLY the infrastructure files (AGENTS.md, substrait.sh, docs/, SETUP.md,
# README.md). Never touches the app's own code or config: backend/, frontend/, cicd/,
# substrait.yaml, openapi.json, .substrait/, .gitignore.
STARTER_REPO="https://github.com/XB-AI-Champions/substrait-starter.git"
_SCAFFOLD_FILES="AGENTS.md substrait.sh SETUP.md README.md docs"

update_scaffold() {
  echo "Updating scaffolding from the starter repo…"
  local tmpdir
  tmpdir="$(mktemp -d)" || { echo "Error: could not create temp directory." >&2; exit 1; }
  # shellcheck disable=SC2064
  trap "rm -rf '$tmpdir'" EXIT

  if ! git clone --depth 1 --config core.autocrlf=false --config core.eol=lf \
       "$STARTER_REPO" "$tmpdir/starter" 2>&1; then
    echo "Error: could not fetch the starter repo." >&2
    echo "       Check your network and try again." >&2
    exit 1
  fi

  # Remove old docs/ so deleted files don't linger
  rm -rf docs/

  # Copy each scaffold file/directory
  local item
  for item in $_SCAFFOLD_FILES; do
    if [ -e "$tmpdir/starter/$item" ]; then
      if [ -d "$tmpdir/starter/$item" ]; then
        cp -r "$tmpdir/starter/$item" "$item"
      else
        cp "$tmpdir/starter/$item" "$item"
      fi
      echo "  updated: $item"
    fi
  done

  # Fix line endings on Windows — the clone should be LF but be safe
  if command -v sed >/dev/null 2>&1; then
    sed -i 's/\r$//' substrait.sh 2>/dev/null || true
  fi

  rm -rf "$tmpdir"
  trap - EXIT

  echo ""
  echo "Scaffolding updated. Your app code is untouched."
  echo "Run 'git diff' to review, then commit when ready."
}

# ── deploy: return as soon as the app is live ─────────────────────────────────
# Since plugin v2026.10.25, a --watch deploy to a non-production environment (dev) keeps
# running for up to 10 more minutes AFTER the app is live, waiting for the Dev security
# scans to print a go-live verdict. That verdict is advisory, but editor runners time out
# long before 10 minutes and report a failure for a deploy that succeeded. So stop at the
# plugin's "✅ Live:" line (its own message says interrupting the wait is safe) and leave
# the verdict to `bash substrait.sh security status`.
# SUBSTRAIT_WAIT_FOR_SCANS=1 keeps the plugin's full behaviour.
deploy_until_live() {
  if [ "${SUBSTRAIT_WAIT_FOR_SCANS:-0}" = "1" ]; then
    bash "$SCRIPTS/substrait-deploy.sh" --watch "$@"; return $?
  fi
  local out pid shown=0 total live=0 rc
  out="$(mktemp)" || { bash "$SCRIPTS/substrait-deploy.sh" --watch "$@"; return $?; }
  bash "$SCRIPTS/substrait-deploy.sh" --watch "$@" > "$out" 2>&1 &
  pid=$!
  while :; do
    total="$(wc -l < "$out" | tr -d ' ')"
    if [ "$total" -gt "$shown" ]; then
      sed -n "$((shown + 1)),${total}p" "$out" | LC_ALL=C grep -vF "Dev security scans (up to 10 min"
      shown=$total
    fi
    if LC_ALL=C grep -qF '✅ Live: https://' "$out"; then live=1; break; fi
    kill -0 "$pid" 2>/dev/null || break
    sleep 2
  done
  if [ "$live" -eq 1 ]; then
    sleep 1   # let the Live line finish writing
    kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null
    sed -n "$((shown + 1)),\$p" "$out" | LC_ALL=C grep -vF "Dev security scans (up to 10 min"
    rm -f "$out"
    echo "Deploy finished — the app is live. Security scans continue on Substrait's side;"
    echo "'bash substrait.sh security status' shows whether anything blocks going live."
    return 0
  fi
  wait "$pid"; rc=$?
  sed -n "$((shown + 1)),\$p" "$out"
  rm -f "$out"
  return $rc
}

cmd="${1:-}"; shift 2>/dev/null || true

# ── Guard: refuse to deploy/check from the shared starter repo ──────────────
# If the git remote still points at the starter, the AI skipped setup step 1.
# Catch it here before code lands in the wrong repository.
_guard_starter() {
  local _origin
  _origin="$(git remote get-url origin 2>/dev/null)" || return 0  # no remote is fine
  case "$_origin" in
    *XB-AI-Champions/substrait-starter*|*xb-ai-champions/substrait-starter*)
      echo "" >&2
      echo "═══════════════════════════════════════════════════════════════════" >&2
      echo "  STOP — git remote still points at the shared STARTER repo:"     >&2
      echo "         $_origin"                                                 >&2
      echo ""                                                                  >&2
      echo "  You must create your OWN repository first."                      >&2
      echo "  See docs/new-app-setup.md for the full steps."                   >&2
      echo ""                                                                  >&2
      echo "  Quick fix:"                                                      >&2
      echo "    rm -rf .git && git init -b main"                               >&2
      echo "    git remote add origin https://USER@github.com/ACCOUNT/REPO.git" >&2
      echo "    git add -A && git commit -m 'initial commit'"                  >&2
      echo "    git push -u origin main"                                       >&2
      echo "═══════════════════════════════════════════════════════════════════" >&2
      echo "" >&2
      exit 1 ;;
  esac
}

case "$cmd" in
  doctor) doctor ;;
  check)  _guard_starter; fetch_tools; bash "$SCRIPTS/substrait-deploy.sh" check ;;
  link)   fetch_tools
          if [ $# -eq 0 ]; then set -- account; fi
          # A login needs the portal address; pass the saved one (else the hosted default)
          # unless the caller gave --portal-url.
          case "$1" in account|save-account)
            case " $* " in *" --portal-url"*) ;; *) set -- "$@" --portal-url "$SUBSTRAIT_LOGIN_PORTAL" ;; esac ;;
          esac
          bash "$SCRIPTS/substrait-link.sh" "$@" ;;
  deploy) _guard_starter; fetch_tools; deploy_until_live "$@" ;;
  security) fetch_tools; bash "$SCRIPTS/substrait-security.sh" "$@" ;;
  env)    fetch_tools; bash "$SCRIPTS/substrait-env.sh" "$@" ;;
  library) fetch_tools; bash "$SCRIPTS/substrait-library.sh" "$@" ;;
  logs)   fetch_tools; bash "$SCRIPTS/substrait-logs.sh" "$@" ;;
  logout) fetch_tools; bash "$SCRIPTS/substrait-link.sh" logout "$@" ;;
  update) update_scaffold ;;
  *) echo "usage: bash substrait.sh {doctor|check|link|deploy|security|env|library|logs|logout|update}" >&2; exit 2 ;;
esac
