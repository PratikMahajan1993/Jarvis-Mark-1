from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.core.features import Feature, ToolSpec, register_feature
from app.sheet_listen import ListenError, monitor_status, refresh_all, refresh_listened_sheet

router = APIRouter()


@router.get("/status")
def api_sheet_listen_status() -> dict[str, Any]:
    return monitor_status()


@router.post("/refresh")
def api_sheet_listen_refresh() -> dict[str, Any]:
    return refresh_all()


@router.post("/refresh/{sheet_id}")
def api_sheet_listen_refresh_one(sheet_id: str) -> dict[str, Any]:
    try:
        return refresh_listened_sheet(sheet_id)
    except ListenError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _tool_refresh_listened_sheets(**_: Any) -> dict[str, Any]:
    """Explicit ask: re-read named tabs into the local copy (read-only)."""
    result = refresh_all()
    state = result.get("state") or monitor_status()
    sheets = state.get("sheets") or []
    stale = [s.get("display_name") for s in sheets if s.get("stale")]
    machines: list[str] = []
    for sheet in sheets:
        for name in sheet.get("machines_today") or []:
            if name not in machines:
                machines.append(str(name))
    if stale:
        speak = "Refreshed listened sheets. Stale: " + ", ".join(str(s) for s in stale if s) + "."
    elif machines:
        speak = "Refreshed. Today's machines: " + ", ".join(machines[:8]) + "."
    elif sheets:
        speak = "Refreshed. No rows today on the listened shop logs."
    else:
        speak = "No listened shop logs are configured yet."
    conflicts = state.get("conflicts") or []
    if conflicts:
        speak += f" {len(conflicts)} conflicting figure(s) — both values kept."
    return {"ok": True, "speak": speak, "data": state}


FEATURE = register_feature(
    Feature(
        id="sheet-listen",
        topics=["sheet-listen.changed"],
        router=router,
        tools=[
            ToolSpec(
                name="refresh_listened_sheets",
                description="Re-read configured shop production tabs into the local copy. Read-only; never writes Google Sheets.",
                handler=_tool_refresh_listened_sheets,
            )
        ],
    )
)
