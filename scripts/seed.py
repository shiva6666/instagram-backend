"""Seed users, posts, and a skewed follow graph for local development.

The defaults create 10,000 users, 1,000,000 posts, and 100,000 follows.
Rows are sent to PostgreSQL with COPY in batches so the complete dataset is
never held in memory.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
import uuid
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, timedelta

import asyncpg
from faker import Faker

from app.core.config import settings

DEFAULT_USERS = 10_000
DEFAULT_POSTS = 1_000_000
DEFAULT_FOLLOWS = 100_000
DEFAULT_BATCH_SIZE = 5_000
POST_HISTORY_DAYS = 365


def uuid7(rng: random.Random, timestamp: datetime) -> uuid.UUID:
    """Return a UUIDv7 using the supplied timestamp and deterministic RNG."""
    timestamp_ms = int(timestamp.timestamp() * 1_000) & ((1 << 48) - 1)
    random_a = rng.getrandbits(12)
    random_b = rng.getrandbits(62)
    value = (timestamp_ms << 80) | (0x7 << 76) | (random_a << 64)
    value |= 0x2 << 62
    value |= random_b
    return uuid.UUID(int=value)


def chunks[T](items: Iterable[T], size: int) -> Iterable[list[T]]:
    batch: list[T] = []
    for item in items:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def weighted_user_index(rng: random.Random, user_count: int) -> int:
    """Pick a user with a long-tail popularity distribution."""
    rank = min(user_count, int(rng.paretovariate(1.16)))
    return rank - 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--users", type=int, default=DEFAULT_USERS)
    parser.add_argument("--posts", type=int, default=DEFAULT_POSTS)
    parser.add_argument("--follows", type=int, default=DEFAULT_FOLLOWS)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--seed", type=int, default=20261106)
    parser.add_argument(
        "--dsn",
        default=os.environ.get("DATABASE_URL") or settings.database_url,
        help="PostgreSQL DSN; defaults to DATABASE_URL",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Delete existing users, posts, and follows before seeding",
    )
    args = parser.parse_args()
    if not args.dsn:
        parser.error("DATABASE_URL or --dsn is required")
    if min(args.users, args.posts, args.follows, args.batch_size) < 0:
        parser.error("counts and batch size must be non-negative")
    if args.batch_size == 0:
        parser.error("batch size must be greater than zero")
    if (args.posts or args.follows) and args.users == 0:
        parser.error("users must be greater than zero when seeding posts or follows")
    if args.follows and args.users < 2:
        parser.error("at least two users are required to seed follows")
    if args.follows > args.users * (args.users - 1):
        parser.error("follows cannot exceed users * (users - 1)")
    return args


def normalize_dsn(dsn: str) -> str:
    return dsn.replace("postgresql+asyncpg://", "postgresql://", 1)


async def copy_rows(
    connection: asyncpg.Connection,
    table: str,
    columns: Sequence[str],
    rows: Iterable[tuple[object, ...]],
    batch_size: int,
) -> None:
    for batch in chunks(rows, batch_size):
        await connection.copy_records_to_table(
            table,
            records=batch,
            columns=list(columns),
        )


async def seed(args: argparse.Namespace) -> None:
    rng = random.Random(args.seed)
    fake = Faker()
    fake.seed_instance(args.seed)
    now = datetime.now(UTC)

    connection = await asyncpg.connect(normalize_dsn(args.dsn))
    try:
        async with connection.transaction():
            if args.truncate:
                await connection.execute("TRUNCATE follows, posts, users CASCADE")

            user_ids: list[uuid.UUID] = []
            usernames: set[str] = set()

            def user_rows() -> Iterable[tuple[object, ...]]:
                for _ in range(args.users):
                    created_at = now - timedelta(days=rng.random() * POST_HISTORY_DAYS)
                    user_id = uuid7(rng, created_at)
                    username = fake.user_name().lower()
                    while username in usernames:
                        username = f"{username}{rng.randrange(10_000)}"
                    usernames.add(username)
                    user_ids.append(user_id)
                    yield (
                        user_id,
                        username,
                        f"{username}@example.test",
                        fake.sentence(nb_words=8),
                        False,
                        "active",
                        created_at,
                        created_at,
                    )

            # asyncpg's binary COPY protocol has no encoder for PostgreSQL's
            # citext type. Copy through text columns, then let PostgreSQL cast
            # into citext during the insert.
            await connection.execute(
                """
                CREATE TEMP TABLE seed_users (
                    id UUID NOT NULL,
                    username TEXT NOT NULL,
                    email TEXT NOT NULL,
                    bio TEXT,
                    is_private BOOLEAN NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                ) ON COMMIT DROP
                """
            )
            await copy_rows(
                connection,
                "seed_users",
                (
                    "id",
                    "username",
                    "email",
                    "bio",
                    "is_private",
                    "status",
                    "created_at",
                    "updated_at",
                ),
                user_rows(),
                args.batch_size,
            )
            await connection.execute(
                """
                INSERT INTO users (
                    id, username, email, bio, is_private, status,
                    created_at, updated_at
                )
                SELECT
                    id, username, email, bio, is_private, status,
                    created_at, updated_at
                FROM seed_users
                """
            )

            def post_rows() -> Iterable[tuple[object, ...]]:
                for _ in range(args.posts):
                    created_at = now - timedelta(days=rng.random() * POST_HISTORY_DAYS)
                    author_id = user_ids[weighted_user_index(rng, args.users)]
                    yield (
                        uuid7(rng, created_at),
                        author_id,
                        fake.sentence(nb_words=rng.randint(4, 18)),
                        created_at,
                        created_at,
                    )

            await copy_rows(
                connection,
                "posts",
                ("id", "user_id", "caption", "created_at", "updated_at"),
                post_rows(),
                args.batch_size,
            )

            def follow_rows() -> Iterable[tuple[object, ...]]:
                edges: set[tuple[uuid.UUID, uuid.UUID]] = set()
                while len(edges) < args.follows:
                    follower_index = rng.randrange(args.users)
                    following_index = weighted_user_index(rng, args.users)
                    if follower_index == following_index:
                        continue
                    edge = (user_ids[follower_index], user_ids[following_index])
                    if edge in edges:
                        continue
                    edges.add(edge)
                    yield (*edge, "accepted", now)

            await copy_rows(
                connection,
                "follows",
                ("follower_id", "following_id", "status", "created_at"),
                follow_rows(),
                args.batch_size,
            )
    finally:
        await connection.close()

    print(
        f"Seeded users={args.users}, posts={args.posts}, follows={args.follows} "
        f"with seed={args.seed}"
    )


def main() -> None:
    asyncio.run(seed(parse_args()))


if __name__ == "__main__":
    main()
