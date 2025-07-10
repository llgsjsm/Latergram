import unittest, io
from urllib import response
from app import create_app
from unittest.mock import patch, MagicMock

class MainRouteTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            'IS_TESTING': True,
        })
        self.client = self.app.test_client()

    def login_as_user(self, user_id):
        with self.client.session_transaction() as session:
            session['user_id'] = user_id

    ## Forgot Password rate limit test
    @patch("backend.routes.main.log_to_splunk")
    def test_forgot_password_rate_limit(self, mock_log_to_splunk):
        for _ in range(5):
            response = self.client.post('/forgot-password', json={})
            self.assertEqual(response.status_code, 200)
        response = self.client.post('/forgot-password', json={})
        self.assertEqual(response.status_code, 429)

    ## Login rate limit test
    @patch("backend.routes.main.log_to_splunk")
    def test_login_rate_limit(self, mock_log_to_splunk):
        for _ in range(7):
            response = self.client.post('/login', json={
                "email": "testuser@email.com",
                "password": "correct-password",
                "action": "login",
                "g-recaptcha-response": "dummy-response"
            })
            self.assertEqual(response.status_code, 400)
        response = self.client.post('/login', json={
            "email": "testuser@email.com",
            "password": "correct-password",
            "action": "login",
            "g-recaptcha-response": "dummy-response"
        })
        self.assertEqual(response.status_code, 429)

    ## Homepage landing health check
    @patch("backend.routes.main.log_to_splunk")
    def test_homepage_health(self, mock_log_to_splunk):
        response = self.client.get('/login')
        self.assertIn(response.status_code, [200, 404])

    ## Force deletion of other posts with authentication
    @patch("backend.routes.main.log_to_splunk")
    def test_user_cannot_delete_others_post(self, mock_log_to_splunk):
        self.login_as_user(user_id=8)
        response = self.client.post('/delete-post/5', json={}) 
        if b'You can only delete your own posts' in response.data:
            self.assertEqual(response.status_code, 403)
        self.assertIn(response.status_code, [403, 404, 500])

    ## Force browsing without authentication
    @patch("backend.routes.main.log_to_splunk")
    def test_force_browsing_moderator(self, mock_log_to_splunk):
        response = self.client.get('/moderation/', follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        location = response.headers.get("Location")
        self.assertIsNotNone(location, "No redirect location found")
        self.assertTrue("/login" in location, f"Expected redirect to /login but got {location}")

    ## Force browsing with logging in as a user
    @patch("backend.routes.main.log_to_splunk")
    def test_user_cannot_access_moderation(self, mock_log_to_splunk):
        self.login_as_user(user_id=99)

        response = self.client.get('/moderation/', follow_redirects=False)
        if response.status_code == 302:
            location = response.headers.get("Location")
            self.assertIsNotNone(location, "No redirect location found")
            self.assertTrue("/login" in location, f"Expected redirect to /login but got {location}")
        else:
            self.assertEqual(response.status_code, 403, "Expected 403 Forbidden for non-moderator access")

    ## Test adding a comment without authentication
    @patch("backend.routes.main.log_to_splunk")
    def test_add_comment_requires_login(self, mock_log_to_splunk):
        response = self.client.post('/comment/1', data={'comment': 'Test comment'})
        self.assertEqual(response.status_code, 401)
        self.assertIn(b'Not logged in', response.data)
        
    ## Test creating a post without authentication
    @patch("backend.routes.main.storage")
    @patch("backend.routes.main.db")
    @patch("backend.routes.main.is_allowed_file_secure", return_value=True)
    @patch("backend.routes.main.log_to_splunk")
    def test_create_post_unauthenticated(self,mock_log_to_splunk,mock_is_allowed_file_secure,mock_db,mock_storage):
        # Set up mocks
        mock_user = MagicMock()
        mock_user.username = "testuser"
        mock_db.session.get.return_value = mock_user
        mock_blob = MagicMock()
        mock_blob.public_url = "https://tstuffvro.com/image.jpg"
        mock_storage.bucket.return_value.blob.return_value = mock_blob
        mock_result = MagicMock()
        mock_result.lastrowid = 123
        mock_db.session.execute.return_value = mock_result

        # FAKE POST upload
        data = {
            "title": "Unit Test Title",
            "content": "This is test content",
            "image": (io.BytesIO(b"fake image data"), "test.png", "image/png")
        }
        response = self.client.post("/create-post", data=data, content_type="multipart/form-data", follow_redirects=False)
        # probably 302 since not logged in
        self.assertIn(response.status_code, [302, 401, 403])
        self.assertIn(b"login", response.data.lower() or b"not logged in")

    ## Test creating a post with authentication
    @patch("backend.routes.main.storage")
    @patch("backend.routes.main.db")
    @patch("backend.routes.main.is_allowed_file_secure", return_value=True)
    @patch("backend.routes.main.log_action")
    @patch("backend.routes.main.log_to_splunk")
    def test_create_post_authenticated(self,mock_log_action,mock_log_to_splunk,mock_is_allowed_file_secure,mock_db,mock_storage):
        self.login_as_user(user_id=99)

        # Set up mocks
        mock_user = MagicMock()
        mock_user.username = "testuser"
        mock_db.session.get.return_value = mock_user
        mock_blob = MagicMock()
        mock_blob.public_url = "https://tstuffvro.com/image.jpg"
        mock_storage.bucket.return_value.blob.return_value = mock_blob
        mock_result = MagicMock()
        mock_result.lastrowid = 123
        mock_db.session.execute.return_value = mock_result

        # FAKE POST upload
        data = {
            "title": "Unit Test Title",
            "content": "This is test content",
            "image": (io.BytesIO(b"fake image data"), "test.png", "image/png")
        }
        response = self.client.post("/create-post", data=data, content_type="multipart/form-data", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/home", response.headers.get("Location", ""))

    ## Test creating a post of invalid type with authentication
    @patch("backend.routes.main.storage")
    @patch("backend.routes.main.db")
    @patch("backend.routes.main.log_to_splunk")
    def test_file_type_authenticated(self,mock_log_to_splunk,mock_db,mock_storage):
        self.login_as_user(user_id=99)

        # Set up mocks
        mock_user = MagicMock()
        mock_user.username = "testuser"
        mock_db.session.get.return_value = mock_user
        mock_blob = MagicMock()
        mock_blob.public_url = "https://tstuffvro.com/image.pdf"
        mock_storage.bucket.return_value.blob.return_value = mock_blob
        mock_result = MagicMock()
        mock_result.lastrowid = 123
        mock_db.session.execute.return_value = mock_result

        # FAKE POST upload
        data = {
            "title": "Unit Test Title",
            "content": "This is test content",
            "image": (io.BytesIO(b"fake image data"), "test.pdf", "application/pdf")
        }
        response = self.client.post("/create-post", data=data, content_type="multipart/form-data", follow_redirects=False)
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Invalid image format", response.data)

    ## Test creating a post with no image
    @patch("backend.routes.main.storage")
    @patch("backend.routes.main.db")
    @patch("backend.routes.main.log_to_splunk")
    def test_create_post_no_image(self, mock_log_to_splunk, mock_db, mock_storage):
        self.login_as_user(user_id=99)

        # Set up mocks
        mock_user = MagicMock()
        mock_user.username = "testuser"
        mock_db.session.get.return_value = mock_user
        mock_result = MagicMock()
        mock_result.lastrowid = 123
        mock_db.session.execute.return_value = mock_result

        # FAKE POST upload without image
        data = {
            "title": "Unit Test Title",
            "content": "This is test content",
            "image": None          
            }
        response = self.client.post("/create-post", data=data, follow_redirects=False)
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"no image provided", response.data)

    @patch("backend.routes.main.is_allowed_file_secure", return_value=True)
    @patch("backend.routes.main.storage")
    @patch("backend.routes.main.db")
    @patch("backend.routes.main.log_to_splunk")
    def test_profanity_in_post_content(self, mock_log_to_splunk, mock_db, mock_storage, mock_is_allowed_file_secure):
        self.login_as_user(user_id=99)
        mock_user = MagicMock()
        mock_user.username = "testuser"
        mock_db.session.get.return_value = mock_user
        mock_result = MagicMock()
        mock_result.lastrowid = 123
        mock_db.session.execute.return_value = mock_result
        data = {
            "title": "Unit Test Title",
            "content": "bitch", 
            "image": (io.BytesIO(b"fake image data"), "test.png", "image/png")
        }
        response = self.client.post("/create-post", data=data, content_type="multipart/form-data", follow_redirects=False)
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Profanity detected", response.data)

    def tearDown(self):
        pass 