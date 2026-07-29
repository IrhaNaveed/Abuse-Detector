from fastapi import FastAPI

from app.api.routes.evaluate import router

app = FastAPI(title="Generic Abuse Detector")

app.include_router(router, prefix="/api")
