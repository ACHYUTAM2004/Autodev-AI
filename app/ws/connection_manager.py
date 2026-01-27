from typing import Dict, List
from fastapi import WebSocket
import asyncio


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, job_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.setdefault(job_id, []).append(websocket)

    def disconnect(self, job_id: str, websocket: WebSocket):
        if job_id in self.active_connections:
            self.active_connections[job_id].remove(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]

    async def broadcast(self, job_id: str, message: dict):
        if job_id not in self.active_connections:
            return

        dead = []
        for ws in self.active_connections[job_id]:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self.disconnect(job_id, ws)


manager = ConnectionManager()
