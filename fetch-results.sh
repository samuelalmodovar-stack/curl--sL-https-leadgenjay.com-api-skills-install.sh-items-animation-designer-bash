#!/usr/bin/env bash
# After the test session goes idle: print the actual cost and download every deliverable.
# Usage: ./fetch-results.sh sesn_xxxxx [output-dir]
set -euo pipefail
cd "$(dirname "$0")"

SID="${1:?Usage: ./fetch-results.sh <session_id> [output-dir]}"
OUT="${2:-./deliverables}"
: "${ANTHROPIC_API_KEY:?Set ANTHROPIC_API_KEY}"

API="https://api.anthropic.com/v1"
HDRS=(-H "x-api-key: $ANTHROPIC_API_KEY"
       -H "anthropic-version: 2023-06-01"
       -H "anthropic-beta: managed-agents-2026-04-01,files-api-2025-04-14")

echo "==> Session status and actual cost"
curl -fsS "$API/sessions/$SID" "${HDRS[@]}" | python3 -c '
import json, sys
s = json.load(sys.stdin)
u = s.get("usage") or {}
cost = (u.get("list_cost") or {})
amount = cost.get("amount")
print("status:        ", s.get("status"))
print("stop_reason:   ", (s.get("stop_reason") or {}).get("type"))
print("list cost:     ", f"${int(amount)/100:.2f}" if amount is not None else "n/a", cost.get("currency",""))
print("active seconds:", u.get("active_seconds"))
print("web searches:  ", (u.get("server_tool_use") or {}).get("web_search_requests"))
for ev in s.get("outcome_evaluations") or []:
    print("outcome:       ", ev.get("outcome_id"), "->", ev.get("result"))
'

echo
echo "==> Downloading deliverables to $OUT"
mkdir -p "$OUT"
# Brief indexing lag between idle and files appearing - retry a couple of times.
for attempt in 1 2 3; do
  FILES=$(curl -fsS "$API/files?scope_id=$SID" "${HDRS[@]}")
  COUNT=$(printf '%s' "$FILES" | python3 -c 'import json,sys; print(len(json.load(sys.stdin).get("data",[])))')
  [ "$COUNT" -gt 0 ] && break
  echo "   (no files yet, retrying $attempt/3)"; sleep 3
done

printf '%s' "$FILES" | python3 -c '
import json, sys
for f in json.load(sys.stdin).get("data", []):
    print(f["id"], f.get("filename",""), f.get("size_bytes",""))
' | while read -r fid fname fsize; do
  [ -n "$fid" ] || continue
  mkdir -p "$OUT/$(dirname "$fname")"
  curl -fsS "$API/files/$fid/content" "${HDRS[@]}" -o "$OUT/$fname"
  echo "   $fname ($fsize bytes)"
done

echo
echo "Deliverables in $OUT"
