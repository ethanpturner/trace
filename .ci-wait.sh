#!/bin/zsh
set -u
sha=$(git rev-parse HEAD)
for i in $(seq 1 40); do
  state=$(gh api "repos/ethanpturner/trace/commits/$sha/check-runs" --jq '[.check_runs[] | select(.name=="lint / typecheck / test")][0] | "\(.status) \(.conclusion)"' 2>/dev/null)
  echo "poll $i: $state"
  if [[ "$state" == "completed success" ]]; then exit 0; fi
  if [[ "$state" == completed* && "$state" != "completed success" ]]; then echo CI_FAILED; exit 1; fi
  sleep 20
done
echo TIMEOUT
exit 2
