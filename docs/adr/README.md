# Architecture Decision Records

ADRs capture durable technical decisions, their alternatives, trade-offs, and conditions for revisiting them. They describe the implementation and constraints at the time of review; they are not a checklist of future architecture components.

| ADR | Decision | Status |
|---|---|---|
| [0001 — Modular monolith](0001-modular-monolith.md) | Keep one FastAPI application with explicit domain boundaries | Accepted; one known cross-module persistence exception is documented |
| [0002 — UUIDv7 identifiers](0002-id-strategy.md) | Generate UUIDv7 for new primary entities; use composite keys for relationships | Accepted; no comparative performance benchmark recorded |
| [0003 — Authentication tokens](0003-authentication-tokens.md) | Short-lived JWT access tokens and rotating opaque refresh tokens | Accepted; browser localStorage is an MVP compromise, not production-hardened |
| [0004 — Image media lifecycle](0004-image-media-lifecycle.md) | Direct private object-storage uploads, validated variants, signed delivery, retryable cleanup | Accepted; cleanup failure integration coverage remains open |
| [0005 — Likes relationship](0005-likes-relationship.md) | Store likes as unique user/post rows with idempotent commands | Accepted; PostgreSQL integration/concurrency and UI hydration remain open |
| [0006 — PostgreSQL chronological feed](0006-postgresql-chronological-feed.md) | Start with a visibility-aware read-time SQL feed and keyset pagination | Accepted; query-plan and load baselines remain open |

## Maintenance rules

- Use the next available number for new ADRs. Do not reuse a number, even for a related topic.
- Keep an accepted ADR as the historical decision record. If the decision materially changes, add a new ADR that supersedes it rather than silently rewriting history.
- Update an ADR when implementation evidence changes its status, consequences, or follow-up work.
- Distinguish implemented behavior from intended production hardening and future architecture.
- Link related learning notes and implementation PRs, but keep the ADR focused on the durable decision and its trade-offs.
