"""Compare the three tiers on realistic Omi-style jobs. Usage: tier_compare.py [host:port] [screenshot.png]
Each case has expected keywords; score = keywords found / expected, plus JSON validity and latency."""
import base64, json, sys, time, urllib.request
hp = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:8790"
png = sys.argv[2] if len(sys.argv) > 2 else "/tmp/xat-jarvis-test/st.png"
IMG = base64.b64encode(open(png, "rb").read()).decode()
TRANS = [
 ("Valex call", "Alan: I need to call Brad tomorrow about the SD card charges on the Valex Ventura account, number 1050750. "
  "Also I have to submit the national account service order by Friday, I'm already behind. And I prefer reviewing work orders in the morning before routing stops.",
  ["brad", "sd card", "friday", "service order"]),
 ("Server chat", "Alan: Jellyfin keeps buffering on the TV. Let's move transcoding off the Mac Studio. Remind me to check the Traefik routes tonight. "
  "I don't want to pay for any more cloud services, keep everything local.",
  ["jellyfin", "transcod", "traefik", "local"]),
 ("Errands", "Alan: Pick up the dry cleaning on Thursday, book the dentist for next month, and get the oil changed before the road trip on the twentieth.",
  ["dry cleaning", "dentist", "oil"]),
]
SCHEMA = {"type": "OBJECT", "properties": {
    "memories": {"type": "ARRAY", "items": {"type": "STRING"}},
    "tasks": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"title": {"type": "STRING"}, "due": {"type": "STRING"}}, "required": ["title"]}}},
    "required": ["memories", "tasks"]}
SYS = "Extract durable facts about the speaker as memories and concrete to-dos as tasks from the conversation. Be concise."

def call(tier, body, lane="memory", wl="extraction"):
    r = urllib.request.Request("http://%s/v1/proxy/gemini/models/gemini-2.5-flash:generateContent" % hp, json.dumps(body).encode(),
                               {"Content-Type": "application/json", "X-FD-Tier": tier, "X-Omi-Lane": lane, "X-Omi-Workload": wl})
    t = time.time()
    try:
        d = json.load(urllib.request.urlopen(r, timeout=200)); parts = d["candidates"][0]["content"]["parts"]
        return parts, time.time() - t, None
    except Exception as e:
        return None, time.time() - t, str(e)[:100]

print("%-12s %-6s %-6s %-8s %s" % ("case", "tier", "json", "recall", "time"))
tot = {}
for name, text, kws in TRANS:
    for tier in ("local", "sub", "api"):
        body = {"system_instruction": {"parts": [{"text": SYS}]}, "contents": [{"parts": [{"text": text}]}],
                "generation_config": {"response_mime_type": "application/json", "response_schema": SCHEMA}}
        parts, dt, err = call(tier, body)
        valid, rec = False, 0
        if parts:
            out = parts[0].get("text", "")
            try: j = json.loads(out); valid = isinstance(j.get("memories"), list) and isinstance(j.get("tasks"), list)
            except Exception: j = {}
            blob = json.dumps(j).lower()
            rec = sum(k in blob for k in kws) / len(kws)
        print("%-12s %-6s %-6s %-8s %.1fs %s" % (name, tier, "ok" if valid else "BAD", "%d%%" % (rec * 100), dt, err or ""))
        t = tot.setdefault(tier, [0, 0, 0.0, 0]); t[0] += valid; t[1] += rec; t[2] += dt; t[3] += 1
# vision
body = {"contents": [{"parts": [{"text": "List the names of the apps or windows visible in this screenshot as a JSON array of strings."}, {"inline_data": {"mime_type": "image/png", "data": IMG}}]}],
        "generation_config": {"response_mime_type": "application/json"}}
for tier in ("local", "sub", "api"):
    parts, dt, err = call(tier, body, "screen_synthesis", "interactive")
    out = (parts[0].get("text", "") if parts else err)[:90].replace("\n", " ")
    print("%-12s %-6s %-6s %-8s %.1fs %s" % ("vision", tier, "", "", dt, out))
print()
for tier, (v, r, dt, n) in tot.items():
    print("%-6s valid %d/%d  mean recall %d%%  mean %.1fs" % (tier, v, n, r / n * 100, dt / n))
