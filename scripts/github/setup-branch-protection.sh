#!/usr/bin/env bash
# Require release-gate.yml's aggregate `release-gate` job as a required status
# check on `main`, so a PR literally cannot merge while it's red.
#
# Not run automatically by anything — this is infrastructure/security-relevant
# repo configuration, applied deliberately by a human. Requires `gh` authenticated
# with admin rights on the repo (repo settings, not just contents).
#
# Usage:
#   ./scripts/github/setup-branch-protection.sh [owner/repo]
# Defaults to the current repo's `origin` remote if no argument is given.
set -euo pipefail

REPO="${1:-$(gh repo view --json nameWithOwner --jq .nameWithOwner)}"

echo "Configuring branch protection for ${REPO}#main ..."
echo "Required status check: release-gate (from .github/workflows/release-gate.yml)"
echo

gh api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  "repos/${REPO}/branches/main/protection" \
  -f "required_status_checks[strict]=true" \
  -f "required_status_checks[contexts][]=release-gate" \
  -F "enforce_admins=true" \
  -f "required_pull_request_reviews[required_approving_review_count]=1" \
  -F "required_pull_request_reviews[dismiss_stale_reviews]=true" \
  -F "restrictions=null" \
  -F "allow_force_pushes=false" \
  -F "allow_deletions=false"

echo
echo "Done. Verify at: https://github.com/${REPO}/settings/branches"
