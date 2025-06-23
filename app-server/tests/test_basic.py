# import pytest

# from app import app 

# @pytest.fixture
# def client():
#     app.config['TESTING'] = True
#     with app.test_client() as client:
#         yield client

# def test_home_status_code(client):
#     """Check if the home page loads correctly (200 OK)"""
#     response = client.get('/home')
#     assert response.status_code == 200

import sys
from app import app

client = app.test_client()
response = client.get("/")

if response.status_code == 200 or response.status_code == 302:
    print("✅ / is working!")
    sys.exit(0)
else:
    print(f"❌ /home returned {response.status_code}")
    sys.exit(1)