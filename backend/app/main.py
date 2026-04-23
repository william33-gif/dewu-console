from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import get_settings
from app.core.db import Base, engine
from app.services.scheduler import start_publish_scheduler, stop_publish_scheduler

settings = get_settings()
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name)
settings.resolved_material_storage_dir.mkdir(parents=True, exist_ok=True)
settings.resolved_result_storage_dir.mkdir(parents=True, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.mount("/media/materials", StaticFiles(directory=settings.resolved_material_storage_dir), name="materials")
app.mount("/media/results", StaticFiles(directory=settings.resolved_result_storage_dir), name="results")


@app.on_event("startup")
def on_startup() -> None:
    start_publish_scheduler()


@app.on_event("shutdown")
def on_shutdown() -> None:
    stop_publish_scheduler()


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
