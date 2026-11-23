# Media reliability: failures, retries, and transaction boundaries

This guide records the reliability contract being tested after the initial media happy path.

## The key boundary: PostgreSQL can roll back; object storage cannot

The media completion endpoint uses the request-scoped SQLAlchemy session. The session dependency commits only after the endpoint returns successfully and rolls back when an exception escapes.

During completion, the service:

1. Locks the media row.
2. Writes PROCESSING and flushes it inside the open database transaction.
3. Reads the original object and processes it.
4. Writes deterministic display and thumbnail keys to object storage.
5. Writes READY and returns.
6. The request dependency commits the database transaction.

If storage or processing raises before step 5 completes, the request dependency rolls back the database transaction. A previously PENDING row therefore remains PENDING in PostgreSQL. The intermediate PROCESSING value was flushed, but was never committed.

This is why the current synchronous design does not need a stale-PROCESSING recovery job. That state would become a durable recovery concern only if a future design deliberately commits the processing claim before handing work to a separate worker.

## Why deterministic keys matter

Object storage is outside the PostgreSQL transaction. Suppose the display variant is uploaded successfully, but writing the thumbnail fails:

- PostgreSQL rolls back to PENDING.
- The display object may remain in MinIO.
- The next completion attempt uses the same media ID and deterministic object keys.
- It overwrites the display object and writes the thumbnail, then commits READY.

The object write is not rolled back; the retry is safe because the operation is repeatable and targets the same keys. The cleanup job also derives both variant keys from the media ID, so it can remove a partial write even when the database never recorded those keys.

## Failure matrix

| Failure | Persisted state / side effect | Expected behavior |
|---|---|---|
| Unsupported or corrupt image bytes | FAILED is committed with a reason | Do not attach to a post; cleanup can remove the original |
| Upload URL expires and no object exists | FAILED plus cleanup_requested_at | Cleanup eventually removes the metadata row |
| Temporary object read failure | Completion transaction rolls back; prior state remains | Return an error; client may retry completion |
| Display or thumbnail write fails | DB transaction rolls back; an earlier variant may remain | Retry overwrites deterministic keys and can reach READY |
| Cleanup object deletion fails | DELETING claim was committed before storage I/O | Keep the row and retry deletion on the next cleanup run |
| API process exits during synchronous completion | Uncommitted DB work rolls back; already-written objects may remain | Retry completion; cleanup handles abandoned assets |

## Cleanup has a different transaction boundary

Cleanup intentionally commits the DELETING claim before contacting MinIO. This is different from synchronous completion:

- The claim must survive a process crash so another cleanup run can find the work.
- Object deletion is idempotent, so a retry can safely repeat deletes that already succeeded.
- The metadata row is removed only after all object deletions succeed and the media remains unattached.

A failure-path integration test for cleanup deletion/retry remains a follow-up.

## What this PR proves

- The existing MinIO-backed happy path still works.
- Invalid image content is durably marked FAILED.
- An expired upload ticket with no uploaded object is marked FAILED and scheduled for cleanup.
- A transient object read failure rolls back the completion transaction, leaving the media PENDING; a retry succeeds.
- A partial variant write leaves the media PENDING; retrying writes both deterministic variants and reaches READY.

## Deliberately deferred

Do not add a queue, outbox, durable worker, lease, or stale-processing sweeper to this synchronous flow. First prove the current transaction and retry contract. A future worker design will need a different state transition: commit a claim/lease, perform work outside the request transaction, and use lease expiry or explicit ownership to recover abandoned jobs.
