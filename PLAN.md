# Sarjy: voice assistant plan

Status: milestones 2–8 implemented; the spike's live voice measurements and the writeup's latency figures are still to do (they need a real API key and someone talking). Last updated 2026-11-17.

## Requirements

The assistant must:

1. Listen and respond by voice.
2. Remember facts and preferences across sessions ("What's my favorite color?" works if it was told earlier).
3. Call at least one external API that makes it more useful, with a 2–3 sentence justification in the writeup.

Guiding principles: latency is the top priority; do things properly without overengineering; start simple.

## Decisions

Each decision lists what was chosen, why, and what was set aside.

### Voice: OpenAI Realtime API, speech-to-speech

- One model hears, reasons, calls tools and speaks, which gives the shortest gap between the user finishing and the reply starting.
- Set aside: a cascaded pipeline (speech-to-text, text model, text-to-speech), which is roughly 2–3x slower; the browser's built-in speech, which is slowest.
- Set aside: OpenAI GPT-Live. It splits voice from reasoning across two models. That split is built for long background work; ours is one search or one database write, so it adds complexity for little gain.
- Model: `gpt-realtime-2.1` or `gpt-realtime-2.1-mini`, decided by measurement in the spike.

### Transport: WebRTC, direct from the browser

- WebRTC drops late audio instead of waiting for it, so a network hiccup causes a small glitch, not growing delay. The browser also handles microphone capture, playback and echo cancellation.
- Audio never passes through our server. The backend only issues a short-lived token for the browser to start the call.
- Set aside: WebSocket audio, which stalls on packet loss and needs hand-written audio handling.

### Tool calls: browser relay

- The model's tool request arrives in the browser, which forwards it to an authenticated backend endpoint and passes the result back.
- OpenAI documents this pattern: "The browser can forward function-call events from its data channel to an authenticated backend for execution."
- Every tool endpoint checks the user's cookie, scopes queries to that user, and search is rate-limited.
- Set aside: a server sideband connection. Its main benefit is server-side transcripts, which nothing in this design needs.

### Backend: FastAPI, async SQLAlchemy 2.0, Alembic, Postgres

- Async throughout (`asyncpg`, `httpx`), since every endpoint waits on the database or an outside API.
- One database session per request through a FastAPI dependency.
- Pydantic schemas kept separate from database models.
- Typed settings from environment variables with `pydantic-settings`.
- Alembic migrations applied on container start.
- A thin service layer: routers handle HTTP; services hold memory, search and session-token logic.
- Deliberately left out: repository pattern, generic base classes, task queue, Redis, separate domain objects.
- Postgres over SQLite because Docker Compose makes it equally easy to run, and it keeps vector search available later.

### Frontend: React, Vite, TypeScript

- The page has real live state: connection status, transcript, memory panel, latency readout. Typed Realtime events catch mistakes early.
- Set aside: a plain HTML/JS page with no build step.

### Memory

- **Writing:** the model calls `remember` and `forget` tools during conversation. To update a fact it replaces the old one by ID.
- **Recall:** all of the user's facts are loaded into the session instructions when a call starts, so recall adds no delay and the model can use facts unprompted.
- **Panel deletes during a call:** the browser tells the model with a system message on the data channel, so a deleted fact stops being used immediately rather than next session.
- **Limit:** the newest 200 facts are loaded. Beyond that, older facts would drop out of the prompt. This is a documented boundary.
- **Upgrade path:** a hybrid of a small always-loaded core plus a `recall` tool backed by pgvector.
- Set aside for now: retrieval per question (slower and less reliable in speech-to-speech), a background pass that extracts facts from transcripts, and ready-made memory services.

### External API: OpenAI web search

- The voice model calls a `web_search` tool; the backend calls OpenAI's Responses API with the hosted web search tool and a small fast model, and returns a short answer to be spoken.
- The whole app needs only one API key.
- Search results are untrusted text. The session instructions tell the model not to follow instructions found in them, so a web page cannot make it save or delete memories.
- Expected to be slower than a raw search API. Mitigations: a fast model at low reasoning effort, short answers, and a spoken "let me check" before the call.
- Draft justification for the writeup: "A voice assistant fails most often on anything recent or outside its training data. Web search turns those dead ends into answers, and one API covers weather, news, scores and prices instead of a single narrow domain."

### Identity: shared passcode plus anonymous browser ID

- A correct passcode creates a `users` row and sets a cookie holding that user's ID.
- The cookie is signed, unreadable by page scripts, HTTPS-only in production, long-lived, and set with `SameSite=Lax` so other sites cannot trigger requests with it.
- Passcode attempts are rate-limited.
- Memory is tied to the browser; clearing cookies or switching device loses it.
- The `users` table is shaped so real login can be added later without touching `memories`.

### Deployment: everything on one VPS

- Docker Compose runs two services: Postgres and one app container.
- The app container runs FastAPI, which serves both the API and the built React files. The Dockerfile builds the frontend, then copies it into the Python image.
- The existing Caddy on the VPS handles HTTPS and forwards a domain to the app. The app port is bound to the server's local address only; Postgres is not exposed.
- Locally, `docker compose up` serves the same thing at `localhost`, where the microphone works without HTTPS.
- Lint and tests run locally before pushing; there is no CI. Deploying is one script run over SSH.
- Nightly database dump on the VPS.
- Spend protection: a per-user daily limit on calls started, plus a monthly budget cap on the OpenAI project.

## Data model

- `users`: `id` (UUID), `created_at`.
- `memories`: `id` (integer), `user_id` (references `users`), `content` (text), `created_at`, `updated_at`. Indexed on `user_id` and `updated_at`.
  - Changed from UUID during implementation: the model sees and repeats every memory id, and 200 UUIDs would cost thousands of tokens per session. All access is scoped by user, so sequential ids reveal nothing.

## Tools given to the voice model

- `remember(content, replaces_id?)`: saves a fact, optionally replacing an existing one.
- `forget(memory_id)`: deletes a fact.
- `web_search(query)`: returns a short answer from the web.

## Backend endpoints

All endpoints are versioned under `/api/v1`.

- `POST /api/v1/auth/passcode`: checks the passcode and sets the cookie.
- `POST /api/v1/realtime/session`: issues the short-lived Realtime token, with the user's memories and the tool definitions.
- `POST /api/v1/tools/remember`, `POST /api/v1/tools/forget`, `POST /api/v1/tools/web_search`: run the tools.
- `GET /api/v1/memories`, `DELETE /api/v1/memories/{id}`, `DELETE /api/v1/memories`: back the memory panel.
- `GET /api/v1/health`: container health check.

## Milestones

1. **Spike.** A bare Realtime call from a minimal page. Confirm the current API shapes against the docs. Measure reply delay, the full model against the mini model, and web search time.
2. **Skeleton.** Compose file, FastAPI app, Postgres, first migration, React scaffold, lint and tests on push.
3. **Access.** Passcode, cookie, attempt limiting.
4. **Voice.** Session endpoint, WebRTC client, speaking and listening states, live transcript.
5. **Memory.** The two tools, loading at session start, the memory panel with delete and "forget everything".
6. **Search.** The tool, the spoken "let me check", answer trimming.
7. **Polish.** On-screen latency readout, error handling (microphone denied, dropped connection, expired token), daily call limit.
8. **Deploy.** Caddy site block, nightly backup, OpenAI budget cap.
9. **Writeup.** Architecture, the API justification, measured latency, known limits.

## Testing

- `pytest` against a real Postgres container for the memory service, the tool endpoints and access checks.
- The search client is tested with mocked OpenAI responses.
- Voice is covered by a manual checklist: a plain turn, a remembered fact recalled in a new session, a fact updated, a search question, an interruption, and a short Arabic exchange.

## Open items

- Which domain or subdomain to point at the VPS.
- Whether the existing Caddy runs on the host or in Docker (a local port versus a shared Docker network).
- Full or mini Realtime model, decided by the spike.
- Latency figures in this plan are estimates until the spike measures them.

## References

- [Realtime API with WebRTC (OpenAI)](https://developers.openai.com/api/docs/guides/realtime-webrtc.md)
- [Server-side controls (OpenAI)](https://developers.openai.com/api/docs/guides/voice-server-controls.md)
- [Voice agents (OpenAI)](https://developers.openai.com/api/docs/guides/voice-agents)
- [Pricing (OpenAI)](https://developers.openai.com/api/docs/pricing)
