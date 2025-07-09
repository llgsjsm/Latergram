from collections import defaultdict
import time
from flask import request, jsonify
from backend.splunk_utils import get_real_ip

request_data = defaultdict(list)

def check_rate_limit(ip, request_data, max_requests=5, time_window=60):
    """Check if the IP has exceeded the rate limit"""
    current_time = time.time()

    # Clean up the timestamps that are outside of the time window
    request_data[ip] = [timestamp for timestamp in request_data[ip] if current_time - timestamp < time_window]

    # Check if the number of requests exceeds the max allowed
    if len(request_data[ip]) >= max_requests:
        return False  # Rate limit exceeded

    return True

def rate_limit_required(func):
    """Custom decorator to apply rate limiting"""
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        ip = get_real_ip()

        # Check if the request is a POST request
        if request.method == "POST":
            if not check_rate_limit(ip, request_data=request_data):
                return jsonify({"error": "Rate limit exceeded"}), 429
        
        # Record the request by adding the current time
        request_data[ip].append(time.time())
        return func(*args, **kwargs)

    return wrapper
