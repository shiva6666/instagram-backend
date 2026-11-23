# Learnings

Use this folder to capture concepts, commands, and decisions you learn while working on the project.

## PR #13 media lifecycle reading path

The original [PR #13 deep dive](./pr13-media-lifecycle.md) is a broad reference. These smaller guides split the same change into focused chunks:

1. [Media domain model and state machine](./media-01-domain-and-state-machine.md)
2. [MinIO/S3 storage layer](./media-02-storage-layer.md)
3. [Image validation and processing](./media-03-image-processing.md)
4. [Upload API and service flow](./media-04-upload-api-and-service.md)
5. [Post, feed, and private image delivery](./media-05-post-feed-integration.md)
6. [Schema migration and legacy data](./media-06-schema-and-legacy-migration.md)
7. [Retryable cleanup and local operations](./media-07-cleanup-and-local-operations.md)
8. [Media reliability: failures, retries, and transaction boundaries](./media-08-reliability.md)

## Suggested entry format

Create one Markdown file per topic, for example `docker-compose.md`.

```md
# Topic name

## What I learned

## Example

## Questions to revisit
```
