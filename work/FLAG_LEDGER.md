# Flag ledger

Five settings in `backend/app/config.py` each keep two implementations of one idea. All five default to **off**. Owner direction on 2026-09-25: turn all five on in the next session and work the features around them. This file does not flip them.

| Flag | Off (what runs today) | On (the other path) | Flip when | Remove the off path when |
| --- | --- | --- | --- | --- |
| `turn_ledger_enabled` | Chat waits and returns one answer. | Server writes the turn first; HUD reconciles. | Next session, after the owner turns it on. | The sync path has a written retirement date and the HUD recovers a crashed turn. |
| `masterdata_enabled` | Quote proof reads `client-names.md` and `mhr-demo.md` plus `mhr-demo-attestation.md`. | Parties, rates, and attestation live in SQL. | Next session, after the owner turns it on. | The markdown readers are unused on a real desk and the Master Data UI covers the same checks. |
| `vision_bench_enabled` | No engineering bench vision queue. | Drawings can sit in `needs_vision` until the owner asks for analysis. | Next session, after the owner turns it on. | Bench ingest no longer has a path around the queue. |
| `knowledge_cards_enabled` | No confirmed-fact cards. | Entity cards hold owner-confirmed facts. | Next session, after the owner turns it on. | "What do we know" no longer answers from anywhere else. |
| `real_embeddings_enabled` | Memory fingerprints are the `hash-v1` word hash. | Local ONNX model `bge-small-en-v1.5`. | Next session, after the model file is present and the owner turns it on. | New notes are no longer stored as `hash-v1`, and old notes have been re-embedded. |

Do not delete a fallback in the same change that flips its flag.
