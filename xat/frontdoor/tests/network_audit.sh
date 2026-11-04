#!/bin/bash
# Phase 0: which remote hosts does the Omi Dev app (and its helper processes) talk to?
# Usage: network_audit.sh [seconds=30] [process pattern="Omi Dev.app/Contents"]
SECS="${1:-30}"; PAT="${2:-Omi Dev.app/Contents}"
TMP="$(mktemp)"; end=$((SECONDS+SECS))
while [ $SECONDS -lt $end ]; do
  for p in $(pgrep -f "$PAT"); do
    nettop -x -n -p "$p" -L 1 2>/dev/null | awk -F, 'NR>1 && $2 ~ /<->/ {print $2 "," $5 "," $6}'
  done >> "$TMP"; sleep 2
done
python3 - "$TMP" <<'PY'
import sys, re, subprocess, collections
rows = collections.defaultdict(lambda: [0, 0, set()])
for line in open(sys.argv[1]):
    f = line.strip().split(",")
    m = re.match(r"\w+ [\d.]+:\d+<->([\d.]+):(\d+)", f[0])
    if not m: continue
    ip, port = m.group(1), m.group(2)
    if ip.startswith(("127.", "192.168.", "10.", "169.254.")): continue
    r = rows[ip]; r[0] = max(r[0], int(f[1] or 0)); r[1] = max(r[1], int(f[2] or 0)); r[2].add(port)
def ptr(ip):
    out = subprocess.run(["dig", "+short", "+time=2", "+tries=1", "-x", ip], capture_output=True, text=True).stdout.strip().splitlines()
    return out[0].rstrip(".") if out else "(no PTR)"
print("%-16s %-8s %-10s %-10s %s" % ("remote ip", "ports", "bytes in", "bytes out", "reverse DNS"))
for ip, (bi, bo, ports) in sorted(rows.items(), key=lambda kv: -kv[1][0]):
    print("%-16s %-8s %-10d %-10d %s" % (ip, ",".join(sorted(ports)), bi, bo, ptr(ip)))
if not rows: print("(no external connections seen)")
PY
rm -f "$TMP"
