import sys
import time
import requests

FLASK_URL = "http://localhost:8080/healthz"  

for i in range(10):
    try:
        res = requests.get(FLASK_URL)
        if res.status_code == 200:
            print("✅ Flask is running and returned 200 OK")
            sys.exit(0)
        else:
            print(f"❌ Received {res.status_code}")
    except Exception as e:
        print(f"⌛ Attempt {i+1}/10: Flask not ready yet... {e}")
    time.sleep(3)

print("❌ Flask did not become ready in time.")
sys.exit(1)