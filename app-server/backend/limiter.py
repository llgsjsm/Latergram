    
from flask_limiter import Limiter
from backend.splunk_utils import get_real_ip

def create_limiter(storage_uri=None):
    return Limiter(
        key_func=get_real_ip,
        default_limits=[],
        storage_uri=storage_uri
    )

limiter = None