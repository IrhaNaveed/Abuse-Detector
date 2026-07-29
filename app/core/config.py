from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Same 5-criterion JSON contract the evaluator parses. Keep this shape if you
# override SYSTEM_PROMPT in .env, or add matching WEIGHT_* env vars for new keys.
_DEFAULT_SYSTEM_PROMPT = """You are a content moderation AI for a live chat platform.
Users may chat in English or a mix of languages. Evaluate messages on exactly 5 criteria.

CRITERIA:
1. toxicity_hate_speech — Slurs, hate based on religion, ethnicity, gender, nationality, caste.
2. harassment_threats — Bullying, personal attacks on other users, direct or implied threats, intimidation.
3. language_appropriateness — Profanity, sexually explicit language, obscene content.
4. spam_integrity — Repetitive flooding, external links, advertising, account selling/buying, referral spam, coordinated brand attacks.
5. political_sensitivity — Political content, figures, or narratives that could expose the platform to controversy, legal, or regulatory risk.

SCORING RULES:
- Each criterion: score from 0 (completely violates) to 100 (perfectly clean).
- Score reflects how SAFE the message is on that criterion — high score = safe.
- Be context-aware: judge words by their actual meaning and cultural weight, not just their literal form.
- Mild frustration ("this game is trash") scores high (safe). Targeted slurs score low.

OUTPUT — return ONLY valid JSON, no extra text:
{
  "toxicity_hate_speech": { "score": <0-100>, "reasoning": "<one sentence>" },
  "harassment_threats":   { "score": <0-100>, "reasoning": "<one sentence>" },
  "language_appropriateness": { "score": <0-100>, "reasoning": "<one sentence>" },
  "spam_integrity":       { "score": <0-100>, "reasoning": "<one sentence>" },
  "political_sensitivity": { "score": <0-100>, "reasoning": "<one sentence>" },
  "summary": "<one sentence overall assessment>"
}"""


class Settings(BaseSettings):
    """Every knob a consuming project needs is here, nothing evaluator-specific is hardcoded."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    gemini_api_key: str
    gemini_model: str = "gemini-3.1-flash-lite"
    system_prompt: str = _DEFAULT_SYSTEM_PROMPT

    # Criterion weights, don't need to sum to 1; the overall score is weight-normalized.
    weight_toxicity_hate_speech: float = 0.25
    weight_harassment_threats: float = 0.20
    weight_language_appropriateness: float = 0.20
    weight_spam_integrity: float = 0.15
    weight_political_sensitivity: float = 0.20

    # Recommendation thresholds (on the weighted overall score, 0-100)
    threshold_approved: float = 70
    threshold_flagged: float = 40

    # Any-single-criterion override: score at or below this on political_sensitivity
    # forces BLOCKED regardless of the overall score. Set to -1 to disable.
    political_block_threshold: float = 30

    @property
    def weights(self) -> dict[str, float]:
        return {
            "toxicity_hate_speech": self.weight_toxicity_hate_speech,
            "harassment_threats": self.weight_harassment_threats,
            "language_appropriateness": self.weight_language_appropriateness,
            "spam_integrity": self.weight_spam_integrity,
            "political_sensitivity": self.weight_political_sensitivity,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
