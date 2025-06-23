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

# tests/test_basic.py
import unittest
from app import app

class BasicTestCase(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_home_status_code(self):
        response = self.client.get('/home')
        self.assertEqual(response.status_code, 200)

if __name__ == '__main__':
    unittest.main()