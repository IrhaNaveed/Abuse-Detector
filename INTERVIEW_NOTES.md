# Project Notes: Generic Abuse Detector

## What this project is

A small FastAPI service that takes a chat message and returns a moderation
verdict: APPROVED, FLAGGED, or BLOCKED. It doesn't do the classification
itself — it sends the message to Gemini (an LLM) with a system prompt that
tells it to score the message on 5 criteria, then applies weighting and
threshold logic on top of those scores to produce the final verdict.

One endpoint: `POST /api/evaluate`, takes `{"content": "..."}`, returns
scores per criterion, an overall weighted score, and a recommendation.

## Why it exists

It's a generalized extraction from an earlier project (`GNG-Abuse-Detector`).
That project had the same evaluation logic, but the model name, API key,
criterion weights, and the score thresholds for each verdict were all
hardcoded in Python. This version moves every one of those values into
`.env`, so the exact same code can be dropped into a different project and
reconfigured just by changing environment variables — no code edits.

## Architecture

```
main.py                        FastAPI app, mounts the router
app/api/routes/evaluate.py     HTTP layer: the /api/evaluate endpoint
app/schemas/evaluation.py      Pydantic request/response models
app/services/message_evaluator.py   Core logic: calls Gemini, scores, decides verdict
app/core/config.py             Settings loaded from .env (pydantic-settings)
```

Request flow:

1. Client POSTs `{"content": "..."}` to `/api/evaluate`.
2. `evaluate.py` calls `evaluator.evaluate(text)`.
3. `MessageEvaluator` sends the text to Gemini with a system prompt asking
   for a fixed JSON shape: a score (0-100) and one-sentence reasoning for
   each of 5 criteria, plus a summary.
4. Gemini's response is parsed as JSON. Each criterion's score is combined
   with its configured weight to produce a single overall score (0-100).
5. The overall score is compared against `THRESHOLD_APPROVED` /
   `THRESHOLD_FLAGGED` to get APPROVED / FLAGGED / BLOCKED.
6. One override sits on top of that: if `political_sensitivity` alone
   scores at or below `POLITICAL_BLOCK_THRESHOLD`, the message is BLOCKED
   regardless of what the overall score says.
7. Response goes back with the full per-criterion breakdown, the overall
   score, and the recommendation.

## The 5 criteria

1. `toxicity_hate_speech` — slurs, hate based on religion/ethnicity/gender/etc.
2. `harassment_threats` — bullying, personal attacks, threats, intimidation.
3. `language_appropriateness` — profanity, sexually explicit content.
4. `spam_integrity` — flooding, links, ads, account trading, referral spam.
5. `political_sensitivity` — content that could expose the platform to
   controversy or regulatory risk.

Each is scored 0-100 where **high = safe**, not high = severe. That's a
deliberate choice: it means all 5 scores are on the same "safety" scale and
can be weighted-averaged directly into one overall number without having to
invert any of them first.

## Design decisions worth being able to explain

**Why config-driven instead of hardcoded?**
So the same service can back multiple products/platforms with different
tolerance levels just by changing `.env` — a stricter kids' platform can
raise thresholds and weight toxicity higher without touching code.

**Why a single-criterion override (political_sensitivity) on top of the
weighted score?**
Because a weighted average can let a severe problem on one axis get diluted
by good scores on the other four. A message that's borderline-political but
otherwise clean could still average out to "safe" — the override exists so
one specific high-risk category can force a block independent of the
average. It's implemented as `-1` to disable, so it's opt-in.

**Why ask Gemini for structured JSON instead of parsing free text?**
`response_mime_type="application/json"` in the Gemini call constrains the
model's output format, so the service can `json.loads()` it directly rather
than regex-parsing prose. Much less brittle.

**What happens if Gemini returns malformed JSON, or the message is empty?**
Both are handled explicitly rather than left to throw:
- Empty/whitespace-only input short-circuits before calling the LLM at all
  (`_empty_evaluation`) — no need to spend an API call scoring nothing.
- If Gemini's response fails `json.loads()`, the same empty-evaluation
  fallback is used and the raw response is logged for debugging, instead of
  the request 500ing.

**What happens on Gemini API errors?**
The route layer (`evaluate.py`) catches `ClientError` from the SDK: a 429
(quota exhausted) is translated into an HTTP 503 with a clear message so
callers know to retry later; any other client error becomes a 502. This
keeps the API's own error semantics separate from the upstream provider's.

**Why `pydantic-settings` instead of `os.environ.get(...)` everywhere?**
Type coercion and validation for free — weights and thresholds are declared
as `float` and pydantic-settings converts the env var strings automatically,
plus one `Settings` object is the single source of truth instead of env
lookups scattered through the codebase. `@lru_cache` on `get_settings()`
means it's read from `.env` once per process, not on every request.

**Why can weights not sum to 1?**
They're normalized at evaluation time (`weight / weight_total`), so you can
hand-tune individual weights without doing the arithmetic to keep them
summing to 1 — one less thing to get wrong when adjusting `.env`.

## Tech stack

- **FastAPI** — HTTP layer, request/response validation via Pydantic models.
- **google-genai** — official SDK for calling Gemini.
- **pydantic-settings** — typed config loaded from `.env`.
- **uvicorn** — ASGI server.

## Likely interview questions and how to answer them

**"Walk me through what happens when a request comes in."**
Use the request flow section above — endpoint receives content, evaluator
calls Gemini with a fixed system prompt, JSON response gets parsed and
weighted, thresholds decide the verdict, response goes back with full
breakdown.

**"Why use an LLM for this instead of a classifier or keyword list?"**
Context-awareness — the prompt explicitly asks the model to judge words by
actual meaning/cultural weight, not literal matches (the prompt gives an
example: "this game is trash" should score as safe, but a targeted slur
shouldn't, even though both could trip a naive keyword filter). An LLM can
generalize to phrasing a fixed keyword list would never anticipate,
especially across mixed-language chat.

**"What are the tradeoffs of that approach?"**
Latency and cost per message (an API call per evaluation, vs. a local
classifier), dependency on an external service's uptime/rate limits (hence
the explicit 429 handling), and less deterministic output than a rules
engine — mitigated here by forcing structured JSON output and clamping the
final decision with fixed numeric thresholds rather than trusting free-form
LLM judgment for the verdict itself.

**"How would you extend this to a 6th criterion?"**
Add the key to the system prompt's JSON contract, add a matching
`weight_<name>` field to `Settings` and to the `weights` property, add it to
`ScoreBreakdown` in the schema. The scoring/weighting logic in
`message_evaluator.py` is generic over `settings.weights.keys()`, so nothing
else needs to change.

**"Is this production-ready? What's missing?"**
Honest answer: no persistence/audit trail of past evaluations, no retries or
backoff on the Gemini call (just a single try that surfaces a 503 on quota
errors), no auth on the endpoint, no rate limiting of its own, no tests.
It's built as a reusable core service to be embedded in something else, not
a fully hardened standalone API.
