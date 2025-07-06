import unittest, io
from app import create_app

class MainRouteTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            'TESTING': True,
        })
        self.client = self.app.test_client()

    def login_as_user(self, user_id):
        with self.client.session_transaction() as session:
            session['user_id'] = user_id

    #########################################################
    ## For rate limit tests - 400 counts towards the limit ##
    #########################################################

    ## Forgot Password rate limit test
    def test_forgot_password_rate_limit(self):
        for _ in range(5):
            response = self.client.post('/forgot-password', json={})
            self.assertEqual(response.status_code, 200)
        response = self.client.post('/forgot-password', json={})
        self.assertEqual(response.status_code, 429)

    ## Login rate limit test
    def test_login_rate_limit(self):
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
    def test_homepage_health(self):
        response = self.client.get('/login')
        self.assertIn(response.status_code, [200, 404])

    ## Force deletion of other posts with logging in
    def test_user_cannot_delete_others_post(self):
        self.login_as_user(user_id=8)
        response = self.client.post('/delete-post/5', json={}) 
        if b'You can only delete your own posts' in response.data:
            self.assertEqual(response.status_code, 403)
        self.assertIn(response.status_code, [403, 404, 500])

    ## Force browsing without logging in
    def test_force_browsing_moderator(self):
        response = self.client.get('/moderation/', follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        location = response.headers.get("Location")
        self.assertIsNotNone(location, "No redirect location found")
        self.assertTrue("/login" in location, f"Expected redirect to /login but got {location}")

    ## Force browsing with logging in as a user
    def test_user_cannot_access_moderation(self):
        self.login_as_user(user_id=99)

        response = self.client.get('/moderation/', follow_redirects=False)
        if response.status_code == 302:
            location = response.headers.get("Location")
            self.assertIsNotNone(location, "No redirect location found")
            self.assertTrue("/login" in location, f"Expected redirect to /login but got {location}")
        else:
            self.assertEqual(response.status_code, 403, "Expected 403 Forbidden for non-moderator access")

    ## Test adding a comment without logging in
    def test_add_comment_requires_login(self):
        response = self.client.post('/comment/1', data={'comment': 'Test comment'})
        self.assertEqual(response.status_code, 401)
        self.assertIn(b'Not logged in', response.data)

    def tearDown(self):
        pass 