from fastapi import APIRouter

from app.api.routes import devices, feishu, logs, materials, tasks

api_router = APIRouter(prefix="/api")
api_router.include_router(tasks.router)
api_router.include_router(materials.router)
api_router.include_router(devices.router)
api_router.include_router(logs.router)
api_router.include_router(feishu.router)
