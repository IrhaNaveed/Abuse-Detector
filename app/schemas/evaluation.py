from pydantic import BaseModel


class EvaluateRequest(BaseModel):
    content: str


class CriterionResult(BaseModel):
    score: float
    weight: float
    reasoning: str


class ScoreBreakdown(BaseModel):
    toxicity_hate_speech: CriterionResult
    harassment_threats: CriterionResult
    language_appropriateness: CriterionResult
    spam_integrity: CriterionResult
    political_sensitivity: CriterionResult


class EvaluateResponse(BaseModel):
    original: str
    scores: ScoreBreakdown
    overall_score: float
    recommendation: str
    summary: str
