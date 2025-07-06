    
from flask_limiter import Limiter
from backend.splunk_utils import get_real_ip

# Create the Limiter without attaching to the app yet
limiter = Limiter(
    key_func=get_real_ip,
    default_limits=[]
)

def init_limiter(app, storage_uri=None):
    limiter.storage_uri = storage_uri  # Set the storage backend
    limiter.init_app(app)