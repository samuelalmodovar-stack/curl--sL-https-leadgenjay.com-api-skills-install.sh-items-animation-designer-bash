#!/usr/bin/env bash
# THE PAID RUN. Starts one session with an $8.00 cap and the test outcome.
# Requires explicit confirmation, because this is the step that spends money:
#   CONFIRM_PAID_RUN=yes ./launch-test.sh
set -euo pipefail
cd "$(dirname "$0")"

[ -f .ids.env ] || { echo "ERROR: run ./setup.sh first."; exit 1; }
source ./.ids.env

if [ "${CONFIRM_PAID_RUN:-}" != "yes" ]; then
  echo "This starts a billable session: \$8.00 cap, which one in-flight model request can"
  echo "overrun by a fraction of a dollar. Nothing else is billed by this script."
  echo
  echo "Re-run as: CONFIRM_PAID_RUN=yes ./launch-test.sh"
  exit 1
fi

source ./_api.sh

BODY=$(python3 - "$AGENT_ID" "$ENV_ID" "$STORE_ID" <<'PY'
import json, sys, pathlib
agent_id, env_id, store_id = sys.argv[1:4]
print(json.dumps({
    "agent": agent_id,
    "environment_id": env_id,
    "title": "Fence prospecting test - Alabama, up to 5 verified prospects",
    "budget": {"type": "limit", "max_list_cost": {"amount": "800", "currency": "USD"}},
    "resources": [{
        "type": "memory_store",
        "memory_store_id": store_id,
        "access": "read_write",
        "instructions": (
            "Partial, user-confirmed exclusions plus research history. Check before "
            "researching or including any company, and record every company you touch "
            "(verified, rejected, or incomplete). The exclusion list is not complete and "
            "is not CRM-reconciled - never describe it as either."
        ),
    }],
    "initial_events": [{
        "type": "user.define_outcome",
        "description": (
            "Target market: Alabama. Find and verify up to five established residential "
            "fence contractors, aiming for five but never relaxing the verification bar to "
            "reach that number. For each verified prospect, produce a prospect brief, one "
            "personalized first-contact message, two follow-up drafts, and discovery-call "
            "questions - all drafts, none sent. Produce prospects.csv with atomic columns, "
            "research-log.csv covering every company touched including rejects, "
            "ghl-import-mapping.md, daily-brief.md ranking the prospects with the evidence "
            "behind each ranking, and run-log.md. Contact nobody: public search and reading "
            "public pages only - no outreach, no forms, no signups, no purchases."
        ),
        "rubric": {"type": "text", "content": pathlib.Path("rubric.md").read_text()},
        "max_iterations": 5,
    }],
}))
PY
)

SID=$(api POST /sessions "$BODY" | field id)

echo "Session: $SID"
echo "$SID" > .last-session
echo "Watch live: https://platform.claude.com/workspaces/<YOUR_WORKSPACE>/sessions/$SID"
echo
echo "Poll status:  ./watch.sh"
echo "When idle:    ./fetch-results.sh $SID"
