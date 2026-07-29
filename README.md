# Generic Abuse Detector

Drop-in LLM message moderation service. Same evaluation logic as
`GNG-Abuse-Detector`'s `message_evaluator`, but nothing is hardcoded.
API key, model, criterion weights, and BLOCKED/FLAGGED/APPROVED thresholds
all come from `.env`, so the same code can be reused across projects by
just swapping the config.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in GEMINI_API_KEY, tune weights/thresholds as needed
uvicorn main:app --reload
```

## Usage

```bash
curl -X POST localhost:8000/api/evaluate -H "Content-Type: application/json" \
  -d '{"content": "some message"}'
```

Or import the service directly in another project:

```python
from app.services.message_evaluator import evaluator

result = evaluator.evaluate("some message")
```

## Configuring

Everything is read via `app/core/config.py` (`pydantic-settings`). See
`.env.example` for every knob:

- `GEMINI_API_KEY`, `GEMINI_MODEL`
- `SYSTEM_PROMPT`: optional full override of the moderation prompt (must
  keep the same 5 criteria keys and JSON shape)
- `WEIGHT_*`: per-criterion weight (auto-normalized, doesn't need to sum to 1)
- `THRESHOLD_APPROVED`, `THRESHOLD_FLAGGED`: cutoffs on the weighted overall score
- `POLITICAL_BLOCK_THRESHOLD`: single-criterion override that forces BLOCKED
