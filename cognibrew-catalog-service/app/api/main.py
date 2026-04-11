from fastapi import APIRouter

from app.api.routes import menu, order, recommendation, utils

api_router = APIRouter()
api_router.include_router(menu.router)
api_router.include_router(recommendation.router)
api_router.include_router(order.router)
api_router.include_router(utils.router)
