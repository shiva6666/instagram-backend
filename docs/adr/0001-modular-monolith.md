# ADR 0001: Start as a modular monolith

- **Status:** Accepted
- **Originally accepted:** 2026-11-04
- **Reviewed:** 2026-11-24

## Context

The project is an Instagram-style social application intended to evolve from a correct, understandable single-application implementation toward the larger system shown in the README architecture blueprint.

Starting with independently deployed services would introduce network failure modes, deployment complexity, distributed transactions, service discovery, and operational overhead before the project has measured a need for them. The product can establish its core domain boundaries inside one process first.

## Decision

Build one versioned FastAPI application as a **modular monolith**:

- Domain modules own their use cases and expose service-level contracts to other modules.
- Each module separates HTTP routing, application/business logic, domain data structures, and persistence adapters where appropriate.
- PostgreSQL is the authoritative store for users, authentication state, posts, social relationships, media metadata, and likes.
- Redis, MinIO, and the event-broker/monitoring containers may run in the local environment, but their presence does not mean every request path depends on them.
- MinIO is currently used for private media bytes. Redis is available for readiness/local infrastructure and future cache/timeline experiments; the current home feed is PostgreSQL-backed. Redpanda/Kafka-style event streaming remains deferred.
- The React + TypeScript frontend is a separate client of the versioned HTTP API. It does not share backend domain code.

## Module interaction rules

1. A module should call another module through an application/service contract, not by reaching into its persistence implementation.
2. ORM rows are persistence details and should not become cross-module domain contracts.
3. HTTP routes translate transport input/output and delegate business decisions to services.
4. The request-scoped database session owns commit/rollback; repositories flush changes but do not independently commit.
5. Database constraints enforce invariants that must remain true under concurrent requests.
6. External systems such as object storage are not part of the PostgreSQL transaction; their failure and retry boundaries must be explicit.

**Known boundary to improve:** the auth repository currently joins the users table by importing the users repository's ORM row/conversion helper. This is a concrete exception to the desired module boundary, not a reason to pretend the rule is already perfectly enforced. Refactor it behind a user-facing persistence/service contract when doing so can be tested without duplicating queries or weakening transaction ownership.

## Alternatives considered

- **Microservices from the start:** rejected because operational and distributed-consistency costs are premature.
- **One large undifferentiated application module:** rejected because it hides domain ownership and makes later extraction harder.
- **Separate databases per domain:** rejected for the current learning/MVP stage; PostgreSQL transactions across core domain operations are valuable now.

## Consequences

### Benefits

- The complete user journey can be run and tested locally.
- Core operations can share a single PostgreSQL transaction where appropriate.
- Module boundaries can be evolved before introducing network boundaries.
- Tests can use service fakes for business rules and real PostgreSQL/MinIO for persistence and integration behavior.

### Costs and constraints

- The application is still one deployment and one failure domain.
- A module boundary is a code-level boundary, not an independent scaling or security boundary.
- Shared database schema requires discipline around ownership, migrations, and cross-module queries.
- Long-running work must not be hidden inside request handlers indefinitely.

## Revisit when

- A module has a measured independent scaling or availability requirement.
- Deployment cadence or team ownership makes independent deployment valuable.
- A domain needs a separate data lifecycle or isolation boundary.
- The cost of in-process coupling is demonstrated by tests, performance, or operational evidence.

Do not split services solely because the target architecture diagram contains separate service boxes.
