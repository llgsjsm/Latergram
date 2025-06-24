import firebase_admin
from firebase_admin import credentials, firestore

# Load service account key
cred = credentials.Certificate("image.json")

# Prevent double initialization (important in some server contexts)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

# Initialize Firestore client
db = firestore.client()