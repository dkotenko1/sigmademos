#!/usr/bin/env bash
# Preflight for a build session: are the official Sigma skills available and is
# the sigma CLI authenticated? Warns, never blocks.
set -u
ok=1
echo "== official Sigma skills (sigmacomputing/sigma-agent-skills) =="
if command -v claude >/dev/null 2>&1; then
  if claude plugin list 2>/dev/null | grep -q "sigma-computing@sigma-computing"; then
    claude plugin list 2>/dev/null | grep -A2 "sigma-computing@sigma-computing" | head -3
  else
    ok=0
    echo "MISSING: install with"
    echo "  claude plugin marketplace add sigmacomputing/sigma-agent-skills"
    echo "  claude plugin install sigma-computing@sigma-computing"
  fi
else
  echo "claude CLI not found; load https://github.com/sigmacomputing/sigma-agent-skills manually"
fi
echo
echo "== sigma CLI =="
CLI="${SIGMA_CLI_BIN:-$HOME/.sigma-cli/bin/sigma}"
if [ -x "$CLI" ]; then
  "$CLI" ${SIGMA_CLI_PROFILE:+-p "$SIGMA_CLI_PROFILE"} auth status 2>&1 | head -6
else
  ok=0
  echo "MISSING: sigma CLI at $CLI (see sigma-skills:sigma-cli)"
fi
echo
[ "$ok" = 1 ] && echo "preflight ok" || echo "preflight: fix the items above before building"
