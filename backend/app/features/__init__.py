"""Explicit backend feature registry (P2). Import side-effects register each Feature."""

from __future__ import annotations

from app.core.features import Feature
from app.features_weather import FEATURE as weather

FEATURES: list[Feature] = [weather]
