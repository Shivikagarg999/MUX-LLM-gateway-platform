# Mux

A multi-provider LLM gateway built with FastAPI — automatic failover across providers, semantic response caching, and per-key auth/rate limiting, all running on free-tier APIs only (Groq + Gemini).

Exposes an **OpenAI-compatible** `/v1/chat/completions` endpoint, so any existing OpenAI SDK client can point at Mux by just changing `base_url`.

## Why this exists

Most "LLM wrapper" projects call one provider and stop. Mux is a small piece of real infrastructure: if Groq rate-limits you, it falls back to Gemini automatically; if you ask something semantically similar to a recent question, it skips the LLM call entirely and serves a cached answer. Both behaviors are tested end-to-end, not just described.

## Architecture

```
Client
  │  Authorization: Bearer mux_xxx
  ▼
┌──────────────────────────────────────────┐
│                  Mux                     │
│                                           │
│  1. Auth          HTTPBearer + SQLite    │
│  2. Rate limit     token bucket / key    │
│  3. Semantic cache check                 │
│       hit  → return cached response      │
│       miss → continue                    │
│  4. Router (fallback chain)              │
│       Groq → Gemini (any error falls     │
│       through to the next provider)      │
│  5. Cache the response + log usage       │
└──────────────────────────────────────────┘
       │                      │
       ▼                      ▼
   Groq API               Gemini API
 (OpenAI-compatible)   (OpenAI-compatible)
```

## Features

- **OpenAI-compatible API** — `/v1/chat/completions` accepts the standard request shape (`model`, `messages`, `temperature`, etc.)
- **Automatic failover** — tries Groq first, falls back to Gemini on any error (rate limit, bad key, timeout, server error)
- **Semantic caching** — embeds prompts locally with `sentence-transformers` (no API call, no cost) and returns a cached response on a similarity match ≥ 0.92, even if the wording differs
- **Per-key auth + rate limiting** — Bearer tokens hashed in SQLite, token-bucket rate limiting per key
- **Usage metering** — `/stats` reports request counts, cache hit rate, tokens used, and tokens saved by caching, scoped to the calling key

## Setup

```bash
git clone <this repo>
cd mux
python -m venv .venv
.venv\Scripts\Activate.ps1      # Windows PowerShell
pip install -r requirements.txt
```

Create `.env`:
```
GROQ_API_KEY=your_groq_key
GEMINI_API_KEY=your_gemini_key
```

Issue yourself an API key:
```bash
python -m scripts.create_key "my-app" --rate-limit 20
```
This prints a `mux_...` key once — save it, it isn't stored anywhere in plaintext.

Run the server:
```bash
uvicorn app.main:app --reload
```

Interactive docs (with an "Authorize" button for your Bearer key) at `http://127.0.0.1:8000/docs`.

## Usage

```bash
curl -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer mux_..." \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama-3.3-70b-versatile",
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 100
  }'
```

Response includes `mux_provider` (which provider actually answered) and `mux_cache` (`hit`/`miss`).

```bash
curl http://127.0.0.1:8000/stats -H "Authorization: Bearer mux_..."
```

## Design decisions & tradeoffs

These were deliberate scope calls, not oversights:

- **No local-model (Ollama) fallback tier.** A self-hosted fallback only works if the host machine has enough RAM, which most free-tier deploy targets don't. A fallback tier that's not actually live in production is worse than not having one — so this was cut rather than shipped half-working.
- **SQLite, not Postgres.** All SQL is isolated in `app/db.py`. For a single-instance deployment SQLite is genuinely sufficient; migrating to Postgres later (for multi-instance scaling) is a contained change to one file, not a rewrite.
- **Linear-scan cosine similarity, not FAISS/Chroma.** At the scale this cache will actually see (dozens to low-thousands of entries), comparing against every cached embedding is simpler and fast enough. An ANN index is the right call once the cache reaches tens of thousands of entries — not before.
- **In-memory rate-limit buckets.** Works correctly for one instance; resets on restart and doesn't share state across multiple instances. Would move to Redis for horizontal scaling.

## Deploying on an Ubuntu VPS

1. Install Python and git:
   ```bash
   sudo apt update
   sudo apt install -y python3 python3-venv python3-pip git
   ```

2. Clone and set up the venv:
   ```bash
   git clone <your-repo-url> mux
   cd mux
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Create `.env` with your real keys (same as local) and issue a production API key:
   ```bash
   python -m scripts.create_key "production" --rate-limit 20
   ```

4. Run it as a systemd service so it survives reboots and crashes. Create `/etc/systemd/system/mux.service`:
   ```ini
   [Unit]
   Description=Mux LLM Gateway
   After=network.target

   [Service]
   User=<your-linux-user>
   WorkingDirectory=/home/<your-user>/mux
   EnvironmentFile=/home/<your-user>/mux/.env
   ExecStart=/home/<your-user>/mux/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

   > Deliberately **no `--workers` flag.** Rate-limit buckets live in memory per-process — running multiple workers would let a client get N× their stated limit by landing on different workers. Scaling to multiple workers safely requires moving rate-limit state to SQLite/Redis first.

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable mux
   sudo systemctl start mux
   sudo systemctl status mux
   ```

5. (Optional) Put nginx in front for a real domain + HTTPS:
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```
   Then `sudo certbot --nginx -d your-domain.com` for free HTTPS via Let's Encrypt.

`mux.db` lives on the VPS's own disk, so it persists naturally across restarts and redeploys — no separate volume setup needed, unlike on ephemeral-disk PaaS platforms.

## Tech stack

FastAPI · httpx · sentence-transformers (local embeddings) · SQLite · Groq API · Gemini API
