"""Master data: parties, materials, suppliers, machines, and rates.

Exports stay lazy so importing this package does not pull the quote stack
(the markdown importers depend on ``quote._parse_numeric``).
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "customer_name_is_known",
    "import_client_names_from_markdown",
    "import_mhr_demo_from_markdown",
    "mhr_demo_floor_rupees_as_of",
    "min_mhr_minor_as_of",
    "parse_client_names_markdown",
    "parse_mhr_demo_table",
    "sync_client_names_if_enabled",
    "sync_mhr_demo_if_enabled",
]

_EXPORTS = {
    "customer_name_is_known": (".lookup", "customer_name_is_known"),
    "sync_client_names_if_enabled": (".lookup", "sync_client_names_if_enabled"),
    "import_client_names_from_markdown": (".import_aliases", "import_client_names_from_markdown"),
    "parse_client_names_markdown": (".import_aliases", "parse_client_names_markdown"),
    "import_mhr_demo_from_markdown": (".import_mhr_demo", "import_mhr_demo_from_markdown"),
    "parse_mhr_demo_table": (".import_mhr_demo", "parse_mhr_demo_table"),
    "mhr_demo_floor_rupees_as_of": (".mhr_lookup", "mhr_demo_floor_rupees_as_of"),
    "min_mhr_minor_as_of": (".mhr_lookup", "min_mhr_minor_as_of"),
    "sync_mhr_demo_if_enabled": (".mhr_lookup", "sync_mhr_demo_if_enabled"),
}


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = target
    from importlib import import_module

    module = import_module(module_name, __name__)
    value = getattr(module, attr)
    globals()[name] = value
    return value
