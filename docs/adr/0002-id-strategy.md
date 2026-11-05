# ADR 0002: Primary key strategy

## Status

Accepted (2026-11-xx)

## Context

Need IDs for users, posts, comments, follows. Requirements: generated without
a DB round trip, index-friendly inserts, usable in cursors, shardable later.

## Options considered

1. **BIGSERIAL:** simple, 8 bytes, but single-writer and enumerable.
2. **UUIDv4:** no coordination, but random inserts fragment the B-tree.
3. **UUIDv7:** time-ordered, 16 bytes, no coordination.
4. **Snowflake-style:** 8 bytes, time-ordered, needs worker-ID management
   and clock-skew handling.

## Decision

UUIDv7 for all public entities, generated in the application.

## Evidence

(Fill in from your experiment: insert 1M rows each with v4 and v7; record
insert time, index size, and buffer cache hit ratio.)

## Consequences

- No coordination, sortable, shardable.
- 16-byte keys: larger indexes and Redis members.
- Creation time is visible in the ID.
- Cursor uses `(created_at, id)`; ID order is not a strict global order.

## Revisit when

Index size or timeline memory becomes a measured problem.
