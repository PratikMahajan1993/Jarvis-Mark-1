# Chat work list

Scratch list for this pass. Not a new architecture doc. Work one area at a time. `turn_ledger_enabled` stays off until that area is opened.

Owner choice, 2026-09-25: keep today's split. Gemini answers ordinary talk. Hermes and the local tools own shop work. Gemini also reads engineering drawings, inside this same chat, in a simple viewing window.

## Areas

1. **Live chat** — in progress. What you say, who answers, what you hear. The drawing window below is the first slice in code.
2. **Sentence kind** — not started. Greeting, shop work, or a desk command.
3. **Spoken reply** — not started. Voicebox makes the WAV. The browser plays it once.
4. **Permission pause** — not started. Authorize / Reject inside the same conversation.
5. **Conversation memory** — not started. Session messages, separate from the three open notes.
6. **Crash recovery** — not started. The turn ledger. Same chat, written down before the work starts.
7. **Lenses** — not started, and not a separate chat. Casual / Monitor / Engineering stay one conversation.

## Live chat today

One request. The desk waits until the turn finishes, then speaks. States are idle, listening, thinking, speaking, one at a time.

- A bare hello, thanks, "how are you", or a joke goes to Gemini.
- If Gemini is down, a fixed line answers ("Yes?", "Of course.", "Good morning.").
- Shop talk goes to Hermes when the gateway is up.
- Mail read, calendar list, briefing, and shop-sheet numbers use local tools. The model does not invent those.
- Yes or no while an Authorize card is open resolves that card.
- The user line is stored before the answer. A crash mid-turn drops the answer.

## Live chat target

One box on every lens. Ordinary talk stays on Gemini and stays short enough to say aloud. Shop numbers stay in tools. Authorize still pauses the chat. The fixed greeting lines stay the offline spare. The ledger is not part of this slice.

### Drawing window

Ready to try on the desk. Part of live chat, not a second product.

- Drop a PDF or image onto the orb from any lens. Jarvis saves the file once under `data/inbox/drawings/`, keyed by its contents. The database stores the path and that fingerprint, not the file itself. The same bytes open the existing drawing instead of saving a second copy.
- That drop is a temporary test permission. Gemini may look, and the notes say it is an unattested test look. Real customer consent still applies when master data is on and the sheet is tied to a customer.
- The next things you say, while that window is open, are about that sheet.
- The panel "From the sheet" shows what Gemini read. If that customer has no attested vision consent, Jarvis refuses to send the file and does not invent sizes. The picture still opens so you can look.
- A quote, mail, or calendar request leaves the drawing chat and follows the normal shop path.
- Close the window, or say "close the drawing", and that viewing ends. The desk chat stays.
