"""Explicit backend feature registry (P2). Import side-effects register each Feature."""

from __future__ import annotations

from app.core.features import Feature
from app.features.sheets import FEATURE as sheets
from app.features.sheet_listen import FEATURE as sheet_listen
from app.features_weather import FEATURE as weather

FEATURES: list[Feature] = [weather, sheet_listen, sheets]
