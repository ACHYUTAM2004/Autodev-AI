from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from app.api.build import router as build_router
from app.api.jobs import router as jobs_router
from app.core.logger import setup_logger

setup_logger()

app = FastAPI(
    title="AutoDev AI",
    version="0.2.0",
    description="Autonomous Software Engineer Agent"
)

app.include_router(build_router)
app.include_router(jobs_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
