import sys
import time
import requests

FLASK_URL = "http://localhost:8080/"

for attempt in range(10):
    try:
        response = requests.get(FLASK_URL)
        if response.status_code == 200 or response.status_code == 302:
            print("✅ Flask health check passed (200 OK)")
            sys.exit(0)
        else:
            print(f"❌ Health check failed with status: {response.status_code}")
    except Exception as e:
        print(f"⌛ Attempt {attempt + 1}: Could not connect — {e}")

    time.sleep(3)

print("❌ Flask did not become healthy in time.")
sys.exit(1)
