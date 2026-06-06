import asyncio
import websockets
import json

async def test_ws():
    print("Connecting to ws://localhost:8081/ws/telemetry...")
    try:
        # Wrap connection in wait_for for timeout
        ws = await asyncio.wait_for(websockets.connect("ws://localhost:8081/ws/telemetry"), timeout=5.0)
        print("Connected! Waiting for message...")
        msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
        print("Message received:")
        data = json.loads(msg)
        print(f"Status Keys: {data.get('status', {}).keys()}")
        print(f"Current Server Time: {data.get('status', {}).get('current_server_time')}")
        print(f"Last Heartbeat: {data.get('status', {}).get('last_heartbeat')}")
        await ws.close()
    except Exception as e:
        print(f"Connection failed: {e}")

asyncio.run(test_ws())
