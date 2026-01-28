import asyncio
import websockets
import json

JOB_ID = "bc74fd3c-64be-423e-8342-8f149f307853"

async def listen():
    url = f"ws://localhost:8000/ws/jobs/{JOB_ID}"
    async with websockets.connect(url) as websocket:
        print("Connected to job stream")
        while True:
            msg = await websocket.recv()
            print(json.loads(msg))

asyncio.run(listen())
