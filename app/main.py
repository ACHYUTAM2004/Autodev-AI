from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from app.api.api import api_router
from app.core.logger import setup_logger

setup_logger()

app = FastAPI(
    title="AutoDev AI",
    version="0.2.0",
    description="Autonomous Software Engineer Agent"
)

# ✅ Single API entrypoint
app.include_router(api_router)

@app.get("/health")
def health_check():
    return {"status": "ok"}
