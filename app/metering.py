from datetime import datetime, timezone

from app.db import get_connection


def log_request(api_key_id: int, provider: str, cache_hit: bool, usage: dict) -> None:
    usage = usage or {}

    conn = get_connection()
    conn.execute(
        """
        INSERT INTO request_logs
            (api_key_id, provider, cache_hit, prompt_tokens, completion_tokens, total_tokens, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            api_key_id,
            provider,
            1 if cache_hit else 0,
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0),
            usage.get("total_tokens", 0),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def get_stats(api_key_id: int) -> dict:
    conn = get_connection()
    rows = conn.execute(
        "SELECT provider, cache_hit, total_tokens FROM request_logs WHERE api_key_id = ?",
        (api_key_id,),
    ).fetchall()
    conn.close()

    total_requests = len(rows)
    cache_hits = sum(1 for r in rows if r["cache_hit"])
    total_tokens = sum(r["total_tokens"] for r in rows)
    tokens_saved_by_cache = sum(r["total_tokens"] for r in rows if r["cache_hit"])

    requests_by_provider = {}
    for r in rows:
        if r["cache_hit"]:
            continue
        key = r["provider"] or "unknown"
        requests_by_provider[key] = requests_by_provider.get(key, 0) + 1

    return {
        "total_requests": total_requests,
        "cache_hits": cache_hits,
        "cache_misses": total_requests - cache_hits,
        "cache_hit_rate": round(cache_hits / total_requests, 4) if total_requests else 0.0,
        "total_tokens_used": total_tokens,
        "tokens_saved_by_cache": tokens_saved_by_cache,
        "requests_by_provider": requests_by_provider,
    }
