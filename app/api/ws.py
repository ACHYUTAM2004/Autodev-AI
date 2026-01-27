from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio

from app.ws.connection_manager import manager
from app.jobs.manager import JobManager

router = APIRouter()


@router.websocket("/ws/jobs/{job_id}")
async def job_updates(websocket: WebSocket, job_id: str):
    await manager.connect(job_id, websocket)

    try:
        # 1️⃣ Send initial snapshot
        job = JobManager.load_job(job_id)
        await websocket.send_json({
            "type": "snapshot",
            "data": job,
        })

        # 2️⃣ Keep connection alive
        while True:
            await asyncio.sleep(30)

    except WebSocketDisconnect:
        manager.disconnect(job_id, websocket)
