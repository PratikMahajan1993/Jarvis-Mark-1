# Deferred notes (archived 2026-09-09)

Forward-looking lines lifted out of the as-built docs before the rewrite. None of it is a
commitment — it is only what the old docs said was coming next. The plans these grew out of
are in `archive/plans/`.

Some lines were already stale when archived: glance and calendar shipped after they were
written, and the canvas exists at `/canvas` as a manual board.

## work/aspects.md

Roadmap rows, one aspect at a time:

| Aspect | Status |
| --- | --- |
| Calendar | Later |
| Files / Drive | Later |
| Task for Gemini (email handoff) | Later |
| Ordinary chat | Later |
| Canvas | Later |

## work/workbook.md

- **Still to redo:** Calendar, files/Drive, Task-for-Gemini, ordinary chat, canvas as a
  separate workspace. Attach marked drawing to a reply can follow the viewer.
- Glance still waits.
- Canvas later. (trailing the drawing-vision entry)

## work/mail.md

- Canvas discussion is later.

## work/briefing.md

- **Glance** (header line) is not this pass.
- "Board **this pass**" and "not drawn on this board **yet**" framing.

## work/architecture.md

- Local Ollama later (`LLM_PROVIDER=ollama`).
- Mail is being redone the same way. Other work still uses phrase heuristics until its aspect.

## work/viewer.md

- **Not this pass:** true CAD, two drawings side by side, attaching the marked-up file to a
  reply (that hook can come right after export exists).
- Canvas (`/canvas`) stays a separate workspace — no "put on canvas" in this pass.

## docs/AS_BUILT.md

- ... `db.add_canvas_item(...)` on the API side — the one call a future `add_to_canvas` tool
  would make.
