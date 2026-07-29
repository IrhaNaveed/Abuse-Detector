import json
import logging

from google import genai
from google.genai import types

from app.core.config import settings

logger = logging.getLogger(__name__)

_client = genai.Client(api_key=settings.gemini_api_key)


def _recommendation(overall_score: float) -> str:
    if overall_score >= settings.threshold_approved:
        return "APPROVED"
    if overall_score >= settings.threshold_flagged:
        return "FLAGGED"
    return "BLOCKED"


class MessageEvaluator:
    def evaluate(self, text: str) -> dict:
        if not text or not text.strip():
            return _empty_evaluation(text)

        response = _client.models.generate_content(
            model=settings.gemini_model,
            contents=text,
            config=types.GenerateContentConfig(
                system_instruction=settings.system_prompt,
                response_mime_type="application/json",
            ),
        )

        raw = (response.text or "{}").strip()
        logger.info("LLM evaluation raw: %s", raw)

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("LLM returned invalid JSON: %r", raw)
            return _empty_evaluation(text)

        weights = settings.weights
        weight_total = sum(weights.values()) or 1.0

        scores = {
            key: {
                "score": parsed[key]["score"],
                "weight": round(weights[key] / weight_total * 100, 2),
                "reasoning": parsed[key]["reasoning"],
            }
            for key in weights
        }

        overall = round(
            sum(scores[k]["score"] * weights[k] for k in weights) / weight_total, 2
        )

        political_score = scores["political_sensitivity"]["score"]
        recommendation = (
            "BLOCKED"
            if political_score <= settings.political_block_threshold
            else _recommendation(overall)
        )

        return {
            "original": text,
            "scores": scores,
            "overall_score": overall,
            "recommendation": recommendation,
            "summary": parsed.get("summary", ""),
        }


def _empty_evaluation(text: str) -> dict:
    weights = settings.weights
    weight_total = sum(weights.values()) or 1.0
    empty_score = {"score": 100, "reasoning": "Empty message, no content to evaluate."}
    return {
        "original": text,
        "scores": {
            key: {**empty_score, "weight": round(weight / weight_total * 100, 2)}
            for key, weight in weights.items()
        },
        "overall_score": 100.0,
        "recommendation": "APPROVED",
        "summary": "Empty message.",
    }


evaluator = MessageEvaluator()
