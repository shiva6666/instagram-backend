# Authentication: Architecture, Security Model, and Implementation Notes

> **Document status:** Architecture and learning notes; authentication is not yet implemented.
>
> **Scope:** Password-based authentication for the current FastAPI modular monolith, with a design that can evolve without prematurely introducing a separate auth service.
>
> **Decision status:** Proposed baseline, not an approved production security review. Revisit the explicit open decisions before implementation.

This document records both the mechanics of authentication and the engineering decisions needed to build it safely. It is intentionally more than a JWT tutorial: authentication is a lifecycle, state-management, and threat-modeling problem.

---

## 1. Executive summary

For the first implementation, use:

- **Argon2id** for human-selected password hashing.
- A separate **authentication identity** model/table rather than putting passwords on the user profile.
- A short-lived, signed **JWT access token** for API authentication.
- A cryptographically random, opaque **refresh token** whose hash/fingerprint is stored server-side.
- **Refresh-token rotation**, reuse detection, and token-family revocation.
- A FastAPI authentication dependency that validates the access token and resolves the current user.
- Explicit authorization checks in application use cases; authentication alone never grants ownership or permissions.
- HTTPS everywhere and client-appropriate credential storage.

The project is currently a modular monolith with PostgreSQL as its source of truth. Do not add a standalone identity service, distributed cache, or complex key infrastructure solely in anticipation of future microservices.

A server-side session design backed by Redis or PostgreSQL is also valid. JWT is a deliberate trade-off, not a requirement for distributed systems.


## Visual guide

The diagrams below are intentionally conceptual. They show the proposed design, not implemented runtime behavior. GitHub renders these Mermaid blocks inline; the same diagrams were also opened as editable draw.io diagrams during this learning session.

### 2.1 Component architecture

This shows where authentication belongs in the current modular monolith. The auth module validates credentials and establishes the principal; application use cases still enforce authorization.

~~~mermaid
flowchart LR
  Client["Browser / Mobile Client"] -->|HTTPS| API["FastAPI API"]
  API --> DEP["get_current_user"]
  DEP --> JWT["JWT validation"]
  JWT --> AUTH["Auth module"]
  AUTH --> ID["Auth identity"]
  AUTH --> USER["Users module"]
  AUTH --> RT["Refresh token service"]
  ID --> DB[("PostgreSQL")]
  USER --> DB
  RT --> DB
  API --> USE["Application use case"]
  USE --> POL["Authorization policy"]
  POL --> DB
~~~

### 2.2 Login and authenticated request

The password is verified once during login. Later API requests validate the access token and resolve its subject; they do not re-check the password.

~~~mermaid
sequenceDiagram
  autonumber
  participant C as Client
  participant R as Auth Router
  participant S as Auth Service
  participant DB as PostgreSQL
  participant K as JWT Signer
  C->>R: POST /auth/login
  R->>S: identifier + password
  S->>DB: Load auth identity
  DB-->>S: Password hash + user ID
  S->>S: Argon2id verify
  alt Credentials valid
    S->>DB: Create refresh family + token hash
    S->>K: Sign short-lived access JWT
    K-->>S: Access JWT
    S-->>R: Access + refresh credentials
    R-->>C: 200 credentials
  else Invalid credentials
    S-->>R: Generic authentication failure
    R-->>C: 401
  end
  C->>R: GET /posts with Bearer access JWT
  R->>K: Verify signature + claims
  K-->>R: Trusted subject (sub)
  R->>DB: Resolve active user
  DB-->>R: User
  R-->>C: Protected response or 401
~~~

### 2.3 Refresh-token state machine

Rotation is a one-time state transition. Consuming the old token and creating its successor must happen atomically in one database transaction.

~~~mermaid
stateDiagram-v2
  [*] --> Active
  Active --> Consumed: Valid refresh
  Consumed --> SuccessorActive: Create successor in same transaction
  Active --> Expired: expires_at reached
  Active --> Revoked: Logout or admin action
  Consumed --> ReuseDetected: Old token presented again
  ReuseDetected --> FamilyRevoked: Revoke token family
  SuccessorActive --> Consumed: Next successful refresh
  SuccessorActive --> Expired: expires_at reached
  SuccessorActive --> Revoked: Logout or admin action
  Expired --> [*]
  Revoked --> [*]
  FamilyRevoked --> [*]
~~~

### 2.4 Conceptual persistence model

This ER diagram is a teaching model for the proposed separation between a user profile, one or more authentication identities, and refresh-token sessions. It is not a migration specification; constraints, provider semantics, and exact columns must be finalized before implementation.

~~~mermaid
erDiagram
  USER ||--o{ AUTH_IDENTITY : owns
  USER ||--o{ REFRESH_TOKEN : has
  AUTH_IDENTITY {
    uuid id PK
    uuid user_id FK
    string provider
    string identifier_normalized UK
    string password_hash
    datetime created_at
    datetime updated_at
  }
  USER {
    uuid id PK
    string username UK
    string email UK
    string status
  }
  REFRESH_TOKEN {
    uuid id PK
    uuid user_id FK
    uuid family_id
    string token_hash UK
    datetime created_at
    datetime expires_at
    datetime consumed_at
    datetime revoked_at
    uuid replaced_by_token_id FK
  }
~~~


---

## 2. Current repository context

The current repository has a modular-monolith architecture:

- \`app/main.py\` creates the FastAPI application and includes the API router.
- \`app/api/router.py\` currently includes the health router; authentication routes are not wired yet.
- \`app/core/config.py\` owns application configuration.
- \`app/core/db.py\` owns the async SQLAlchemy engine/session infrastructure.
- \`app/modules/users/models.py\` defines an immutable domain \`User\` dataclass.
- \`app/modules/users/repository.py\` contains the users repository port and SQLAlchemy adapter/\`UserRow\`.
- The current users table stores profile/account fields, not password credentials.
- The roadmap lists JWT access/refresh tokens and Argon2 hashing in Week 2.

The existing separation between domain objects, services, repositories, and SQLAlchemy rows is a useful foundation. Authentication should follow those boundaries rather than bypassing them.

---

## 3. Security goals, non-goals, and threat model

### 3.1 Goals

The first release should:

1. Prove control of a registered credential during login.
2. Establish a stable application user identity for each authenticated request.
3. Limit the lifetime and usefulness of stolen credentials.
4. Support logout and server-side invalidation of long-lived credentials.
5. Prevent password disclosure through database compromise.
6. Enforce authorization at the resource/use-case boundary.
7. Produce enough audit and operational signals to investigate suspicious activity.
8. Keep the design understandable and testable inside the existing modular monolith.

### 3.2 Important threats and controls

| Threat | Primary controls | Residual limitation |
|---|---|---|
| Database read compromise | Argon2id password hashes; hashed refresh tokens; least-privilege DB access | Weak user passwords can still be guessed offline |
| Password guessing / credential stuffing | Rate limits, throttling, generic login errors, monitoring; consider breached-password checks | Distributed attacks require layered detection |
| Network interception | HTTPS; secure cookie settings | Compromised client/device remains a risk |
| JWT tampering | Signature verification; strict algorithm/issuer/audience validation | A stolen valid token remains usable until expiry/revocation |
| Refresh-token theft | High-entropy opaque token, hash-at-rest, rotation, reuse detection | Theft before legitimate use may not be immediately distinguishable |
| CSRF against cookie-authenticated endpoints | SameSite policy, CSRF token/origin checks | Requires correct client and deployment configuration |
| XSS in browser | Avoid exposing refresh token to JavaScript; CSP and output encoding | HttpOnly does not prevent an attacker from acting through an already-compromised page |
| Authorization bugs / IDOR | Derive actor from verified identity; enforce ownership in use cases/queries | Requires endpoint-by-endpoint policy tests |
| Key compromise | Secret management, key rotation, restricted access, incident procedure | Tokens signed with a compromised key may need invalidation |

Do not claim that JWT signatures detect theft. They detect invalid signatures and payload modification. Theft is a separate problem.

### 3.3 Non-goals for the first slice

Do not build all of these into the first authentication milestone unless a product requirement requires them:

- A standalone identity microservice.
- Multi-region identity replication.
- Social login / OIDC.
- Enterprise SSO, SAML, or SCIM.
- Device fingerprinting as an authentication factor.
- Complex risk-scoring or adaptive authentication.
- Passwordless login or MFA (important future security capabilities, but separate product/security work).

Keep the design extensible enough to add these without coupling them to the profile model.

---

## 4. Core concepts: authentication, identity, credentials, authorization

These concepts should not be conflated.

- **User/profile:** The application person/account: username, email, bio, privacy, account status.
- **Identity:** A way to authenticate as a user, such as a password identity or a Google OIDC subject.
- **Credential:** A secret or proof used by an identity, such as a password, refresh token, or external identity-provider assertion.
- **Authentication:** Establishes the caller's identity.
- **Authorization:** Decides whether that identity may perform a particular action on a particular resource.

A valid access token proves that the trusted issuer issued a token for a subject. It does not prove that the subject owns every post or may perform every action.

The authenticated principal should be derived from a verified credential, never from a client-supplied \`user_id\` in a request body or query parameter.

---

## 5. Password lifecycle: one-way verification, not decryption

Passwords are human-chosen, relatively low-entropy secrets. Store a password-specific hash, not plaintext and not reversible encryption.

### 5.1 Registration

1. Accept the password over HTTPS.
2. Validate input and apply password policy.
3. Hash with Argon2id using a vetted library and current recommended parameters.
4. Persist the encoded hash in the password identity record.
5. Never log the password or include it in telemetry/errors.

An encoded Argon2id hash contains the algorithm/version, cost parameters, salt, and derived hash. The salt is not a secret.

### 5.2 Login

1. Normalize the login identifier consistently (for example, email case handling).
2. Load the relevant password identity and its encoded hash.
3. Verify the submitted password using the library's verification function.
4. On success, create an authenticated session/token family.
5. On failure, return a generic error that does not reveal whether the account exists.

~~~python
# Illustrative only; use the chosen library's exact API.
if password_hasher.verify(stored_hash, incoming_password):
    # Credential is valid; continue login.
    ...
~~~

Do not hash the submitted password and compare strings. Argon2id uses a random salt, so hashing the same password again normally yields a different encoded value. The verifier extracts the stored salt and parameters and performs the correct verification operation.

Password verification occurs at login and when re-authentication is required for a sensitive operation—not on every API request.

### 5.3 Operational requirements

- Tune Argon2id parameters on representative production hardware; hashing must be expensive for attackers but not cause avoidable capacity exhaustion.
- Rehash on successful login when stored parameters are below current policy.
- Rate-limit login attempts by more than one dimension (for example, account identifier and source/network); avoid relying only on IP address.
- Use a generic response for unknown account and incorrect password.
- Consider a dummy hash verification for unknown accounts to reduce timing-based account enumeration.
- Define password reset/recovery as a separate credential lifecycle with single-use, expiring reset tokens. Do not implement password reset by emailing or recovering the old password.
- A password change/reset should revoke existing refresh-token families according to the product's security policy.

---

## 6. Identity and persistence model

Keep credentials separate from the profile domain object.

### 6.1 Suggested tables

The following is a conceptual model, not a final migration specification.

#### \`auth_identities\`

| Column | Intent |
|---|---|
| \`id\` | Identity primary key |
| \`user_id\` | FK to \`users.id\` |
| \`provider\` | For example \`password\` or \`google\` |
| \`provider_subject\` | Stable external subject for an OIDC identity; nullable for local password identity |
| \`normalized_identifier\` | Login identifier, if needed for password login |
| \`password_hash\` | Argon2id encoded hash for password identity; null for external identity |
| \`created_at\`, \`updated_at\` | Audit/lifecycle timestamps |

Constraints to decide and enforce:
- Unique external identity on \`(provider, provider_subject)\`.
- A defined uniqueness policy for normalized email/login identifiers.
- Check constraints that ensure each provider type has the required fields.
- Foreign key to the user with deliberate delete behavior.
- Do not assume email from an external provider is verified unless the provider's verified claim is validated.

A user may eventually have multiple identities (password, Google, etc.). Linking identities is a security-sensitive operation and should require proof of control of both identities or a recent authenticated session.

#### \`refresh_tokens\`

| Column | Intent |
|---|---|
| \`id\` | Internal record identifier |
| \`user_id\` | FK to user |
| \`family_id\` | Groups the rotation chain for one login/device session |
| \`token_hash\` | Hash/fingerprint of the opaque token; never raw token |
| \`created_at\` | Issuance time |
| \`expires_at\` | Absolute expiry |
| \`consumed_at\` | When used for rotation |
| \`revoked_at\` | Explicit revocation time |
| \`replaced_by_token_id\` | Optional link to successor |
| \`client_label\` / metadata | Optional, non-secret device/session description |

Use indexes for token fingerprint lookup, active sessions by user/family, and cleanup by expiry. Avoid collecting unnecessary device or location data.

The exact schema should support the chosen concurrency strategy. A unique token fingerprint and transactional state transition are essential.

### 6.2 Hashing opaque refresh tokens

Generate refresh tokens with a cryptographically secure random generator and sufficient entropy (for example, 256 random bits). Since this is a machine-generated high-entropy secret, a fast cryptographic hash such as SHA-256 is suitable as a lookup fingerprint; a keyed HMAC is another option if its key is separately protected.

This is different from human passwords:
- Human passwords need a deliberately slow password hash such as Argon2id.
- Random 256-bit tokens already resist guessing; use a fast cryptographic fingerprint for lookup.

Never log raw refresh tokens.

---

## 7. Access JWT: claims, signing, and validation

### 7.1 Token shape

A signed JWT is generally:

~~~text
base64url(header).base64url(payload).signature
~~~

Illustrative payload:

~~~json
{
  "sub": "user_101",
  "iss": "instagram-backend",
  "aud": "instagram-api",
  "iat": 1794100000,
  "nbf": 1794100000,
  "exp": 1794100900,
  "jti": "unique-token-id"
}
~~~

- \`sub\`: stable user identifier.
- \`iss\`: trusted issuer.
- \`aud\`: intended API/service audience.
- \`iat\`: issued-at time.
- \`nbf\`: not-before time, if used.
- \`exp\`: expiry time.
- \`jti\`: token identifier, useful for tracing or denylisting.

Do not put passwords, secrets, refresh tokens, or sensitive profile data in the payload. JWT payloads are encoded, not encrypted.

### 7.2 Signature model

With HS256, the same secret signs and verifies. Every verifier holding that secret can also mint tokens.

With RS256/ES256, a private key signs and a public key verifies. A verifier holding only the public key cannot mint tokens. Asymmetric signing can reduce the number of components that need signing authority, but it introduces key distribution and rotation responsibilities.

For a single-process modular monolith, either can work if configured correctly. Pick one deliberately, use a vetted library, and do not allow the token header to choose arbitrary algorithms.

### 7.3 Validation checklist

Every protected request should validate:
1. Token syntax and allowed algorithm.
2. Signature against the expected trusted key.
3. Issuer (\`iss\`).
4. Audience (\`aud\`).
5. Expiration (\`exp\`) and not-before (\`nbf\`) where present.
6. Required subject (\`sub\`) and claim types.
7. User existence and current account status according to policy.

A JWT signature is not unique per user. The issuer signs each token using its signing key; the verified \`sub\` identifies the subject. The server does not keep a per-user signature registry.

A valid signature proves trusted issuance and integrity—not that the presenter is the original person. A stolen, unexpired bearer token can generally be replayed.

### 7.4 Expiration and revocation

The verifier compares \`exp\` with current UTC time. No database lookup is needed solely to check JWT expiry.

A stateless access JWT is not immediately revoked just because a refresh token is revoked. Options include:
- Short access-token lifetime and accept the bounded residual window.
- A \`jti\` denylist checked on requests.
- A per-user/session token version or session-state lookup.

Choose the required revocation latency explicitly; immediate revocation adds state and operational cost.

---

## 8. Refresh-token lifecycle and rotation

The refresh token is a long-lived credential used only at the refresh endpoint, not on every normal API request.

### 8.1 Login

After successful password verification:
- Issue a short-lived access JWT.
- Generate a random opaque refresh token.
- Store only its fingerprint and lifecycle metadata.
- Return the access token and deliver the refresh token using the client-appropriate mechanism.

Illustrative lifetime values such as 10–15 minutes for access and several days for refresh are starting points, not universal requirements. Choose based on product risk and client behavior.

### 8.2 Refresh state transition

A refresh operation should be a single-use state transition:

~~~text
ACTIVE --successful refresh--> CONSUMED
                              |
                              +--> successor token becomes ACTIVE
~~~

Algorithm:
1. Receive the raw refresh token.
2. Compute its fingerprint.
3. Find and lock the corresponding row (or perform an equivalent atomic conditional update).
4. Check existence, expiry, revocation, and consumed state.
5. If active, mark it consumed and create the successor token record in the same database transaction.
6. Issue a new access JWT and return the new raw refresh token once.
7. Commit the transaction.

The old token must not remain usable after successful rotation.

### 8.3 Concurrency is a security property

Two refresh requests can arrive at nearly the same time (for example, multiple frontend requests all notice an expired access token). Without atomicity, both could observe the old token as active and both mint successors.

Use a transaction with row locking (for example, \`SELECT ... FOR UPDATE\`) or a conditional update such as “consume only where consumed_at and revoked_at are null and expires_at is in the future.” Check the affected row count. Only one request may win.

The client should also implement single-flight refresh coordination so simultaneous failed API calls share one refresh attempt. Server-side atomicity remains mandatory; client coordination is not a security boundary.

### 8.4 Reuse detection

If a previously consumed refresh token is presented again, it may mean a stolen copy is being replayed. The server can revoke the token family and require a new login.

This is a signal, not proof of who stole the token. Legitimate client races or retries can also cause reuse events, so client coordination and clear retry behavior matter.

### 8.5 Expiry

Store an absolute \`expires_at\` value in UTC. It can be computed at issuance:

~~~python
created_at = datetime.now(timezone.utc)
expires_at = created_at + timedelta(days=7)
~~~

Storing both timestamps supports auditability and direct expiry checks. The signature does not reveal whether a token is stolen; expiry, revocation, and reuse are separate checks.

---

## 9. Request flows

### 9.1 Login

~~~text
Client
  | POST /auth/login (identifier + password over HTTPS)
  v
Auth API -> Auth service
  | load identity
  | Argon2id verify
  | create refresh-token family
  | sign access JWT
  v
Client receives access token + refresh credential
~~~

Return generic authentication errors. Never return password hashes or internal credential records.

### 9.2 Authenticated API request

~~~text
Client -- Authorization: Bearer <access JWT> --> FastAPI
                                                   |
                                             get_current_user
                                                   |
                                     verify signature + claims
                                                   |
                                        resolve sub to User
                                                   |
                                         route / use case
                                                   |
                                      authorization policy
                                                   |
                                             response
~~~

Password verification is not repeated on normal requests.

### 9.3 Refresh

~~~text
Client -- refresh credential --> POST /auth/refresh
                                      |
                              fingerprint token
                                      |
                         atomic DB state transition
                                      |
                         consume old / create successor
                                      |
                        issue access JWT + new refresh
                                      |
                                    Client
~~~

### 9.4 Logout

Revoke the relevant refresh token or token family, then clear client credentials. A previously issued access JWT may remain valid until expiry unless an immediate access-token revocation mechanism is also implemented.

---

## 10. Browser and mobile transport/storage

The right delivery mechanism depends on the client; do not finalize it without knowing the client.

### Browser

A common pattern:
- Refresh token in a \`Secure\`, \`HttpOnly\`, appropriately \`SameSite\` cookie.
- CSRF protection for cookie-authenticated refresh/logout operations (CSRF token and/or strict Origin checks, chosen for the deployment).
- Access token kept in memory where practical rather than long-lived localStorage.
- HTTPS only; configure cookie domain/path narrowly.

HttpOnly prevents JavaScript from reading the cookie, but it does not prevent XSS from making authenticated requests in the victim's browser. CSRF controls are still required when cookies are automatically attached.

### Native mobile

Store refresh credentials in platform secure storage (iOS Keychain / Android Keystore-backed storage). Avoid logging credentials. Use TLS and define behavior for app reinstall, device logout, and multiple devices.

---

## 11. Sessions vs. JWT: the actual distributed-systems trade-off

JWT is not required merely because a system may later be distributed.

### Server-side session

- Client holds an opaque session ID.
- Server stores session state in shared Redis/PostgreSQL.
- Any instance/service that validates the session must access the shared store, or trust a gateway that validates it and securely propagates identity.
- Revocation is direct: invalidate the server-side session record.

An in-memory-only session store fails when requests land on a different instance. Sticky sessions can hide that issue but couple routing to instance state. A shared session store is usually the robust session design.

### JWT access token

- Services can verify the signature and claims locally without a shared lookup on every request.
- Services need trusted verification keys, key rotation, consistent issuer/audience/claim validation, and clear trust boundaries.
- Immediate revocation is harder without adding shared state.

The coordination has not disappeared; it has moved from session-state lookup to key distribution, configuration, and revocation strategy.

For this repository, start with the modular monolith and avoid designing for hypothetical services before there is a concrete deployment boundary. If browser-only clients and immediate revocation are dominant requirements, a shared server-side session may be simpler.

---

## 12. FastAPI and module boundaries

A possible structure aligned with the existing users module:

~~~text
app/modules/auth/
    schemas.py        # Pydantic HTTP input/output contracts
    models.py         # Pure auth domain objects, if needed
    repository.py     # Repository port + SQLAlchemy adapter
    service.py        # Register, login, refresh, logout use cases
    tokens.py         # Password hasher, JWT, opaque-token helpers
    dependencies.py   # get_current_user / authenticated principal
    router.py         # Auth HTTP endpoints
~~~

Keep ORM row mappings in the persistence adapter (or a clearly separated ORM module). Do not let other modules import auth ORM rows directly.

### Schemas vs. domain models vs. ORM models

| Type | Responsibility | Example |
|---|---|---|
| Pydantic API schema | Validate incoming HTTP data and shape responses | \`RegisterRequest\`, \`LoginRequest\`, \`TokenResponse\` |
| Domain model | Represent a business concept independent of HTTP/ORM | Existing immutable \`User\` dataclass |
| ORM model | Map Python attributes to database tables/columns | SQLAlchemy \`UserRow\`, \`RefreshTokenRow\` |

A request schema may contain a plaintext password because it is transient input. The service hashes it before persistence. A response schema must never expose the password or password hash.

### Dependency responsibilities

\`get_current_user\` should be a transport/application boundary:
- Extract bearer credentials.
- Validate access-token cryptography and claims.
- Resolve the subject to an active user.
- Return a trusted principal/user to the endpoint.

It should not contain business rules such as “can this user delete this post?” That belongs in the relevant application service/use case or policy, using the authenticated actor ID.

---

## 13. Operational design

Authentication is a high-value attack surface. Production readiness requires more than passing unit tests.

### Secrets and keys

- Load signing keys from environment-backed secret management, not committed configuration.
- Separate development, test, and production keys.
- Plan key rotation. With asymmetric keys, support key IDs (\`kid\`) and a controlled trusted-key set; never fetch arbitrary key URLs supplied by an untrusted token.
- Define a compromise procedure: rotate keys, invalidate affected sessions/refresh families, and force re-authentication where necessary.
- Never log passwords, access tokens, refresh tokens, authorization headers, or cookie values.

### Rate limiting and abuse controls

- Rate-limit login and refresh endpoints.
- Apply limits across account and network dimensions; account-only throttling can be abused for denial of service, while IP-only limits are bypassable.
- Emit metrics for login failures, refresh failures, reuse events, and rate-limit decisions.
- Avoid high-cardinality or sensitive labels in metrics.
- Alert on abnormal spikes and refresh-token reuse.
- Keep audit events free of raw secrets.

### Database lifecycle

- Use UTC-aware timestamps.
- Add indexes and uniqueness constraints for lookup and integrity.
- Define cleanup/retention for expired refresh records.
- Keep token state transitions transactional.
- Consider whether account disable/delete should revoke all refresh families.
- Ensure migrations can be deployed safely and rolled back or forward-fixed.

### Error handling

- Use generic login failure responses to reduce account enumeration.
- Return 401 for missing/invalid authentication; use 403 when the authenticated principal lacks permission (subject to API conventions).
- Do not expose token parsing details, signature errors, or database state to clients.
- Log a safe internal reason code, not the credential.

---

## 14. Test strategy and security invariants

Test observable behavior, not only helper functions.

### Password and identity tests

- Correct password verifies; incorrect password fails.
- Same password with independently generated salts yields different encoded hashes but both verify.
- Password hash never appears in API response or logs.
- Unknown account and wrong password have indistinguishable external errors.
- Duplicate identity constraints behave correctly under concurrent registration.
- Disabled/deleted users cannot authenticate or use protected endpoints.

### Access-token tests

- Valid token succeeds.
- Malformed token, invalid signature, wrong algorithm, wrong issuer, wrong audience, expired token, and not-yet-valid token fail.
- Missing/invalid subject fails.
- User disabled after token issuance is rejected according to the chosen current-status policy.
- Client-supplied user IDs cannot override the authenticated principal.

### Refresh-token tests

- Valid active token rotates successfully.
- Unknown, expired, revoked, and consumed tokens are rejected.
- Old token fails after successful rotation.
- Reuse triggers the documented family-revocation policy.
- Two concurrent refreshes result in exactly one successful consumption.
- Logout revokes the intended family.
- Password reset/change revokes sessions according to policy.
- Expired records are cleaned up without affecting active records.

### Authorization tests

- User A cannot update/delete User B's post by changing a path/body ID.
- Private-account and follow-related rules are enforced in application use cases, not assumed from authentication.
- Every protected route has explicit authentication/authorization expectations.

### Property/integration testing

Use the project's pytest/async test stack and a real PostgreSQL instance for transaction/locking behavior. Unit tests with mocked repositories cannot prove row-locking or concurrent refresh correctness. Add integration tests that exercise the actual migration and concurrent requests.

---

## 15. Delivery plan and exit criteria

Build incrementally; do not implement every security feature in one large change.

### Slice 1 — Credential persistence and password verification

- Define identity model and migration.
- Add uniqueness/check constraints.
- Implement Argon2id hashing and verification.
- Add registration/login service tests.

**Exit:** passwords are never stored or returned in plaintext; duplicate and concurrent identity creation are safe.

### Slice 2 — Access-token authentication

- Define token claims and configuration.
- Implement signing/validation with explicit algorithm and issuer/audience checks.
- Add FastAPI dependency and protected test endpoint.
- Add account-status checks.

**Exit:** valid access token resolves the correct active user; invalid/expired/tampered tokens fail closed.

### Slice 3 — Refresh lifecycle

- Add refresh-token persistence.
- Implement opaque token generation and fingerprint lookup.
- Implement atomic rotation, expiry, logout, and family reuse handling.
- Add concurrency/integration tests.

**Exit:** old tokens cannot be used after rotation; concurrent refresh cannot mint multiple successors; logout and reuse policy work.

### Slice 4 — Authorization and operational hardening

- Add resource ownership checks.
- Add rate limiting, safe audit events, metrics, and secret configuration.
- Decide browser/mobile storage and CSRF policy.
- Document key rotation and incident response.

**Exit:** protected use cases enforce ownership; secrets are not logged; abuse signals are observable; deployment configuration is reviewed.

### Week 2 end-to-end acceptance scenario

1. Register a user.
2. Log in and receive access + refresh credentials.
3. Create a post with the access token.
4. Reject the expired access token.
5. Refresh and receive a new access + refresh pair.
6. Reject the old refresh token.
7. Revoke the family on logout or detected reuse.
8. Prove a different user cannot modify the first user's post.

---

## 16. Decisions still to make before implementation

These are product/deployment decisions, not details to guess:

1. **Client type:** browser, native mobile, or both? This changes refresh-token transport and CSRF requirements.
2. **Login identifier:** email, username, or either? Define normalization and uniqueness.
3. **Session policy:** fixed refresh expiry or sliding expiry with an absolute maximum lifetime?
4. **Access-token revocation:** accept the short expiry window, or require immediate revocation?
5. **Multiple devices:** one refresh-token family per login/device, with a “log out all devices” operation?
6. **External identity:** add Google/OIDC now or keep the provider abstraction but defer it?
7. **Password recovery and MFA:** required for the first product milestone or later?

Record the final choice and rationale in an ADR under \`docs/adr/\` when the client/product constraints are known.

---

## 17. Key principles to retain

- A password hash is verified at login; it is not decrypted and is not checked on every request.
- Argon2id is for human passwords; fast cryptographic fingerprints are appropriate for high-entropy random refresh tokens.
- JWT signature verification establishes issuer authenticity and integrity, not presenter identity or token non-theft.
- The JWT subject (\`sub\`) identifies the user after the token is verified.
- JWT expiry is checked from \`exp\`; refresh expiry/revocation is server-side state.
- Refresh rotation is a transactional, single-use state transition—not merely issuing another token.
- Reuse detection is a risk signal; it is not proof of theft.
- Authentication and authorization are separate checks.
- API schemas, domain models, and ORM models have different responsibilities.
- Sessions can scale across instances when backed by shared state. JWT shifts coordination toward signing-key distribution and revocation.
- Staff-level design means stating assumptions, invariants, failure modes, operational responsibilities, and trade-offs—not just selecting a library.
