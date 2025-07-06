import firebase_admin
from firebase_admin import credentials, storage
import os

def ensure_firebase_initialized():
    global bucket
    if not firebase_admin._apps:
        file_location = os.environ.get('FILE_LOCATION', '')
        bucket_name = os.environ.get('BUCKET', '')
        if file_location and bucket_name:
            cred = credentials.Certificate(file_location)
            firebase_admin.initialize_app(cred, {
                'storageBucket': bucket_name
            })
        else:
            raise RuntimeError('Firebase FILE_LOCATION or BUCKET not set in environment variables')
    bucket = storage.bucket()