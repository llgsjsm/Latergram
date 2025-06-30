import requests
import os

CAPTCHA_KEY = os.environ.get('CAPTCHA_KEY', '')
IS_TESTING = os.getenv("IS_TESTING", "false").lower() == "true"

def verify_recaptcha(token, remote_ip):
    if IS_TESTING:
        print("Skipping reCAPTCHA verification in test mode")
        return True
    if not token:
        return False
    response = requests.post(
        'https://www.google.com/recaptcha/api/siteverify',
        data={
            'secret': CAPTCHA_KEY,
            'response': token,
            'remoteip': remote_ip
        }
    ).json()
    return response.get('success', False)