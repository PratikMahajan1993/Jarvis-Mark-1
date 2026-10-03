from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.core.features import Feature, ToolSpec, register_feature
from app.features.sheets.draft import ModelError, get_model, outline, put_model
from app.features.sheets.talk import tool_apply, tool_clone, tool_edit, tool_list, tool_read

router = APIRouter()


@router.get("/draft")
def api_get_sheet_model(session_id: str = "default") -> dict[str, Any]:
    state = get_model(session_id)
    if state.get("error"):
        raise HTTPException(status_code=409, detail=state["error"])
    return {
        "model": state["model"],
        "outline": outline(state["model"]),
        "updated_at": state.get("updated_at"),
    }


@router.put("/draft")
async def api_put_sheet_model(request: Request, session_id: str = "default") -> dict[str, Any]:
    try:
        raw = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid JSON") from exc
    if isinstance(raw, dict) and "workbook_title" in raw and "tabs" not in raw:
        raise HTTPException(status_code=400, detail="header-only sheet drafts are retired")
    try:
        saved = put_model(raw, session_id)
    except ModelError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "model": saved["model"],
        "outline": outline(saved["model"]),
        "updated_at": saved["updated_at"],
    }


FEATURE = register_feature(
    Feature(
        id="sheets",
        topics=["sheets.changed"],
        router=router,
        tools=[
            ToolSpec(
                name="sheet_model_read",
                description="Read the open workbook model and the next gap. Does not write Google.",
                handler=tool_read,
            ),
            ToolSpec(
                name="sheet_model_edit",
                description="Edit the open workbook model (title, tabs, blocks, columns). Does not write Google.",
                handler=tool_edit,
            ),
            ToolSpec(
                name="sheet_template_list",
                description="List structure-only sheet templates saved from earlier creates.",
                handler=tool_list,
            ),
            ToolSpec(
                name="sheet_template_clone",
                description="Copy a saved template into the open model under a new title, without sample values.",
                handler=tool_clone,
            ),
            ToolSpec(
                name="sheet_model_apply",
                description="Create a new spreadsheet file from the model in one batch. Owner only. Does not add a tab to an existing workbook.",
                handler=tool_apply,
                external=True,
            ),
        ],
    )
)
