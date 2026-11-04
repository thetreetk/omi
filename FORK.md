# Omi, XAT fork: run Omi's background AI on your own models

> Unofficial fork of [BasedHardware/omi](https://github.com/BasedHardware/omi) (MIT). Not affiliated with or endorsed by Omi/Based Hardware.
> Upstream's `README.md` and licence are unchanged; this file and the `xat/` directory are the only additions apart from two small Swift patches.

## What this fork is for
Omi's desktop app sends its background AI (dictation clean-up, proactive screen assistants, memory and task extraction, live notes,
embeddings, screen-task extraction) and its spoken replies through Omi's own server, which calls Google Gemini and a cloud voice.
On the free plan some of that is gated, and none of it can be pointed at another model. This fork adds **one switch** that sends those calls
to a service on your own machine, which answers from, in order: your **Claude subscription** (Claude Code CLI, no API key), an
**Anthropic API key**, or a **local model** (Ollama). Sign-in, storage and sync still use Omi's backend; this does not host a backend.

When the switch is unset the app behaves exactly like upstream.

## Branches
| Branch | Contents |
|---|---|
| `main` | mirror of upstream `main` (sync from the GitHub "Sync fork" button or `git fetch upstream`) |
| `xat-open` (default) | upstream + the commits below + `FORK.md` + `xat/` |

Base commit: [`05374e9f`](https://github.com/BasedHardware/omi/commit/05374e9f) (upstream `main`, 2026-11-03), whose macOS app sources match release `v0.12.560+12560-macos`.
Syncing: `git fetch upstream && git rebase upstream/main` on `xat-open`; the patches are about 40 lines in 5 files, so conflicts are rare. Re-run the checks in "Verify" after each sync.

## The patches (macOS app, `desktop/macos/Desktop/Sources`)
| File | Change |
|---|---|
| `ProactiveAssistants/Core/GeminiProxyOverride.swift` (new) | reads `OMI_GEMINI_PROXY_URL`; accepts only loopback `http://` URLs |
| `ProactiveAssistants/Core/GeminiClient.swift` | `proxyBaseURL` returns the override first, which redirects every client that shares it (generate, embed, batch embed) |
| `Services/SubscriptionEntitlementService.swift` | with the override active, the proactive-assistant plan gate is open (the gate only protects Omi's paid proxy) |
| `LocalInference/ScreenCloudEntitlementService.swift` | same for the cloud-embedding gate |
| `ProactiveAssistants/Assistants/TaskExtraction/ScreenTaskTransport.swift` | screen-task extraction calls to `v1/proxy/gemini/*` use the override |
| `Services/APIClient/APIClient+People.swift` | cloud text-to-speech (`v1/tts/synthesize`) uses the override too |

## The companion service: `xat/frontdoor/omi-frontdoor`
A single-file Python 3.9+ service (standard library only) that answers Gemini-format `generateContent`, `embedContent` and
`batchEmbedContents` requests plus Omi's `v1/tts/synthesize`.
- **Tier order** per request (configurable): interactive work `subscription -> API key -> local`; background or lite work `local -> subscription -> API key`;
  function calling `API key -> local`. A sliding-hour cap (`FD_SUB_MAX_PER_HOUR`, default 40) protects the subscription.
- **Subscription tier** runs `claude -p` in lean mode (about 600 tokens of overhead per call, images through the Read tool).
- **Local tier** uses Ollama: vision, JSON-schema output and tools; embeddings with `nomic-embed-text`, zero-padded to Omi's 3072 dimensions.
- **Text to speech** goes to a local OpenAI-compatible speech server (Kokoro), returned as mp3.
- Logs sizes, lane, tier and latency to `/tmp/omi-frontdoor.log`; never request content. `GET /stats` for counters.

## Run it
```bash
# 1. service (needs Ollama with a vision model and nomic-embed-text; the `claude` CLI logged in for the subscription tier)
install -m 755 xat/frontdoor/omi-frontdoor ~/.local/bin/ && python3 ~/.local/bin/omi-frontdoor      # 127.0.0.1:8790
# optional: ~/.config/omi-frontdoor/env  (see xat/frontdoor/frontdoor.env.example), launchd plist in xat/frontdoor/
# 2. app: copy the settings and build the dev bundle
cp xat/env.app.dev.example desktop/macos/.env.app.dev
cd desktop/macos && ./run.sh --yolo --no-wait --full      # --full matters: the fast path re-signs in place and macOS kills the app
defaults write com.omi.desktop-dev chatBridgeMode claudeCode   # chat on your Claude subscription instead of Omi's cloud model
```
Only non-production bundles honour the override (the shipped `com.omi.computer-macos` bundles ignore backend settings by design).

## Verify
`xat/frontdoor/tests/`: `frontdoor_test.py` (7 request shapes), `frontdoor_fallback_test.sh` (tier fallbacks), `tier_compare.py`
(quality and latency per tier), `omi_e2e.sh` (drives the running app through Omi's own automation bridge), `network_audit.sh` (which hosts the app contacts).

Results on the author's machine (Apple silicon, Ollama `qwen3-vl:30b-a3b-instruct`):
| Check | Result |
|---|---|
| Front door request shapes (subscription JSON, local text, local vision JSON, subscription vision, function calling, 3072-dim embeddings) | 7/7 |
| Fallback chain (no subscription, hourly cap, API key, healthy) | 4/4 |
| End to end in the real app: dictation clean-up reaches the service, chat runs on the Claude adapter even with the free quota at 30/30, local summaries are schema-valid | 4/4 |
| Quality on three extraction transcripts (JSON valid / keyword recall / mean time) | local 3/3, 100%, 2.2 s; subscription 3/3, 91%, 2.7 s; API 3/3, 100%, 1.9 s |
| Idle network inventory | two Google Cloud addresses (Omi's backend); no Gemini, Deepgram, OpenAI or analytics hosts (dev builds skip analytics and update checks) |

## Known limits
- Omi's backend still stores your data and runs its own server-side conversation processing, realtime voice and cloud transcription; this fork does not replace those.
- Chat sessions are durable and pin their adapter: switch `chatBridgeMode` before first use, or delete the dev bundle's `AgentRuntime/<bundle id>/omi-agentd.sqlite3` and relaunch.
- Local vision on full screenshots can invent app names; subscription and API tiers are accurate.
- Omi's floating bar can leave a transparent 382x350 window after an answer that swallows clicks (`omi-ctl action debug_bar_state state=idle` resets it).

## Licence and credit
MIT, same as upstream; see `LICENSE`. All upstream credit stays with the Omi/Based Hardware authors. Changes here are by [@thetreetk](https://github.com/thetreetk).
