---
name: shop-sheets
description: >-
  Build a new shop workbook (attendance, PPAP, or any other sheet) as a model,
  then create a new Google file when the owner says to. Triggers: "new workbook",
  "attendance sheet", "PPAP sheet", "create a spreadsheet", "new sheet for",
  "make a sheet". Jarvis sheet-model tools only. Never call the raw Sheets toolkit.
  Never add a tab to an existing shop workbook.
---

# Shop sheets playbook

## Purpose

Turn what the owner describes into one open workbook model, then create a **new Google spreadsheet file** when they say to create it. Attendance, PPAP, and any other new workbook use this same skill.

Load `shop-sheets` when the owner wants a new workbook. Do not rebuild the sheet in prose. Do not call the raw Sheets toolkit, `create_spreadsheet`, or any tool that adds a tab to an existing shop workbook.

## Who may create

Only the owner may create a file.

- Desk: when the owner says to create it, ask for the sheet password. It is alphanumeric. Pass it once as `password` on `jarvis_sheet_model_apply`. Do not repeat it, store it in the model, or include it in the outline. If the tool says to ask, ask again. If it says the password was refused, stop.
- Staff at the desk: pass `actor` `staff`. The tool refuses. Do not retry without it, and do not ask them for the password.
- Telegram: pass `telegram_user_id`. It must be in `TELEGRAM_OWNER_USER_IDS`, the same gate as rate attestation. Do not ask for the desk password. If the tool refuses, say only an owner may create a sheet and stop. Do not retry with another id.

Editing the model does not create a file. Apply is the only create.

## How to work

1. `jarvis_sheet_model_read` first.
2. Change the model only with `jarvis_sheet_model_edit`. One edit at a time.
3. After every edit, read the `outline` back to the owner, then ask the `speak` line.
4. Ask only for the next gap: title, then one tab, then one block on that tab.
5. Store text, headings, and sample rows only when the owner stated them. Do not invent numbers.
6. Formulas name columns (`Hours * Rate`). Do not write A1 references.
7. Call `jarvis_sheet_model_apply` only when the owner says to create it, and only when `missing` is null. From the desk, ask for the alphanumeric password first and pass it on that call.

"Add Rate after Quantity" is an insert. If the tool says Quantity is not on the table, the model was left unchanged. Read the outline and ask. Do not invent another place for the column.

## Model

One open model. `new_file` is always true.

- `title`
- `tabs[]`, each with `blocks[]` in order
- Block kinds: `title` (text the owner stated), `table` (columns), `section` (a heading plus its own columns), `chart` (bound to a table or section on the same tab by that block's id)
- Column fields: `name`, `kind` (`text`, `number`, `date`, `formula`), `filled_by` (`owner`, `staff`, `jarvis`, or empty), `formula` (column names), `dropdown` (list of values)

## Edits

`jarvis_sheet_model_edit` takes `action` and `payload` (a JSON object).

| Action | Payload |
| --- | --- |
| `set_title` | `{"title":"Attendance"}` |
| `add_tab` | `{"title":"October"}` |
| `rename_tab` | `{"tab":"October","title":"November"}` |
| `remove_tab` | `{"tab":"October"}` |
| `add_block` | `{"tab":"October","kind":"table","columns":[{"name":"Quantity","kind":"number"}]}` |
| `add_block` section | `{"tab":"PPAP","kind":"section","heading":"Dimensional results","columns":[{"name":"Characteristic","kind":"text"}]}` |
| `add_block` title | `{"tab":"October","kind":"title","text":"October attendance"}` |
| `add_block` chart | `{"tab":"October","kind":"chart","source":"b1"}` |
| `insert_column` | `{"anchor":"Quantity","place":"after","column":{"name":"Rate","kind":"number","filled_by":"staff"}}` |
| `rename_column` | `{"name":"Qty","new_name":"Quantity"}` |
| `remove_column` | `{"name":"Rate"}` |
| `set_kind` | `{"name":"Hours","kind":"number"}` |
| `set_filler` | `{"name":"Hours","filled_by":"staff"}` |
| `set_formula` | `{"name":"Pay","formula":"Hours * Rate"}` |
| `set_dropdown` | `{"name":"Status","values":["Present","Absent"]}` |
| `set_text` | `{"block":0,"text":"October attendance"}` |
| `set_rows` | `{"rows":[{"Name":"Ada","Hours":8}]}` |

`place` is `before` or `after`. Omit `tab` and `block` when the model has only one place that fits. `source` is the block id in the outline, such as `b1`, not a position that shifts when a block is inserted.

## Templates

A saved attendance or PPAP model is a template. Apply stores the structure (no sample numbers) under a template id.

- `jarvis_sheet_template_list` — names already saved.
- `jarvis_sheet_template_clone` — `template_id` and a **new** title. The copy has no sample numbers. If the open model already has work, the tool refuses until `discard` is true. Then keep editing, and apply only when the owner says to create it.

## Create

`jarvis_sheet_model_apply` creates a new spreadsheet file and writes it in one batch: headers, labels, formulas down the sheet, dropdowns, freeze, charts, and only the numbers the owner stored. A chart does not require sample rows. It does not add a tab to an existing workbook. If the model is incomplete, or the batch would be invalid, nothing is written. Saying create again, with no edits since the last success, returns the same file url. On success, tell the owner the file url and read the outline.

## Never

- Invent sample numbers, dropdown values, or a formula the owner did not ask for
- Hand-write A1 formulas into the model
- Call the raw Sheets toolkit or add a tab to a shop workbook that already exists
- Apply because the model looks finished. Wait until the owner says to create it
- Let staff create a sheet
