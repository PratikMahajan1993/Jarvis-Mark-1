---
name: shop-masterdata
description: >-
  Create shop master-data records from Telegram or chat. Triggers: "new customer",
  "add a supplier", "new product", "create master data", "add customer Priya",
  "register product", "masterdata", "new supplier". Jarvis masterdata MCP tools only;
  never invent GSTIN, prices, or a customer that is not in the table.
---

# Shop master-data playbook

## Purpose

Create a **customer**, **supplier**, or **product** through Jarvis tools. Ask only for missing required fields. Do not invent GSTIN, payment terms, prices, or a customer name that is not already stored when creating a product.

## Opening choice

Offer exactly these three numbered options, then wait:

1. New customer
2. New supplier
3. New product

If the owner already named the choice in the message, skip the menu and go to that path.

## New customer

Required: **name**, then one yes/no — **NDA? Drawings must not leave the shop.**

- Yes → call `jarvis_masterdata_create_customer` with `nda=yes` (cloud vision stays denied).
- No → call with `nda=no` (nda and cloud vision both denied).

Do **not** ask for GSTIN or payment terms on create. Scope stays ask. If the tool returns a duplicate, tell the owner the existing row and stop — do not invent a new name.

## New supplier

Required: **name** only. Call `jarvis_masterdata_create_supplier`. On duplicate, report the existing supplier and stop.

## New product

Required before save:

1. Product name
2. Product number
3. Customer (must already exist — list or confirm from master data; never invent)
4. Unit of measure
5. Monitor stock? yes/no (flag only — no quantity)

Optional: material id (grade already in materials). Call `jarvis_masterdata_create_product`. Missing fields → ask; do not guess. Duplicate product number → report the existing row.

## Rate attest (owner only)

`jarvis_mhr_attest_rate` is owner-gated. Pass the Telegram user id. If refused, tell them only an owner may attest — do not retry with another id.

## Toolbox

| Tool | Use |
| --- | --- |
| `jarvis_masterdata_create_customer` | name + nda yes/no |
| `jarvis_masterdata_create_supplier` | name |
| `jarvis_masterdata_create_product` | name, product_number, customer, uom, monitor_stock |
| `jarvis_mhr_attest_rate` | owner Telegram ids only |

## Never

- Invent GSTIN, prices, MHR, or a customer not in the table
- Create a product without a real customer id or exact customer name match
- Hard-delete anything — replace/supersede is a separate desk flow
