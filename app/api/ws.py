from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.ws.connection_manager import manager
from app.jobs.manager import JobManager

router = APIRouter(prefix="/ws", tags=["WebSocket"])

@router.websocket("/jobs/{job_id}")
async def job_updates(websocket: WebSocket, job_id: str):
    await manager.connect(job_id, websocket)

    try:
        job = JobManager.load_job(job_id)
        await websocket.send_json({
            "type": "snapshot",
            "data": job,
        })

        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        manager.disconnect(job_id, websocket)
