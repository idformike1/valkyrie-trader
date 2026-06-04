import asyncio
import json
import websockets

async def test_websocket_sync():
    uri = "ws://localhost:8081/ws/telemetry"
    print("Testing multi-tab / WebSocket synchronization...")
    
    async with websockets.connect(uri) as client_a, websockets.connect(uri) as client_b:
        print("Connected Client A and Client B successfully.")
        
        # Read the first message from both
        msg_a = await client_a.recv()
        msg_b = await client_b.recv()
        
        data_a = json.loads(msg_a)
        data_b = json.loads(msg_b)
        
        status_a = data_a.get("status", {})
        status_b = data_b.get("status", {})
        
        print("\nClient A Telemetry:")
        print(f"  Session ID: {status_a.get('session_id')}")
        print(f"  Start Time: {status_a.get('session_start_timestamp')}")
        print(f"  State:      {status_a.get('state')}")
        
        print("\nClient B Telemetry:")
        print(f"  Session ID: {status_b.get('session_id')}")
        print(f"  Start Time: {status_b.get('session_start_timestamp')}")
        print(f"  State:      {status_b.get('state')}")
        
        # Assertions
        assert status_a.get("session_id") == status_b.get("session_id"), "Session ID mismatch!"
        assert status_a.get("session_start_timestamp") == status_b.get("session_start_timestamp"), "Start timestamp mismatch!"
        assert status_a.get("state") == status_b.get("state"), "State mismatch!"
        
        print("\nSUCCESS: Client A and Client B telemetry are perfectly synchronized!")

if __name__ == "__main__":
    asyncio.run(test_websocket_sync())
