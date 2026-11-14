"""Create a small, repeatable Instagram demo dataset in PostgreSQL.

Run with `make seed`. All demo users can log in with the documented local
password. The script is additive and idempotent: it never truncates or deletes
existing application data.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

import asyncpg
from argon2 import PasswordHasher
from faker import Faker

from app.core.config import settings

DEFAULT_USERS = 30
DEFAULT_POSTS = 180
DEFAULT_FOLLOWS = 150
DEFAULT_SEED = 20261114
DEMO_PASSWORD = "DemoPassword123!"
HISTORY_DAYS = 180

DEMO_ACCOUNTS = (
    ("demo_alice", "Alice", False),
    ("demo_bob", "Bob", True),
    ("demo_charlie", "Charlie", False),
    ("demo_david", "David", True),
)

IMAGE_IDS = (
    "photo-1500530855697-b586d89ba3ee",
    "photo-1470770841072-f978cf4d019e",
    "photo-1500534623283-312aade485b7",
    "photo-1518837695005-2083093ee35b",
    "photo-1493246507139-91e8fad9978e",
    "photo-1470252649378-9c29740c9fa8",
    "photo-1501785888041-af3ef285b470",
    "photo-1472214103451-9374bd1c798e",
)


def stable_id(kind: str, value: str) -> UUID:
    """Return a stable UUID so rerunning the seeder does not duplicate rows."""
    return uuid5(NAMESPACE_URL, f"instagram-demo:{kind}:{value}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--users", type=int, default=DEFAULT_USERS)
    parser.add_argument("--posts", type=int, default=DEFAULT_POSTS)
    parser.add_argument("--follows", type=int, default=DEFAULT_FOLLOWS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--dsn",
        default=os.environ.get("DATABASE_URL") or settings.database_url,
        help="PostgreSQL DSN; defaults to the application DATABASE_URL",
    )
    args = parser.parse_args()

    if not args.dsn:
        parser.error("DATABASE_URL or --dsn is required")
    if args.users < len(DEMO_ACCOUNTS):
        parser.error(f"--users must be at least {len(DEMO_ACCOUNTS)}")
    if min(args.posts, args.follows) < 0:
        parser.error("posts and follows must be non-negative")
    if args.follows > args.users * (args.users - 1):
        parser.error("follows cannot exceed users * (users - 1)")
    return args


def normalize_dsn(dsn: str) -> str:
    return dsn.replace("postgresql+asyncpg://", "postgresql://", 1)


def build_users(
    count: int, rng: random.Random, fake: Faker, now: datetime
) -> tuple[list[dict[str, object]], list[UUID]]:
    users: list[dict[str, object]] = []
    user_ids: list[UUID] = []

    for index in range(count):
        if index < len(DEMO_ACCOUNTS):
            username, display_name, is_private = DEMO_ACCOUNTS[index]
        else:
            username = f"demo_user_{index + 1:02d}"
            display_name = fake.first_name()
            is_private = rng.random() < 0.2

        user_id = stable_id("user", username)
        created_at = now - timedelta(days=rng.randint(0, HISTORY_DAYS))
        users.append(
            {
                "id": user_id,
                "username": username,
                "email": f"{username}@example.com",
                "bio": (
                    f"{display_name} | "
                    f"{fake.sentence(nb_words=7).rstrip('.')}."
                ),
                "avatar_key": None,
                "is_private": is_private,
                "status": "active",
                "created_at": created_at,
            }
        )
        user_ids.append(user_id)

    return users, user_ids


def build_posts(
    users: list[dict[str, object]],
    rng: random.Random,
    fake: Faker,
    now: datetime,
    count: int,
) -> tuple[list[tuple[object, ...]], list[tuple[object, ...]], list[UUID]]:
    user_ids = [user["id"] for user in users]
    weights = [max(1, len(users) - index) ** 1.35 for index in range(len(users))]
    posts: list[tuple[object, ...]] = []
    images: list[tuple[object, ...]] = []
    post_ids: list[UUID] = []

    for index in range(count):
        author_index = rng.choices(range(len(users)), weights=weights, k=1)[0]
        author = users[author_index]
        author_created_at = author["created_at"]
        assert isinstance(author_created_at, datetime)
        days_since_signup = max(0, (now - author_created_at).days)
        created_at = now - timedelta(
            days=rng.randint(0, min(HISTORY_DAYS, days_since_signup)),
            minutes=rng.randint(0, 1439),
        )
        post_id = stable_id("post", str(index))
        post_ids.append(post_id)

        caption = fake.sentence(nb_words=rng.randint(5, 16)).rstrip(".")
        posts.append(
            (
                post_id,
                user_ids[author_index],
                caption,
                False,
                created_at,
                created_at,
            )
        )

        image_count = rng.choices((1, 2, 3), weights=(7, 2, 1), k=1)[0]
        selected_images = rng.sample(IMAGE_IDS, image_count)
        for position, image_id in enumerate(selected_images):
            url = (
                f"https://images.unsplash.com/{image_id}"
                "?auto=format&fit=crop&w=1080&q=80"
            )
            images.append((post_id, position, url))

    return posts, images, post_ids


def build_follows(
    users: list[dict[str, object]],
    user_ids: list[UUID],
    rng: random.Random,
    count: int,
    now: datetime,
) -> list[tuple[object, ...]]:
    max_edges = len(user_ids) * (len(user_ids) - 1)
    target = min(count, max_edges)
    private_user_ids = {
        user["id"] for user in users if user["is_private"] is True
    }
    edges: dict[tuple[UUID, UUID], str] = {}

    # Explicit relationships make the private-account flows easy to explore.
    demo_edges = (
        ("demo_alice", "demo_bob"),
        ("demo_charlie", "demo_bob"),
        ("demo_bob", "demo_alice"),
        ("demo_alice", "demo_charlie"),
        ("demo_david", "demo_charlie"),
        ("demo_charlie", "demo_david"),
    )
    username_to_id = {str(user["username"]): user["id"] for user in users}
    for follower_name, following_name in demo_edges[:target]:
        follower_id = username_to_id[follower_name]
        following_id = username_to_id[following_name]
        status = "pending" if following_id in private_user_ids else "accepted"
        edges[(follower_id, following_id)] = status

    while len(edges) < target:
        follower_id, following_id = rng.sample(user_ids, 2)
        status = "pending" if following_id in private_user_ids else "accepted"
        edges[(follower_id, following_id)] = status

    return [
        (
            follower_id,
            following_id,
            status,
            now - timedelta(days=rng.randint(0, HISTORY_DAYS)),
        )
        for (follower_id, following_id), status in edges.items()
    ]


async def seed(args: argparse.Namespace) -> None:
    rng = random.Random(args.seed)
    fake = Faker("en_US")
    fake.seed_instance(args.seed)
    now = datetime.now(UTC)

    users, user_ids = build_users(args.users, rng, fake, now)
    posts, images, post_ids = build_posts(
        users, rng, fake, now, args.posts
    )
    follows = build_follows(users, user_ids, rng, args.follows, now)

    # Hash once: all local demo accounts intentionally share one password.
    password_hash = PasswordHasher().hash(DEMO_PASSWORD)
    identities = [
        (
            stable_id("auth-identity", str(user["username"])),
            user["id"],
            "password",
            user["email"],
            password_hash,
            now,
            now,
        )
        for user in users
    ]

    blocks: list[tuple[UUID, UUID]] = []
    if len(users) >= 10:
        blocks = [
            (user_ids[3], user_ids[4]),
            (user_ids[5], user_ids[8]),
        ]

    connection = await asyncpg.connect(normalize_dsn(args.dsn))
    try:
        async with connection.transaction():
            await connection.executemany(
                """
                INSERT INTO users (
                    id, username, email, bio, avatar_key, is_private,
                    status, created_at, updated_at
                )
                VALUES (
                    $1, $2::text::citext, $3::text::citext, $4, $5,
                    $6, $7, $8, $8
                )
                ON CONFLICT (id) DO NOTHING
                """,
                [
                    (
                        user["id"],
                        user["username"],
                        user["email"],
                        user["bio"],
                        user["avatar_key"],
                        user["is_private"],
                        user["status"],
                        user["created_at"],
                    )
                    for user in users
                ],
            )

            await connection.executemany(
                """
                INSERT INTO auth_identities (
                    id, user_id, provider, provider_subject, password_hash,
                    created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (id) DO NOTHING
                """,
                identities,
            )

            if posts:
                await connection.executemany(
                    """
                    INSERT INTO posts (
                        id, user_id, caption, is_private, created_at, updated_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    posts,
                )

            if images:
                await connection.executemany(
                    """
                    INSERT INTO post_images (post_id, position, url)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (post_id, position) DO NOTHING
                    """,
                    images,
                )

            if follows:
                await connection.executemany(
                    """
                    INSERT INTO follows (
                        follower_id, following_id, status, created_at
                    )
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (follower_id, following_id) DO NOTHING
                    """,
                    follows,
                )

            if blocks:
                await connection.executemany(
                    """
                    INSERT INTO user_blocks (blocker_id, blocked_id)
                    VALUES ($1, $2)
                    ON CONFLICT (blocker_id, blocked_id) DO NOTHING
                    """,
                    blocks,
                )

            counts = await connection.fetchrow(
                """
                SELECT
                    (SELECT count(*) FROM users
                     WHERE id = ANY($1::uuid[])) AS users,
                    (SELECT count(*) FROM auth_identities
                     WHERE user_id = ANY($1::uuid[])) AS auth_identities,
                    (SELECT count(*) FROM posts
                     WHERE id = ANY($2::uuid[])) AS posts,
                    (SELECT count(*) FROM post_images
                     WHERE post_id = ANY($2::uuid[])) AS post_images,
                    (SELECT count(*) FROM follows
                     WHERE follower_id = ANY($1::uuid[])
                       AND following_id = ANY($1::uuid[])) AS follows
                """,
                user_ids,
                post_ids,
            )
    finally:
        await connection.close()

    print("Demo data is ready.")
    print(
        "Rows present for this seed: "
        f"users={counts['users']}, "
        f"auth_identities={counts['auth_identities']}, "
        f"posts={counts['posts']}, "
        f"post_images={counts['post_images']}, "
        f"follows={counts['follows']}"
    )
    print("Demo login: demo_alice@example.com")
    print(f"Demo password: {DEMO_PASSWORD}")
    print("Other demo accounts: demo_bob, demo_charlie, demo_david")


def main() -> None:
    asyncio.run(seed(parse_args()))


if __name__ == "__main__":
    main()
