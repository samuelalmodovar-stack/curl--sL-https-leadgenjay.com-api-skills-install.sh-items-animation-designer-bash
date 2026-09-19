#!/usr/bin/env bash
# After the session stops: report the actual cost and download every deliverable.
# Usage: ./fetch-results.sh [session_id] [output-dir]
set -euo pipefail
cd "$(dirname "$0")"

SID="${1:-$(cat .last-session 2>/dev/null || true)}"
[ -n "$SID" ] || { echo "Usage: ./fetch-results.sh <session_id> [output-dir]"; exit 1; }
OUT="${2:-./deliverables}"

source ./_api.sh

echo "==> Session status and actual cost"
api GET "/sessions/$SID" | python3 -c '
import json, sys
s = json.load(sys.stdin)
if "error" in s:
    sys.exit("API error: " + str(s["error"].get("message")))
u = s.get("usage") or {}
c = u.get("list_cost") or {}
amt = c.get("amount")
print("status:        ", s.get("status"))
print("stop_reason:   ", (s.get("stop_reason") or {}).get("type"))
print("actual cost:   ", f"${int(amt)/100:.2f}" if amt is not None else "n/a", c.get("currency",""))
print("active seconds:", u.get("active_seconds"))
print("input tokens:  ", u.get("input_tokens"))
print("output tokens: ", u.get("output_tokens"))
print("web searches:  ", (u.get("server_tool_use") or {}).get("web_search_requests"))
for ev in s.get("outcome_evaluations") or []:
    print("outcome:       ", ev.get("result"), "-", (ev.get("explanation") or "")[:300])
'

echo
echo "==> Downloading deliverables to $OUT"
mkdir -p "$OUT"

# Files written to /mnt/session/outputs/ are indexed a second or two after the session
# goes idle, so an empty first listing is normal.
FILES=""
for attempt in 1 2 3; do
  FILES=$(curl -sS "$API/files?scope_id=$SID" \
    -H "x-api-key: $ANTHROPIC_API_KEY" \
    -H "anthropic-version: 2023-06-01" \
    -H "anthropic-beta: $BETA,files-api-2025-04-14")
  COUNT=$(printf '%s' "$FILES" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(len(d.get("data",[])) if "error" not in d else 0)')
  [ "$COUNT" -gt 0 ] && break
  echo "   (nothing indexed yet, retry $attempt/3)"; sleep 3
done

printf '%s' "$FILES" | python3 -c '
import json, sys
d = json.load(sys.stdin)
if "error" in d:
    sys.exit("API error: " + str(d["error"].get("message")))
for f in d.get("data", []):
    print(f["id"], f.get("size_bytes",""), f.get("filename",""))
' | while read -r fid fsize fname; do
  [ -n "${fname:-}" ] || continue
  mkdir -p "$OUT/$(dirname "$fname")"
  curl -sS "$API/files/$fid/content" \
    -H "x-api-key: $ANTHROPIC_API_KEY" \
    -H "anthropic-version: 2023-06-01" \
    -H "anthropic-beta: $BETA,files-api-2025-04-14" \
    -o "$OUT/$fname"
  echo "   $fname ($fsize bytes)"
done

echo
echo "Read run-log.md first — it lists what could not be verified and anything refused."
