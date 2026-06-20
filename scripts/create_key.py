import argparse
import secrets
from datetime import datetime, timezone

from app.auth import hash_key
from app.db import get_connection, init_db


def create_key(name: str, rate_limit: int) -> str:
    init_db()
    raw_key = "mux_" + secrets.token_urlsafe(32)

    conn = get_connection()
    conn.execute(
        "INSERT INTO api_keys (key_hash, name, rate_limit_per_minute, is_active, created_at) VALUES (?, ?, ?, 1, ?)",
        (hash_key(raw_key), name, rate_limit, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()

    return raw_key


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a new Mux API key")
    parser.add_argument("name", help="Label for who/what this key is for")
    parser.add_argument("--rate-limit", type=int, default=20, help="Requests allowed per minute")
    args = parser.parse_args()

    key = create_key(args.name, args.rate_limit)
    print(f"Created key for '{args.name}' (limit: {args.rate_limit}/min)")
    print(key)
    print("Save this now -- it will not be shown again.")
