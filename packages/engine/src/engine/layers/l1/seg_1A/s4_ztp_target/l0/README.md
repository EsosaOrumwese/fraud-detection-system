# S4 ZTP Target – L0 Primitives

Status: **Implemented** (authoritative constants + writer).

L0 provides the frozen identifiers that every layer shares when emitting S4
logs and the `ZTPEventWriter`, which enforces the contract-level guarantees for
each stream.

## Surfaces
- `constants.py` exposes the canonical literals:
  - `MODULE_NAME`, `CONTEXT`, and `SUBSTREAM_LABEL` for audit metadata.
  - Stream ids for Poisson attempts, rejections, retry exhaustion markers,
    finals, and the trace log.
- `ZTPEventWriter` stamps JSONL envelopes, checks consuming vs non-consuming
  invariants, appends a cumulative trace row after every event, and publishes
  helper properties for tests to locate the generated files.

Higher layers should import these primitives via
`engine.layers.l1.seg_1A.s4_ztp_target.l0` to avoid scattering literals and to
maintain a single implementation of the event-writing discipline.
