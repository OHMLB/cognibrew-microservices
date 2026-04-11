from fastapi import APIRouter

from app.api.routes import auth, catalog, feedback, notification, order, recognition, recommendation, utils
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(catalog.router)
api_router.include_router(feedback.router)
api_router.include_router(notification.router)
api_router.include_router(order.router)
api_router.include_router(recognition.router)
api_router.include_router(recommendation.router)
api_router.include_router(utils.router)

if settings.ENVIRONMENT == "local":
    pass
