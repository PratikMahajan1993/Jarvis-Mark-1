"""Hermes package — brain bridge, MCP tools, HITL."""

from .bridge import hermes_available, run_hermes_turn
from .hitl import request_human_approval

__all__ = ["hermes_available", "request_human_approval", "run_hermes_turn"]
