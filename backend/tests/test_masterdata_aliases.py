"""Alias CRUD resolves exact spellings and refuses similarity guesses."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings


def setup_module(_module=None):
    tmp = Path(tempfile.mkdtemp(prefix="jarvis-md-alias-"))
    settings.data_dir = tmp / "data"
    settings.exports_dir = tmp / "exports"
    settings.canvas_dir = settings.data_dir / "canvas"
    for path in (settings.data_dir, settings.exports_dir, settings.canvas_dir):
        path.mkdir(parents=True, exist_ok=True)
    from app import db
    from app.masterdata.seed_master_data import seed_master_data

    db.init_db()
    with db.connect() as conn:
        seed_master_data(conn)


def test_customer_alias_exact_only():
    from app import db
    from app.masterdata.aliases import (
        add_customer_alias,
        list_customer_aliases,
        remove_customer_alias,
        resolve_customer_alias,
    )

    with db.connect() as conn:
        customer = conn.execute("SELECT id FROM customers WHERE name = 'Deepak'").fetchone()
        cid = customer["id"]
        added = add_customer_alias(conn, cid, "Dee-Deepak", "manual")
        assert added["canonical_id"] == cid
        assert resolve_customer_alias(conn, "dee-deepak") == cid
        assert resolve_customer_alias(conn, "Deep") is None
        listed = list_customer_aliases(conn, cid)
        assert any(row["alias"] == "Dee-Deepak" for row in listed)
        remove_customer_alias(conn, "Dee-Deepak")
        assert resolve_customer_alias(conn, "Dee-Deepak") is None


def test_machine_and_vendor_aliases():
    from app import db
    from app.masterdata.aliases import add_machine_alias, add_vendor_alias, resolve_machine_alias, resolve_vendor_alias

    with db.connect() as conn:
        machine = conn.execute("SELECT id FROM machines WHERE machine_type = 'Demo engine lathe'").fetchone()
        supplier = conn.execute("SELECT id FROM suppliers WHERE name = 'RM stockist (seed)'").fetchone()
        add_machine_alias(conn, machine["id"], "the lathe", "manual")
        add_vendor_alias(conn, supplier["id"], "stockist", "manual")
        assert resolve_machine_alias(conn, "The Lathe") == machine["id"]
        assert resolve_vendor_alias(conn, "stockist") == supplier["id"]
        assert resolve_machine_alias(conn, "lathes") is None


def test_customer_name_is_known_follows_customer_window_not_alias_dates():
    """Alias rows stay undated. The joined customer window decides."""
    from app import db
    from app.masterdata.lookup import customer_name_is_known

    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO customers (id, name, currency, status, effective_from, effective_to)
            VALUES
              ('cust_open', 'Window Works', 'INR', 'active', '2020-01-01', NULL),
              ('cust_future', 'Window Later', 'INR', 'active', '2099-01-01', NULL),
              ('cust_ended', 'Window Ended', 'INR', 'active', '2020-01-01', '2020-06-01'),
              ('cust_old_status', 'Window Retired', 'INR', 'superseded', '2020-01-01', NULL)
            """
        )
        conn.execute(
            """
            INSERT INTO customer_aliases (customer_id, alias, source) VALUES
              ('cust_open', 'Window Nick', 'manual'),
              ('cust_future', 'Later Nick', 'manual'),
              ('cust_ended', 'Ended Nick', 'manual'),
              ('cust_old_status', 'Retired Nick', 'manual')
            """
        )
        assert customer_name_is_known(conn, "Window Works", as_of="2026-09-26") is True
        assert customer_name_is_known(conn, "window nick", as_of="2026-09-26") is True
        assert customer_name_is_known(conn, "Window Later", as_of="2026-09-26") is False
        assert customer_name_is_known(conn, "Later Nick", as_of="2026-09-26") is False
        assert customer_name_is_known(conn, "Later Nick", as_of="2099-01-01") is True
        assert customer_name_is_known(conn, "Window Ended", as_of="2020-05-31") is True
        assert customer_name_is_known(conn, "Ended Nick", as_of="2020-06-01") is False
        assert customer_name_is_known(conn, "Window Retired", as_of="2026-09-26") is False
        assert customer_name_is_known(conn, "Retired Nick", as_of="2026-09-26") is False
        assert customer_name_is_known(conn, "Window Works") is True
        assert customer_name_is_known(conn, "Window Later") is False
        assert customer_name_is_known(conn, "") is False
