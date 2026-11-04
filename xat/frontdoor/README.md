# omi-frontdoor

Local stand-in for the Gemini proxy and TTS route that Omi's desktop app calls. See `../../FORK.md` for the why and the full setup.
Config: environment variables `FD_*` (see the top of `omi-frontdoor`) or `~/.config/omi-frontdoor/env`. Stats: `curl localhost:8790/stats`.
Tier pinning for tests: send header `X-FD-Tier: sub|api|local`.
