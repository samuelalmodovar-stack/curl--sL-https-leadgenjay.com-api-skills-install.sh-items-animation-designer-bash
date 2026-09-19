#!/usr/bin/env bash
# Apply an edit to fence-prospecting.agent.yaml as a NEW VERSION of the existing agent.
# This is the correct way to change the agent — never create a second one.
set -euo pipefail
cd "$(dirname "$0")"

[ -f .ids.env ] || { echo "ERROR: run ./setup.sh first."; exit 1; }
source ./.ids.env
source ./_api.sh

CURRENT=$(api GET "/agents/$AGENT_ID" | field version)
echo "==> Current version: $CURRENT"

# Send the version we read, so a concurrent edit is a 409 rather than a silent overwrite.
BODY=$(python3 -c '
import json, sys, yaml
cfg = yaml.safe_load(open("fence-prospecting.agent.yaml"))
cfg["version"] = int(sys.argv[1])
print(json.dumps(cfg))
' "$CURRENT")

NEW=$(api POST "/agents/$AGENT_ID" "$BODY" | field version)
echo "==> Updated to version: $NEW"
echo
echo "Sessions already running keep the version they started on."
echo "New sessions pick this up, because launch-test.sh references the agent by ID."
