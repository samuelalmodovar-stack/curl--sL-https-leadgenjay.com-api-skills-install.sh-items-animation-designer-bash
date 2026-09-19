#!/usr/bin/env bash
# Poll a session until it stops working. Prints status and running cost.
# Usage: ./watch.sh [session_id]   (defaults to the last session launched)
set -euo pipefail
cd "$(dirname "$0")"

SID="${1:-$(cat .last-session 2>/dev/null || true)}"
[ -n "$SID" ] || { echo "Usage: ./watch.sh <session_id>"; exit 1; }

source ./_api.sh

while :; do
  DONE=$(api GET "/sessions/$SID" | python3 -c '
import json, sys
s = json.load(sys.stdin)
if "error" in s:
    sys.exit("API error: " + str(s["error"].get("message")))
u = s.get("usage") or {}
amount = (u.get("list_cost") or {}).get("amount")
cost = f"${int(amount)/100:.2f}" if amount is not None else "n/a"
status = s.get("status")
stop = (s.get("stop_reason") or {}).get("type")
print(f"{status:<13} cost {cost:>8}   stop_reason={stop}", file=sys.stderr)

# Working: keep polling. Stopped: say why.
if status == "terminated":
    print("done")
elif status == "idle":
    if stop == "requires_action":
        print("needs-you")
    elif stop == "budget_reached":
        print("budget")
    else:
        print("done")
else:
    print("")
')
  case "$DONE" in
    done)      echo; echo "Session stopped. Next: ./fetch-results.sh $SID"; break ;;
    budget)    echo; echo "PAUSED AT THE \$8 CAP. Deliverables may be partial."
               echo "It resumes only if the cap is raised — do not raise it without approval."
               echo "Check what exists so far: ./fetch-results.sh $SID"; break ;;
    needs-you) echo; echo "PAUSED FOR APPROVAL — a tool call is waiting on a decision"
               echo "(most likely a web_fetch the server would not run unreviewed)."
               echo "Open the Console session to review and allow or deny it."; break ;;
  esac
  sleep 20
done
