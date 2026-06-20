import time

_buckets = {}


def check_rate_limit(key_id: int, limit_per_minute: int) -> bool:
    now = time.monotonic()
    bucket = _buckets.get(key_id)

    if bucket is None:
        bucket = {"tokens": float(limit_per_minute), "last_refill": now}
        _buckets[key_id] = bucket

    elapsed = now - bucket["last_refill"]
    refill_rate = limit_per_minute / 60.0
    bucket["tokens"] = min(limit_per_minute, bucket["tokens"] + elapsed * refill_rate)
    bucket["last_refill"] = now

    if bucket["tokens"] >= 1:
        bucket["tokens"] -= 1
        return True

    return False
