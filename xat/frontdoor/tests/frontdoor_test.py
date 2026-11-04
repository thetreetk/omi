"""Exercises omi-frontdoor with Gemini-format requests like Omi sends.  Usage: frontdoor_test.py [host:port] [image.png]"""
import base64, json, sys, time, urllib.request
hp = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:8790"
png = sys.argv[2] if len(sys.argv) > 2 else "/tmp/xat-jarvis-test/st.png"
B64 = base64.b64encode(open(png, "rb").read()).decode()

def call(model, action, body, lane="", wl=""):
    r = urllib.request.Request("http://%s/v1/proxy/gemini/models/%s:%s" % (hp, model, action), json.dumps(body).encode(),
                               {"Content-Type": "application/json", "X-Omi-Lane": lane, "X-Omi-Workload": wl})
    t = time.time()
    try:
        return json.load(urllib.request.urlopen(r, timeout=200)), time.time() - t
    except Exception as e:
        return {"error": str(e)}, time.time() - t

def txt(resp):
    try:
        return "".join(p.get("text", "") or ("CALL:" + json.dumps(p["functionCall"])) for p in resp["candidates"][0]["content"]["parts"])
    except Exception:
        return "ERR " + json.dumps(resp)[:200]

SCHEMA = {"type": "OBJECT", "properties": {"answer": {"type": "STRING"}, "confidence": {"type": "NUMBER"}}, "required": ["answer"]}
ok = 0; total = 0
def check(name, cond, detail):
    global ok, total
    total += 1; ok += bool(cond)
    print("%-44s %s  %s" % (name, "PASS" if cond else "FAIL", detail))

# 1 interactive JSON-schema text -> subscription
r, dt = call("gemini-2.5-flash", "generateContent", {
    "system_instruction": {"parts": [{"text": "You answer arithmetic questions."}]},
    "contents": [{"parts": [{"text": "What is 17 times 3?"}]}],
    "generation_config": {"response_mime_type": "application/json", "response_schema": SCHEMA}}, "suggestions", "interactive")
t = txt(r)
try: ans = json.loads(t)["answer"]
except Exception: ans = ""
check("interactive JSON (subscription first)", "51" in ans, "%.1fs %s" % (dt, t[:80]))

# 2 lite model -> local
r, dt = call("gemini-2.5-flash-lite", "generateContent", {"contents": [{"parts": [{"text": "Give a 3-word title for: grocery list for tacos"}]}]}, "memory", "extraction")
check("lite/extraction text (local first)", len(txt(r)) > 3 and "ERR" not in txt(r), "%.1fs %s" % (dt, txt(r)[:60]))

# 3 vision + JSON, background -> local
r, dt = call("gemini-2.5-flash", "generateContent", {
    "contents": [{"parts": [{"text": "Which application's menu bar is visible at the top? Answer in JSON."}, {"inline_data": {"mime_type": "image/png", "data": B64}}]}],
    "generation_config": {"response_mime_type": "application/json", "response_schema": SCHEMA}}, "task_extraction", "extraction")
check("vision JSON, background (local)", "ERR" not in txt(r) and txt(r).startswith("{"), "%.1fs %s" % (dt, txt(r)[:90]))

# 4 vision interactive -> subscription (Read tool)
r, dt = call("gemini-2.5-flash", "generateContent", {
    "contents": [{"parts": [{"text": "Describe in one sentence what this screenshot shows."}, {"inline_data": {"mime_type": "image/png", "data": B64}}]}]}, "screen_synthesis_x", "interactive")
check("vision interactive (subscription+Read)", "ERR" not in txt(r) and len(txt(r)) > 20, "%.1fs %s" % (dt, txt(r)[:100]))

# 5 function calling -> local (no API key)
r, dt = call("gemini-2.5-flash", "generateContent", {
    "contents": [{"role": "user", "parts": [{"text": "Create a task named 'call Brad about SD cards'."}]}],
    "tools": [{"function_declarations": [{"name": "create_task", "description": "Create a task", "parameters": {"type": "OBJECT", "properties": {"title": {"type": "STRING"}}, "required": ["title"]}}]}]}, "insight", "interactive")
check("function calling (local tier)", "CALL:" in txt(r) and "create_task" in txt(r), "%.1fs %s" % (dt, txt(r)[:100]))

# 6 embeddings
r, dt = call("gemini-embedding-001", "embedContent", {"model": "models/gemini-embedding-001", "content": {"parts": [{"text": "hello world"}]}, "taskType": "RETRIEVAL_DOCUMENT"})
v = r.get("embedding", {}).get("values", [])
check("embedContent: 3072 dims, unit length", len(v) == 3072 and abs(sum(x * x for x in v) - 1) < 1e-3, "%.1fs dims=%d" % (dt, len(v)))
r, dt = call("gemini-embedding-001", "batchEmbedContents", {"requests": [{"content": {"parts": [{"text": t}]}} for t in ("cat", "dog", "invoice")]})
e = r.get("embeddings", [])
sim = lambda a, b: sum(x * y for x, y in zip(a, b))
check("batchEmbedContents: 3 vectors, cat~dog>cat~invoice", len(e) == 3 and sim(e[0]["values"], e[1]["values"]) > sim(e[0]["values"], e[2]["values"]), "%.1fs" % dt)

# 7 stats
st = json.load(urllib.request.urlopen("http://%s/stats" % hp))
print("stats:", json.dumps({k: st[k] for k in ("requests", "by_tier", "failures", "sub_calls_last_hour")}))
print("RESULT %d/%d" % (ok, total))
