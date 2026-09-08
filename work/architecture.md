# Architecture

Four parts: ears (browser speech), face (HUD), hands (tools), brain (LLM).

**Tools own facts.** Mail, calendar, files, Drive, and web search come from connectors. The brain picks tools and writes *speak* (whisper) and *board* (scene). It must not invent prices, threads, or calendar rows.

**Brain now:** Gemini when `GEMINI_API_KEY` is set (`LLM_PROVIDER=auto`). Local Ollama later (`LLM_PROVIDER=ollama`). Email **Task for Gemini** is a Gmail handoff tool, not this brain.

**Work vs chat.** Ordinary talk can go straight to the model. Work turns must use tools. Research already does: Gemini may call `research`, then `refine_research` grounds speak/board in page notes. Mail is being redone the same way. Other work still uses phrase heuristics until its aspect.

**Surfaces:** home HUD (voice + board); canvas at `/canvas` (manual only, no agent yet).
