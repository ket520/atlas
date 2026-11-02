import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page.goto("https://www.amazon.co.uk/ap/signin?openid.pape.max_auth_age=3600&openid.return_to=https%3A%2F%2Fship.amazon.co.uk%2F&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.assoc_handle=amzn_swa_shipper_desktop_uk&openid.mode=checkid_setup&marketPlaceId=AGJTXQVCWGLM9&language=en_GB&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&pageId=loginCheckout-amzn_swa_shipper_desktop_uk_amazon&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0")
    page.get_by_role("textbox", name="Enter mobile number or email").click()
    page.get_by_role("textbox", name="Enter mobile number or email").fill("cs1.starpark.my@gmail.com")
    page.get_by_role("button", name="Continue").click()
    page.get_by_role("textbox", name="Password").fill("Johor9798")
    page.get_by_role("textbox", name="Password").click()
    page.get_by_role("button", name="Sign in").click()
    page.get_by_role("textbox", name="Search by tracking #, order #").click()
    page.get_by_role("textbox", name="Search by tracking #, order #").fill("UK4946273407")
    page.get_by_text("Ioannis Rizos").click()

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
