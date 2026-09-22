"""Master data: parties, materials, suppliers (S1); machines / MHR (S2)."""

from .import_aliases import import_client_names_from_markdown, parse_client_names_markdown
from .import_mhr_demo import import_mhr_demo_from_markdown, parse_mhr_demo_table
from .lookup import customer_name_is_known, sync_client_names_if_enabled
from .mhr_lookup import mhr_demo_floor_rupees_as_of, min_mhr_minor_as_of, sync_mhr_demo_if_enabled

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
