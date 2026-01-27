import asyncio
import websockets
import json

JOB_ID = "PASTE_JOB_ID_HERE"

async def listen():
    url = f"ws://localhost:8000/ws/jobs/{JOB_ID}"
    async with websockets.connect(url) as websocket:
        print("Connected to job stream")
        while True:
            msg = await websocket.recv()
            print(json.loads(msg))

asyncio.run(listen())
