
## Entry: 2026-01-28 09:52:10 — Oracle storage + interface boundary pinned in WSP authority

### Trigger
User asked to append guidance on where the engine “oracle” outputs live per environment, and whether WSP replaces the engine interface pack.

### Decision
- Oracle outputs live in immutable object storage per environment (local filesystem/MinIO, dev S3‑compatible, prod S3).
- WSP does **not** replace the engine interface pack; it is downstream and consumes SR’s join surface only.

### Change
- Added a new section “Oracle storage + engine interface boundary (environment ladder)” to the WSP design authority.

