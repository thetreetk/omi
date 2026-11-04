#!/bin/bash
# End-to-end checks against the running Omi Dev app through its automation bridge (omi-ctl).
# Needs: Omi Dev running and signed in, front door running, TextEdit available. Usage: omi_e2e.sh [omi-checkout]
OMI="${1:-$HOME/src/omi-checkout/omi}"; CTL="$OMI/desktop/macos/scripts/omi-ctl"; S="${SCRATCH:-/tmp/xat-omi-test}"; mkdir -p "$S"
pass=0; total=0; ok() { total=$((total+1)); [ "$2" = 1 ] && { pass=$((pass+1)); echo "PASS $1"; } || echo "FAIL $1  ($3)"; }
log() { ls -t /tmp/omi-dev-*.log | head -1; }
"$CTL" wait-ready 60 >/dev/null 2>&1 || { echo "Omi Dev is not ready"; exit 1; }

# 1 Gemini-lane calls from the real app reach the front door (dictation polish through the network path)
curl -s -m 30 localhost:8880/v1/audio/speech -H 'Content-Type: application/json' -d '{"model":"kokoro","input":"Type. um so remind me to call Brad tomorrow about the uh SD card charges","voice":"am_adam","response_format":"wav"}' -o "$S/d.wav"
python3 - "$S" <<'PY'
import sys,wave,audioop
S=sys.argv[1]+"/"; w=wave.open(S+"d.wav"); d=w.readframes(w.getnframes())
if w.getnchannels()>1: d=audioop.tomono(d,w.getsampwidth(),0.5,0.5)
d,_=audioop.ratecv(d,w.getsampwidth(),1,w.getframerate(),16000,None); open(S+"d.pcm","wb").write(d)
PY
osascript -e 'tell application "TextEdit" to activate' -e 'tell application "TextEdit" to make new document' >/dev/null 2>&1; sleep 2
: > /tmp/omi-frontdoor.log
out=$("$CTL" action voice_typing_dictate pcm="$S/d.pcm" network=true 2>&1); sleep 4
echo "$out" | grep -q '"polished" : "true"' && p=1 || p=0; ok "dictation polished through the Gemini lane" $p "$(echo "$out" | grep -E 'polished|error' | head -1)"
grep -q "lane=dictation" /tmp/omi-frontdoor.log && p=1 || p=0; ok "front door saw the dictation lane" $p "$(tail -2 /tmp/omi-frontdoor.log)"
osascript -e 'tell application "TextEdit" to close every document saving no' -e 'tell application "TextEdit" to quit' >/dev/null 2>&1

# 2 Chat runs on the Claude subscription (acp), not on Omi's cloud model, and is not blocked by a full free quota
"$CTL" action apply_usage_quota used=30 limit=30 >/dev/null 2>&1
n=$(grep -a -c "chat_agent_query_completed" "$(log)")
"$CTL" action ask query="What is 9 plus 4? Answer with just the number." >/dev/null 2>&1
for _ in $(seq 1 40); do [ "$(grep -a -c 'chat_agent_query_completed' "$(log)")" -gt "$n" ] && break; sleep 1; done
grep -a "chat_agent_query_completed" "$(log)" | tail -1 | grep -q "session_adapter_id=acp" && p=1 || p=0
ok "chat completes on session_adapter_id=acp with the quota at 30/30" $p "$(grep -a 'chat_agent_' "$(log)" | tail -1 | cut -c1-200)"

# 3 Local summary engine (Ollama) returns schema-valid output for every session it ran
r=$("$CTL" action local_summary_benchmark limit=3 engine=local-server 2>&1)
rep=$(echo "$r" | grep '"path"' | sed -E 's/.*: "(.*)".*/\1/; s#\\/#/#g')
python3 - "$rep" <<'PY' && p=1 || p=0
import json,sys
c=json.load(open(sys.argv[1]))["cases"]; sys.exit(0 if c and all(x["schemaValid"] and not x["fallback"] for x in c) else 1)
PY
ok "local summaries schema-valid on every session" $p "report: $rep"
echo "RESULT $pass/$total"
