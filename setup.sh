#!/usr/bin/env bash
# ONE-TIME SETUP. Creates the agent, the environment, and the persistent datastore,
# then writes their IDs to .ids.env. Starts no session and incurs no model cost.
#
# Guarded: refuses to run twice, so you never accumulate duplicate agent objects.
# To apply an edit to the YAML afterwards, use ./update-agent.sh (a new version of the
# same agent), never a second setup run.
set -euo pipefail
cd "$(dirname "$0")"

if [ -f .ids.env ]; then
  echo "ERROR: .ids.env already exists — these objects were already created."
  echo "Edited the YAML? Run ./update-agent.sh instead."
  exit 1
fi

source ./_api.sh

echo "==> Creating agent"
AGENT_ID=$(api POST /agents "$(yaml2json fence-prospecting.agent.yaml)" | field id)
echo "    $AGENT_ID"

echo "==> Creating environment"
ENV_ID=$(api POST /environments "$(yaml2json fence-prospecting.environment.yaml)" | field id)
echo "    $ENV_ID"

echo "==> Creating persistent datastore"
STORE_BODY=$(python3 -c '
import json
print(json.dumps({
  "name": "Samuel Scales Marketing - Pipeline",
  "description": (
    "Partial, user-confirmed exclusions plus the research history for every company "
    "already looked at (verified, rejected, or incomplete). Check before researching or "
    "including any company. The exclusion list is NOT reconciled against the CRM and is "
    "not a complete list of who must be excluded."
  ),
}))')
STORE_ID=$(api POST /memory_stores "$STORE_BODY" | field id)
echo "    $STORE_ID"

# POST to /memory_stores/{id}/memories is inferred from the SDK method plus the documented
# GET on the same path. If it errors, check the current API reference for this one call.
seed() {
  local body
  body=$(python3 -c 'import json,sys; print(json.dumps({"path": sys.argv[1], "content": sys.argv[2]}))' "$1" "$2")
  api POST "/memory_stores/$STORE_ID/memories" "$body" | field id >/dev/null
  echo "    seeded $1"
}

echo "==> Seeding exclusions and the business brief"
seed /exclusions/README.md 'PARTIAL exclusion list — user-confirmed entries only.

This list has NOT been reconciled against the CRM. It is not a complete list of companies
that must be excluded. A company being absent from this list means only that it is absent
from this list. Never describe exclusions as complete, verified, or CRM-checked.

Still unconfirmed: the full current-client list, the opt-out list, and protected territories.'

seed /exclusions/confirmed.md 'Confirmed excluded — do not research, include, or draft outreach for:

- Summit Fencing LLC
- Samuel Scales Marketing (own business)
- Drone Syndrome Media (own business)'

seed /brief/offer.md 'Samuel Scales Marketing helps established residential fence contractors generate
qualified estimate opportunities through the Fence Clients On Demand System: Meta
advertising, a conversion page or form, and GoHighLevel follow-up.

Pricing: $1,500/month management, plus a separate $1,000/month client advertising budget
(that budget is the client spend, not agency revenue).
Goal: $100,000+ in annual management revenue (~six retained clients).
Voice: direct and conversational. Only substantiated proof — never invented results,
testimonials, guarantees, or any claim of having reviewed a prospect private accounts.'

cat > .ids.env <<EOF
export AGENT_ID=$AGENT_ID
export ENV_ID=$ENV_ID
export STORE_ID=$STORE_ID
EOF

echo
echo "IDs written to .ids.env. Nothing has run and no model cost was incurred."
echo "Next: CONFIRM_PAID_RUN=yes ./launch-test.sh"
