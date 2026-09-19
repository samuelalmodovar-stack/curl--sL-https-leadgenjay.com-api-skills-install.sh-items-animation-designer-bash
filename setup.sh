#!/usr/bin/env bash
# ONE-TIME SETUP. Creates the agent, the environment, and the persistent datastore,
# then writes their IDs to .ids.env. Creates nothing billable and starts no session.
#
# Guarded: refuses to run twice, so you never end up with duplicate agent objects.
# Re-running after an edit to the YAML is an `ant beta:agents update`, not a second create.
set -euo pipefail
cd "$(dirname "$0")"

if [ -f .ids.env ]; then
  echo "ERROR: .ids.env already exists — the agent/environment/store were already created."
  echo "To apply YAML changes instead:"
  echo "  source .ids.env"
  echo "  ant beta:agents update --agent-id \"\$AGENT_ID\" --version N < fence-prospecting.agent.yaml"
  exit 1
fi

: "${ANTHROPIC_API_KEY:?Set ANTHROPIC_API_KEY, or run 'ant auth login' and unset this check}"
command -v ant >/dev/null || { echo "ERROR: the 'ant' CLI is not installed."; exit 1; }

echo "==> Creating agent"
AGENT_ID=$(ant beta:agents create < fence-prospecting.agent.yaml --transform id -r)

echo "==> Creating environment"
ENV_ID=$(ant beta:environments create < fence-prospecting.environment.yaml --transform id -r)

# Memory store calls go through curl: the REST paths are documented, and the exact
# `ant` subcommand surface for memory stores is not confirmed here. The POST shape for
# creating a memory under a store is inferred from the SDK method and the documented
# GET on the same path — if it 404s, check the current API reference for that one call.
API="https://api.anthropic.com/v1"
HDRS=(-H "x-api-key: $ANTHROPIC_API_KEY"
       -H "anthropic-version: 2023-06-01"
       -H "anthropic-beta: managed-agents-2026-04-01"
       -H "content-type: application/json")

echo "==> Creating persistent datastore"
STORE_ID=$(curl -fsS "$API/memory_stores" "${HDRS[@]}" -d '{
  "name": "Samuel Scales Marketing - Pipeline",
  "description": "Partial, user-confirmed exclusions and the research history for every company already looked at (verified, rejected, or incomplete). Check before researching or including any company. The exclusion list is NOT reconciled against the CRM and is not a complete list of who must be excluded."
}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

seed_memory() {
  curl -fsS "$API/memory_stores/$STORE_ID/memories" "${HDRS[@]}" \
    -d "$(python3 -c 'import json,sys; print(json.dumps({"path": sys.argv[1], "content": sys.argv[2]}))' "$1" "$2")" \
    >/dev/null
}

echo "==> Seeding exclusions and the business brief"
seed_memory /exclusions/README.md 'PARTIAL exclusion list — user-confirmed entries only.

This list has NOT been reconciled against the CRM. It is not a complete list of companies
that must be excluded. A company being absent from this list means only that it is absent
from this list. Never describe exclusions as complete, verified, or CRM-checked.

Unconfirmed and still outstanding: full current-client list, opt-out list, protected
territories.'

seed_memory /exclusions/confirmed.md 'Confirmed excluded (do not research, do not include, do not draft outreach for):

- Summit Fencing LLC
- Samuel Scales Marketing (own business)
- Drone Syndrome Media (own business)'

seed_memory /brief/offer.md 'Samuel Scales Marketing helps established residential fence contractors generate
qualified estimate opportunities through the Fence Clients On Demand System: Meta
advertising, a conversion page or form, and GoHighLevel follow-up.

Pricing: $1,500/month management, plus a separate $1,000/month client advertising budget.
Goal: $100,000+ in annual management revenue (~six retained clients).
Voice: direct and conversational. Only substantiated proof — no invented results,
testimonials, guarantees, or claims of having reviewed a prospect private accounts.'

cat > .ids.env <<EOF
export AGENT_ID=$AGENT_ID
export ENV_ID=$ENV_ID
export STORE_ID=$STORE_ID
EOF

echo
echo "Done. IDs written to .ids.env:"
cat .ids.env
echo
echo "Nothing has run yet and nothing has been billed. Next: ./launch-test.sh"
