# Sarjy

A voice assistant you talk to in the browser. It remembers facts about you across conversations and can search the web for anything current.

- **Voice:** speech-to-speech over WebRTC with the OpenAI Realtime API. You can interrupt it mid-sentence.
- **Memory:** tell it "my favorite color is green", and in a later conversation "what's my favorite color?" works. A side panel shows everything it remembers, and you can delete any of it.
- **Web search:** news, weather, scores, prices and anything else recent, through OpenAI's hosted web search tool.

## Why web search

A voice assistant fails most often on anything recent or outside its training data, and those are exactly the questions people ask out loud: the weather, the news, whether a shop is open. Web search turns those dead ends into answers, and one API covers all of them instead of a single narrow domain. It also works with memory: the assistant puts remembered context such as your city into the query, so "do I need an umbrella?" just works.

## Architecture

```
                        audio + events (WebRTC)
   Browser  ◀──────────────────────────────────────▶  OpenAI Realtime API
   (React)                                             (speech-to-speech model)
      │
      │  /api/v1  (same origin, signed cookie)
      ▼
   FastAPI  ──────▶  Postgres (users, memories)
      │
      └─────────▶  OpenAI API: client secrets, Responses + hosted web search
```

- **The browser talks to OpenAI directly.** The backend mints a short-lived key with `POST /v1/realtime/client_secrets`; the browser uses it to open the WebRTC call. Audio never passes through our server, and the standard API key never leaves it.
- **Memory is loaded at the start of each call.** The newest 200 facts go into the session instructions, so recall costs no extra round trip and the model can use facts unprompted. The model saves and deletes facts through `remember` and `forget` tools.
- **Tool calls are relayed by the browser.** The model's tool requests arrive on the WebRTC data channel; the browser forwards them to the backend, which checks the session cookie and only touches that user's data. OpenAI documents this pattern for browser clients.
- **Identity is a shared passcode plus an anonymous browser ID.** Entering the passcode creates a user and sets a signed, HttpOnly cookie. Memory belongs to that browser.

`PLAN.md` records every design decision, why it was made, and what was set aside.

## Run it

You need Docker and an OpenAI API key.

```sh
cp .env.example .env    # then fill in OPENAI_API_KEY, ACCESS_PASSCODE, SESSION_SECRET, POSTGRES_PASSWORD
docker compose up --build
```

Open http://localhost:8000, enter the passcode, start a call, and allow the microphone. Browsers only allow microphone access on `localhost` or HTTPS.

Containers read `.env` only when they are created. After editing it, run `docker compose up -d` to recreate them; `docker compose restart` keeps the old values.

## Develop

Run Postgres in Docker, and the backend and frontend directly, for hot reload:

```sh
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d db

cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:create_app --factory --reload    # http://127.0.0.1:8000

cd frontend
npm install
npm run dev                                               # http://localhost:5173, proxies /api
```

Checks to run before pushing:

```sh
cd backend  && uv run ruff check . && uv run ruff format --check . && uv run pytest
cd frontend && npm run lint && npm run build
```

Backend tests run against real Postgres. They use `TEST_DATABASE_URL`, or `DATABASE_URL` with the database renamed to `sarjy_test`, which is created if missing.

To change the schema, edit `backend/app/models.py`, then run `uv run alembic revision --autogenerate -m "describe the change"` and review the generated file.

## Configuration

Set in `.env`. Only the first four are required.

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | | OpenAI key, used only on the server |
| `ACCESS_PASSCODE` | | Shared passcode for the site |
| `SESSION_SECRET` | | Signs the session cookie; 32+ random characters |
| `POSTGRES_PASSWORD` | | Database password |
| `COOKIE_SECURE` | `true` | Must be `true` over HTTPS; `false` for http://localhost |
| `REALTIME_MODEL` | `gpt-realtime-2.1` | Voice model; `gpt-realtime-2.1-mini` is cheaper |
| `REALTIME_VOICE` | `marin` | Voice |
| `REALTIME_REASONING_EFFORT` | `low` | `minimal` may reply faster |
| `TRANSCRIPTION_MODEL` | `gpt-live-transcribe` | Transcribes your speech for the on-screen transcript |
| `SEARCH_MODEL` | `gpt-6.1-terra` | Model that runs web searches |
| `SEARCH_REASONING_EFFORT` | `low` | Higher is slower but more thorough |
| `MEMORY_PROMPT_LIMIT` | `200` | Newest facts loaded into each call |
| `SESSIONS_PER_USER_PER_DAY` | `50` | Calls each user can start per day |
| `SEARCHES_PER_USER_PER_MINUTE` | `10` | Web searches per user per minute |
| `PASSCODE_ATTEMPTS_PER_15_MIN` | `5` | Passcode attempts per IP address |

## Deploy to a VPS

The app runs in Docker Compose behind an existing Caddy, which handles HTTPS.

1. Clone the repository on the server (for example to `/srv/sarjy`) and create `.env` with production values, including `COOKIE_SECURE=true`.
2. Add the site block from `deploy/Caddyfile.example` to Caddy's configuration, with your domain, and reload Caddy.
3. Deploy with `ssh your-vps 'cd /srv/sarjy && sh scripts/deploy.sh'`. It pulls, rebuilds, and waits for the health check. Run it again for every later deploy.
4. Schedule a nightly backup with cron: `15 3 * * * cd /srv/sarjy && sh scripts/backup.sh >> backups/backup.log 2>&1`.
5. Set a monthly budget cap on the OpenAI project. It is the hard stop on spend; the per-user limits only slow abuse down.

The app's port is published on the server's loopback address only, so Caddy is the only way in. Postgres is not published at all.

## Latency

The on-screen "reply delay" measures from the moment the end of your speech is detected to the first sound of the reply. It does not include the turn-detection wait itself, which semantic VAD at high eagerness keeps short.

| Turn | Median reply delay |
|---|---|
| Plain question | _to measure_ |
| Memory question | _to measure_ |
| Web search (time to "let me check") | _to measure_ |
| Web search (tool duration, shown in the transcript) | _to measure_ |

## Known limits

- **Memory cap.** Only the newest 200 facts are loaded into a call. The upgrade path is a small always-loaded core plus a `recall` tool backed by pgvector.
- **Memory is per browser.** Clearing cookies or switching devices starts a new, empty memory.
- **Limits are in-process.** Rate limits and daily caps reset when the container restarts and assume a single app container.
- **Search adds a second model.** A search question goes through the voice model and then the search model, so it takes noticeably longer than a plain answer. The assistant says a short "let me check" to cover the gap.
- **Prompt-injection defence is instructions only.** Search results are marked as untrusted in the prompts, and the model is told never to act on them. That reduces the risk but does not remove it; the damage is limited to the current user's own memory.
