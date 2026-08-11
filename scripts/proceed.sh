#!/usr/bin/env bash
# Route "proceed to issue #N" to the model its tier label names.
#
# Reads the tier via triage.py --route, which enforces the deny-list, label freshness,
# and the blocked flag; triages on the spot when the issue has no tier or a stale one;
# pauses for confirmation on a low-confidence machine tier; then launches claude with
# the mapped model and the delivery prompt (standing guards plus prior attempt records).
#
#   scripts/proceed.sh 74
set -euo pipefail

if [[ $# -ne 1 || ! $1 =~ ^[0-9]+$ ]]; then
  echo "usage: scripts/proceed.sh <issue-number>" >&2
  exit 64
fi
n=$1
cd "$(dirname "$0")/.."

route() {
  # Capture stdout while letting the verdict come back as the exit code.
  set +e
  model=$(uv run python scripts/triage.py --route "$n")
  rc=$?
  set -e
}

route
if [[ $rc -eq 2 ]]; then
  # No tier, or the body moved since classification: triage now, then re-route once.
  uv run python scripts/triage.py --issue "$n" --apply
  route
fi
if [[ $rc -eq 3 ]]; then
  # Machine-assigned, low confidence. The tier is a floor; a human keypress launches.
  read -r -p "Low-confidence tier; launch with ${model}? [y/N] " answer
  [[ $answer == y || $answer == Y ]] || exit 1
  rc=0
fi
if [[ $rc -ne 0 ]]; then
  # Deny-list refusal or blocked label. Overriding is deliberate: launch claude with an
  # explicit --model instead of re-running this wrapper.
  exit "$rc"
fi

prompt=$(uv run python scripts/triage.py --launch-prompt "$n")
echo "launching claude --model ${model} for issue #${n}"
exec claude --model "$model" "$prompt"
