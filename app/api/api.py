from fastapi import APIRouter
from app.api import build, jobs,ws

api_router = APIRouter()

api_router.include_router(build.router, tags=["Build"])
api_router.include_router(jobs.router, tags=["Jobs"])
api_router.include_router(ws.router)
