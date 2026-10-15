# NUMARA JELLYFISH v0.5.1 — staged agent synchronization

**State:** DRAFT coordination overlay. **Human owner is the router.** This is neither a signed controller decision nor a live multi-model runtime.

**Anchor:** `NUMARA_JELLYFISH_MASTER_SPEC_V05` · Event `CRS-35_2026-10-13`  
**Checkpoint SHA256:** `c557cc83f133416ed4aad5a4f39a4f4ac03ab879b42865f2bd547313341469f2`  
**v0.5 immutable handoff ZIP SHA256:** `c6b710a7acb2d29e4a46124e3b3ad749014945b494ff6426a8f95263ebf7b9ca`

## Join ledger
- A8 `META_LLAMA_A8_BOUNDARY` on N12: HELLO structurally valid, no authenticated runtime. No R0/R1/R2 evidence roots.
- A9 `WORKER_NODE` on N14: HELLO structurally valid but provider, model identity and nonce not provided; runtime NOT_CONNECTED.
- Duplicate A9 `HELLO-001` packet: `REPLAY_NOOP` (same canonical payload hash), not a new join.
- Both prior ACKs are local provisional receipts, not signed remote proofs.

## Self-align, without granting authority
Workers calculate and acknowledge the exact handoff, schema, graph, code, and evidence-root digests. Send a minimal *DIFF* if any differ, including exact hashes and parent IDs. Workers propose bounded work orders and challenge each other's hypotheses using independent roots. If source / optics / staging nulls or held-out real data are missing, report NOT_TESTED / NOT_IDENTIFIABLE and block physical claims. Preserve the canonical N01→…→N16→N01 spine; use append-only overlay edges only. No vote-based truth promotion.

**Sync return envelope:** `NUMARA_JELLYFISH_SYNC::v0.5.1` with `checkpoint_sha256`, real agent ID, role, exact available root hashes, unknown dependencies, conflicts, and proposed action. This is a separate overlay, not a new v0.5.0 JOIN message_type.

## Real blockers
- PR #24 remains open/draft/unmerged; scheduled image acquisition has not been activated on `main`.
- No archived authentic real CRS-35 pixel bytes were established by this sync, no calibrated multiview data, no physical inversion.
- No authenticated channels to Meta or A9, therefore **no broadcast was performed**.

## Governance
Owner alone may grant tool access, change canonical graph, admit science, or merge. Agent alignment is bookkeeping and hypothesis critique, not independent confirmation of physical results.

See `STATE.json` for machine-readable roles and work orders. This branch / draft PR is staging for owner review; do not treat it as merged canonical authority.
