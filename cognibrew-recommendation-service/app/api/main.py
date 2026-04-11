from fastapi import APIRouter

from app.api.routes import recommendation, utils

api_router = APIRouter()
api_router.include_router(recommendation.router)
api_router.include_router(utils.router)
