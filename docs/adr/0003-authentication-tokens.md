# ADR 0003: Use short-lived JWT access tokens and rotating opaque refresh tokens

- **Status:** Accepted
- **Date:** 2026-11-10

## Context

The first client is expected to be a native/mobile client. It needs a compact
credential for authenticated API calls, a way to continue a session without
asking for a password frequently, and a server-side way to end a session when a
refresh credential is revoked or appears to have been stolen.

Access credentials and long-lived session credentials have different security
properties. A self-contained access token avoids a database lookup on every
request, while a long-lived self-contained token would be difficult to revoke
promptly. Browser cookie transport has different CSRF and origin requirements
from native-client storage.

## Decision

### Access tokens

Issue signed JWT access tokens with a default lifetime of **15 minutes**
(`AUTH_ACCESS_TOKEN_TTL_SECONDS=900`). Tokens use the currently configured
HS256 signing secret, which must be at least 32 bytes and must not be committed
to source control. Validation uses an explicit `HS256` allow-list and requires
the signature, issuer, audience, subject, issued-at time, expiry, and token ID.
The access token type is explicitly `access`.

Access tokens are presented as `Authorization: Bearer <token>`. The
`get_current_user` dependency validates the token and then loads the user,
rejecting suspended or deleted accounts. Access tokens are not individually
stored or revoked; after logout they can remain valid until they expire.

### Refresh tokens

Issue a cryptographically random opaque refresh token with a default lifetime
of **30 days** (`AUTH_REFRESH_TOKEN_TTL_DAYS=30`). Return the raw value only to
the client. Store only its SHA-256 fingerprint in PostgreSQL, with its user,
family ID, creation time, expiry, consumption time, revocation time, and
successor reference.

Each refresh consumes the presented token and creates a successor in the same
database transaction. The refresh row is locked while it is consumed so only
one request can rotate a token. Presenting a previously consumed token revokes
the entire token family. Logout also revokes the presented token's family.
Unknown, expired, revoked, or unavailable-account refresh tokens are rejected.

Clients must serialize refresh requests and replace their stored refresh token
with the successor. Two devices or requests using the same old token may be
treated as reuse and revoke the family; this is an intentional security versus
concurrent-client trade-off.

### Client storage and transport

The current API returns access and refresh tokens in JSON. Native clients must
keep the refresh token only in platform secure storage, such as Keychain or
Keystore, and should avoid logging either credential.

Browser clients are not a supported production transport yet. Before one is
introduced, move the refresh token to an `HttpOnly`, `Secure`, appropriately
scoped `SameSite` cookie and add CSRF and origin protections. Do not put refresh
tokens in browser local storage.

## Alternatives considered

- **Long-lived JWTs only:** simple, but provides no reliable server-side
  revocation for a stolen credential.
- **Opaque access tokens with a database lookup:** immediate revocation is
  simpler, but every protected request requires a session lookup. This is not
  needed for the first baseline.
- **Cookie-only browser sessions:** suitable for a browser-first product, but
  requires CSRF/origin controls and does not meet the current native-client
  transport decision.
- **Asymmetric JWT signing now:** useful when independent verifiers need public
  keys, but adds key-distribution and rotation complexity before it is needed.

## Consequences

- Protected requests remain self-contained except for loading the current user
  and therefore reject account-state changes promptly.
- Refresh-token families provide server-side logout and theft/reuse response.
- A database transaction is required for refresh rotation, and refresh callers
  must handle the concurrent-refresh trade-off.
- Existing access tokens cannot be force-revoked before their short expiry.
- HS256 makes the API signing secret sensitive; separate verification services
  should not be introduced without revisiting the signing approach.

## Revisit when

- Browser clients, multiple devices/session management, OIDC, MFA, or password
  reset are added.
- Immediate access-token revocation, signing-key rotation, or independently
  deployed token verifiers are required.
- Measurements show protected-route user lookups need a different approach.
