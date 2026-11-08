# Authentication Module — Implementation Guide

This document explains the first password-based authentication implementation. It is a learning guide, not a claim that all production-hardening work is complete.

## Architecture

```text
HTTP router
  └── AuthService
       ├── UserService + UserRepository (create profile)
       ├── AuthRepository (identity + refresh sessions)
       ├── Argon2 PasswordHasher
       └── JWT / opaque refresh-token helpers

SQLAlchemy adapters
  ├── users
  ├── auth_identities
  └── refresh_tokens
```

Domain dataclasses are separate from ORM rows. Services depend on repository protocols; SQLAlchemy is an adapter.

## Data model

- `users` stores profile and account data.
- `auth_identities` stores a login credential. The first provider is `password`; the normalized email is its provider subject. Passwords are stored only as Argon2id hashes.
- `refresh_tokens` stores SHA-256 fingerprints of high-entropy random refresh tokens, never the raw token.

This separation leaves room to link OAuth/OIDC identities later without adding password fields to the profile model.

## Password lifecycle

Registration hashes passwords with Argon2id. Login verifies the submitted password against the stored encoded hash. Do not hash the submitted password again and compare strings: Argon2 uses a random salt.

Public deployment still requires rate limiting and tuning Argon2 parameters for the deployment hardware.

## Access tokens

Access tokens are signed JWTs using HS256 in this first version. Validation checks the fixed algorithm allow-list, signature, issuer, audience, expiry, and required claims. `sub` is the user UUID. JWTs are signed, not encrypted.

Set `AUTH_JWT_SECRET` to a random secret of at least 32 bytes. Never commit it. The default access-token lifetime is 15 minutes. Send the token as `Authorization: Bearer <token>`.

The `get_current_user` dependency validates the token and loads the user, rejecting suspended or deleted accounts. Logout revokes refresh sessions; existing access tokens remain valid until expiry in this version.

## Refresh-token rotation

Refresh tokens are opaque random values. Only their SHA-256 hash is stored because they have high machine-generated entropy; this is different from human passwords, which need Argon2id.

Refresh flow:
1. Hash the presented token.
2. Select its row with `FOR UPDATE`.
3. Reject unknown, expired, or revoked tokens.
4. If already consumed, revoke the family and report reuse.
5. Mark the old token consumed and insert its successor in the same transaction.
6. Return a new access token and refresh token.

The row lock serializes refresh attempts for one token. The request-scoped DB dependency commits successful requests and rolls back failures. A reuse response explicitly commits family revocation before returning the error.

Reuse detection is a security signal, not proof of theft. Concurrent refreshes from one client can trigger it; clients should single-flight refresh calls and always use the newest token.

## API

All routes are under `/api/v1`.

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/register` | Create profile + password identity + initial tokens |
| POST | `/auth/login` | Verify credentials and issue tokens |
| POST | `/auth/refresh` | Rotate refresh token |
| POST | `/auth/logout` | Revoke the presented refresh-token family |
| GET | `/auth/me` | Return the authenticated user's profile |

Tokens are returned in JSON. This is a starting contract for a native/mobile client that stores refresh tokens in platform secure storage. A browser client should use an HttpOnly, Secure, SameSite cookie with CSRF/origin protections; that transport is not implemented yet.

## Transaction boundary

The FastAPI session dependency owns the request transaction: commit after successful endpoint execution and rollback on exceptions. Repositories flush but do not commit. Registration therefore inserts the user, password identity, and refresh-token row atomically.

## Known gaps before public production use

- Add rate limits and abuse monitoring for registration, login, and refresh.
- Add dummy Argon2 verification for unknown email addresses to reduce timing-based account enumeration.
- Add email verification, password reset, MFA, and OIDC only when requirements call for them.
- Add JWT signing-key rotation and define an explicit access-token revocation policy.
- Add browser cookie + CSRF transport if a browser client is introduced.
- Add PostgreSQL integration tests, especially concurrent refresh, reuse, and rollback cases.
- Add failed-login monitoring and account recovery.
- Ensure password changes and account deletion revoke active refresh families.
- Improve unique-constraint error translation so unrelated integrity violations are not reported as duplicate users.
