#!/usr/bin/env bash
set -euo pipefail

# Required: set these in your environment
: "${DREMIO_USER:?Set DREMIO_USER in your environment}"
: "${DREMIO_PASSWORD:?Set DREMIO_PASSWORD in your environment}"

# Optional overrides
DREMIO="${DREMIO:-http://localhost:9047}"
TOKFILE="${TOKFILE:-token.txt}"

mkdir -p "$(dirname "$TOKFILE")"

# Hit the login endpoint, capture body + HTTP status
resp="$(curl -sS -X POST "$DREMIO/apiv2/login" \
  -H 'Content-Type: application/json' \
  -d "{\"userName\":\"$DREMIO_USER\",\"password\":\"$DREMIO_PASSWORD\"}" \
  -w $'\n%{http_code}')"

# Split body and status
http_code="${resp##*$'\n'}"
body="${resp%$'\n'*}"

if [[ "$http_code" != "200" ]]; then
  echo "❌ Login failed. HTTP $http_code"
  echo "— Response body —"
  printf '%s\n' "$body"
  exit 1
fi

# Parse token robustly (prefer jq if present)
if command -v jq >/dev/null 2>&1; then
  token="$(printf '%s' "$body" | jq -r '.token // empty')"
else
  token="$(python3 - <<'PY'
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get("token",""))
except Exception as e:
    sys.stderr.write(f"JSON parse error: {e}\n")
    sys.exit(2)
PY
  <<<"$body")"
fi

if [[ -z "${token:-}" ]]; then
  echo "❌ No token found in response:"
  printf '%s\n' "$body"
  exit 1
fi

printf '%s\n' "$token" > "$TOKFILE"
echo "✅ Token saved to $TOKFILE"
