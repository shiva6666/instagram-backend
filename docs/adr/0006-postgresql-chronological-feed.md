# ADR 0006: Start with a PostgreSQL chronological home feed

- **Status:** Accepted; baseline feed implemented in PR #5
- **Date:** 2026-11-24 (documentation of the implemented decision)

## Context

The home feed needs to combine the viewer's own posts with posts from accounts they follow, while enforcing private-account, block, deletion, and account-state rules. The original system-design blueprint shows a hybrid fan-out architecture with Redis timelines, push/pull candidate generation, ranking, and asynchronous workers.

Building that architecture before measuring the baseline would add write amplification, derived-state repair, event delivery, and cache consistency concerns before the product has demonstrated a feed bottleneck.

## Decision

Start with a **read-time, chronological PostgreSQL query**. PostgreSQL remains the source of truth; no Redis timeline or fan-out worker participates in the current feed request path.

### Candidate eligibility

The query selects posts that:

- belong to the viewer, or to an account the viewer follows with an accepted relationship;
- are not soft-deleted;
- have an active, non-deleted author;
- are visible under the current private-post rule;
- are not blocked in either direction.

Eligibility and visibility are applied in SQL before ordering and limiting, so an ineligible post does not consume a page slot.

### Query and pagination

- Use one set-based query with an `EXISTS` predicate for accepted follow relationships rather than one query per followed account.
- Order by `created_at DESC, id DESC`.
- Use a keyset cursor containing both `created_at` and `post_id`; the next page predicate is lexicographically older than that pair.
- Fetch `limit + 1` rows to determine whether another page exists.
- Bound page size at the API boundary.
- Batch-load `post_media` rows for the selected posts rather than joining image rows into the candidate query, avoiding row multiplication and an N+1 query pattern.
- Resolve private media URLs only after the feed has applied post visibility rules.

The feed is chronological, not ranked. A cursor is a position in this ordering, not a snapshot of the entire feed; new posts can appear between page requests.

## Alternatives considered

- **Fan-out-on-write for every author:** rejected as the first implementation because each post would create writes proportional to follower count and require reliable asynchronous fan-out.
- **Hybrid push/pull for high-follower accounts:** deferred until a measured follower-count/read-write distribution shows that a single read-time query is insufficient.
- **Offset pagination:** rejected because deep offsets become increasingly expensive and concurrent inserts can shift page boundaries.
- **One query per followee:** rejected because query count grows with the number of followed accounts.
- **Join post images into the candidate query:** avoided because one post with multiple images multiplies candidate rows and complicates pagination.

## Consequences

### Benefits

- Simple source-of-truth semantics and no derived timeline to rebuild.
- Visibility rules are enforced before pagination.
- Stable page ordering with a deterministic tie-breaker.
- Bounded query count and batched image hydration.
- A useful correctness/performance baseline before introducing distributed feed infrastructure.

### Costs and limitations

- Feed reads perform work proportional to the relevant post/follow graph data; very large graphs may require a different access pattern.
- A read-time query can become expensive for users following many accounts.
- The cursor does not promise snapshot isolation across multiple HTTP page requests.
- Ranking, recommendation candidates, and celebrity pull paths are not implemented.
- Query-plan and p50/p95/p99 measurements on a representative skewed dataset remain required before deciding on Redis timelines.

## Validation and follow-up

PR #5 implemented the PostgreSQL feed, SQL visibility filters, keyset cursor pagination, batched image hydration, and initial integration tests.

Remaining proof includes equal timestamps, empty feeds, block changes, inactive authors, page boundaries while new posts arrive, and representative `EXPLAIN (ANALYZE, BUFFERS)`/latency measurements.

## Revisit when

- Query plans and load tests show unacceptable feed latency or database load.
- Follower-count skew causes read-time candidate generation to become a demonstrated bottleneck.
- Product requirements justify ranking or recommendation candidates.

If scaling is needed, introduce Redis timelines as rebuildable projections and consider hybrid fan-out. Keep PostgreSQL authoritative and preserve visibility checks during hydration.
