#!/bin/bash
# Fallback behaviour of omi-frontdoor on a throw-away instance (port 8791): sub -> api -> local. (The api case needs a key in ~/.config/omi-frontdoor/env.)
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; BIN="${FD_BIN:-$HERE/../bin/omi-frontdoor}"; PORT=8791; pass=0; total=0
req='{"system_instruction":{"parts":[{"text":"Answer tersely."}]},"contents":[{"parts":[{"text":"What is 2+2? Answer with just the number."}]}]}'
run() {  # name, env assignments..., expected tier
  local name="$1" want="$2"; shift 2
  : > /tmp/omi-frontdoor-test.log
  env "$@" FD_LISTEN=127.0.0.1:$PORT python3 "$BIN" >/dev/null 2>&1 & local pid=$!
  for _ in $(seq 1 20); do curl -s -m 1 localhost:$PORT/ >/dev/null && break; sleep 0.3; done
  out=$(curl -s -m 150 localhost:$PORT/v1/proxy/gemini/models/gemini-2.5-flash:generateContent -H 'X-Omi-Workload: interactive' -d "$req")
  stats=$(curl -s localhost:$PORT/stats); kill $pid 2>/dev/null; wait $pid 2>/dev/null
  tier=$(python3 -c 'import sys,json; s=json.loads(sys.argv[1]); print(",".join(s["by_tier"]))' "$stats")
  text=$(python3 -c 'import sys,json; print(json.loads(sys.argv[1])["candidates"][0]["content"]["parts"][0]["text"][:40])' "$out" 2>/dev/null)
  total=$((total+1)); [ "$tier" = "$want" ] && { pass=$((pass+1)); r=PASS; } || r=FAIL
  echo "$name: $r (tier=$tier want=$want) reply='$text'"
}
run "no subscription, no key -> local"        local FD_CLAUDE_BIN=/nonexistent ANTHROPIC_API_KEY=
run "subscription cap 0, no key -> local"     local FD_SUB_MAX_PER_HOUR=0 ANTHROPIC_API_KEY=
run "no subscription, key present -> api"     api FD_CLAUDE_BIN=/nonexistent
run "healthy -> subscription"                 sub
echo "RESULT $pass/$total"
