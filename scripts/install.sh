#!/usr/bin/env bash
# Install playmaker + its pinned OpenKB engine into a local virtualenv.
#
# Use case: redeploy on a fresh machine. Clone the repo, then run this. It
# creates ./.venv, installs the package (which pulls OpenKB pinned in
# pyproject.toml from GitHub), and verifies both CLIs work.
#
#   ./scripts/install.sh            # runtime install
#   ./scripts/install.sh --dev      # also install test deps + run the suite
#
# Requirements on the new machine: Python >= 3.10 and git (the OpenKB pin is a
# git+https dependency). `uv` is used if present (faster); otherwise stdlib
# venv + pip.
set -euo pipefail

DEV=0
[[ "${1:-}" == "--dev" ]] && DEV=1

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
VENV="$REPO_ROOT/.venv"

echo "==> playmaker install (repo: $REPO_ROOT)"

# --- preflight ---
command -v git >/dev/null 2>&1 || { echo "ERROR: git is required (OpenKB is a git dependency)."; exit 1; }

PYTHON="${PYTHON:-python3}"
command -v "$PYTHON" >/dev/null 2>&1 || { echo "ERROR: $PYTHON not found."; exit 1; }
PYVER="$("$PYTHON" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
"$PYTHON" - <<'PY' || { echo "ERROR: Python >= 3.10 required (found $PYVER)."; exit 1; }
import sys
sys.exit(0 if sys.version_info >= (3, 10) else 1)
PY
echo "    Python $PYVER OK"

# --- create venv + install ---
EXTRAS="."
[[ $DEV -eq 1 ]] && EXTRAS=".[dev]"

if command -v uv >/dev/null 2>&1; then
  echo "==> using uv"
  uv venv --python "$PYTHON" "$VENV"
  uv pip install --python "$VENV/bin/python" -e "$EXTRAS"
else
  echo "==> using stdlib venv + pip"
  "$PYTHON" -m venv "$VENV"
  "$VENV/bin/python" -m pip install --upgrade pip
  "$VENV/bin/python" -m pip install -e "$EXTRAS"
fi

# --- verify ---
echo "==> verifying CLIs"
"$VENV/bin/playmaker" --version
"$VENV/bin/openkb" --help >/dev/null && echo "    openkb engine OK"

if [[ $DEV -eq 1 ]]; then
  echo "==> running offline test suite"
  "$VENV/bin/python" -m pytest -q
fi

cat <<EOF

==> Done. Activate the environment with:
      source $VENV/bin/activate

    Then create a playbook instance OUTSIDE this repo, e.g.:
      playmaker init ~/playbooks/my-domain --model openai/<your-model>
      cp ~/playbooks/my-domain/.env.example ~/playbooks/my-domain/.env
      # edit that .env: LLM_API_KEY + OPENAI_API_BASE

    See README.md "Quick start".
EOF
