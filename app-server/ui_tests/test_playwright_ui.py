import pytest
from playwright.sync_api import sync_playwright, expect

## UI Testing with Playwright ##

@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()

@pytest.fixture
def page(browser):
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()

def test_forgot_password(page):
    page.goto("http://localhost:8080/reset_password_portal")
    page.fill('input[name="reset-email"]', 'playwright@latergram.com')
    page.click('button[type="submit"]')
    page.wait_for_timeout(1000)
    assert "An OTP has been sent" in page.content()
