import json
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from app.db import get_connection

_model = SentenceTransformer("all-MiniLM-L6-v2")

SIMILARITY_THRESHOLD = 0.92


def embed(text: str) -> list:
    return _model.encode(text, normalize_embeddings=True).tolist()


def extract_prompt(messages: list) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return message["content"]
    return ""


def find_similar(query_embedding: list) -> Optional[dict]:
    query_vector = np.array(query_embedding)

    conn = get_connection()
    rows = conn.execute("SELECT prompt_text, embedding, response_json FROM cache_entries").fetchall()
    conn.close()

    best_score = -1.0
    best_row = None

    for row in rows:
        candidate_vector = np.array(json.loads(row["embedding"]))
        score = float(np.dot(query_vector, candidate_vector))
        if score > best_score:
            best_score = score
            best_row = row

    if best_row is not None and best_score >= SIMILARITY_THRESHOLD:
        return {
            "response": json.loads(best_row["response_json"]),
            "similarity": best_score,
            "matched_prompt": best_row["prompt_text"],
        }

    return None


def store(prompt_text: str, embedding: list, response: dict) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO cache_entries (prompt_text, embedding, response_json, created_at) VALUES (?, ?, ?, ?)",
        (prompt_text, json.dumps(embedding), json.dumps(response), datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()
