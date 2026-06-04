import urllib.request
import json
import time
from datetime import datetime

url = "http://localhost:8081/telemetry"

print("Starting session persistence audit log...")
print(f"Start audit time: {datetime.now().isoformat()}")
print("-" * 80)

# Run for 150 seconds (2.5 minutes), sampling every 10 seconds
for i in range(16):
    try:
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
            status = data.get("status", {})
            state = status.get("state")
            session_id = status.get("session_id")
            start_ts = status.get("session_start_timestamp")
            server_time = status.get("current_server_time")
            heartbeat = status.get("last_heartbeat")
            
            # Calculate runtime if possible
            if start_ts and server_time:
                try:
                    start_dt = datetime.fromisoformat(start_ts)
                    server_dt = datetime.fromisoformat(server_time)
                    runtime = str(server_dt - start_dt)
                except Exception as e:
                    runtime = f"Error: {e}"
            else:
                runtime = "N/A"
                
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Sample {i:02d}: State={state} | SessionID={session_id} | Start={start_ts} | Runtime={runtime} | Heartbeat={heartbeat}")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Sample {i:02d} failed: {e}")
        
    if i < 15:
        time.sleep(10)

print("-" * 80)
print(f"End audit time: {datetime.now().isoformat()}")
print("Persistence audit log finished.")
