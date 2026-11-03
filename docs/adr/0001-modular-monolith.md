# ADR 0001: Start as a modular monolith

- **Status:** Accepted
- **Date:** 2026-11-04

## Context

The project is an Instagram-style backend intended to evolve from a correct
single-node implementation into a distributed system. Starting with independent
services would add deployment and data-consistency costs before their benefits
can be measured.

## Decision

Build one FastAPI application with domain modules, one PostgreSQL source of
truth, and explicit service interfaces between modules. Add Redis and the local
event broker as later phases require them.

## Consequences

- Local development and tests can exercise the whole application in one place.
- Module boundaries can be measured and refactored without premature network
  APIs.
- Modules must not depend directly on another module's ORM models.
- Infrastructure services are available locally, but are not yet part of
  application request paths.
