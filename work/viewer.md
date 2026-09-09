# Drawing viewer (built)

HUD **overlay** on top of the mail board. Canvas (`/canvas`) stays a separate workspace; there is no “put on canvas” action.

**Open:** only files already **Saved** locally (`backend/exports/drawings/`). Button on the attachment row, or “view the piston PDF” / “open DPIS000377”.

**What it does**
- View PDF or image over the HUD (mail still behind)
- Zoom, pan, next/prev page
- Crop
- Draw with markers
- Save the edited result as PNG → `backend/exports/drawings` and Drive (same as save-selected)
- Voice while open: zoom in/out, next/prev page, close the drawing (HUD intercept, not the brain)

**Not supported:** true CAD, two drawings side by side, attaching the marked-up file to a reply.

**Status:** Built — HUD overlay, View button, voice open/view commands, zoom/pan/page/crop/mark, Save marked PNG to `exports/drawings` + Drive.
