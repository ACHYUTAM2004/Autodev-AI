from fastapi import FastAPI
from app.api.build import router as build_router
from app.core.logger import setup_logger

setup_logger()

app = FastAPI(
    title="AutoDev AI",
    version="0.2.0",
    description="Autonomous Software Engineer Agent"
)

app.include_router(build_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
