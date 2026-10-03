from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.features import Feature, register_feature
from app.features.sheets.draft import DraftError, get_draft, put_draft

router = APIRouter()


class ColumnBody(BaseModel):
    name: str = ""
    kind: str = "text"
    filled_by: str = ""
    formula: str = ""


class DraftBody(BaseModel):
    workbook_title: str = ""
    tab_title: str = ""
    columns: list[ColumnBody] = Field(default_factory=list)


@router.get("/draft")
def api_get_sheet_draft() -> dict[str, Any]:
    return get_draft()


@router.put("/draft")
def api_put_sheet_draft(body: DraftBody) -> dict[str, Any]:
    try:
        return put_draft(body.model_dump())
    except DraftError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


FEATURE = register_feature(
    Feature(
        id="sheets",
        topics=["sheets.changed"],
        router=router,
    )
)
