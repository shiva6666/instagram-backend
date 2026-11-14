import random
from datetime import UTC, datetime
from pathlib import Path
from runpy import run_path
from uuid import uuid4

from faker import Faker
from pydantic import EmailStr, TypeAdapter

seed_script = run_path(str(Path(__file__).parents[1] / "scripts" / "seed.py"))
build_follows = seed_script["build_follows"]
build_users = seed_script["build_users"]


def test_build_follows_respects_requested_count() -> None:
    names = ("demo_alice", "demo_bob", "demo_charlie", "demo_david")
    users = [
        {"username": name, "id": uuid4(), "is_private": name == "demo_bob"}
        for name in names
    ]
    user_ids = [user["id"] for user in users]

    follows = build_follows(
        users,
        user_ids,
        random.Random(1),
        2,
        datetime.now(UTC),
    )

    expected_edges = {
        (users[0]["id"], users[1]["id"]),
        (users[2]["id"], users[1]["id"]),
    }
    assert len(follows) == 2
    assert {(follow[0], follow[1]) for follow in follows} == expected_edges


def test_seeded_emails_are_accepted_by_auth_schema() -> None:
    users, _ = build_users(
        4,
        random.Random(1),
        Faker("en_US"),
        datetime.now(UTC),
    )
    validate_email = TypeAdapter(EmailStr).validate_python

    for user in users:
        validate_email(user["email"])
