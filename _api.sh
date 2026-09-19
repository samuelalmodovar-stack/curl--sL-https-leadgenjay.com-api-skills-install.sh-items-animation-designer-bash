# Shared helpers. Sourced by the other scripts, not run directly.
# Uses only curl + python3 so nothing has to be installed.

: "${ANTHROPIC_API_KEY:?ANTHROPIC_API_KEY is not set. See README.md > Authentication.}"

API="${ANTHROPIC_BASE_URL:-https://api.anthropic.com}/v1"
BETA="managed-agents-2026-04-01"

# api METHOD PATH [JSON_BODY] -> response body on stdout
api() {
  local method="$1" path="$2" body="${3:-}"
  local args=(-sS -X "$method" "$API$path"
    -H "x-api-key: $ANTHROPIC_API_KEY"
    -H "anthropic-version: 2023-06-01"
    -H "anthropic-beta: $BETA"
    -H "content-type: application/json")
  [ -n "$body" ] && args+=(-d "$body")
  curl "${args[@]}"
}

yaml2json() {
  python3 -c 'import json,sys,yaml; print(json.dumps(yaml.safe_load(sys.stdin)))' < "$1"
}

# Pull a field out of a response, or print the API error and exit.
field() {
  python3 -c '
import json, sys
key = sys.argv[1]
raw = sys.stdin.read()
try:
    d = json.loads(raw)
except ValueError:
    sys.exit("Non-JSON response from API:\n" + raw[:800])
if isinstance(d, dict) and "error" in d:
    err = d["error"] or {}
    etype = err.get("type", "?")
    emsg = err.get("message", raw[:800])
    sys.exit("API error (" + str(etype) + "): " + str(emsg))
if key not in d:
    sys.exit("Response had no " + repr(key) + " field:\n" + raw[:800])
print(d[key])
' "$1"
}
