from flask import Flask, render_template, request
import requests
import json

app = Flask(__name__)

# SPLUNK HEC Configuration
SPLUNK_HEC_URL = "https://10.20.0.100:8088/services/collector"
SPLUNK_HEC_TOKEN = "e4e0bbe8-2549-4a8e-bafa-28d0eb22244b"

def get_real_ip():
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.remote_addr

def log_to_splunk(event_data):
    client_ip = get_real_ip()
    payload = {
        "event": {
            "message": event_data,
            "path": request.path,
            "method": request.method,
            "ip": client_ip,
            "user_agent": request.headers.get("User-Agent")
        },
        "sourcetype": "flask-web",
        "host": client_ip
    }

    headers = {
        "Authorization": f"Splunk {SPLUNK_HEC_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(SPLUNK_HEC_URL, headers=headers, data=json.dumps(payload), verify=False)
        if response.status_code != 200:
            print(f"Splunk HEC error: {response.status_code} - {response.text}")
        else:
            print(f"Sent log to Splunk: {event_data}")
    except Exception as e:
        print(f"Failed to send log to Splunk: {e}")

@app.route('/home')
def home():
    log_to_splunk("Visited /home")
    return render_template('home.html')

@app.route('/')
def hello_world():
    log_to_splunk("Visited /")
    return 'Hello, World!'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
