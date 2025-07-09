    
# from flask_limiter import Limiter
# from backend.splunk_utils import get_real_ip

# Create the Limiter without attaching to the app yet
# limiter = Limiter(key_func=get_real_ip, default_limits=[])

# def init_limiter(app, storage_uri=None):
#     limiter.storage_uri = storage_uri
#     limiter.init_app(app)


import time, os
from collections import defaultdict

# arguably bad and unsustanable since it doesn't scale and persist
request_data = defaultdict(list)

rate_limited_paths = [
    "/api/send-email-update-otp",
    "/api/verify-email-update-otp",
    "/api/send-password-change-otp",
    "/forgot-password",
    "/login",
    "/verify-login-otp",
    "/verify-register-otp",
    "/verify-reset-otp",
    "/resend-login-otp"
]

def check_rate_limit(ip, max_requests=15, time_window=20, request_data=None):
    if request_data is None:
        request_data = defaultdict(list) 
    current_time = time.time()
    request_data[ip] = [timestamp for timestamp in request_data[ip] if current_time - timestamp < time_window]
    print(f"Requests for IP {ip}: {len(request_data[ip])} within {time_window} seconds.")
    if len(request_data[ip]) >= max_requests:
        print(f"Rate limit exceeded for IP {ip}.")
        return False
    return True

def record_request(ip, request_data=None):
    if request_data is None:
        request_data = defaultdict(list) 
    request_data[ip].append(time.time())

def get_rate_limited_paths():
    """ Returns the list of paths that are rate-limited """
    return rate_limited_paths