# ADR 0002: Use application-generated UUIDv7 identifiers

- **Status:** Accepted
- **Originally accepted:** Date not recorded
- **Reviewed:** 2026-11-24

## Context

Users, posts, media assets, and authentication records need stable identifiers that can be generated without a database sequence round trip and can be created independently by application instances. The project also uses identifiers in API resources, object-storage keys, and cursor tie-breakers.

The schema uses PostgreSQL UUID columns. PostgreSQL 16 does not provide a built-in UUIDv7 generator, so application code supplies UUIDv7 values for normal new domain entities. Database defaults using `gen_random_uuid()` remain in the initial schema for database-generated/legacy paths.

## Options considered

1. **BIGSERIAL / identity:** compact and convenient, but requires database allocation and exposes enumerable identifiers.
2. **UUIDv4:** decentralized and random, but inserts are distributed across the B-tree.
3. **UUIDv7:** 16-byte decentralized identifiers with a time-ordered prefix; random suffix avoids a central allocator.
4. **Snowflake-style IDs:** compact and time ordered, but require worker-ID allocation and clock-skew handling.

## Decision

Use UUIDv7 generated in application code for newly created primary entities. The implementation is `backend/app/core/ids.py:new_uuid7()`, which encodes the current UTC millisecond timestamp, UUIDv7 version/variant bits, and random bits.

The decision is scoped to entity IDs, not every relationship row:

- Users, posts, media records, auth identities, and refresh-token records use application-generated UUIDv7 in their current creation flows.
- Relationship tables use natural/composite keys where that models the invariant directly (for example, follows and post likes).
- Legacy URL-backed post-media compatibility rows may still use UUIDv4, and the initial schema retains `gen_random_uuid()` defaults. These are compatibility/database fallback paths, not a claim that all UUID values in the database are v7.

Pagination uses explicit `(created_at, id)` ordering rather than relying on UUID ordering as a substitute for the business timestamp.

## Consequences

### Benefits

- IDs can be generated before persistence and without coordination between application instances.
- The time-ordered prefix generally improves insertion locality compared with UUIDv4.
- IDs work across API boundaries and can be generated for storage keys before a database insert.
- No worker-ID allocation or central ID service is required.

### Trade-offs

- UUIDs are 16 bytes and make indexes and references larger than 64-bit integers.
- The timestamp portion reveals approximate creation time.
- UUIDv7 values generated in the same millisecond are not a strict global sequence.
- UUIDv7 does not replace explicit `created_at` ordering or a stable compound cursor.
- Database defaults and legacy UUIDv4 paths mean the database is not guaranteed to contain only UUIDv7 values.

## Evidence and validation

The project has a custom UUIDv7 generator and uses it in the primary entity creation paths described above. No controlled million-row UUIDv4-versus-UUIDv7 benchmark has been recorded. The expected index-locality benefit is a design rationale, not a measured performance claim for this repository.

## Revisit when

- Index size, write throughput, or cache behavior is measured to be a bottleneck.
- The project adopts a different database/ID-generation capability.
- A security or privacy review changes the acceptable identifier metadata exposure.
