"""Phase 2 chat tools: drawing identity, fact confirm, recall, shop-floor log."""

from __future__ import annotations

from typing import Any

from ..shop.state import (
    get_component_stock,
    get_machine_status,
    get_oee_trend,
    get_vendor_turnaround,
    log_downtime,
    log_oee,
    log_scrap,
    log_stock,
    log_vendor_turnaround,
)
from .confirm import confirm_drawing_fact
from .cards import recall_drawing_knowledge
from .identity import resolve_drawing_identity_tool


def _speak(result: dict[str, Any], fallback: str) -> dict[str, Any]:
    if not result.get("speak"):
        result = dict(result)
        result["speak"] = str(result.get("summary") or result.get("banner") or fallback)
    return result


def resolve_drawing_identity(
    session_id: str = "",
    drawing_sha256: str = "",
    fingerprint_text: str = "",
    customer_id: str = "",
    drawing_no: str = "",
    revision: str = "",
    **_: Any,
) -> dict[str, Any]:
    result = resolve_drawing_identity_tool(
        session_id=session_id,
        drawing_sha256=drawing_sha256,
        fingerprint_text=fingerprint_text,
        customer_id=customer_id,
        drawing_no=drawing_no,
        revision=revision,
    )
    return _speak(result, "Drawing identity resolved.")


def confirm_drawing_fact_tool(
    session_id: str = "",
    entity_type: str = "part_revision",
    entity_id: str = "",
    field: str = "",
    value: str = "",
    unit: str = "",
    source_ref: str = "",
    **_: Any,
) -> dict[str, Any]:
    result = confirm_drawing_fact(
        session_id=session_id,
        entity_type=entity_type,
        entity_id=entity_id,
        field=field,
        value=value,
        unit=unit,
        source_ref=source_ref,
    )
    return _speak(result, "Fact confirmation recorded.")


def recall_drawing_knowledge_tool(
    session_id: str = "",
    drawing_sha256: str = "",
    entity_id: str = "",
    **_: Any,
) -> dict[str, Any]:
    result = recall_drawing_knowledge(
        session_id=session_id,
        drawing_sha256=drawing_sha256,
        entity_id=entity_id,
    )
    return _speak(result, "Drawing recall ready.")


def _log_downtime(session_id: str = "", machine_id: str = "", minutes: float = 0, reason: str = "", machine_name: str = "", **_: Any) -> dict[str, Any]:
    del session_id
    result = log_downtime(machine_id, float(minutes or 0), reason, machine_name)
    return _speak(result, "Downtime logged.")


def _log_scrap(session_id: str = "", machine_id: str = "", qty: float = 0, unit: str = "pcs", cause: str = "", **_: Any) -> dict[str, Any]:
    del session_id
    result = log_scrap(machine_id, float(qty or 0), unit, cause)
    return _speak(result, "Scrap logged.")


def _log_oee(session_id: str = "", machine_id: str = "", oee_pct: float = 0, **_: Any) -> dict[str, Any]:
    del session_id
    result = log_oee(machine_id, float(oee_pct or 0))
    return _speak(result, "OEE logged.")


def _log_stock(
    session_id: str = "",
    component_id: str = "",
    on_hand: float = 0,
    allocated: float = 0,
    unit: str = "pcs",
    **_: Any,
) -> dict[str, Any]:
    del session_id
    result = log_stock(component_id, float(on_hand or 0), float(allocated or 0), unit)
    return _speak(result, "Stock logged.")


def _log_vendor(session_id: str = "", vendor: str = "", days: float = 0, last_delivery: str = "", **_: Any) -> dict[str, Any]:
    del session_id
    result = log_vendor_turnaround(vendor, float(days or 0), last_delivery)
    return _speak(result, "Vendor turnaround logged.")


def _machine_status(session_id: str = "", machine_id: str = "", **_: Any) -> dict[str, Any]:
    del session_id
    return _speak(get_machine_status(machine_id), "Machine status.")


def _vendor_turnaround(session_id: str = "", vendor: str = "", **_: Any) -> dict[str, Any]:
    del session_id
    return _speak(get_vendor_turnaround(vendor), "Vendor turnaround.")


def _component_stock(session_id: str = "", component_id: str = "", **_: Any) -> dict[str, Any]:
    del session_id
    return _speak(get_component_stock(component_id), "Component stock.")


def _oee_trend(session_id: str = "", days: int = 30, **_: Any) -> dict[str, Any]:
    del session_id
    return _speak(get_oee_trend(int(days or 30)), "OEE trend.")


HANDLERS = {
    "resolve_drawing_identity": resolve_drawing_identity,
    "confirm_drawing_fact": confirm_drawing_fact_tool,
    "recall_drawing_knowledge": recall_drawing_knowledge_tool,
    "log_downtime": _log_downtime,
    "log_scrap": _log_scrap,
    "log_oee": _log_oee,
    "log_stock": _log_stock,
    "log_vendor_turnaround": _log_vendor,
    "get_machine_status": _machine_status,
    "get_vendor_turnaround": _vendor_turnaround,
    "get_component_stock": _component_stock,
    "get_oee_trend": _oee_trend,
}

SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "resolve_drawing_identity",
            "description": "Resolve a drawing by sha256, text fingerprint, then customer + drawing number + revision. Revision changes include a diff and are never silent reuse.",
            "parameters": {
                "type": "object",
                "properties": {
                    "drawing_sha256": {"type": "string"},
                    "fingerprint_text": {"type": "string"},
                    "customer_id": {"type": "string"},
                    "drawing_no": {"type": "string"},
                    "revision": {"type": "string"},
                },
                "required": ["drawing_sha256"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_drawing_fact",
            "description": "Owner confirms a candidate drawing fact. High-value fields (material, scope, qty, tolerance, heat treat) require the value.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_type": {"type": "string"},
                    "entity_id": {"type": "string"},
                    "field": {"type": "string"},
                    "value": {"type": "string"},
                    "unit": {"type": "string"},
                    "source_ref": {"type": "string"},
                },
                "required": ["entity_id", "field", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall_drawing_knowledge",
            "description": "Deterministic recall from owner-confirmed drawing facts only. States unconfirmed gaps plainly.",
            "parameters": {
                "type": "object",
                "properties": {
                    "drawing_sha256": {"type": "string"},
                    "entity_id": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_downtime",
            "description": "Log machine downtime from the operator. Writes a shop event. Does not invent minutes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "machine_id": {"type": "string"},
                    "minutes": {"type": "number"},
                    "reason": {"type": "string"},
                    "machine_name": {"type": "string"},
                },
                "required": ["machine_id", "minutes"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_scrap",
            "description": "Log scrap quantity from the operator.",
            "parameters": {
                "type": "object",
                "properties": {
                    "machine_id": {"type": "string"},
                    "qty": {"type": "number"},
                    "unit": {"type": "string"},
                    "cause": {"type": "string"},
                },
                "required": ["machine_id", "qty"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_oee",
            "description": "Log an OEE percent the operator read. Does not invent the figure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "machine_id": {"type": "string"},
                    "oee_pct": {"type": "number"},
                },
                "required": ["machine_id", "oee_pct"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_stock",
            "description": "Log on-hand and allocated stock for a component.",
            "parameters": {
                "type": "object",
                "properties": {
                    "component_id": {"type": "string"},
                    "on_hand": {"type": "number"},
                    "allocated": {"type": "number"},
                    "unit": {"type": "string"},
                },
                "required": ["component_id", "on_hand"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_vendor_turnaround",
            "description": "Log a vendor turnaround in days and the last delivery date the operator stated.",
            "parameters": {
                "type": "object",
                "properties": {
                    "vendor": {"type": "string"},
                    "days": {"type": "number"},
                    "last_delivery": {"type": "string"},
                },
                "required": ["vendor", "days"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_machine_status",
            "description": "Read projected machine status from shop events. Asks when no row exists.",
            "parameters": {
                "type": "object",
                "properties": {"machine_id": {"type": "string"}},
                "required": ["machine_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_vendor_turnaround",
            "description": "Average vendor turnaround days from logged events.",
            "parameters": {
                "type": "object",
                "properties": {"vendor": {"type": "string"}},
                "required": ["vendor"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_component_stock",
            "description": "On-hand, allocated, and available stock from logged events.",
            "parameters": {
                "type": "object",
                "properties": {"component_id": {"type": "string"}},
                "required": ["component_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_oee_trend",
            "description": "OEE points logged inside the day window.",
            "parameters": {
                "type": "object",
                "properties": {"days": {"type": "integer"}},
            },
        },
    },
]
