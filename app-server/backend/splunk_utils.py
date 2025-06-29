from flask import request
import requests
import json
import os

SPLUNK_HEC_TOKEN = os.environ.get('SPLUNK_HEC_TOKEN', '') 
SPLUNK_HEC_URL = os.environ.get('SPLUNK_HEC_URL', '') 

def get_real_ip():
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.remote_addr

from flask import request
import json, requests

def log_to_splunk(event_type, event_data=None, username=None):
    client_ip = get_real_ip() 
    payload = {
        "event": {
            "type": event_type,  # e.g., "login", "create_post", etc.
            "message": event_data or {},
            "path": request.path,
            "method": request.method,
            "ip": client_ip,
            "user_agent": request.headers.get("User-Agent"),
            "username": username
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
            print(f"[{event_type.upper()}] Log sent to Splunk: {event_data}")
    except Exception as e:
        print(f"[{event_type.upper()}] Failed to send log to Splunk: {e}")
