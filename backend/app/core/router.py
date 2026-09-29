"""Shop intent router: ONNX bi-encoder, utterance routes, no regex layer.

semantic-router 0.1.x requires Python <3.14, so this desk (3.14) runs the same
idea on FastEmbed: embed each route's example lines once, then score a new
line by its closest example (cosine). Callers map the route name onto the
coarse intent the desk already understands.

The encoder is not loaded until ``warm()``. A missing model or a failed
download leaves ``classify_fast`` returning None so the Gemini router still runs.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from ..config import settings

log = logging.getLogger("jarvis.router")

ENCODER_MODEL = "BAAI/bge-small-en-v1.5"
HIGH_SCORE = 0.75
# bge-small cosine is not a probability. 0.50 still accepted "explain quantum
# physics" as casual (about 0.58). Real shop lines in the acceptance set sit
# at 0.69 and above, so the floor is just under that band.
ROUTE_MIN_SCORE = 0.65

# Coarse intent + HUD agent. Tools still come from intent.py.
ROUTE_INTENT: dict[str, tuple[str, str]] = {
    "cad_drawing_task": ("vision_task", "DAT.03"),
    "shop_query": ("tool_ops", "DAT.03"),
    "rfq_quote": ("tool_ops", "DAT.03"),
    "email_read": ("tool_ops", "SEC.02"),
    "email_send": ("tool_ops", "OPS.04"),
    "casual_chat": ("casual_chat", "RES.01"),
    "ui_command": ("ui_command", "SYS"),
}

_UTTERANCES: dict[str, tuple[str, ...]] = {
    "cad_drawing_task": (
        "inspect the GD&T on this blueprint",
        "check GD&T on the drawing",
        "hey jarvis, inspect GD&T on this print",
        "read the hole coordinates off this drawing",
        "what are the hole coordinates on the print",
        "jarvis check the drill depth on this view",
        "what's the drill depth called out here",
        "list the tolerance callouts on this drawing",
        "are these tolerances bilateral or limit",
        "dimension offsets on the section view",
        "parse this blueprint for me",
        "read the section view on the print",
        "what's the surface finish callout",
        "check the surface finish on the bore",
        "is the runout in spec on this print",
        "perpendicularity callout on the face",
        "flatness and perpendicularity on this drawing",
        "find the material cert for this heat",
        "what's the heat number on the cert",
        "which revision is this drawing",
        "revision control on the latest print",
        "hey jarvis, what revision is the blueprint",
        "true position of the bolt circle",
        "datum scheme on this machining print",
        "profile of a surface callout",
        "counterbore depth on the flange drawing",
        "thread callout and pitch on this view",
        "jarvis read the title block revision",
    ),
    "shop_query": (
        "what's the OEE today",
        "what's the OEE",
        "check OEE",
        "OEE today",
        "hey jarvis, what's OEE",
        "jarvis check OEE please",
        "production efficiency this shift",
        "how's efficiency on the cell",
        "downtime so far today",
        "why is the cell down",
        "scrap rate this week",
        "how much scrap on the last job",
        "production status on the floor",
        "are we ahead on the work order",
        "work order progress",
        "tool wear on the roughing tool",
        "how's the insert looking",
        "fixture status for the vise job",
        "is the fixture loaded",
        "machine utilization this morning",
        "cycle time on the last part",
        "what changed in the setup",
        "setup change on mill two",
        "hey jarvis, shop status",
        "how many parts done this shift",
        "spindle hours since the last tool change",
        "which machine is idle",
        "jarvis what's the downtime code",
    ),
    "rfq_quote": (
        "quote this drawing",
        "start the RFQ workflow",
        "start quote workflow",
        "build a quotation for this part",
        "hey jarvis, quote this print",
        "jarvis start a quote",
        "price the material for this job",
        "what's the material price on this RFQ",
        "operation sequence for the quote",
        "how should we sequence the ops",
        "lead time on this quotation",
        "what lead time do we promise",
        "customer requirements on the RFQ",
        "delivery schedule for the quote",
        "when can we deliver this batch",
        "cost the milling and the turning",
        "machine hour rate for this quote",
        "hey jarvis, build the quotation",
        "new quote for the flange",
        "quote the bracket from the print",
        "RFQ response with a price",
        "jarvis price this enquiry",
        "quantity break on the quote",
        "outside process cost for anodize",
        "include the setup in the quote",
        "revise the quote lead time",
        "customer asked for a formal quotation",
        "jarvis make a quotation for the housing",
    ),
    "email_read": (
        "search my inbox for Deepak",
        "check the inbox",
        "any unread mail",
        "hey jarvis, what's in the inbox",
        "jarvis read the latest email",
        "open the mail from the vendor",
        "unread messages this morning",
        "find the purchase order in the inbox",
        "did the test report arrive",
        "look for the material cert email",
        "inbox attachment from the customer",
        "hey jarvis, check mail please",
        "any mail about the late delivery",
        "read the shift note that came in",
        "who emailed about the rejected lot",
        "search inbox for the quote follow-up",
        "jarvis show unread from purchasing",
        "is there a mail with the drawing attached",
        "find the vendor's shipping notice",
        "check if quality sent the report",
        "inbox from the night shift",
        "any new mail on the open RFQ",
        "jarvis look through today's mail",
        "read the customer complaint email",
        "search mail for heat number",
        "did accounts send the remittance",
    ),
    "email_send": (
        "draft email to ops saying shop clear",
        "draft an email to ops saying hello",
        "send a mail to the customer",
        "hey jarvis, draft a reply",
        "jarvis write to purchasing",
        "schedule a maintenance window",
        "put a meeting on the calendar",
        "send a calendar invite to the buyer",
        "out of office for Friday",
        "draft the purchase order email",
        "reply to the vendor about the late tools",
        "forward the test report to quality",
        "hey jarvis, mail the shift turnover",
        "write the shift handover note",
        "invite planning to the capacity meeting",
        "draft a follow-up on the open quote",
        "email the customer the delivery date",
        "jarvis schedule tool maintenance",
        "send the quote follow-up",
        "book a meeting with the supplier",
        "tell ops the cell is back up",
        "draft a mail that the lot passed",
        "calendar hold for the setup change",
        "hey jarvis, reply to that PO",
        "write purchasing about the shortage",
        "send out of office until Monday",
    ),
    "casual_chat": (
        "hey what's up",
        "hi jarvis",
        "good morning",
        "how are you",
        "thanks",
        "thank you",
        "cheers",
        "tell me a joke",
        "say something funny about the shop",
        "what is an RFQ",
        "what does RFQ mean",
        "in our shop, what does RFQ stand for",
        "what does OEE mean on the floor",
        "define OEE for a machine cell",
        "what do the GD&T symbols mean",
        "what does GD&T stand for on a print",
        "what's the weather",
        "who are you",
        "what's your name",
        "nice work",
        "much obliged",
        "good night",
        "how's your day",
        "tell me about yourself",
        "jarvis you there",
        "just saying hello",
        "appreciate it",
        "what is a heat number, in general",
    ),
    "ui_command": (
        "hide the dock",
        "show the dock",
        "hide conversations",
        "show conversations",
        "minimize the note",
        "minimise that conversation",
        "open notes",
        "maximize the conversation",
        "maximise the note",
        "expand the drawing note",
        "switch notes",
        "close this note",
        "hey jarvis, hide the dock",
        "jarvis show the dock",
        "bring up the conversation list",
        "tuck the dock away",
        "open the other note",
        "collapse the open notes",
        "restore the minimized conversation",
        "show me the desk notes",
        "hide the open conversations",
        "jarvis minimize this window",
        "expand that note",
        "switch to the other conversation",
        "please hide the dock",
    ),
}


_lock = threading.Lock()
_ready = False
_failed = False
_matrix = None  # numpy ndarray, rows are L2-normalized utterance vectors
_row_route: list[str] = []


def cache_dir() -> Path:
    path = Path(settings.data_dir) / "models" / "fastembed"
    path.mkdir(parents=True, exist_ok=True)
    return path


def intent_for_route(route: str) -> tuple[str, str]:
    """Coarse desk intent and HUD agent for an encoder route name."""
    return ROUTE_INTENT[route]


def band_for_score(score: float) -> str:
    if score > HIGH_SCORE:
        return "high"
    if score >= ROUTE_MIN_SCORE:
        return "medium"
    return "fallback"


def _embed(model: object, lines: list[str]):
    import numpy as np

    rows = [np.asarray(vector, dtype=np.float32) for vector in model.embed(lines)]  # type: ignore[attr-defined]
    matrix = np.vstack(rows)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def warm() -> bool:
    """Load the encoder and the utterance index. Safe to call more than once."""
    global _ready, _failed, _matrix, _row_route
    with _lock:
        if _ready:
            return True
        if _failed:
            return False
        try:
            from fastembed import TextEmbedding

            model = TextEmbedding(model_name=ENCODER_MODEL, cache_dir=str(cache_dir()))
            labels: list[str] = []
            lines: list[str] = []
            for route, samples in _UTTERANCES.items():
                if route not in ROUTE_INTENT:
                    raise RuntimeError(f"route {route} has no intent map")
                for sample in samples:
                    labels.append(route)
                    lines.append(sample)
            _matrix = _embed(model, lines)
            _row_route = labels
            # Keep the model for query embeds. Stored on the function to avoid a second load.
            warm._model = model  # type: ignore[attr-defined]
            _ready = True
            log.info(
                "aurelio encoder ready model=%s utterances=%s",
                ENCODER_MODEL,
                len(lines),
            )
            return True
        except Exception as exc:
            _failed = True
            _ready = False
            log.warning("aurelio encoder unavailable: %s", exc)
            return False


def classify_fast(text: str) -> tuple[str, float] | None:
    """Best route and cosine score, or None when the encoder is not ready.

    Does not download a model. ``warm()`` does that. A score below 0.5 is
    still returned so the caller can log the fallback band.
    """
    line = (text or "").strip()
    if not line or not _ready or _matrix is None:
        return None
    try:
        import numpy as np

        model = warm._model  # type: ignore[attr-defined]
        query = _embed(model, [line])[0]
        scores = _matrix @ query
        best_by_route: dict[str, float] = {}
        for route, score in zip(_row_route, scores.tolist(), strict=True):
            value = float(score)
            if route not in best_by_route or value > best_by_route[route]:
                best_by_route[route] = value
        route = max(best_by_route, key=best_by_route.get)
        return route, best_by_route[route]
    except Exception as exc:
        log.warning("aurelio classify failed: %s", exc)
        return None
