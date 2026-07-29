from fastapi import APIRouter, HTTPException
from google.genai.errors import ClientError

from app.schemas.evaluation import EvaluateRequest, EvaluateResponse
from app.services.message_evaluator import evaluator

router = APIRouter()


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate_message(request: EvaluateRequest):
    try:
        result = evaluator.evaluate(request.content)
    except ClientError as e:
        if e.code == 429:
            raise HTTPException(status_code=503, detail="AI quota exhausted. Please try again later.")
        raise HTTPException(status_code=502, detail=f"AI service error: {e.message}")

    return EvaluateResponse(**result)
