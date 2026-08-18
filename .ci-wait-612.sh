#!/bin/zsh
# Poll PR #612's required check until terminal, then squash-merge and close #597.
sha="b1e7d442e988fc2042fb17641fc156aaed5b388e"
for i in $(seq 1 40); do
  state=$(gh api "repos/ethanpturner/trace/commits/$sha/check-runs" \
    --jq '[.check_runs[] | select(.name=="lint / typecheck / test")][0] | .status + " " + (.conclusion // "pending")' 2>/dev/null)
  echo "poll $i: $state"
  if [ "$state" = "completed success" ]; then
    merged=$(gh api -X PUT repos/ethanpturner/trace/pulls/612/merge -f merge_method=squash --jq '.merged' 2>&1)
    echo "merged: $merged"
    if [ "$merged" = "true" ]; then
      gh issue close 597 --repo ethanpturner/trace --comment "Delivered in PR #612 (squash-merged to develop), DEC-132: future-features 3.1 discharges as trace source add-repo — read-only, an allowlisted loader-readable file set, a full-SHA pin re-resolved after checkout, fetched content entering as untrusted source documents through the existing boundary, the token confined to the clone subprocess and redacted from errors, and the threat model's source-document boundary carrying the channel's transport rows. The issue's benchmark-repository measurement waits on #574 and is recorded as the stated gap in DEC-132."
    fi
    exit 0
  fi
  case "$state" in
    completed*) echo "CHECK FAILED: $state"; exit 1 ;;
  esac
  sleep 25
done
echo "poll budget exhausted"
exit 1
