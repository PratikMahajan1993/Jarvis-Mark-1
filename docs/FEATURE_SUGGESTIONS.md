# Jarvis Mark-1 — Feature Suggestions (Creative Expansion)

**Generated:** 2026-09-26  
**Scope:** 15+ new capabilities Jarvis could provide to the precision machining office.  
**Constraint:** Must respect existing invariants (HITL gates, tool-owned data, local-first, no hallucinated numbers).

---

## Feature Philosophy

Every feature below follows the **Jarvis DNA**:
- **Tools own the numbers** — LLM never invents prices, rates, dimensions, or calendar facts
- **HITL before external effects** — Send, write, promote, delete = Authorize first
- **Local-first, controllable retention** — No cloud memory, no surprise data egress
- **Progressive disclosure** — Engineering desk reveals depth on demand, never sprawl
- **Observable & auditable** — Every action logged, every decision traceable

---

## 1. **Voice-Native Shift Handover** 🎙️

**What:** End-of-shift voice dictation → structured handover note + next-shift briefing.

**Flow:**
```
Operator: "Jarvis, shift handover. CNC-3 bearing running hot since 14:00, 
          VMC-2 program 8472 needs tool 12 replaced. 
          Order 4421 delayed — supplier says Thursday."
          
Jarvis:   [Records structured event log]
          • Machine: CNC-3 | Issue: Bearing temperature | Since: 14:00 | Action: Logged downtime
          • Machine: VMC-2 | Program: 8472 | Tool: #12 | Action: Logged tool change needed
          • Order: 4421 | Status: Delayed | New ETA: Thursday | Action: Updated vendor turnaround
          
          "Handover captured. Next shift briefing will include these three items. 
           Want me to flag CNC-3 for maintenance?"
```

**Why it fits:** Uses existing `log_downtime`, `log_scrap`, `log_oee`, `log_vendor_turnaround` tools. Voice-first, keyboard-equal. HITL only if operator asks to *send* the handover to someone.

---

## 2. **Drawing Diff Lens** 🔍

**What:** Side-by-side visual diff of two drawing revisions with semantic change detection.

**Capabilities:**
- Upload Rev A + Rev B → PDF.js dual viewer with synchronized pan/zoom
- Auto-detect: Added/removed dimensions, tolerance changes, view additions, BOM deltas
- Output: `DrawingIdentityResult.changed_fields` + visual heatmap overlay
- One-click "Update quote for Rev B" → preserves operations, flags affected ops

**UI:**
```
Engineering Desk → Drawing Stage → [Compare] button
                    │
                    ├─ Rev A (left) ◀──sync pan──▶ Rev B (right)
                    │
                    └─ Change Panel: 
                       🔴 OD: φ45.0 → φ45.5  (tolerance ±0.02 → ±0.01)
                       🟡 New Section D-D added
                       🟢 Note 7 removed
```

**Why it fits:** Extends `resolve_drawing_identity()` revision_change cascade. Uses existing `knowledge/identity.py` diff logic. Zero new external calls.

---

## 3. **Supplier Negotiation Coach** 🤝

**What:** Before sending RFQ or PO, Jarvis briefs you with supplier intelligence.

**Flow:**
```
User: "Draft PO for EN8 bar from MetalCorp"
      
Jarvis: [Pulls supplier_rm_quotes, vendor_turnaround, shop_events]
        "MetalCorp profile:
         • Last 3 EN8 quotes: ₹185, ₹192, ₹188/kg (avg ₹188)
         • Avg delivery: 11 days (range 8-14)
         • Last delivery: 2026-09-10, 9 days, 2,000kg
         • Quality issues: 2 scrap logs last quarter (surface finish)
         
         Suggested PO: ₹185/kg, 10-day lead, penalty clause for >12 days.
         Want me to draft the email?"
```

**Why it fits:** Read-only tools (`get_vendor_turnaround`, `supplier_rm_quote_as_of`, `shop_events`). No hallucination — all numbers from logs. HITL at email send.

---

## 4. **Capacity-Aware Promise Date** 📅

**What:** When quoting delivery, show real capacity — not a guess.

**Flow:**
```
User: "What delivery can I promise for this quote?"
      
Jarvis: [Queries: machine_hour_rates + routing_operations + shop_events]
        "Current load (next 10 days):
         • CNC-1: 78% booked (28/36 hrs) — next free: 2026-09-29
         • VMC-3: 45% booked — next free: 2026-09-26
         • Heat treat (outsource): Vendor 3-day queue
         
         If we use CNC-1 + VMC-3 parallel: earliest ship 2026-10-02
         If CNC-1 only: 2026-10-05
         Owner types delivery: [________] days  ← never computed, only suggested"
```

**Why it fits:** Uses existing `machine_hour_rates`, `routing_operations` (migration 0013), `shop_events`. **Never computes delivery** — only shows capacity. Owner types the number (per SYSTEM_TRUTH §4.7).

---

## 5. **Cost-to-Serve Dashboard** 💰

**What:** Per-customer, per-part profitability — actuals vs quote.

**Data Sources (all local):**
- `quote_revisions` + `external_effects` (sent quotes)
- `production_logs` (actual cycle times, scrap, downtime)
- `supplier_rm_quotes` (actual material cost)
- `outsource_quotes` (actual vendor cost)
- `machine_hour_rates` (actual MHR used)

**Output:**
```
Customer: Precision Gears Pvt Ltd
┌──────────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
│ Part         │ Quoted   │ Actual   │ Variance │ Margin   │ Trend    │
├──────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ PG-200 Shaft │ ₹12,450  │ ₹13,890  │ +11.6%   │ 18.2%    │ 📉       │
│ PG-400 Gear  │ ₹28,900  │ ₹27,100  │ -6.2%    │ 24.5%    │ 📈       │
└──────────────┴──────────┴──────────┴──────────┴──────────┴──────────┘
⚠ PG-200: Cycle time 22min vs quoted 18min (CNC-1). Scrap 3% vs 1% budget.
```

**Why it fits:** Extends `quote_variance.rank_margin_erosion()` (migration 0012). All numbers from logs. Read-only — no HITL needed.

---

## 6. **Tooling Lifecycle Manager** 🔧

**What:** Track every insert, holder, collet — from purchase to scrap.

**Schema Extension:**
```sql
-- backend/migrations/0029_tooling.sql
CREATE TABLE tooling_instances (
    id TEXT PRIMARY KEY,
    tool_id TEXT REFERENCES tools(id),
    serial_number TEXT,
    purchased_from TEXT,
    purchase_date TEXT,
    purchase_price_minor INTEGER,
    machine_id TEXT REFERENCES machines(id),
    status TEXT CHECK (status IN ('new','in_use','sharpening','retired')),
    total_cut_time_min REAL DEFAULT 0,
    total_parts_made INTEGER DEFAULT 0,
    last_inspection TEXT,
    retired_at TEXT,
    retired_reason TEXT
);
```

**Features:**
- Voice: "Tool T-404 on CNC-3 just hit 450 minutes" → logs `toolwatch` + updates `total_cut_time_min`
- Alert: "T-404 at 90% of recommended life (500 min). Order replacement?"
- Cost allocation: Amortize tool cost across parts made → feeds `quote_verify` tooling line
- Sharpening log: Track vendor, cost, turnaround → vendor turnaround data

**Why it fits:** Extends `toolwatch` (migration 0016). Voice-first logging. Feeds quote tooling cost with real data.

---

## 7. **Automated First-Article Inspection (FAI) Helper** 📋

**What:** Guide operator through FAI, capture results, auto-populate drawing card.

**Flow:**
```
User: "Start FAI for drawing D-4421 Rev C"
      
Jarvis: [Loads drawing card confirmed fields]
        "FAI for D-4421 Rev C — 12 critical dimensions.
         I'll read each, you speak the measured value.
         
         1. OD φ45.0 ±0.02 — [Operator: 44.99]
         ✅ Pass. Next: 2. ID φ30.0 ±0.015 — [Operator: 30.005]
         ✅ Pass. ...
         
         5. Surface finish Ra 0.8 — [Operator: 0.65]
         ✅ Pass.
         
         FAI complete. All 12 pass. 
         Want me to confirm these as measured facts on the drawing card?"
```

**Output:** `entity_facts` with `source_kind='measured'`, `confirmed_by='operator_name'`, `confirmed_at=now`. Auto-updates `part_revision` card.

**Why it fits:** Uses `confirm_drawing_fact` tool. Voice-driven. Builds knowledge cards with measured (not vision) data. High-value fields get value-level confirm per existing rules.

---

## 8. **Energy & Carbon Tracker** 🌱

**What:** Per-part, per-machine energy consumption + CO₂ estimate.

**Data Model:**
```sql
-- backend/migrations/0030_energy.sql
CREATE TABLE machine_energy_profiles (
    machine_id TEXT PRIMARY KEY REFERENCES machines(id),
    spindle_kw REAL,           -- from machines table
    coolant_kw REAL,
    chip_conveyor_kw REAL,
    auxiliary_kw REAL,
    carbon_intensity_kg_per_kwh REAL DEFAULT 0.82  -- India grid average
);

CREATE TABLE part_energy_log (
    id TEXT PRIMARY KEY,
    part_revision_id TEXT,
    machine_id TEXT,
    actual_cycle_min REAL,
    energy_kwh REAL,
    carbon_kg REAL,
    logged_at TEXT
);
```

**Features:**
- Auto-calc from `log_oee` + `routing_operations` actual cycle time
- Quote integration: "This part: 2.3 kWh, 1.9 kg CO₂"
- Customer report: "Your order PG-200: 450 kg CO₂ total"
- Benchmarking: "CNC-1: 0.18 kWh/part vs VMC-3: 0.31 kWh/part for similar ops"

**Why it fits:** Local-only. Uses existing machine specs + logged cycle times. Optional feature (off by default). No external API.

---

## 9. **Multi-Language Shop Floor** 🌐

**What:** HUD + Voice in Hindi/Marathi/Tamil for shop operators.

**Implementation:**
- `settings.hud_language` + `settings.voice_language` (ISO 639-1)
- Voicebox profile per language (Kokoro supports hi, mr, ta)
- Tool schemas translated via JSON schema `title`/`description` localization
- HITL modals: "अधिकृत करें / अस्वीकार करें"
- Briefing: "शुभ प्रभात, सर। ३ अपठित मेल। शॉप OEE ८७ प्रतिशत।"

**Why it fits:** Voicebox supports Indic languages via Kokoro. No cloud translation — local TTS. HUD text from `orchestrator` strings can be i18n'd. Inclusive design for Indian shop floor.

---

## 10. **Predictive Maintenance Nudges** 🔮

**What:** From downtime/scrap patterns, suggest maintenance before failure.

**Logic (runs nightly via `ingest_queue`):**
```
For each machine:
  1. Analyze downtime_reason frequency (last 30 days)
  2. If 'bearing' > 2x baseline → "CNC-3: Bearing downtime 3x normal. Schedule inspection?"
  3. If scrap trend ↑ + vibration logs (if added) → "VMC-2: Scrap +15% last week. Check spindle runout?"
  4. If tool life variance ↑ → "Tool holder T-404 showing inconsistent wear. Check collet?"
  
  → Creates suggested_task (kind: 'maintenance', blast_radius: 2)
  → Appears in Monitor workspace + morning briefing
```

**Why it fits:** Uses `shop_events` + `downtime_reasons` (migration 0011). No ML model — rule-based on thresholds. Creates `suggested_tasks` (existing system). Human validates.

---

## 11. **Customer Portal Link Generator** 🔗

**What:** One-click secure link for customer to view quote status, drawings, delivery.

**Flow:**
```
User: "Send customer portal link for quote Q-4421"
      
Jarvis: [Creates signed JWT with: quote_revision_id, customer_id, expiry=7d]
        "Portal link: https://jarvis.shop/portal/Q-4421?token=eyJ...
         Customer sees:
         • Quote PDF (watermarked)
         • Delivery status: 'In machining — CNC-1, 40% complete'
         • Drawing: D-4421 Rev C (view-only, no download)
         • Messages: Thread with your replies
         Expires: 2026-10-03. Revoke anytime."
```

**Tech:** FastAPI `/portal/{quote_id}` route + JWT verification. Read-only. No auth system — token *is* auth. HITL at link creation.

**Why it fits:** Extends `quote_send` + `external_effects`. Uses existing artifact storage. Zero new infrastructure.

---

## 12. **Regulatory Compliance Pack** 📜

**What:** Auto-generate PPAP, CoC, RoHS, REACH docs from quote + material + process data.

**Templates (Jinja2 in `backend/app/compliance/`):**
- **PPAP Level 3**: Design records, engineering change docs, DFMEA, PFMEA, control plan, MSA, dimensional results, material certs, sample parts
- **Certificate of Conformance**: Part, rev, spec, heat lot, material cert reference, inspection results
- **RoHS/REACH**: Material grade → substance declaration (from `materials` table)

**Flow:**
```
User: "Generate PPAP for PG-200 Shaft, customer wants Level 3"
      
Jarvis: [Checks: drawing card confirmed, material cert logged, FAI done, MSA logged]
        "Missing for PPAP Level 3:
         ❌ PFMEA not on file
         ❌ Gage R&R (MSA) not done
         ✅ Drawing card: 12/12 confirmed
         ✅ Material: EN8, heat lot H-2244, cert uploaded
         ✅ FAI: All pass (2026-09-20)
         
         Want me to create PFMEA template? Schedule MSA?"
```

**Why it fits:** Read-only assembly of existing data. HITL at document generation (PDF artifact). Local-only. High value for automotive/aerospace customers.

---

## 13. **Apprentice Mode** 🎓

**What:** Guided learning for junior operators — "Jarvis, teach me to set up CNC-1 for this part."

**Flow:**
```
Apprentice: "How do I set up CNC-1 for PG-200?"
           
Jarvis: [Pulls: routing_operations, machine_capabilities, tooling_instances]
        "Setup for PG-200 on CNC-1 (FANUC 0i-TF):
         
         1. WORK OFFSET: G54 = X0 Y0 Z0 (face of part)
         2. TOOLS:
            T01: CNMG 120408 (OD rough) — Tool offset 1
            T02: TNMG 160404 (ID finish) — Tool offset 2
            T03: Grooving insert 3mm — Tool offset 3
         3. PROGRAM: O8472 (in exports/nc/O8472.nc)
         4. STOCK: φ50 × 120mm EN8 bar
         5. WORKHOLDING: 3-jaw chuck, 45mm grip
         
         Want me to walk you through each step? Say 'next' or 'repeat'."
```

**Why it fits:** Uses existing `routing_operations`, `machines`, `tooling_instances`. Voice-guided. No external calls. Safe — only reads, never writes.

---

## 14. **Digital Twin Light** 🪞

**What:** 3D viewport of machine + part + toolpath (WebGL, no cloud).

**Tech:** `three.js` + `gcode-parser` in `frontend/src/digital-twin/`. Loads:
- Machine envelope from `machines` (travel_x/y/z, chuck_mm)
- Stock from quote `material` + `vision_summary`
- Toolpath from `exports/nc/` G-code (parsed client-side)
- Tool geometry from `tooling_instances`

**Features:**
- Collision check: "Rapid at N120 passes 2mm from chuck jaw"
- Cycle time visual: Simulated motion with `machines.rapid_x/y/z`, `accel_g`
- Work offset verify: "G54 Z-zero at face — matches drawing?"

**Why it fits:** Extends `program_verify` (G-code checks) to visual. WebGL in existing substrate worker. Local-only. Optional (off by default).

---

## 15. **Voice-Only "Jarvis Lite" for Mobile** 📱

**What:** Telegram/WhatsApp bot for away-from-desk commands.

**Capabilities (read-only + HITL queue):**
- "Jarvis, what's CNC-3 status?" → `get_machine_status`
- "Any urgent mail?" → `search_emails unread_only=true limit=5`
- "Approve quote send Q-4421" → `POST /api/confirm` (with idempotency key)
- "Remind me to call MetalCorp at 3pm" → `create_calendar_event` (HITL)
- "Brief me" → `build_briefing` (speak via Voicebox → voice note reply)

**Architecture:**
```
Telegram Bot API → Webhook → FastAPI /api/webhook/telegram
                    │
                    ├─ Verify user (pre-shared secret + chat_id allowlist)
                    ├─ Map command → internal tool
                    ├─ If HITL needed → queue pending_action + reply "Authorize in HUD"
                    └─ Reply via bot.sendMessage / sendVoice (Voicebox WAV)
```

**Why it fits:** Reuses all existing tools. HITL still in HUD (security). Voicebox WAV → Telegram voice note. No new brain — just thin adapter.

---

## 16. **Contractual SLA Monitor** ⚖️

**What:** Track customer contract SLAs (delivery, quality, response time) against actuals.

**Schema:**
```sql
-- backend/migrations/0031_sla.sql
CREATE TABLE customer_slas (
    id TEXT PRIMARY KEY,
    customer_id TEXT REFERENCES customers(id),
    metric TEXT CHECK (metric IN ('delivery_ontime_pct','quality_ppm','response_hours')),
    target REAL NOT NULL,
    window_days INTEGER DEFAULT 90,
    effective_from TEXT,
    effective_to TEXT
);
```

**Dashboard:**
```
Customer: Bharat Forge
┌─────────────────────┬──────────┬──────────┬──────────┐
│ SLA                 │ Target   │ Actual   │ Status   │
├─────────────────────┼──────────┼──────────┼──────────┤
│ Delivery on-time    │ ≥95%     │ 91.2%    │ 🔴 BREACH│
│ Quality (PPM)       | ≤500     │ 1,240    │ 🔴 BREACH│
│ Response < 4hrs     │ 100%     │ 98.5%    │ 🟡 RISK  │
└─────────────────────┴──────────┴──────────┴──────────┘
⚠ Delivery breach driven by: VMC-3 downtime (Sep 12-15), MetalCorp late RM (Sep 20)
```

**Why it fits:** Uses `shop_events`, `vendor_turnaround`, `external_effects` (sent quotes with delivery). Local computation. Alerts via `suggested_tasks`.

---

## 17. **Knowledge Graph Explorer** 🕸️

**What:** Visual graph of customers → parts → drawings → quotes → machines → suppliers.

**Tech:** `cytoscape.js` in `/canvas` route (existing). Nodes = entities, Edges = relationships.

**Interactions:**
- Click customer → see all parts, open quotes, preferred machines, approved suppliers
- Click part → see drawing revisions, quote history, routing, actuals
- Click machine → see parts run, OEE trend, tooling, operators
- "Shortest path: Customer A → Part X → Machine Y → Supplier Z"

**Why it fits:** Uses existing `entity_cards` + `entity_facts` + `masterdata` foreign keys. Read-only visualization. Canvas route already exists (Phase 8).

---

## 18. **Automated Vendor Scorecard** 📊

**What:** Monthly PDF per vendor — on-time, quality, price trend, responsiveness.

**Auto-generated (monthly cron via `ingest_queue`):**
```
VENDOR SCORECARD — MetalCorp Supplies — Sep 2026
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
On-Time Delivery:     87% (target 95%) 🔴
  • 13/15 orders on time
  • Late: PO-4421 (3 days), PO-4455 (1 day)
  
Quality (Incoming):   99.2% pass 🟢
  • 2,450 kg received, 18 kg rejected (surface)
  
Price Trend (EN8):    +4.2% vs 6mo avg 🟡
  • Current: ₹188/kg
  • 6mo avg: ₹180/kg
  
Responsiveness:       4.2 hrs avg 🟢
  • 23 RFQs, all replied < 24hrs
  
Communication:        Excellent 🟢
  • Proactive delay notices
  • Clear certs with shipment
  
RECOMMENDATION: Discuss delivery root cause. 
                Consider dual-source for critical grades.
```

**Why it fits:** Aggregates `supplier_rm_quotes`, `shop_events` (vendor kind), `external_effects` (PO emails). Local. HITL at "Send scorecard to vendor".

---

## 19. **Emergency "Red Phone" Mode** 🚨

**What:** One-tap mode for critical issues — auto-logs, alerts, creates war room.

**Activation:** Voice: "Jarvis, red phone. CNC-1 spindle crash." OR Hardware button (GPIO on desk Pi).

**Actions:**
1. Instant `log_downtime` with `reason="EMERGENCY: spindle crash"`, `source="red_phone"`
2. Creates `suggested_task` kind=`emergency` blast_radius=5 → appears on ALL workspaces
3. SMS/Telegram to owner + maintenance lead (if configured)
4. Opens `EngineeringDesk` on CNC-1 with live `shop_floor_snapshot`
5. Voice: "What happened? I'm logging everything."

**Why it fits:** Uses existing `log_downtime`, `suggested_tasks`, `shop_floor_snapshot`. Minimal code — mostly wiring. Safety-critical.

---

## 20. **Quote "What-If" Sandbox** 🧪

**What:** Instantly explore quote variants without committing.

**UI:**
```
Engineering Desk → Quote Stack → [Sandbox] tab

┌─────────────────────────────────────────────────────────────┐
│ BASE: Labour-only, EN8, CNC-1, ₹450/hr → ₹12,450            │
├─────────────────────────────────────────────────────────────┤
│ WHAT-IF:                                                    │
│ ▸ With material (EN8 @ ₹185/kg)        → ₹15,200 (+22%)     │
│ ▸ Switch to VMC-3 (₹600/hr)             → ₹13,100 (+5%)      │
│ ▸ Outsource heat treat (₹800/part)      → ₹13,850 (+11%)     │
│ ▸ 100-off batch (setup amortized)       → ₹11,800 (-5%)      │
│ ▸ Customer scope: Labour-only           → ₹12,450 (base)     │
├─────────────────────────────────────────────────────────────┤
│ [Apply: With Material + VMC-3] → Updates pipeline stage     │
└─────────────────────────────────────────────────────────────┘
```

**Engine:** Clones `quote_pipeline` to temp `pipeline_id="sandbox-{uuid}"`, runs `build_quote` + `quote_verify(stage="draft")` in memory, shows results. Zero persistence until "Apply".

**Why it fits:** Uses existing `quote_build`, `quote_verify`, `machine_hour_rates`, `supplier_rm_quotes`. No new tools. Empowers owner to explore tradeoffs before committing.

---

## Implementation Priority Matrix (Subjective)

| Feature | User Value | Technical Leverage | Effort | Dependencies |
|---------|------------|-------------------|--------|--------------|
| Voice Shift Handover | ⭐⭐⭐⭐⭐ | High (existing tools) | Low | None |
| Drawing Diff Lens | ⭐⭐⭐⭐ | High (identity cascade) | Medium | PDF.js dual view |
| Supplier Coach | ⭐⭐⭐⭐ | High (read-only tools) | Low | None |
| Capacity Promise Date | ⭐⭐⭐⭐ | Medium (routing + logs) | Medium | Routing ops data |
| Cost-to-Serve Dashboard | ⭐⭐⭐⭐ | High (quote_variance) | Medium | Actuals logging |
| Tooling Lifecycle | ⭐⭐⭐ | Medium (toolwatch) | Medium | Migration 0029 |
| FAI Helper | ⭐⭐⭐⭐ | High (knowledge cards) | Low | confirm_drawing_fact |
| Energy/Carbon Tracker | ⭐⭐⭐ | Low (new schema) | Medium | Migration 0030 |
| Multi-Language | ⭐⭐⭐ | High (Voicebox ready) | Medium | i18n strings |
| Predictive Maintenance | ⭐⭐⭐ | Medium (shop_events) | Low | Nightly ingest |
| Customer Portal | ⭐⭐⭐ | Medium (artifacts + JWT) | Medium | FastAPI route |
| Compliance Pack | ⭐⭐⭐⭐ | High (template engine) | High | Jinja2 + data |
| Apprentice Mode | ⭐⭐⭐ | High (routing + tools) | Low | Voice guidance |
| Digital Twin | ⭐⭐ | Medium (three.js + gcode) | High | Substrate worker |
| Jarvis Lite Mobile | ⭐⭐⭐ | Medium (webhook adapter) | Medium | Telegram API |
| SLA Monitor | ⭐⭐⭐ | High (contracts + logs) | Medium | Migration 0031 |
| Knowledge Graph | ⭐⭐ | Medium (cytoscape) | Low | Canvas route |
| Vendor Scorecard | ⭐⭐⭐ | High (aggregation) | Low | Monthly cron |
| Red Phone Mode | ⭐⭐⭐⭐⭐ | High (existing tools) | Low | GPIO/Hardware |
| Quote Sandbox | ⭐⭐⭐⭐ | High (pipeline clone) | Medium | Pipeline API |

---

## Guiding Principles for Future Features

1. **Never add a new brain** — Extend Hermes playbooks or local tools
2. **Never add a new HUD pane** — Use existing `Pane` slots + depth
3. **Never store numbers in chat memory** — SQLite tables with provenance
4. **Never skip HITL** — Even for "obvious" sends/writes
5. **Prefer voice-first, keyboard-equal** — Every feature works both ways
6. **Local-first, offline-capable** — No feature requires cloud to function
7. **Observable by default** — Every feature emits `mission_steps` + `audit`

---

*End of Feature Suggestions. This is a creative menu — not a roadmap. Prioritize via `jarvis-observation-dispatch` when real office use reveals pain points.*