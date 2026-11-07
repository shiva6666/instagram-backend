# Users Module

Concepts learned while reading `app/modules/users/` — covering architecture, design decisions, and end-to-end data flow.

---

## 1. Architecture — Three-Layer Separation

The users module is built using **Domain-Driven Design (DDD)** and **Ports & Adapters (Hexagonal Architecture)**.

```
API / Routes
     │
     ▼
UserService          ← Business Logic (use cases, validation, invariants)
     │
     ▼
UserRepository       ← Port/Contract (Protocol — the "what")
     │
     ▼
SqlAlchemyUserRepository  ← Adapter (the "how" — PostgreSQL/SQLAlchemy)
```

Each layer has a **single responsibility**:

| Layer | File | Responsibility |
| :--- | :--- | :--- |
| Domain Entity | `models.py` | Pure data structure, no framework coupling |
| Repository Protocol | `repository.py` | Defines storage contract |
| Repository Implementation | `repository.py` | Translates domain ↔ database |
| Business Logic | `service.py` | Use cases, validation, orchestration |

---

## 2. The Domain Entity — `User` dataclass (`models.py`)

```python
@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    username: str
    email: str
    bio: str | None
    is_private: bool
    status: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
```

**Key decisions:**
- `frozen=True` — Immutable after creation. Prevents accidental mutation across layers.
- `slots=True` — Reduces memory overhead per instance.
- **Zero framework imports** — no SQLAlchemy, no FastAPI. Completely portable.
- `deleted_at: datetime | None` — Soft deletes: accounts can be "deactivated" without being permanently erased from the database.

---

## 3. The Repository Pattern (`repository.py`)

### Why two things instead of one?

| Component | Type | Answers |
| :--- | :--- | :--- |
| `UserRepository` | `Protocol` (interface) | *"What operations do we need?"* |
| `SqlAlchemyUserRepository` | Concrete class | *"How do we do it with PostgreSQL?"* |

**`UserRepository` (Protocol)** is the **port** — an abstract contract the service depends on:

```python
class UserRepository(Protocol):
    async def add(self, user: User) -> User: ...
    async def get_by_id(self, user_id: UUID) -> User | None: ...
    async def get_by_username(self, username: str) -> User | None: ...
    async def get_by_email(self, email: str) -> User | None: ...
```

**`SqlAlchemyUserRepository`** is the **adapter** — the concrete PostgreSQL implementation.

**Why not merge them?** If `UserService` depended directly on `SqlAlchemyUserRepository`:
- Unit tests would require a live PostgreSQL database.
- Swapping the database (e.g. to Redis or DynamoDB) would require rewriting business logic.
- Wrapping with a caching layer would be impossible without touching the service.

**Using `Protocol` (not ABC):**
- `SqlAlchemyUserRepository` does **not** need to inherit from `UserRepository`.
- As long as it has matching method signatures, type checkers (`mypy`, `pyright`) accept it.
- Zero runtime overhead.

### `add()` method — line by line

```python
async def add(self, user: User) -> User:
    # 1. Translate domain entity → SQLAlchemy ORM row (data boundary crossing)
    row = UserRow(id=user.id, username=user.username, ...)

    # 2. Register with session's identity map (no SQL yet)
    self._session.add(row)

    try:
        # 3. Send pending INSERT to PostgreSQL, inside the current transaction
        #    flush() ≠ commit() — the transaction is not finalized yet
        await self._session.flush()

    except IntegrityError as error:
        # 4. Clean up poisoned session state
        await self._session.rollback()
        # 5. Translate low-level DB error → high-level domain error
        raise UserAlreadyExistsError from error

    # 6. Convert ORM row back to pure immutable domain entity
    return _to_domain(row)
```

**`flush()` vs `commit()`:**
- `flush()` — Sends SQL to the DB within the current transaction. Triggers constraint checks. Does **not** finalize.
- `commit()` — Finalizes the transaction permanently. Only the transaction manager (the route handler) should commit.

**Exception normalization:**
- `IntegrityError` (SQLAlchemy) → `UserAlreadyExistsError` (domain).
- Callers never need to know about SQL error codes.

---

## 4. The Service Layer (`service.py`)

### Why is it needed?

Without a service layer, business logic leaks into API routes. That means:
- Duplicate logic across HTTP routes, CLI commands, and background workers.
- Business rules (normalize username, set `status="active"`) scattered everywhere.
- Impossible to unit-test without booting an HTTP server.

`UserService` is the **single source of truth** for all user-related business rules.

### Constructor — Dependency Injection

```python
class UserService:
    def __init__(
        self,
        repository: UserRepository,            # depends on the interface, not SQLAlchemy
        id_factory: Callable[[], UUID] = new_uuid7,  # injectable for testing
    ) -> None:
```

- `repository: UserRepository` — Accepts any object that satisfies the protocol. In production: `SqlAlchemyUserRepository`. In tests: `FakeUserRepository` (in-memory dict).
- `id_factory` — Defaults to `new_uuid7` in production. In tests, inject `lambda: fixed_uuid` for deterministic IDs.

### `create_user()` — step by step

```python
async def create_user(self, *, username: str, email: str, bio=None, is_private=False):
```
- `*` forces keyword-only arguments — prevents swapping `username` and `email` by accident.

```python
    normalized_username = username.strip().lower()   # "  Alice  " → "alice"
    normalized_email    = email.strip().lower()      # " Alice@Example.com " → "alice@example.com"
```
- Normalization happens in the service, not the API or the database.

```python
    if not normalized_username: raise ValueError("username must not be empty")
    if not normalized_email:    raise ValueError("email must not be empty")
```
- Guards against whitespace-only strings becoming empty after stripping.

```python
    if await self._repository.get_by_username(normalized_username) is not None:
        raise UserAlreadyExistsError("username is already in use")
    if await self._repository.get_by_email(normalized_email) is not None:
        raise UserAlreadyExistsError("email is already in use")
```
- Proactive duplicate check **before** INSERT — produces a clear, field-specific error message.

```python
    now = datetime.now(UTC)
    return await self._repository.add(
        User(
            id=self._id_factory(),
            status="active",        # always set by service, never by the caller
            created_at=now,
            updated_at=now,         # same timestamp for both at creation
            ...
        )
    )
```

---

## 5. Key Design Decisions

### UUIDv7 over UUIDv4

```python
def new_uuid7() -> uuid.UUID:
    timestamp_ms = int(datetime.now(UTC).timestamp() * 1_000) & ((1 << 48) - 1)
    value = timestamp_ms << 80
    ...
```

| | UUIDv4 | UUIDv7 |
| :--- | :--- | :--- |
| Structure | Fully random | 48-bit timestamp prefix + random suffix |
| DB index behavior | Random insertions → B-tree fragmentation | Time-ordered → sequential inserts, efficient B-tree |
| Sortable | ❌ | ✅ (by creation time) |
| Guessable | ❌ | ❌ (random suffix) |

### PostgreSQL `CITEXT` for username/email columns

- `CITEXT` = Case-Insensitive TEXT.
- Stores as-is but compares case-insensitively at the database level.
- Combined with app-level `.lower()` normalization, uniqueness is enforced at both layers (defence in depth).

### Soft Deletes (`deleted_at`)

- `deleted_at = None` → account is active.
- `deleted_at = <timestamp>` → account is deactivated/deleted.
- Keeps data for grace periods (Instagram lets you recover an account for 30 days).
- Never actually removes the row from the DB.

---

## 6. Testability — `FakeUserRepository`

Because `UserService` depends on the `UserRepository` **Protocol**, tests can inject a pure in-memory fake:

```python
class FakeUserRepository:
    def __init__(self):
        self.users: dict[UUID, User] = {}

    async def add(self, user: User) -> User:
        if any(u.username == user.username or u.email == user.email
               for u in self.users.values()):
            raise UserAlreadyExistsError
        self.users[user.id] = user
        return user

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)
    ...
```

**Benefits:**
- Tests run in milliseconds — no Docker, no migrations, no database.
- Tests are deterministic — no network, no I/O, no race conditions.
- Tests verify real business logic — the fake behaves like a real repository.

---

## 7. End-to-End Data Flow — Real Example

**Request:**
```http
POST /users
{ "username": "  Alice  ", "email": " Alice@Example.com ", "bio": "📸", "is_private": false }
```

```
Step 1  API Route
        receives raw JSON → calls service.create_user(username="  Alice  ", email=" Alice@Example.com ")

Step 2  UserService — Normalize
        "  Alice  "          → "alice"
        " Alice@Example.com " → "alice@example.com"

Step 3  UserService — Validate
        "alice" is not empty            ✅
        "alice@example.com" is not empty ✅

Step 4  UserService — Uniqueness Check
        SELECT WHERE username = 'alice'           → None ✅
        SELECT WHERE email = 'alice@example.com'  → None ✅

Step 5  UserService — Build Domain Entity
        User(
            id         = "0193d2f4-a3b1-7e02-85c4-1a2b3c4d5e6f",  ← UUIDv7
            username   = "alice",
            email      = "alice@example.com",
            bio        = "📸",
            is_private = False,
            status     = "active",    ← set by service
            created_at = 2026-11-08T02:25:53Z,
            updated_at = 2026-11-08T02:25:53Z,
            deleted_at = None,
        )

Step 6  SqlAlchemyUserRepository.add() — Translate to ORM
        User  →  UserRow (SQLAlchemy model)

Step 7  session.add(row)
        Marks row as PENDING in SQLAlchemy identity map. No SQL sent yet.

Step 8  await session.flush()
        Sends SQL inside the current transaction:

        INSERT INTO users (id, username, email, bio, is_private, status, created_at, updated_at, deleted_at)
        VALUES ('0193d2f4-...', 'alice', 'alice@example.com', '📸', false, 'active',
                '2026-11-08 02:25:53+00', '2026-11-08 02:25:53+00', NULL);

        PostgreSQL responds: INSERT 0 1 ✅

Step 9  _to_domain(row)
        UserRow  →  User (pure dataclass, detached from session)

Step 10 HTTP Response
        201 Created
        {
          "id": "0193d2f4-a3b1-7e02-85c4-1a2b3c4d5e6f",
          "username": "alice",
          "email": "alice@example.com",
          "bio": "📸",
          "is_private": false,
          "status": "active",
          "created_at": "2026-11-08T02:25:53Z",
          "updated_at": "2026-11-08T02:25:53Z",
          "deleted_at": null
        }
```

### Failure path — duplicate username

```
Second request: POST /users { "username": "ALICE", ... }

Step 2  Normalize: "ALICE" → "alice"
Step 4  get_by_username("alice") → returns existing User  (not None)
        raise UserAlreadyExistsError("username is already in use")

→ 409 Conflict  { "detail": "username is already in use" }

No INSERT was attempted. The error is caught before touching the database.
```

### Data transformation at every boundary

```
HTTP JSON     →   "  Alice  "              raw string
Service in    →   "  Alice  "              still raw
Service norm  →   "alice"                  clean string
Service out   →   User(username="alice")   immutable dataclass
Repo in       →   User(username="alice")   immutable dataclass
Repo internal →   UserRow(username="alice") SQLAlchemy ORM (lives ONLY inside repo)
PostgreSQL    →   CITEXT 'alice'           stored in DB
Repo out      →   User(username="alice")   back to immutable dataclass
HTTP JSON     →   "alice"                  serialized
```

---

## Questions to Revisit

- Where does `session.commit()` actually happen — which layer owns the transaction lifecycle?
- How will the router handle `UserAlreadyExistsError` and `UserNotFoundError` and map them to HTTP status codes?
- Will `get_user` be extended to also look up by username (for public profile pages)?
- Should `status` be an `Enum` instead of a bare `str` to prevent invalid values?
