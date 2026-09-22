"""Master data: parties, materials, suppliers (S1)."""

from .import_aliases import import_client_names_from_markdown, parse_client_names_markdown
from .lookup import customer_name_is_known, sync_client_names_if_enabled

__all__ = [
    "customer_name_is_known",
    "import_client_names_from_markdown",
    "parse_client_names_markdown",
    "sync_client_names_if_enabled",
]
