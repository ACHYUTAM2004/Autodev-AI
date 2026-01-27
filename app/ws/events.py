# app/ws/events.py
import asyncio
from app.ws.connection_manager import manager

async def emit_job_event(job_id: str, payload: dict):
    await manager.broadcast(job_id, payload)
