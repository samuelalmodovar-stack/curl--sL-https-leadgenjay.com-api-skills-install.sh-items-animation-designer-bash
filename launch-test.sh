#!/usr/bin/env bash
# THE PAID RUN. Starts one session with an $8.00 cap and the test outcome.
# Requires explicit confirmation, because this is the step that spends money:
#   CONFIRM_PAID_RUN=yes ./launch-test.sh
set -euo pipefail
cd "$(dirname "$0")"

[ -f .ids.env ] || { echo "ERROR: run ./setup.sh first."; exit 1; }
source .ids.env

if [ "${CONFIRM_PAID_RUN:-}" != "yes" ]; then
  echo "This starts a billable session (cap \$8.00, may overrun by up to one model request)."
  echo "Re-run as: CONFIRM_PAID_RUN=yes ./launch-test.sh"
  exit 1
fi

: "${ANTHROPIC_API_KEY:?Set ANTHROPIC_API_KEY, or run 'ant auth login' and unset this check}"

# Build the request body with python3 so the rubric file is embedded verbatim —
# no heredoc indentation or YAML-escaping hazards.
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
            "questions - all as drafts, none sent. Produce prospects.csv with atomic "
            "columns, research-log.csv covering every company touched including rejects, "
            "ghl-import-mapping.md, daily-brief.md ranking the prospects with the evidence "
            "behind each ranking, and run-log.md. Contact nobody: public search and reading "
            "public pages only, no outreach, no forms, no signups, no purchases."
        ),
        "rubric": {"type": "text", "content": pathlib.Path("rubric.md").read_text()},
        "max_iterations": 5,
    }],
}))
PY
)

SID=$(printf '%s' "$BODY" | ant beta:sessions create --transform id -r)

echo "Session: $SID"
echo "Watch live: https://platform.claude.com/workspaces/<YOUR_WORKSPACE>/sessions/$SID"
echo
ant beta:sessions:events stream --session-id "$SID"
