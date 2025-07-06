# import pytest
# from playwright.sync_api import sync_playwright, expect

# @pytest.fixture(scope="session")
# def browser():
#     with sync_playwright() as p:
#         browser = p.chromium.launch(headless=True)
#         yield browser
#         browser.close()

# @pytest.fixture
# def page(browser):
#     context = browser.new_context()
#     page = context.new_page()
#     yield page
#     context.close()


# def test_login_success(page):
#     page.goto("http://localhost:8080/login")
#     page.fill('input[name="email"]', 'playwright@latergram.com')
#     page.fill('input[name="password"]', 'latergram-is-playwright')
#     page.click('button[type=\"submit\"]')
#     page.wait_for_url("**/home")
#     assert "/home" in page.url
#     expect(page.locator("text=Welcome")).to_be_visible()

# def test_login_failure(page):
#     page.goto("http://localhost:8080/login")
#     page.fill('input[name="email"]', 'fakeuser@example.com')
#     page.fill('input[name="password"]', 'wrongpass')
#     page.click('button[type=\"submit\"]')
#     page.wait_for_url("**/login")
#     assert "/login" in page.url
#     expect(page.locator("text=Error logging in. Try again.")).to_be_visible()

# def test_forgot_password(page):
#     page.goto("http://localhost:8080/reset_password_portal")
#     page.fill('input[name="reset-email"]', 'playwright@latergram.com')
#     page.click('button[type="submit"]')
#     page.wait_for_timeout(1000)
#     assert "An OTP has been sent" in page.content()
