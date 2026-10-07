# Financial intelligence, chat and saving goals (phases 10–12)

## Enable the optional LLM

Add these settings to **backend/.env**, then restart the backend:

```dotenv
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=gpt-4.1-mini
LLM_TIMEOUT_SECONDS=15
```

Keep the key in the backend only. Never use a VITE_ variable for secrets. The env file is ignored by Git. No key is required for local financial explanations, chat, forecasts or goals. The UI labels local analysis explicitly; configured-provider failures also fall back to verified local analysis. A live paid provider call has not been tested; integration tests use a mocked HTTP transport.

The integration uses the [OpenAI Responses API](https://developers.openai.com/api/docs/guides/migrate-to-responses) and [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs). The model is configurable; the default is [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini). Requests disable response storage (`store:false`); that setting does not guarantee zero provider retention. Consult your provider's data policy before enabling financial-summary sharing. Calls incur provider usage charges.

## Grounding and privacy

Python queries always use the authenticated user's ID. Only category aggregates, verified fact sentences, forecast estimates and total goal requirements reach the provider. Names, email, merchant, descriptions, raw bank statements, user questions and conversation history are excluded. There are no model tools, SQL access, unrestricted retrieval or provider-managed conversations.

The model selects and orders verified fact IDs and approved saving-suggestion IDs using a strict JSON schema. The server validates these identifiers and renders the final sentences. This deliberately limits free-form generation: it prevents fabricated amounts, invented spending causes, promised affordability and unsupported advice. Required facts remain visible regardless of model selection. Unsupported questions are answered locally without an LLM call. Error bodies, prompts and secrets are not logged by the integration.

Analysis excludes future-dated transactions. Current-month figures are month-to-date; previous months are full calendar months, so comparisons are not matched-day comparisons. Financial records may be incomplete. Saving feasibility describes recorded surplus and missing future income/commitments, rather than guaranteeing that a requested saving is achievable.

Question classification is local and supports spending changes, category spend, biggest expenses, month comparison, saving feasibility, reductions, forecasts and goals. Include full month names with a year, or YYYY-MM. Short follow-ups beginning “And” or “What about” reuse the prior selected month when no month is supplied. Unsupported topics are redirected to supported financial questions.

## APIs

All endpoints require JWT authentication:

- GET /api/ai/insights?month=2026-10-01
- GET /api/ai/goal-recommendations
- POST /api/ai/chat with question and optional month
- GET /api/ai/chat: latest 30 turns; next_before supports older history
- DELETE /api/ai/chat: clear only the signed-in user's history
- GET/POST /api/goals
- PUT/DELETE /api/goals/{id}
- POST /api/goals/{id}/funds with a positive decimal amount

Chat turns persist in PostgreSQL and are deleted with their user. History includes source and disclaimer. The provider receives a newly generated summary for each question; prior raw messages are not forwarded.

## Goal calculations

Remaining = max(target − saved, 0). Progress = saved / target × 100; the displayed bar caps at 100%, while the percentage can show overfunding. Remaining monthly periods are the calendar-month difference plus one when the due day is later than today's day, with a minimum of one. A six-month deadline on the same day therefore divides by six. Required monthly savings rounds up to the nearest cent. Past-due unfinished goals are flagged and use one period until the user revises the date.

Goal funds track allocation only: they do not transfer funds, create transactions or reduce the dashboard balance. Add-funds and edits lock the owned row to avoid lost updates. The UI prevents repeated submission while pending; the API does not provide network-retry idempotency, so do not automatically retry a timed-out add-funds operation.

## Verification

25 backend tests, seven real browser tests, production frontend build, and Alembic schema comparison passed on October 7, 2026. Tests cover private chat history and clearing, future transaction exclusion, category/month comparisons, owner-only goal operations, positive funding, goal progress and monthly calculations, grounded provider output, timeouts, authorization errors and invalid fact IDs. Browser tests cover dashboard insights, suggested questions, persisted chat, unsupported questions, goal creation/edit/funding/deletion and 390px layout.
